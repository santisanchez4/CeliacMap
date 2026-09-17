// CeliacMap — Chatbot RAG: the core Edge Function (ADR-006 / PLAN-chatbot-rag.md
// Fase B).
//
// Unlike outreach-reply/ and place-report-created/ (webhook mechanics only,
// never call an LLM — the real judgment always happens in Python, reusing
// RUBRIC unmodified), this is the first Edge Function that calls an LLM
// directly and synchronously, returning straight to the browser: a chat
// reply has to come back in seconds, and the async
// webhook -> repository_dispatch -> GitHub Actions pattern has a 30-90s
// cold start that a chat can't tolerate. See CLAUDE.md's "The Chatbot System
// Prompts" section and ADR-006 for the full design and why this doesn't
// duplicate any safety-judgment logic: the chatbot has ZERO authority over
// places.status — it only relates what the Validator already approved and
// routes input into the existing place_reports / suggestions intake tables.
//
// Two Haiku calls per turn (see prompts.ts):
//   1. ROUTER  — classifies into buscar/reportar/celiaquia/confirmar/
//      fuera_de_alcance + extracts structured fields. JSON only, the scope
//      choke point.
//   2. REDACTOR — drafts the reply using ONLY the <datos> / <datos_cercanos>
//      this function passes it for this turn.
// fuera_de_alcance and the reportar/confirmar stub (Módulos 2/4 ship in Fase
// C) skip the redactor entirely and use a canned reply instead — cheaper, and
// it means a hostile fuera_de_alcance message is never even shown to the
// second call.
//
// Fase B scope: Módulo 1 (buscar) and Módulo 3 (celiaquia) are fully wired.
// Módulo 2 (reportar) and Módulo 4 (confirmar) return a fixed "not yet"
// reply — writing to place_reports/suggestions ships in Fase C.
//
// Required secrets (`supabase secrets set`, see README.md): ANTHROPIC_API_KEY,
// CHAT_MODEL, CHAT_MAX_MESSAGES_PER_SESSION, CHAT_MAX_MESSAGES_PER_IP_DAY,
// CHAT_DAILY_CALL_CAP, CHAT_MAX_HISTORY_TURNS. SUPABASE_URL,
// SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY are auto-injected by the
// platform (the anon key is used for Módulo 1's RAG query, precisely so the
// "public read approved places" RLS is the structural backstop — never the
// service_role key, ADR-006 decision 9).

import Anthropic from "npm:@anthropic-ai/sdk@0";
import { createClient } from "npm:@supabase/supabase-js@2";
import { RESPONDER_PROMPT, ROUTER_PROMPT } from "./prompts.ts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequestBody {
  messages: ChatMessage[];
  session_token: string;
  pending_submission: unknown | null; // validated via validatePendingSubmission before use — never trust the shape
}

// ---------------------------------------------------------------------------
// PendingSubmission types — discriminated union, produced by browser forms
// and consumed by Tasks 3-7. The request's pending_submission field is
// client-echoed and untrusted; validatePendingSubmission is the trust
// boundary.
// ---------------------------------------------------------------------------

export type PendingReportSubmission = {
  kind: "report";
  place_id: string | null;
  place_name_text: string | null;
  report_type: "positive" | "negative";
  description: string;
};

export type PendingSuggestionSubmission = {
  kind: "suggestion";
  name: string;
  city: string;
  country: "Uruguay" | "Argentina" | null;
  address: string | null; // null while still being collected (Task 4)
  category: "restaurant" | "cafe" | "shop" | null;
  notes: string | null;
};

export type PendingSubmission = PendingReportSubmission | PendingSuggestionSubmission;

export interface ChatAction {
  type: "report_submitted" | "suggestion_submitted";
}

export interface ChatResponseBody {
  reply: string;
  pending_submission: PendingSubmission | null;
  action: ChatAction | null;
  rate_limited: boolean;
}

// ---------------------------------------------------------------------------
// PendingSubmission validation (trust boundary)
// ---------------------------------------------------------------------------

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isNonEmptyString(x: unknown, maxLen: number): x is string {
  return typeof x === "string" && x.trim().length > 0 && x.length <= maxLen;
}

export function validatePendingSubmission(x: unknown): PendingSubmission | null {
  if (x === null || typeof x !== "object") return null;
  const obj = x as Record<string, unknown>;

  if (obj.kind === "report") {
    const placeId = obj.place_id;
    const placeNameText = obj.place_name_text;
    const placeIdOk = placeId === null || (typeof placeId === "string" && UUID_RE.test(placeId));
    const placeNameOk = placeNameText === null || isNonEmptyString(placeNameText, 120);
    if (!placeIdOk || !placeNameOk) return null;
    if (placeId === null && placeNameText === null) return null; // schema requires one of the two
    if (obj.report_type !== "positive" && obj.report_type !== "negative") return null;
    if (!isNonEmptyString(obj.description, 2000)) return null;
    return {
      kind: "report",
      place_id: placeId as string | null,
      place_name_text: placeNameText as string | null,
      report_type: obj.report_type,
      description: obj.description as string,
    };
  }

  if (obj.kind === "suggestion") {
    if (!isNonEmptyString(obj.name, 120)) return null;
    if (!isNonEmptyString(obj.city, 80)) return null;
    if (obj.country !== null && obj.country !== "Uruguay" && obj.country !== "Argentina") return null;
    const address = obj.address;
    if (address !== null && !isNonEmptyString(address, 200)) return null;
    const category = obj.category;
    if (category !== null && category !== "restaurant" && category !== "cafe" && category !== "shop") return null;
    const notes = obj.notes;
    if (notes !== null && !isNonEmptyString(notes, 1000)) return null;
    return {
      kind: "suggestion",
      name: obj.name as string,
      city: obj.city as string,
      country: (obj.country ?? null) as "Uruguay" | "Argentina" | null,
      address: (address ?? null) as string | null,
      category: (category ?? null) as "restaurant" | "cafe" | "shop" | null,
      notes: (notes ?? null) as string | null,
    };
  }

  return null;
}

const MODULOS = ["buscar", "reportar", "celiaquia", "confirmar", "fuera_de_alcance"] as const;
const CATEGORIES = ["restaurant", "cafe", "shop"] as const;
const PAISES = ["Argentina", "Uruguay"] as const;
const REPORT_TYPES = ["positive", "negative"] as const;
const IDIOMAS = ["es", "en"] as const;

export interface RouterOutput {
  modulo: (typeof MODULOS)[number];
  ciudad: string | null;
  pais: (typeof PAISES)[number] | null;
  zona: string | null;
  category: (typeof CATEGORIES)[number] | null;
  texto_libre: string | null;
  lugar_nombre: string | null;
  reporte_tipo: (typeof REPORT_TYPES)[number] | null;
  reporte_texto: string | null;
  confirma_envio: boolean;
  idioma: (typeof IDIOMAS)[number];
  // Only meaningful when modulo="celiaquia" (per the ROUTER prompt's own
  // instruction): true when the message describes the user's own symptoms,
  // or asks for a diagnosis/dose/treatment/"do I have celiac disease?" — the
  // same medical hard line already enforced by REDACTOR instruction 4. The
  // router flags it so handleRequest can mark the turn for raw-text audit
  // logging (ADR-006 decision 10); it does not change what the redactor is
  // allowed to say, since that boundary is already enforced in the
  // RESPONDER_PROMPT itself regardless of this field.
  limite_medico: boolean;
}

// ---------------------------------------------------------------------------
// CORS (ADR-006 decision 9) — an allowlist, not an auth boundary: the anon
// key embedded in js/config.js is already public, chat_usage is the real
// backstop. This just stops a random page from silently piggy-backing on the
// endpoint from a browser.
// ---------------------------------------------------------------------------

const ALLOWED_ORIGINS = new Set([
  "https://celiacmap.org",
  "https://www.celiacmap.org",
  "https://santisanchez4.github.io",
]);
const LOCALHOST_ORIGIN_RE = /^http:\/\/localhost(:\d+)?$/;

export function isAllowedOrigin(origin: string | null): boolean {
  if (!origin) return false;
  return ALLOWED_ORIGINS.has(origin) || LOCALHOST_ORIGIN_RE.test(origin);
}

export function buildCorsHeaders(origin: string | null): Record<string, string> {
  if (!isAllowedOrigin(origin)) return {};
  return {
    "Access-Control-Allow-Origin": origin as string,
    "Vary": "Origin",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "apikey, authorization, content-type",
  };
}

// ---------------------------------------------------------------------------
// Módulo 1 — RAG query building (ADR-006 decision 3)
// ---------------------------------------------------------------------------

// The allowlist is deliberately narrower than the map's own `select` (no
// social_url — see CLAUDE.md's Módulo 1 design section) and hardcoded here,
// never derived from a wildcard `select=*`, so a schema change elsewhere in
// the project can't silently widen what the chatbot exposes.
export const PLACES_SELECT_FIELDS = [
  "name",
  "address",
  "city",
  "country",
  "category",
  "safety_level",
  "rating",
  "user_ratings_total",
  "opening_hours",
  "website",
  "phone",
  "lat",
  "lng",
  "vote_count",
] as const;

const PLACES_SEARCH_LIMIT = 8;

/** Defense in depth on top of the query's own `select=`: even if a bug ever
 * widens the PostgREST select list, the redactor still never sees a field
 * outside this allowlist. */
export function filterPlaceFields(row: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const field of PLACES_SELECT_FIELDS) {
    if (field in row) out[field] = row[field];
  }
  return out;
}

interface PlacesQueryParams {
  ciudad?: string | null;
  zona?: string | null;
  category?: string | null;
  texto_libre?: string | null;
}

export function buildPlacesSearchUrl(supabaseUrl: string, params: PlacesQueryParams): string {
  const parts = [`select=${PLACES_SELECT_FIELDS.join(",")}`, "status=eq.approved"];
  if (params.ciudad) parts.push(`city=ilike.*${encodeURIComponent(params.ciudad)}*`);
  if (params.zona) parts.push(`address=ilike.*${encodeURIComponent(params.zona)}*`);
  if (params.category) parts.push(`category=eq.${encodeURIComponent(params.category)}`);
  if (params.texto_libre) parts.push(`name=ilike.*${encodeURIComponent(params.texto_libre)}*`);
  parts.push("order=vote_count.desc,rating.desc.nullslast,name.asc");
  parts.push(`limit=${PLACES_SEARCH_LIMIT}`);
  return `${supabaseUrl}/rest/v1/places?${parts.join("&")}`;
}

// <datos_cercanos> — deliberate simplification (TODO in PLAN-chatbot-rag.md
// left this open for Fase B to decide): `places` has no barrio column and no
// curated neighborhood list exists, so "otras zonas" is a single real,
// city-level count via PostgREST `Prefer: count=exact` — never a per-
// neighborhood breakdown grouped client-side from a `limit=50` list (the
// PLAN's own NO NEGOCIABLE rule: never show a fabricated count).
export function buildNearbyCountUrl(supabaseUrl: string, ciudad: string): string {
  return `${supabaseUrl}/rest/v1/places?select=id&status=eq.approved&city=ilike.*${
    encodeURIComponent(ciudad)
  }*&limit=1`;
}

// ---------------------------------------------------------------------------
// Place lookup — shared by Tasks 3 (reportar/recommend) and 5 (confirmar),
// and Task 11's live verification. Matches exactly one place by name+city or
// no match (zero or ambiguous multi-match). No inference: if the row count
// != 1, the user must resolve the ambiguity themselves (Tasks 3/5 have their
// own no-match flows).
// ---------------------------------------------------------------------------

export interface PlaceMatch {
  id: string;
  name: string;
  city: string | null;
}

export function sanitizeIlikeTerm(term: string): string {
  // PostgREST reserves `,` (list separator) and `*` (ilike wildcard marker) in filter values.
  return term.replace(/[,*]/g, "").trim();
}

export function buildPlaceLookupUrl(
  supabaseUrl: string,
  nombre: string,
  ciudad: string | null,
  status: "approved" | "needs_review",
): string {
  const params = new URLSearchParams();
  params.set("select", "id,name,city");
  params.set("name", `ilike.*${sanitizeIlikeTerm(nombre)}*`);
  if (ciudad) params.set("city", `ilike.*${sanitizeIlikeTerm(ciudad)}*`);
  params.set("status", `eq.${status}`);
  params.set("limit", "3");
  return `${supabaseUrl}/rest/v1/places?${params.toString()}`;
}

export function decideMatchFromRows(rows: PlaceMatch[]): PlaceMatch | null {
  return rows.length === 1 ? rows[0] : null;
}

export async function fetchPlaceMatch(
  supabaseUrl: string,
  apiKey: string,
  nombre: string,
  ciudad: string | null,
  status: "approved" | "needs_review",
): Promise<PlaceMatch | null> {
  const url = buildPlaceLookupUrl(supabaseUrl, nombre, ciudad, status);
  const res = await fetch(url, {
    headers: { apikey: apiKey, Authorization: `Bearer ${apiKey}` },
  });
  if (!res.ok) throw new Error(`place lookup failed: ${res.status}`);
  const rows = (await res.json()) as PlaceMatch[];
  return decideMatchFromRows(rows);
}

// ---------------------------------------------------------------------------
// Módulo 2 turn-1 decision (reportar/recommend) — Task 3
// ---------------------------------------------------------------------------

export type ReportarDraftResult =
  | { kind: "ask_more_detail" }
  | { kind: "ask_which_place" }
  | { kind: "draft_ready"; pending: PendingReportSubmission }
  | { kind: "needs_address"; pending: PendingSuggestionSubmission };

export function decideReportarDraft(input: {
  match: PlaceMatch | null;
  reporteTipo: "positive" | "negative" | null;
  lugarNombre: string | null;
  ciudad: string | null;
  reporteTexto: string | null;
}): ReportarDraftResult {
  const texto = input.reporteTexto?.trim() ?? "";
  if (texto.length < 5) return { kind: "ask_more_detail" };
  if (!input.lugarNombre) return { kind: "ask_which_place" };

  const reporteTipo = input.reporteTipo ?? "positive";
  const description = texto.slice(0, 2000);

  if (input.match) {
    return {
      kind: "draft_ready",
      pending: {
        kind: "report",
        place_id: input.match.id,
        place_name_text: null,
        report_type: reporteTipo,
        description,
      },
    };
  }

  if (reporteTipo === "negative") {
    return {
      kind: "draft_ready",
      pending: {
        kind: "report",
        place_id: null,
        place_name_text: input.lugarNombre.slice(0, 120),
        report_type: "negative",
        description,
      },
    };
  }

  // positive + no match -> route into a suggestion draft, address still unknown
  return {
    kind: "needs_address",
    pending: {
      kind: "suggestion",
      name: input.lugarNombre.slice(0, 120),
      city: (input.ciudad ?? "").slice(0, 80),
      country: null,
      address: null,
      category: null,
      notes: description,
    },
  };
}

// ---------------------------------------------------------------------------
// Módulo 2 turn-2+ — suggestion address-collection continuation (Task 4)
//
// Follows a "needs_address" draft from decideReportarDraft (Task 3): the
// pending PendingSuggestionSubmission is missing `address` (and possibly
// `country`), and this collects them from the user's next message(s).
//
// Ruling folded in on top of the base brief: decideReportarDraft sets
// city: (input.ciudad ?? "").slice(0, 80) on the needs_address pending --
// "" when the router never extracted a ciudad. suggestions.city has a DB
// CHECK requiring >= 2 characters, so an empty city would fail the eventual
// insert. Rather than reopening Task 3 or adding a whole new conversational
// "ask for city" round-trip, an invalid city is backfilled deterministically
// from the address text as soon as one is available this turn -- the user is
// never asked for city specifically. City is never part of the
// still_collecting/draft_ready gate below (that stays address+country only);
// it is always auto-resolved once address exists.
// ---------------------------------------------------------------------------

export type SuggestionCollectionResult =
  | { kind: "still_collecting"; pending: PendingSuggestionSubmission; askFor: "address" | "country" | "address_and_country" }
  | { kind: "draft_ready"; pending: PendingSuggestionSubmission };

export function detectCountryMention(text: string): "Uruguay" | "Argentina" | null {
  const lower = text.toLowerCase();
  if (lower.includes("uruguay")) return "Uruguay";
  if (lower.includes("argentina")) return "Argentina";
  return null;
}

function isValidCity(city: string): boolean {
  return city.trim().length >= 2;
}

export function deriveCityFromAddress(address: string): string {
  const parts = address.split(",").map((p) => p.trim()).filter((p) => p.length > 0);
  if (parts.length >= 2) {
    const withoutCountry = parts.filter((p) => detectCountryMention(p) === null);
    const candidates = withoutCountry.length > 0 ? withoutCountry : parts;
    const candidate = candidates[candidates.length - 1];
    if (isValidCity(candidate)) return candidate.slice(0, 80);
  }
  // No usable comma-separated segment — fall back to the raw address text itself,
  // guaranteeing a non-empty city rather than leaving the DB's 2-char floor unmet.
  return address.slice(0, 80);
}

export function continueSuggestionCollection(
  pending: PendingSuggestionSubmission,
  rawReply: string,
): SuggestionCollectionResult {
  const text = rawReply.trim();
  const needsAddress = pending.address === null;
  const mentionedCountry = detectCountryMention(text);

  let address = pending.address;
  let country = pending.country;

  if (needsAddress && text.length >= 5) {
    address = text.slice(0, 200);
    if (!country && mentionedCountry) country = mentionedCountry;
  } else if (!needsAddress && !country) {
    // this turn is answering the country-only question
    if (mentionedCountry) country = mentionedCountry;
  }

  let city = pending.city;
  if (!isValidCity(city) && address) {
    city = deriveCityFromAddress(address);
  }

  const updated: PendingSuggestionSubmission = { ...pending, address, country, city };

  if (updated.address && updated.country) {
    return { kind: "draft_ready", pending: updated };
  }

  const askFor = !updated.address && !updated.country ? "address_and_country" : !updated.address ? "address" : "country";
  return { kind: "still_collecting", pending: updated, askFor };
}

export function parseContentRange(header: string | null): number | null {
  if (!header) return null;
  const match = /\/(\d+|\*)$/.exec(header.trim());
  if (!match) return null;
  if (match[1] === "*") return null;
  const total = Number(match[1]);
  return Number.isFinite(total) ? total : null;
}

// ---------------------------------------------------------------------------
// History trimming (CHAT_MAX_HISTORY_TURNS)
// ---------------------------------------------------------------------------

export function trimHistory(messages: ChatMessage[], maxTurns: number): ChatMessage[] {
  const maxMessages = Math.max(1, maxTurns) * 2;
  return messages.length <= maxMessages ? messages : messages.slice(-maxMessages);
}

// ---------------------------------------------------------------------------
// Router output parsing — tolerant to prose/code fences (mirrors
// agents/clients/llm.py's _parse_json), and the modulo/category/pais enums
// are re-validated in code rather than trusted from the model: any value
// outside the allowed set (or a parse failure) collapses to
// "fuera_de_alcance" / null, the same "ante la duda" bias as the router
// prompt itself, enforced structurally.
// ---------------------------------------------------------------------------

const JSON_BLOCK_RE = /\{[\s\S]*\}/;

function tryParseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    const match = JSON_BLOCK_RE.exec(text);
    if (!match) throw new Error("no JSON object found in router output");
    return JSON.parse(match[0]);
  }
}

function asEnum<T extends string>(value: unknown, allowed: readonly T[]): T | null {
  return typeof value === "string" && (allowed as readonly string[]).includes(value) ? (value as T) : null;
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

export function parseRouterOutput(text: string): RouterOutput {
  let raw: unknown;
  try {
    raw = tryParseJson(text);
  } catch {
    raw = {};
  }
  const obj = typeof raw === "object" && raw !== null ? (raw as Record<string, unknown>) : {};

  return {
    modulo: asEnum(obj.modulo, MODULOS) ?? "fuera_de_alcance",
    ciudad: asNullableString(obj.ciudad),
    pais: asEnum(obj.pais, PAISES),
    zona: asNullableString(obj.zona),
    category: asEnum(obj.category, CATEGORIES),
    texto_libre: asNullableString(obj.texto_libre),
    lugar_nombre: asNullableString(obj.lugar_nombre),
    reporte_tipo: asEnum(obj.reporte_tipo, REPORT_TYPES),
    reporte_texto: asNullableString(obj.reporte_texto),
    confirma_envio: obj.confirma_envio === true,
    idioma: asEnum(obj.idioma, IDIOMAS) ?? "es",
    limite_medico: obj.limite_medico === true,
  };
}

export function buildRouterUserMessage(history: ChatMessage[]): string {
  const last = history[history.length - 1];
  return [
    "Historial reciente (más nuevo al final):",
    JSON.stringify(history),
    "",
    `Último mensaje del usuario: ${JSON.stringify(last?.content ?? "")}`,
  ].join("\n");
}

// ---------------------------------------------------------------------------
// Redactor user message — the ONLY place real place data enters the prompt.
// buscar passes exactly the (already-filtered) query rows as <datos>; every
// other module omits it, so the model structurally cannot "find" a place it
// wasn't given (the Enharinate Mendoza guard from CLAUDE.md's Decisions Log).
// ---------------------------------------------------------------------------

export function buildResponderUserMessage(args: {
  modulo: RouterOutput["modulo"];
  userMessage: string;
  datos?: Record<string, unknown>[];
  datosCercanos?: { city: string; count: number } | null;
}): string {
  const parts = [`modulo: ${args.modulo}`];
  if (args.datos) parts.push(`<datos>${JSON.stringify(args.datos)}</datos>`);
  if (args.datosCercanos) parts.push(`<datos_cercanos>${JSON.stringify(args.datosCercanos)}</datos_cercanos>`);
  parts.push(`Mensaje del usuario: ${args.userMessage}`);
  return parts.join("\n");
}

// ---------------------------------------------------------------------------
// Rate limiting (chat_usage, ADR-006 decision 8)
//
// bump_chat_usage(p_keys, p_day) increments every key it's given by exactly
// +1 per call (see db/schema.sql) — there's no variable-amount parameter. A
// turn calls it once, after passing the check below, so all three buckets
// (session/ip/global) count TURNS, not raw model calls, regardless of
// whether a turn makes 1 or 2 Haiku calls. CHAT_DAILY_CALL_CAP is therefore
// enforced here as a turns/day ceiling, not the calls/day ceiling ADR-006's
// table names it as. Its literal value must change to match: ADR-006 sized
// 1000 as "~500 turns ≈ US$2-3/day" under a calls-based counter: applying
// that same literal 1000 to a TURNS counter would silently double the real
// spend ceiling to ~US$4-6/day, which was never approved. The default below
// is therefore 500 (turns), not 1000 — the number that actually preserves
// the originally-approved ~US$2-3/day ceiling under this counter's real
// behavior. Changing bump_chat_usage's own signature to count calls instead
// is out of scope for this fase; ADR-006 / PLAN-chatbot-rag.md's budget
// table should be corrected to 500 to match (tracked, not yet done).
// ---------------------------------------------------------------------------

export function computeBucketKeys(sessionToken: string, ipHash: string): [string, string, string] {
  return [`session:${sessionToken}`, `ip:${ipHash}`, "global"];
}

export async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function getClientIp(req: Request): string {
  const forwarded = req.headers.get("x-forwarded-for");
  const first = forwarded?.split(",")[0]?.trim();
  return first || "unknown";
}

export interface RateLimitCounts {
  session: number;
  ip: number;
  global: number;
}

export type RateLimitReason = "session" | "ip" | "global" | null;

export function isRateLimited(
  counts: RateLimitCounts,
  caps: RateLimitCounts,
): { limited: boolean; reason: RateLimitReason } {
  if (counts.session >= caps.session) return { limited: true, reason: "session" };
  if (counts.ip >= caps.ip) return { limited: true, reason: "ip" };
  if (counts.global >= caps.global) return { limited: true, reason: "global" };
  return { limited: false, reason: null };
}

// ---------------------------------------------------------------------------
// Canned replies — no model call needed (rate limit, scope decline, and the
// Fase B stub for reportar/confirmar are all deterministic).
// ---------------------------------------------------------------------------

type Idioma = (typeof IDIOMAS)[number];

export const RATE_LIMIT_REPLIES: Record<Idioma, string> = {
  es:
    "Por hoy llegamos al límite de mensajes del asistente. Probá de nuevo más tarde — el mapa y el buscador siguen disponibles mientras tanto.",
  en:
    "We've hit the assistant's message limit for now. Please try again later — the map and search are still available in the meantime.",
};

export const SCOPE_DECLINE_REPLIES: Record<Idioma, string> = {
  es:
    "Solo puedo ayudarte a buscar lugares sin TACC en Argentina y Uruguay, dejar un comentario sobre un lugar, o responder dudas generales sobre la celiaquía.",
  en:
    "I can only help you find gluten-free places in Argentina and Uruguay, leave a comment about a place, or answer general questions about celiac disease.",
};

export const STUB_INTAKE_REPLIES: Record<Idioma, string> = {
  es:
    'Todavía no puedo enviar reportes ni sugerencias por acá, pero ya estamos trabajando en eso. Mientras tanto podés usar el formulario de la sección "Sumá un lugar".',
  en:
    'I can\'t send reports or suggestions through here just yet, but we\'re working on it. In the meantime you can use the form in the "Add a place" section.',
};

export function getReply(dict: Record<Idioma, string>, idioma: Idioma): string {
  return dict[idioma] ?? dict.es;
}

// ---------------------------------------------------------------------------
// Request body validation
// ---------------------------------------------------------------------------

const MAX_MESSAGE_LENGTH = 2000;

export function validateRequestBody(
  json: unknown,
): { ok: true; value: ChatRequestBody } | { ok: false; error: string } {
  if (typeof json !== "object" || json === null) {
    return { ok: false, error: "body must be an object" };
  }
  const body = json as Record<string, unknown>;

  if (!Array.isArray(body.messages) || body.messages.length === 0) {
    return { ok: false, error: "messages must be a non-empty array" };
  }

  const messages: ChatMessage[] = [];
  for (const raw of body.messages) {
    if (typeof raw !== "object" || raw === null) {
      return { ok: false, error: "invalid message in history" };
    }
    const entry = raw as Record<string, unknown>;
    if (
      (entry.role !== "user" && entry.role !== "assistant") ||
      typeof entry.content !== "string" ||
      entry.content.trim().length === 0 ||
      entry.content.length > MAX_MESSAGE_LENGTH
    ) {
      return { ok: false, error: "invalid message in history" };
    }
    messages.push({ role: entry.role, content: entry.content });
  }
  if (messages[messages.length - 1].role !== "user") {
    return { ok: false, error: "the last message must be from the user" };
  }

  if (typeof body.session_token !== "string" || body.session_token.trim().length === 0) {
    return { ok: false, error: "session_token is required" };
  }

  return {
    ok: true,
    value: {
      messages,
      session_token: body.session_token,
      pending_submission: body.pending_submission ?? null,
    },
  };
}

// ---------------------------------------------------------------------------
// handleRequest — orchestration. Not unit tested directly (same scope split
// as outreach-reply/ and place-report-created/): it wires the Anthropic SDK
// and Supabase together, which needs a real deployed environment. Covered by
// the PLAN's Fase B live verification (curl against the deployed endpoint)
// instead.
// ---------------------------------------------------------------------------

function jsonResponse(body: unknown, status: number, extraHeaders: Record<string, string>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });
}

function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

function parsePositiveIntEnv(name: string, fallback: number): number {
  const raw = Deno.env.get(name);
  const parsed = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

async function callModel(
  anthropic: Anthropic,
  model: string,
  system: string,
  userMessage: string,
  maxTokens: number,
): Promise<{ text: string; usage: { in: number; out: number } }> {
  const resp = await anthropic.messages.create({
    model,
    max_tokens: maxTokens,
    system: [{ type: "text", text: system, cache_control: { type: "ephemeral" } }],
    messages: [{ role: "user", content: userMessage }],
  });
  let text = "";
  for (const block of resp.content) {
    if (block.type === "text") text += block.text;
  }
  return { text, usage: { in: resp.usage.input_tokens, out: resp.usage.output_tokens } };
}

// Sanitized 500s: the client only ever sees a fixed, generic body — never a
// Supabase/Anthropic exception message, which can carry connection strings,
// stack frames, or other internal detail. The real error is always logged
// server-side first (console.error, for the Edge Function's own log stream,
// AND agent_log with action='error', for a queryable audit trail alongside
// every other agent's error rows) — logging failure must never mask or
// replace the original error, and must never throw back into the caller.
async function logServerError(
  // deno-lint-ignore no-explicit-any
  supabase: any,
  context: string,
  err: unknown,
  extra?: Record<string, unknown>,
): Promise<void> {
  console.error(`[chat] ${context}:`, err);
  try {
    await supabase.from("agent_log").insert({
      agent: "chatbot",
      action: "error",
      status: "error",
      result: { context, message: err instanceof Error ? err.message : String(err), ...extra },
    });
  } catch (logErr) {
    console.error("[chat] failed to write error to agent_log:", logErr);
  }
}

function internalErrorResponse(cors: Record<string, string>): Response {
  return jsonResponse({ error: "internal_error" }, 500, cors);
}

// deno-lint-ignore no-explicit-any
async function logChatTurn(supabase: any, entry: {
  action: string;
  modulo: string | null;
  marked: boolean;
  markedReason: string | null;
  query?: Record<string, unknown> | null;
  resultCount?: number | null;
  nearbyCount?: number | null;
  routerUsage?: { in: number; out: number } | null;
  redactorUsage?: { in: number; out: number } | null;
  rawUserMessage?: string;
  rawBotReply?: string;
}): Promise<void> {
  const result: Record<string, unknown> = {
    modulo: entry.modulo,
    marked: entry.marked,
    marked_reason: entry.markedReason,
  };
  if (entry.query !== undefined) result.query = entry.query;
  if (entry.resultCount !== undefined) result.result_count = entry.resultCount;
  if (entry.nearbyCount !== undefined) result.nearby_count = entry.nearbyCount;
  if (entry.routerUsage) result.router_tokens = entry.routerUsage;
  if (entry.redactorUsage) result.redactor_tokens = entry.redactorUsage;
  if (entry.marked) {
    result.raw_user_message = entry.rawUserMessage ?? null;
    result.raw_bot_reply = entry.rawBotReply ?? null;
  }
  try {
    await supabase.from("agent_log").insert({ agent: "chatbot", action: entry.action, status: "success", result });
  } catch {
    // Logging must never fail the user-facing turn.
  }
}

export async function handleRequest(req: Request): Promise<Response> {
  const origin = req.headers.get("origin");
  const cors = buildCorsHeaders(origin);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: cors });
  }
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405, headers: cors });
  }

  let parsedBody: unknown;
  try {
    parsedBody = JSON.parse(await req.text());
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400, cors);
  }

  const validated = validateRequestBody(parsedBody);
  if (!validated.ok) {
    return jsonResponse({ error: validated.error }, 400, cors);
  }
  const { messages, session_token: sessionToken } = validated.value;

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
  const anthropicApiKey = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
  const model = Deno.env.get("CHAT_MODEL")?.trim() || "claude-haiku-4-5";
  const maxHistoryTurns = parsePositiveIntEnv("CHAT_MAX_HISTORY_TURNS", 8);
  const caps: RateLimitCounts = {
    session: parsePositiveIntEnv("CHAT_MAX_MESSAGES_PER_SESSION", 15),
    ip: parsePositiveIntEnv("CHAT_MAX_MESSAGES_PER_IP_DAY", 40),
    global: parsePositiveIntEnv("CHAT_DAILY_CALL_CAP", 500),
  };

  const supabase = createClient(supabaseUrl, serviceRoleKey);
  const history = trimHistory(messages, maxHistoryTurns);
  const lastUserMessage = history[history.length - 1].content;

  const ipHash = await sha256Hex(getClientIp(req));
  const [sessionKey, ipKey, globalKey] = computeBucketKeys(sessionToken, ipHash);
  const day = todayUtc();

  const counts: RateLimitCounts = { session: 0, ip: 0, global: 0 };
  try {
    const { data, error } = await supabase
      .from("chat_usage")
      .select("bucket_key, count")
      .in("bucket_key", [sessionKey, ipKey, globalKey])
      .eq("day", day);
    if (error) throw error;
    for (const row of data ?? []) {
      if (row.bucket_key === sessionKey) counts.session = row.count;
      else if (row.bucket_key === ipKey) counts.ip = row.count;
      else if (row.bucket_key === globalKey) counts.global = row.count;
    }
  } catch (err) {
    await logServerError(supabase, "usage_lookup_failed", err);
    return internalErrorResponse(cors);
  }

  const rateCheck = isRateLimited(counts, caps);
  if (rateCheck.limited) {
    // No router call yet -> no detected idioma. Default es (majority of
    // traffic), same conservative default parseRouterOutput itself uses.
    const reply = getReply(RATE_LIMIT_REPLIES, "es");
    await logChatTurn(supabase, {
      action: "rate_limited",
      modulo: null,
      marked: true,
      markedReason: `rate_limited_${rateCheck.reason}`,
      rawUserMessage: lastUserMessage,
      rawBotReply: reply,
    });
    return jsonResponse({ reply, pending_submission: null, action: null, rate_limited: true }, 200, cors);
  }

  if (!anthropicApiKey) {
    // Checked BEFORE the bump below: a misconfigured deployment (missing
    // secret) must not consume the user's rate-limit quota for a turn that
    // was never going to succeed.
    await logServerError(supabase, "missing_anthropic_api_key", new Error("ANTHROPIC_API_KEY is not set"));
    return internalErrorResponse(cors);
  }
  const anthropic = new Anthropic({ apiKey: anthropicApiKey });

  try {
    const { error } = await supabase.rpc("bump_chat_usage", { p_keys: [sessionKey, ipKey, globalKey], p_day: day });
    if (error) throw error;
  } catch (err) {
    await logServerError(supabase, "usage_bump_failed", err);
    return internalErrorResponse(cors);
  }

  let router: RouterOutput;
  let routerUsage: { in: number; out: number };
  try {
    const routerCall = await callModel(anthropic, model, ROUTER_PROMPT, buildRouterUserMessage(history), 400);
    router = parseRouterOutput(routerCall.text);
    routerUsage = routerCall.usage;
  } catch (err) {
    await logServerError(supabase, "router_call_failed", err);
    return internalErrorResponse(cors);
  }

  let reply: string;
  let redactorUsage: { in: number; out: number } | null = null;
  let marked = false;
  let markedReason: string | null = null;
  let queryLog: Record<string, unknown> | null = null;
  let resultCount: number | null = null;
  let nearbyCount: number | null = null;

  try {
    if (router.modulo === "fuera_de_alcance") {
      reply = getReply(SCOPE_DECLINE_REPLIES, router.idioma);
      marked = true;
      markedReason = "fuera_de_alcance";
    } else if (router.modulo === "reportar" || router.modulo === "confirmar") {
      // Módulos 2/4 ship in Fase C (writes to place_reports / suggestions).
      reply = getReply(STUB_INTAKE_REPLIES, router.idioma);
    } else if (router.modulo === "celiaquia") {
      if (router.limite_medico) {
        // Same logging treatment as fuera_de_alcance (ADR-006 decision 10) —
        // the redactor still answers normally (RESPONDER_PROMPT instruction 4
        // already declines diagnosis/dose/treatment and redirects to
        // <fuentes>); this only marks the turn for raw-text audit logging.
        marked = true;
        markedReason = "limite_medico";
      }
      const redactorCall = await callModel(
        anthropic,
        model,
        RESPONDER_PROMPT,
        buildResponderUserMessage({ modulo: router.modulo, userMessage: lastUserMessage }),
        600,
      );
      reply = redactorCall.text;
      redactorUsage = redactorCall.usage;
    } else {
      // buscar
      queryLog = { ciudad: router.ciudad, zona: router.zona, category: router.category, texto_libre: router.texto_libre };
      const searchRes = await fetch(buildPlacesSearchUrl(supabaseUrl, router), {
        headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}` },
      });
      if (!searchRes.ok) throw new Error(`places search failed: ${searchRes.status}`);
      const rows = (await searchRes.json()) as Record<string, unknown>[];
      const datos = rows.map(filterPlaceFields);
      resultCount = datos.length;

      let datosCercanos: { city: string; count: number } | null = null;
      if (datos.length === 0 && router.zona && router.ciudad) {
        try {
          const nearbyRes = await fetch(buildNearbyCountUrl(supabaseUrl, router.ciudad), {
            headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}`, Prefer: "count=exact" },
          });
          const total = parseContentRange(nearbyRes.headers.get("content-range"));
          nearbyCount = total ?? 0;
          if (total !== null && total > 0) datosCercanos = { city: router.ciudad, count: total };
        } catch {
          // Best-effort — a failed nearby lookup must not fail the whole turn.
        }
      }

      const redactorCall = await callModel(
        anthropic,
        model,
        RESPONDER_PROMPT,
        buildResponderUserMessage({ modulo: router.modulo, userMessage: lastUserMessage, datos, datosCercanos }),
        600,
      );
      reply = redactorCall.text;
      redactorUsage = redactorCall.usage;
    }
  } catch (err) {
    await logServerError(supabase, "responder_call_failed", err, { modulo: router.modulo });
    return internalErrorResponse(cors);
  }

  await logChatTurn(supabase, {
    action: "chat_turn",
    modulo: router.modulo,
    marked,
    markedReason,
    query: queryLog,
    resultCount,
    nearbyCount,
    routerUsage,
    redactorUsage,
    rawUserMessage: marked ? lastUserMessage : undefined,
    rawBotReply: marked ? reply : undefined,
  });

  return jsonResponse({ reply, pending_submission: null, action: null, rate_limited: false }, 200, cors);
}

// Only start the HTTP server when this file is run directly (the real Edge
// Function entrypoint) — not when it's imported, e.g. by index.test.ts, which
// would otherwise try to bind a port under the test runner's sandbox.
if (import.meta.main) {
  Deno.serve(handleRequest);
}
