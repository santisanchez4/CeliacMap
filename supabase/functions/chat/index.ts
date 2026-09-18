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
// fuera_de_alcance skips the redactor entirely and uses a canned reply
// instead — cheaper, and it means a hostile message is never even shown to
// the second call.
//
// All four modules are wired (Fase C): Módulo 1 (buscar) and Módulo 3
// (celiaquia) answer from the redactor; Módulo 2 (reportar/recomendar) and
// Módulo 4 (confirmar) additionally write into the SAME public intake tables
// the browser forms use — place_reports and suggestions, through the anon key,
// under the same RLS. The chatbot is a third writer into that existing
// pipeline; it never touches `places`, so a chat message can no more publish a
// place than a form submission can.
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
  // The real place name when matched (place_id set); null for the
  // no-match/free-text case (place_name_text carries the name there
  // instead). Round-tripped across the draft -> confirm turn cycle purely
  // so the confirm turn's redactor ack can name the place even when the
  // person doesn't repeat it in their confirmation message (e.g. "dale,
  // mandalo") — never written to place_reports, there is no such column.
  // See buildPlaceReportInsertPayload, which deliberately excludes it.
  place_name: string | null;
  report_type: "positive" | "negative";
  description: string;
};

export type PendingSuggestionSubmission = {
  kind: "suggestion";
  name: string;
  // null while still unknown — the router has no address field and often
  // extracts no ciudad either, so a draft legitimately starts without one.
  // `null` (never "") is the sentinel, so the producer's own output survives
  // validatePendingSubmission on the next turn's round-trip; the city is
  // backfilled from the collected address (deriveCityFromAddress) before the
  // draft can ever be confirmed, and decideConfirmTurn refuses to send a
  // suggestion whose city is still null (suggestions.city is NOT NULL).
  city: string | null;
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
    const placeName = obj.place_name ?? null;
    const placeIdOk = placeId === null || (typeof placeId === "string" && UUID_RE.test(placeId));
    const placeNameOk = placeNameText === null || isNonEmptyString(placeNameText, 120);
    const placeNameFieldOk = placeName === null || isNonEmptyString(placeName, 120);
    if (!placeIdOk || !placeNameOk || !placeNameFieldOk) return null;
    if (placeId === null && placeNameText === null) return null; // schema requires one of the two
    if (obj.report_type !== "positive" && obj.report_type !== "negative") return null;
    if (!isNonEmptyString(obj.description, 2000)) return null;
    return {
      kind: "report",
      place_id: placeId as string | null,
      place_name_text: placeNameText as string | null,
      place_name: placeName as string | null,
      report_type: obj.report_type,
      description: obj.description as string,
    };
  }

  if (obj.kind === "suggestion") {
    if (!isNonEmptyString(obj.name, 120)) return null;
    // city is null-or-valid, exactly like address/country below: the draft is
    // produced before a city is necessarily known, and rejecting that shape
    // here would silently destroy the whole in-progress draft on the client's
    // next echo (the producer/validator contract must accept what the producer
    // emits — "clamp on the way in, never reject silently").
    const city = obj.city;
    if (city !== null && !isNonEmptyString(city, 80)) return null;
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
      city: (city ?? null) as string | null,
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
        place_name: input.match.name,
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
        place_name: null,
        report_type: "negative",
        description,
      },
    };
  }

  // positive + no match -> route into a suggestion draft, address still unknown.
  // Every field here must satisfy validatePendingSubmission's suggestion rules:
  // the client echoes this exact object back next turn and a rejection there
  // would wipe the whole draft. Hence `null` (not "") for an unknown city, and
  // a 1000-char `notes` — suggestions.notes' DB bound is stricter than the
  // 2000 of place_reports.description that `description` was clamped to.
  return {
    kind: "needs_address",
    pending: {
      kind: "suggestion",
      name: input.lugarNombre.slice(0, 120),
      city: input.ciudad ? input.ciudad.slice(0, 80) : null,
      country: null,
      address: null,
      category: null,
      notes: description.slice(0, 1000),
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
// city: null on the needs_address pending when the router never extracted a
// ciudad. suggestions.city is NOT NULL with a DB CHECK requiring >= 2
// characters, so a null/blank city would fail the eventual insert. Rather
// than reopening Task 3 or adding a whole new conversational "ask for city"
// round-trip, an invalid city is backfilled deterministically from the
// address text as soon as one is available this turn -- the user is never
// asked for city specifically. City is never part of the
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

function isValidCity(city: string | null): boolean {
  return city !== null && city.trim().length >= 2;
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

// ---------------------------------------------------------------------------
// Módulo 4 decision (confirmar) — Task 5, single-turn flow
// Módulo 4 is a person volunteering evidence about a place under review
// (status='needs_review'). Unlike Módulo 2, this is SINGLE-TURN — the
// function immediately decides whether to insert a place_report or ask
// for clarification, never returning a pending submission to echo to the
// client for a later confirm turn (decision 1 in the brief).
// ---------------------------------------------------------------------------

export type ConfirmarResult =
  | { kind: "ask_more_detail" }
  | { kind: "ask_which_place" }
  | { kind: "insert_now"; payload: { place_id: string | null; place_name_text: string | null; report_type: "positive"; description: string } };

export function decideConfirmarSubmission(input: {
  match: PlaceMatch | null;
  lugarNombre: string | null;
  reporteTexto: string | null;
}): ConfirmarResult {
  const texto = input.reporteTexto?.trim() ?? "";
  if (texto.length < 5) return { kind: "ask_more_detail" };
  if (!input.lugarNombre) return { kind: "ask_which_place" };

  const description = texto.slice(0, 2000);
  return {
    kind: "insert_now",
    payload: {
      place_id: input.match?.id ?? null,
      place_name_text: input.match ? null : input.lugarNombre.slice(0, 120),
      report_type: "positive",
      description,
    },
  };
}

// ---------------------------------------------------------------------------
// Módulo 2 confirmation dispatch (Task 6) — decideConfirmTurn
// ---------------------------------------------------------------------------
//
// Consumes: confirma_envio (router output), and a pending_submission that has
// already been validated by validatePendingSubmission (Task 1), so we trust
// its shape.
//
// Produces: ConfirmTurnResult — either insert_report, insert_suggestion, or
// nothing_pending (the fallback if there's no usable pending submission to
// confirm).
//
// Key rule: a suggestion is only confirmable if BOTH address AND country are
// non-null. If either is still missing, return nothing_pending — the upstream
// Task 4 (continueSuggestionCollection) is responsible for collecting those.
//
// `city` is checked too, as defense in depth: suggestions.city is a NOT NULL
// column with a >= 2 char CHECK, and continueSuggestionCollection always
// backfills it from the address before a draft can complete — so a null city
// here means something upstream went wrong, and refusing is far better than
// posting a row the database will reject.

export type ConfirmTurnResult =
  | { kind: "nothing_pending" }
  | { kind: "insert_report"; payload: PendingReportSubmission }
  | { kind: "insert_suggestion"; payload: PendingSuggestionSubmission };

/**
 * Caller must only invoke this when the router's confirma_envio === true.
 * pending must already be the output of validatePendingSubmission (trusted shape).
 */
export function decideConfirmTurn(pending: PendingSubmission | null): ConfirmTurnResult {
  if (!pending) return { kind: "nothing_pending" };
  if (pending.kind === "report") return { kind: "insert_report", payload: pending };
  if (pending.kind === "suggestion") {
    if (!pending.address || !pending.country || !pending.city) return { kind: "nothing_pending" };
    return { kind: "insert_suggestion", payload: pending };
  }
  return { kind: "nothing_pending" };
}

// ---------------------------------------------------------------------------
// Step-3 gate (Task 7) — does an in-progress suggestion own this turn?
// ---------------------------------------------------------------------------
//
// An incomplete suggestion draft owns the turn regardless of the modulo the
// router assigned, because the person is answering the question the bot just
// asked and the router has no address/country field to classify that answer
// with.
//
// "Incomplete" is deliberately the SAME test decideConfirmTurn uses to refuse
// a confirmation (`!address || !country`) and the same one
// continueSuggestionCollection uses to decide whether it is still collecting:
// the set of drafts that cannot yet be sent is exactly the set that must keep
// being collected. Gating on `address === null` alone leaves a hole — once the
// address lands but the country is still missing, the follow-up "Uruguay"
// reply falls through to the confirm/modulo dispatch and the half-collected
// draft is silently dropped.
//
// A COMPLETE draft deliberately does not match: it must fall through so the
// confirm turn can actually send it.
//
// decideConfirmTurn additionally refuses a null `city` (a NOT NULL column) as
// defense in depth; that clause is deliberately NOT mirrored here, because a
// draft with an address always has a city (continueSuggestionCollection
// backfills it), so the only way to reach address+country+null-city is a
// hand-crafted client echo — which must fail closed at the write, not be
// handed back to the collector as if the person still owed us an answer.
export function decideCollectingSuggestion(
  modulo: RouterOutput["modulo"],
  pending: PendingSubmission | null,
): PendingSuggestionSubmission | null {
  if (modulo === "fuera_de_alcance") return null;
  if (pending?.kind !== "suggestion") return null;
  return !pending.address || !pending.country ? pending : null;
}

// ---------------------------------------------------------------------------
// Intake insert payloads (Task 7) — the exact PostgREST row shapes written to
// place_reports / suggestions, mirroring js/report.js and js/suggest.js
// verbatim (same tables, same anon key, same RLS `with check`). The chatbot
// is just a third writer into the SAME intake pipeline the public forms
// already use — it never touches `places`, and has zero authority over
// places.status (ADR-006).
// ---------------------------------------------------------------------------

export function buildPlaceReportInsertPayload(p: PendingReportSubmission) {
  return {
    place_id: p.place_id,
    place_name_text: p.place_name_text,
    report_type: p.report_type,
    description: p.description,
  };
}

export function buildSuggestionInsertPayload(p: PendingSuggestionSubmission) {
  return {
    name: p.name,
    address: p.address,
    city: p.city,
    country: p.country,
    category: p.category,
    evidence_url: null,
    notes: p.notes,
    origin: "community",
  };
}

// A failed intake write must never be reported to the user as a success (the
// person would believe their report was recorded when it wasn't), so this
// returns an outcome instead of throwing: both a transport failure and a
// non-2xx (an RLS `with check` violation or a column CHECK failure both come
// back as 4xx here) become `ok: false`, and the caller responds with the
// redactor's "error_envio" state rather than an ack. Deliberately NOT
// `throw new Error(...)` like the buscar-path fetches: those 500 the turn,
// which for a write would leave the person with no reply at all instead of an
// honest "hubo un problema, ¿lo intento de nuevo?".
export async function insertIntakeRow(
  supabaseUrl: string,
  anonKey: string,
  table: "place_reports" | "suggestions",
  payload: Record<string, unknown>,
): Promise<{ ok: true } | { ok: false; error: Error; extra: Record<string, unknown> }> {
  try {
    const res = await fetch(`${supabaseUrl}/rest/v1/${table}`, {
      method: "POST",
      headers: {
        apikey: anonKey,
        Authorization: `Bearer ${anonKey}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify(payload),
    });
    if (res.ok) return { ok: true };
    let body = "";
    try {
      body = (await res.text()).slice(0, 500);
    } catch {
      // The status code alone is enough to log; a body we can't read is not fatal.
    }
    return {
      ok: false,
      error: new Error(`${table} insert failed: ${res.status}`),
      extra: { table, status: res.status, body },
    };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err : new Error(String(err)),
      extra: { table, status: null },
    };
  }
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
//
// EnvioContext is the reportar/confirmar (Módulo 2/4) analogue of <datos>: it
// carries the in-progress report/suggestion draft's state so the redactor can
// ask for a missing address, show a draft for confirmation, or report a send
// outcome — without ever inventing what was or wasn't actually sent.
// "error_envio" exists so a failed place_reports/suggestions write (network
// error, RLS/CHECK rejection) can be surfaced honestly instead of the model
// claiming "listo, lo envié" when nothing was written.
// ---------------------------------------------------------------------------

export interface EnvioContext {
  estado:
    | "necesita_mas_detalle"
    | "necesita_lugar"
    | "necesita_direccion"
    | "borrador_listo"
    | "enviado"
    | "error_envio";
  lugar_nombre?: string | null;
  ciudad?: string | null;
  // Suggestion-draft state only (the "recommend a new place" path): what has
  // been collected so far, including while still null. Without these the
  // redactor can't tell that an address already exists — so it re-asks for one
  // it was given — and, at the confirmation step, has no grounded way to recite
  // the draft back (history is not passed to the redactor call; <envio> is the
  // only channel), which is exactly where a model would otherwise invent one.
  direccion?: string | null;
  pais?: string | null;
  report_type?: "positive" | "negative" | null;
  texto?: string | null;
}

export function buildResponderUserMessage(args: {
  modulo: RouterOutput["modulo"];
  userMessage: string;
  datos?: Record<string, unknown>[];
  datosCercanos?: { city: string; count: number } | null;
  envio?: EnvioContext;
}): string {
  const parts = [`modulo: ${args.modulo}`];
  if (args.datos) parts.push(`<datos>${JSON.stringify(args.datos)}</datos>`);
  if (args.datosCercanos) parts.push(`<datos_cercanos>${JSON.stringify(args.datosCercanos)}</datos_cercanos>`);
  if (args.envio) parts.push(`<envio>${JSON.stringify(args.envio)}</envio>`);
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
// Canned replies — no model call needed (rate limit and scope decline are both
// deterministic).
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
  // The client echoes back whatever pending_submission the previous turn
  // returned; validatePendingSubmission is the trust boundary (Task 1) — every
  // read below goes through this normalized value, never the raw field.
  const pendingIn = validatePendingSubmission(validated.value.pending_submission);

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
    // The turn did nothing: no lookup, no draft, no write. The in-progress
    // draft is echoed back unchanged so a rate-limited turn doesn't silently
    // destroy a report the person already described (action stays null —
    // nothing was submitted).
    return jsonResponse(
      { reply, pending_submission: pendingIn, action: null, rate_limited: true },
      200,
      cors,
    );
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

  // An in-progress (incomplete) suggestion owns the turn — see
  // decideCollectingSuggestion for the completeness rule. Checked BEFORE
  // confirma_envio on purpose: a mis-fired confirmation there would hit
  // decideConfirmTurn's nothing_pending and fall through to a fresh lookup,
  // silently discarding the name/city/notes already collected.
  const collectingSuggestion = decideCollectingSuggestion(router.modulo, pendingIn);

  // nothing_pending deliberately falls through to the modulo dispatch below
  // (no dead-end reply): a confirmation with nothing to confirm just becomes a
  // normal turn, and if the message names a place it can start a fresh draft.
  const confirmTurn: ConfirmTurnResult = !collectingSuggestion && router.confirma_envio
    ? decideConfirmTurn(pendingIn)
    : { kind: "nothing_pending" };

  // "" is never returned: every branch below either assigns `reply` directly
  // or sets `envio`, and the shared redactor call after the chain assigns
  // `reply` for every envio branch.
  let reply = "";
  let redactorUsage: { in: number; out: number } | null = null;
  let marked = false;
  let markedReason: string | null = null;
  let queryLog: Record<string, unknown> | null = null;
  let resultCount: number | null = null;
  let nearbyCount: number | null = null;
  // Módulo 2/4 state for this turn: what the redactor is told about the draft
  // or the send outcome, and what the client gets back to echo next turn.
  let envio: EnvioContext | null = null;
  let envioModulo: RouterOutput["modulo"] = router.modulo;
  let responsePending: PendingSubmission | null = null;
  let responseAction: ChatAction | null = null;

  try {
    if (router.modulo === "fuera_de_alcance") {
      reply = getReply(SCOPE_DECLINE_REPLIES, router.idioma);
      marked = true;
      markedReason = "fuera_de_alcance";
    } else if (collectingSuggestion) {
      // Address/country collection continuation (Task 4). The raw last user
      // message is the only source for an address — the router never extracts
      // one. Always presented as REPORTAR: this is the tail of a Módulo 2
      // flow, whatever the router called this particular turn.
      envioModulo = "reportar";
      const collected = continueSuggestionCollection(collectingSuggestion, lastUserMessage);
      responsePending = collected.pending;
      envio = {
        estado: collected.kind === "draft_ready" ? "borrador_listo" : "necesita_direccion",
        lugar_nombre: collected.pending.name,
        ciudad: collected.pending.city,
        direccion: collected.pending.address,
        pais: collected.pending.country,
        texto: collected.pending.notes,
      };
    } else if (confirmTurn.kind === "insert_report") {
      envioModulo = "reportar";
      const inserted = await insertIntakeRow(
        supabaseUrl,
        anonKey,
        "place_reports",
        buildPlaceReportInsertPayload(confirmTurn.payload),
      );
      if (inserted.ok) {
        responseAction = { type: "report_submitted" };
        responsePending = null;
        envio = {
          estado: "enviado",
          lugar_nombre: confirmTurn.payload.place_name ?? confirmTurn.payload.place_name_text,
          report_type: confirmTurn.payload.report_type,
          texto: confirmTurn.payload.description,
        };
      } else {
        await logServerError(supabase, "place_report_insert_failed", inserted.error, inserted.extra);
        // Nothing was written: no action, and the same draft is echoed back
        // unchanged so "dale" one more time retries this exact confirm turn.
        responsePending = confirmTurn.payload;
        envio = {
          estado: "error_envio",
          lugar_nombre: confirmTurn.payload.place_name ?? confirmTurn.payload.place_name_text,
          report_type: confirmTurn.payload.report_type,
          texto: confirmTurn.payload.description,
        };
      }
    } else if (confirmTurn.kind === "insert_suggestion") {
      envioModulo = "reportar";
      const inserted = await insertIntakeRow(
        supabaseUrl,
        anonKey,
        "suggestions",
        buildSuggestionInsertPayload(confirmTurn.payload),
      );
      if (inserted.ok) {
        responseAction = { type: "suggestion_submitted" };
        responsePending = null;
        envio = {
          estado: "enviado",
          lugar_nombre: confirmTurn.payload.name,
          ciudad: confirmTurn.payload.city,
          direccion: confirmTurn.payload.address,
          pais: confirmTurn.payload.country,
          texto: confirmTurn.payload.notes,
        };
      } else {
        await logServerError(supabase, "suggestion_insert_failed", inserted.error, inserted.extra);
        responsePending = confirmTurn.payload;
        envio = {
          estado: "error_envio",
          lugar_nombre: confirmTurn.payload.name,
          ciudad: confirmTurn.payload.city,
          direccion: confirmTurn.payload.address,
          pais: confirmTurn.payload.country,
          texto: confirmTurn.payload.notes,
        };
      }
    } else if (router.modulo === "reportar") {
      // Módulo 2 turn 1 — the lookup runs against APPROVED places with the
      // anon key, so the same "public read approved places" RLS that backs
      // Módulo 1 is the structural backstop here too.
      const match = router.lugar_nombre
        ? await fetchPlaceMatch(supabaseUrl, anonKey, router.lugar_nombre, router.ciudad, "approved")
        : null;
      const draft = decideReportarDraft({
        match,
        reporteTipo: router.reporte_tipo,
        lugarNombre: router.lugar_nombre,
        ciudad: router.ciudad,
        reporteTexto: router.reporte_texto,
      });
      if (draft.kind === "ask_more_detail") {
        envio = {
          estado: "necesita_mas_detalle",
          lugar_nombre: router.lugar_nombre,
          ciudad: router.ciudad,
          report_type: router.reporte_tipo,
        };
      } else if (draft.kind === "ask_which_place") {
        envio = {
          estado: "necesita_lugar",
          ciudad: router.ciudad,
          report_type: router.reporte_tipo,
          texto: router.reporte_texto,
        };
      } else if (draft.kind === "draft_ready") {
        responsePending = draft.pending;
        envio = {
          estado: "borrador_listo",
          // Same three-way fallback the confirm turn uses, so a matched place's
          // canonical name is shown consistently on both turns (a matched place
          // is always `approved`, i.e. already public — never a status leak).
          lugar_nombre: draft.pending.place_name ?? draft.pending.place_name_text ?? router.lugar_nombre,
          ciudad: router.ciudad,
          report_type: draft.pending.report_type,
          texto: draft.pending.description,
        };
      } else {
        // needs_address — a recommendation for a place that isn't on the map
        // yet, routed into the suggestions pipeline once the address is known.
        responsePending = draft.pending;
        envio = {
          estado: "necesita_direccion",
          lugar_nombre: draft.pending.name,
          ciudad: draft.pending.city,
          direccion: draft.pending.address,
          pais: draft.pending.country,
          texto: draft.pending.notes,
        };
      }
    } else if (router.modulo === "confirmar") {
      // Módulo 4 — single-turn: evidence about a place still under review.
      // needs_review places are NOT anon-readable (RLS publishes only
      // approved), so this one lookup is the sole service_role use in the
      // whole turn; the insert below still goes through the anon key.
      const match = router.lugar_nombre
        ? await fetchPlaceMatch(supabaseUrl, serviceRoleKey, router.lugar_nombre, router.ciudad, "needs_review")
        : null;
      const decision = decideConfirmarSubmission({
        match,
        lugarNombre: router.lugar_nombre,
        reporteTexto: router.reporte_texto,
      });
      if (decision.kind === "ask_more_detail") {
        envio = { estado: "necesita_mas_detalle", lugar_nombre: router.lugar_nombre, ciudad: router.ciudad };
      } else if (decision.kind === "ask_which_place") {
        envio = { estado: "necesita_lugar", ciudad: router.ciudad, texto: router.reporte_texto };
      } else {
        // insert_now — payload is already exactly the place_reports row shape.
        const inserted = await insertIntakeRow(supabaseUrl, anonKey, "place_reports", decision.payload);
        if (inserted.ok) {
          responseAction = { type: "report_submitted" };
          envio = {
            estado: "enviado",
            lugar_nombre: decision.payload.place_name_text ?? router.lugar_nombre,
            ciudad: router.ciudad,
            report_type: decision.payload.report_type,
            texto: decision.payload.description,
          };
        } else {
          await logServerError(supabase, "place_report_insert_failed", inserted.error, inserted.extra);
          // Módulo 4 is single-turn: there is no pending_submission to echo
          // back, so a retry means the person repeating their message.
          envio = {
            estado: "error_envio",
            lugar_nombre: decision.payload.place_name_text ?? router.lugar_nombre,
            ciudad: router.ciudad,
            report_type: decision.payload.report_type,
            texto: decision.payload.description,
          };
        }
      }
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

    // One shared redactor call for every Módulo 2/4 branch above — same shape
    // as the celiaquia/buscar calls, with <envio> in place of <datos>. The
    // redactor never decides what happened: it only phrases the estado this
    // function already resolved (and on "error_envio" it says so, instead of
    // claiming a send that never landed).
    if (envio) {
      const redactorCall = await callModel(
        anthropic,
        model,
        RESPONDER_PROMPT,
        buildResponderUserMessage({ modulo: envioModulo, userMessage: lastUserMessage, envio }),
        600,
      );
      reply = redactorCall.text;
      redactorUsage = redactorCall.usage;
      queryLog = {
        lugar_nombre: router.lugar_nombre,
        ciudad: router.ciudad,
        confirma_envio: router.confirma_envio,
        envio_estado: envio.estado,
      };
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

  return jsonResponse(
    { reply, pending_submission: responsePending, action: responseAction, rate_limited: false },
    200,
    cors,
  );
}

// Only start the HTTP server when this file is run directly (the real Edge
// Function entrypoint) — not when it's imported, e.g. by index.test.ts, which
// would otherwise try to bind a port under the test runner's sandbox.
if (import.meta.main) {
  Deno.serve(handleRequest);
}
