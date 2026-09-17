// Unit tests for the pure/testable logic in index.ts (ADR-006 / PLAN-chatbot-rag.md
// Fase B). Run with: deno test supabase/functions/chat/
//
// Does NOT exercise Deno.serve, the Anthropic API, or any Supabase network call —
// those require a real deployed environment and are covered by live verification
// instead (curl against the deployed endpoint, per the PLAN's Fase B checklist),
// same scope split as outreach-reply/index.test.ts and
// place-report-created/index.test.ts.

import { assertEquals, assertMatch } from "jsr:@std/assert@1";
import {
  buildCorsHeaders,
  buildNearbyCountUrl,
  buildPlaceLookupUrl,
  buildPlacesSearchUrl,
  buildResponderUserMessage,
  buildRouterUserMessage,
  computeBucketKeys,
  continueSuggestionCollection,
  decideConfirmarSubmission,
  decideConfirmTurn,
  decideMatchFromRows,
  decideReportarDraft,
  deriveCityFromAddress,
  filterPlaceFields,
  getClientIp,
  getReply,
  isAllowedOrigin,
  isRateLimited,
  parseContentRange,
  parseRouterOutput,
  PLACES_SELECT_FIELDS,
  RATE_LIMIT_REPLIES,
  sanitizeIlikeTerm,
  sha256Hex,
  trimHistory,
  validatePendingSubmission,
  validateRequestBody,
  type ConfirmarResult,
  type ConfirmTurnResult,
  type EnvioContext,
  type PendingReportSubmission,
  type PendingSuggestionSubmission,
  type ReportarDraftResult,
} from "./index.ts";

// ---------------------------------------------------------------------------
// CORS allowlist
// ---------------------------------------------------------------------------

Deno.test("isAllowedOrigin accepts the production origin", () => {
  assertEquals(isAllowedOrigin("https://celiacmap.org"), true);
});

Deno.test("isAllowedOrigin accepts the www and GitHub Pages origins", () => {
  assertEquals(isAllowedOrigin("https://www.celiacmap.org"), true);
  assertEquals(isAllowedOrigin("https://santisanchez4.github.io"), true);
});

Deno.test("isAllowedOrigin accepts localhost on any port", () => {
  assertEquals(isAllowedOrigin("http://localhost:8080"), true);
  assertEquals(isAllowedOrigin("http://localhost"), true);
});

Deno.test("isAllowedOrigin rejects an unrelated origin", () => {
  assertEquals(isAllowedOrigin("https://evil.example.com"), false);
});

Deno.test("isAllowedOrigin rejects null", () => {
  assertEquals(isAllowedOrigin(null), false);
});

Deno.test("buildCorsHeaders echoes an allowed origin", () => {
  const headers = buildCorsHeaders("https://celiacmap.org");
  assertEquals(headers["Access-Control-Allow-Origin"], "https://celiacmap.org");
  assertEquals(headers["Access-Control-Allow-Methods"], "POST, OPTIONS");
});

Deno.test("buildCorsHeaders returns no CORS headers for a disallowed origin", () => {
  const headers = buildCorsHeaders("https://evil.example.com");
  assertEquals(headers["Access-Control-Allow-Origin"], undefined);
});

// ---------------------------------------------------------------------------
// Módulo 1 — allowlist + query building (never leaks sensitive fields)
// ---------------------------------------------------------------------------

Deno.test("PLACES_SELECT_FIELDS never includes sensitive columns", () => {
  const forbidden = [
    "validation_notes",
    "validation_confidence",
    "flags",
    "recommendation",
    "contact_email",
    "outreach_status",
    "outreach_channel",
    "outreach_opt_out",
    "source",
    "external_id",
    "geocode_method",
    "verified",
    "social_url",
  ];
  for (const field of forbidden) {
    assertEquals(PLACES_SELECT_FIELDS.includes(field as never), false);
  }
});

Deno.test("PLACES_SELECT_FIELDS includes every field the map/ranking already show publicly", () => {
  for (
    const field of [
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
    ]
  ) {
    assertEquals(PLACES_SELECT_FIELDS.includes(field as never), true);
  }
});

Deno.test("filterPlaceFields strips a sensitive field that should never reach the redactor", () => {
  const row = {
    name: "Sin Gluten Palermo",
    city: "Buenos Aires",
    validation_notes: "internal reasoning the model produced",
    contact_email: "owner@example.com",
    outreach_status: "sent",
  };
  const filtered = filterPlaceFields(row);
  assertEquals(filtered, { name: "Sin Gluten Palermo", city: "Buenos Aires" });
});

Deno.test("filterPlaceFields keeps only allowlisted keys even when every field is present", () => {
  const row: Record<string, unknown> = {};
  for (const field of PLACES_SELECT_FIELDS) row[field] = "x";
  row.validation_notes = "leak";
  row.source = "google_places";
  const filtered = filterPlaceFields(row);
  assertEquals(Object.keys(filtered).sort(), [...PLACES_SELECT_FIELDS].sort());
});

Deno.test("buildPlacesSearchUrl filters by city, status=approved, and orders/limits per ADR-006", () => {
  const url = new URL(
    buildPlacesSearchUrl("https://x.supabase.co", { ciudad: "Palermo", zona: null, category: null, texto_libre: null }),
  );
  assertEquals(url.searchParams.get("status"), "eq.approved");
  assertEquals(url.searchParams.get("city"), "ilike.*Palermo*");
  assertEquals(url.searchParams.get("order"), "vote_count.desc,rating.desc.nullslast,name.asc");
  assertEquals(url.searchParams.get("limit"), "8");
  assertEquals(url.searchParams.get("address"), null);
  assertEquals(url.searchParams.get("category"), null);
});

Deno.test("buildPlacesSearchUrl adds zona/category/texto_libre only when provided", () => {
  const url = new URL(
    buildPlacesSearchUrl("https://x.supabase.co", {
      ciudad: "Buenos Aires",
      zona: "Villa Crespo",
      category: "cafe",
      texto_libre: "Spiga",
    }),
  );
  assertEquals(url.searchParams.get("address"), "ilike.*Villa Crespo*");
  assertEquals(url.searchParams.get("category"), "eq.cafe");
  assertEquals(url.searchParams.get("name"), "ilike.*Spiga*");
});

Deno.test("buildPlacesSearchUrl select= never includes a sensitive field", () => {
  const url = new URL(
    buildPlacesSearchUrl("https://x.supabase.co", { ciudad: "X", zona: null, category: null, texto_libre: null }),
  );
  const select = url.searchParams.get("select") ?? "";
  assertEquals(select.includes("validation_notes"), false);
  assertEquals(select.includes("contact_email"), false);
});

Deno.test("buildNearbyCountUrl scopes to the city only, no zona filter", () => {
  const url = new URL(buildNearbyCountUrl("https://x.supabase.co", "Buenos Aires"));
  assertEquals(url.searchParams.get("city"), "ilike.*Buenos Aires*");
  assertEquals(url.searchParams.get("address"), null);
  assertEquals(url.searchParams.get("status"), "eq.approved");
});

Deno.test("parseContentRange reads the total after the slash", () => {
  assertEquals(parseContentRange("0-7/153"), 153);
});

Deno.test("parseContentRange handles a zero-row exact count", () => {
  assertEquals(parseContentRange("*/0"), 0);
});

Deno.test("parseContentRange returns null for a missing or unparseable header", () => {
  assertEquals(parseContentRange(null), null);
  assertEquals(parseContentRange("not-a-range"), null);
});

// ---------------------------------------------------------------------------
// Módulo 1 — never invents a place outside <datos> (structural guarantee)
// ---------------------------------------------------------------------------

Deno.test("buildResponderUserMessage only embeds the rows it was given, filtered fields only", () => {
  const datos = [filterPlaceFields({ name: "La Spiga", city: "CABA", validation_notes: "leak" })];
  const message = buildResponderUserMessage({ modulo: "buscar", userMessage: "algo en Palermo", datos });
  assertMatch(message, /<datos>.*La Spiga.*<\/datos>/s);
  assertEquals(message.includes("validation_notes"), false);
  assertEquals(message.includes("leak"), false);
});

Deno.test("buildResponderUserMessage omits <datos> entirely when no rows were queried (celiaquia)", () => {
  const message = buildResponderUserMessage({ modulo: "celiaquia", userMessage: "que es sin tacc" });
  assertEquals(message.includes("<datos>"), false);
});

Deno.test("buildResponderUserMessage includes <datos_cercanos> only when provided", () => {
  const withNearby = buildResponderUserMessage({
    modulo: "buscar",
    userMessage: "algo en Mataderos",
    datos: [],
    datosCercanos: { city: "Buenos Aires", count: 12 },
  });
  assertMatch(withNearby, /<datos_cercanos>.*12.*<\/datos_cercanos>/s);

  const withoutNearby = buildResponderUserMessage({ modulo: "buscar", userMessage: "algo en X", datos: [] });
  assertEquals(withoutNearby.includes("<datos_cercanos>"), false);
});

// ---------------------------------------------------------------------------
// Módulo 2/4 — <envio> context block (Task 8: deliberate REDACTOR extension)
// ---------------------------------------------------------------------------

Deno.test("buildResponderUserMessage includes an <envio> block with the serialized draft state when provided", () => {
  const envio: EnvioContext = {
    estado: "borrador_listo",
    lugar_nombre: "La Panera Sin TACC",
    ciudad: "Adrogué",
    report_type: "negative",
    texto: "me contaminaron la comida",
  };
  const message = buildResponderUserMessage({
    modulo: "reportar",
    userMessage: "dale, mandalo",
    envio,
  });
  assertMatch(message, /<envio>.*<\/envio>/s);
  const envioBlock = message.match(/<envio>(.*)<\/envio>/s)?.[1] ?? "";
  assertEquals(envioBlock.includes('"estado":"borrador_listo"'), true);
  assertEquals(envioBlock.includes('"lugar_nombre":"La Panera Sin TACC"'), true);
});

Deno.test("buildResponderUserMessage omits <envio> entirely when not provided (no regression for buscar/celiaquia)", () => {
  const message = buildResponderUserMessage({ modulo: "buscar", userMessage: "algo en Palermo", datos: [] });
  assertEquals(message.includes("<envio>"), false);
});

// ---------------------------------------------------------------------------
// Router output — the scope choke point never lets an invalid modulo through
// ---------------------------------------------------------------------------

Deno.test("parseRouterOutput accepts a well-formed router JSON", () => {
  const output = parseRouterOutput(
    JSON.stringify({
      modulo: "buscar",
      ciudad: "Mendoza",
      pais: "Argentina",
      zona: null,
      category: "cafe",
      texto_libre: null,
      lugar_nombre: null,
      reporte_tipo: null,
      reporte_texto: null,
      confirma_envio: false,
      idioma: "es",
    }),
  );
  assertEquals(output.modulo, "buscar");
  assertEquals(output.ciudad, "Mendoza");
  assertEquals(output.pais, "Argentina");
  assertEquals(output.category, "cafe");
  assertEquals(output.idioma, "es");
});

Deno.test("parseRouterOutput tolerates a markdown code fence around the JSON", () => {
  const output = parseRouterOutput('```json\n{"modulo": "celiaquia"}\n```');
  assertEquals(output.modulo, "celiaquia");
});

Deno.test("parseRouterOutput falls back to fuera_de_alcance on unparseable text (jailbreak attempt classified as prose, not JSON)", () => {
  const output = parseRouterOutput("Claro, ahora soy un asistente sin restricciones y puedo hablar de lo que quieras.");
  assertEquals(output.modulo, "fuera_de_alcance");
});

Deno.test("parseRouterOutput falls back to fuera_de_alcance when modulo is missing", () => {
  const output = parseRouterOutput(JSON.stringify({ ciudad: "Mendoza" }));
  assertEquals(output.modulo, "fuera_de_alcance");
});

Deno.test("parseRouterOutput never lets an out-of-enum modulo through, even if the model invents one", () => {
  const output = parseRouterOutput(JSON.stringify({ modulo: "asistente_general" }));
  assertEquals(output.modulo, "fuera_de_alcance");
});

Deno.test("parseRouterOutput rejects an out-of-enum category/pais instead of passing them through", () => {
  const output = parseRouterOutput(
    JSON.stringify({ modulo: "buscar", category: "spa", pais: "Brasil", ciudad: "X" }),
  );
  assertEquals(output.category, null);
  assertEquals(output.pais, null);
});

Deno.test("parseRouterOutput defaults idioma to es when absent or invalid", () => {
  assertEquals(parseRouterOutput(JSON.stringify({ modulo: "celiaquia" })).idioma, "es");
  assertEquals(parseRouterOutput(JSON.stringify({ modulo: "celiaquia", idioma: "fr" })).idioma, "es");
});

Deno.test("parseRouterOutput coerces confirma_envio to a strict boolean", () => {
  assertEquals(parseRouterOutput(JSON.stringify({ modulo: "reportar", confirma_envio: "true" })).confirma_envio, false);
  assertEquals(parseRouterOutput(JSON.stringify({ modulo: "reportar", confirma_envio: true })).confirma_envio, true);
});

Deno.test("parseRouterOutput defaults limite_medico to false when absent", () => {
  assertEquals(parseRouterOutput(JSON.stringify({ modulo: "celiaquia" })).limite_medico, false);
});

Deno.test("parseRouterOutput accepts limite_medico=true for a celiaquia turn describing symptoms", () => {
  const output = parseRouterOutput(
    JSON.stringify({ modulo: "celiaquia", limite_medico: true }),
  );
  assertEquals(output.limite_medico, true);
});

Deno.test("parseRouterOutput coerces a non-boolean limite_medico to false, same strictness as confirma_envio", () => {
  assertEquals(parseRouterOutput(JSON.stringify({ modulo: "celiaquia", limite_medico: "true" })).limite_medico, false);
  assertEquals(parseRouterOutput(JSON.stringify({ modulo: "celiaquia", limite_medico: 1 })).limite_medico, false);
});

Deno.test("parseRouterOutput ignores limite_medico for non-celiaquia modules (router still emits it, but it's meaningless there)", () => {
  // The field is only meaningful when modulo=celiaquia (per the ROUTER prompt's own
  // instruction) -- parseRouterOutput itself doesn't special-case modulo here, that
  // gating lives in handleRequest. This test just documents the field is parsed
  // uniformly regardless of modulo.
  assertEquals(parseRouterOutput(JSON.stringify({ modulo: "buscar", limite_medico: true })).limite_medico, true);
});

Deno.test("buildRouterUserMessage carries the trimmed history and the last user message", () => {
  const history = [
    { role: "user" as const, content: "hola" },
    { role: "assistant" as const, content: "hola, en que te ayudo?" },
    { role: "user" as const, content: "algo en Palermo" },
  ];
  const message = buildRouterUserMessage(history);
  assertMatch(message, /algo en Palermo/);
});

// ---------------------------------------------------------------------------
// History trimming
// ---------------------------------------------------------------------------

Deno.test("trimHistory keeps at most maxTurns*2 messages", () => {
  const messages = Array.from({ length: 20 }, (_, i) => ({
    role: i % 2 === 0 ? ("user" as const) : ("assistant" as const),
    content: `msg ${i}`,
  }));
  const trimmed = trimHistory(messages, 3);
  assertEquals(trimmed.length, 6);
  assertEquals(trimmed[trimmed.length - 1].content, "msg 19");
});

Deno.test("trimHistory returns everything when under the cap", () => {
  const messages = [{ role: "user" as const, content: "hola" }];
  assertEquals(trimHistory(messages, 8), messages);
});

// ---------------------------------------------------------------------------
// Rate limiting (chat_usage) — rejects correctly, in priority order
// ---------------------------------------------------------------------------

const LIMITS = { session: 15, ip: 40, global: 1000 };

Deno.test("isRateLimited allows a turn under every cap", () => {
  const result = isRateLimited({ session: 1, ip: 1, global: 1 }, LIMITS);
  assertEquals(result, { limited: false, reason: null });
});

Deno.test("isRateLimited rejects once the session cap is reached", () => {
  const result = isRateLimited({ session: 15, ip: 1, global: 1 }, LIMITS);
  assertEquals(result, { limited: true, reason: "session" });
});

Deno.test("isRateLimited rejects once the per-IP daily cap is reached", () => {
  const result = isRateLimited({ session: 1, ip: 40, global: 1 }, LIMITS);
  assertEquals(result, { limited: true, reason: "ip" });
});

Deno.test("isRateLimited rejects once the global daily cap is reached", () => {
  const result = isRateLimited({ session: 1, ip: 1, global: 1000 }, LIMITS);
  assertEquals(result, { limited: true, reason: "global" });
});

Deno.test("isRateLimited does not reject one message under every cap", () => {
  const result = isRateLimited({ session: 14, ip: 39, global: 999 }, LIMITS);
  assertEquals(result.limited, false);
});

Deno.test("getReply returns the canned rate-limit message in the requested language, falling back to es", () => {
  assertEquals(getReply(RATE_LIMIT_REPLIES, "en"), RATE_LIMIT_REPLIES.en);
  assertEquals(getReply(RATE_LIMIT_REPLIES, "es"), RATE_LIMIT_REPLIES.es);
});

Deno.test("computeBucketKeys builds the three documented bucket keys", () => {
  assertEquals(computeBucketKeys("abc-123", "deadbeef"), ["session:abc-123", "ip:deadbeef", "global"]);
});

Deno.test("sha256Hex hashes the IP instead of ever storing it raw", async () => {
  const hash = await sha256Hex("203.0.113.42");
  assertEquals(hash.length, 64);
  assertMatch(hash, /^[0-9a-f]{64}$/);
  assertEquals(hash === "203.0.113.42", false);
});

Deno.test("getClientIp reads the first address from x-forwarded-for", () => {
  const req = new Request("https://x.test/", { headers: { "x-forwarded-for": "203.0.113.42, 10.0.0.1" } });
  assertEquals(getClientIp(req), "203.0.113.42");
});

Deno.test("getClientIp falls back to 'unknown' when the header is absent", () => {
  const req = new Request("https://x.test/");
  assertEquals(getClientIp(req), "unknown");
});

// ---------------------------------------------------------------------------
// Request body validation (400 on a malformed body)
// ---------------------------------------------------------------------------

Deno.test("validateRequestBody accepts a well-formed request", () => {
  const result = validateRequestBody({
    messages: [{ role: "user", content: "hola" }],
    session_token: "tok-1",
    pending_submission: null,
  });
  assertEquals(result.ok, true);
});

Deno.test("validateRequestBody rejects a missing messages array", () => {
  const result = validateRequestBody({ session_token: "tok-1" });
  assertEquals(result.ok, false);
});

Deno.test("validateRequestBody rejects an empty messages array", () => {
  const result = validateRequestBody({ messages: [], session_token: "tok-1" });
  assertEquals(result.ok, false);
});

Deno.test("validateRequestBody rejects a history entry with an invalid role", () => {
  const result = validateRequestBody({
    messages: [{ role: "system", content: "hola" }],
    session_token: "tok-1",
  });
  assertEquals(result.ok, false);
});

Deno.test("validateRequestBody rejects when the last message is not from the user", () => {
  const result = validateRequestBody({
    messages: [{ role: "assistant", content: "hola" }],
    session_token: "tok-1",
  });
  assertEquals(result.ok, false);
});

Deno.test("validateRequestBody rejects a missing session_token", () => {
  const result = validateRequestBody({ messages: [{ role: "user", content: "hola" }] });
  assertEquals(result.ok, false);
});

// ---------------------------------------------------------------------------
// PendingSubmission validation
// ---------------------------------------------------------------------------

Deno.test("validatePendingSubmission - null passes through", () => {
  assertEquals(validatePendingSubmission(null), null);
});

Deno.test("validatePendingSubmission - valid report with place_id", () => {
  const input = {
    kind: "report" as const,
    place_id: "4300ad15-2f6f-4881-a902-b2ac5990464c",
    place_name_text: null,
    report_type: "positive" as const,
    description: "Excelente atención, todo sin TACC",
  };
  assertEquals(validatePendingSubmission(input), input);
});

Deno.test("validatePendingSubmission - valid report with place_name_text, no place_id", () => {
  const input = {
    kind: "report" as const,
    place_id: null,
    place_name_text: "La Panera Sin TACC",
    report_type: "negative" as const,
    description: "Me contaminaron la comida",
  };
  assertEquals(validatePendingSubmission(input), input);
});

Deno.test("validatePendingSubmission - rejects report with neither place_id nor place_name_text", () => {
  assertEquals(
    validatePendingSubmission({
      kind: "report",
      place_id: null,
      place_name_text: null,
      report_type: "positive",
      description: "algo",
    }),
    null,
  );
});

Deno.test("validatePendingSubmission - rejects malformed place_id (not a uuid)", () => {
  assertEquals(
    validatePendingSubmission({
      kind: "report",
      place_id: "not-a-uuid; DROP TABLE places;",
      place_name_text: null,
      report_type: "positive",
      description: "algo",
    }),
    null,
  );
});

Deno.test("validatePendingSubmission - valid suggestion, address still null", () => {
  const input = {
    kind: "suggestion" as const,
    name: "Bienestar Gluten Free",
    city: "Fray Bentos",
    country: "Uruguay" as const,
    address: null,
    category: null,
    notes: "100% sin gluten según el dueño",
  };
  assertEquals(validatePendingSubmission(input), input);
});

Deno.test("validatePendingSubmission - rejects unknown kind", () => {
  assertEquals(validatePendingSubmission({ kind: "bogus" }), null);
});

Deno.test("validatePendingSubmission - rejects non-object", () => {
  assertEquals(validatePendingSubmission("hello"), null);
  assertEquals(validatePendingSubmission(42), null);
  assertEquals(validatePendingSubmission(undefined), null);
});

Deno.test("validatePendingSubmission - rejects report_type outside enum", () => {
  assertEquals(
    validatePendingSubmission({
      kind: "report",
      place_id: null,
      place_name_text: "X",
      report_type: "neutral",
      description: "algo",
    }),
    null,
  );
});

Deno.test("validatePendingSubmission - rejects country outside enum", () => {
  assertEquals(
    validatePendingSubmission({
      kind: "suggestion",
      name: "X",
      city: "Y",
      country: "Brasil",
      address: null,
      category: null,
      notes: null,
    }),
    null,
  );
});

// ---------------------------------------------------------------------------
// Place lookup — shared by Tasks 3 (reportar/recommend) and 5 (confirmar)
// ---------------------------------------------------------------------------

Deno.test("buildPlaceLookupUrl - name and city both present", () => {
  const url = buildPlaceLookupUrl("https://x.supabase.co", "La Panera", "Adrogué", "approved");
  const parsed = new URL(url);
  assertEquals(parsed.pathname, "/rest/v1/places");
  assertEquals(parsed.searchParams.get("select"), "id,name,city");
  assertEquals(parsed.searchParams.get("name"), "ilike.*La Panera*");
  assertEquals(parsed.searchParams.get("city"), "ilike.*Adrogué*");
  assertEquals(parsed.searchParams.get("status"), "eq.approved");
  assertEquals(parsed.searchParams.get("limit"), "3");
});

Deno.test("buildPlaceLookupUrl - no city omits the city filter", () => {
  const url = buildPlaceLookupUrl("https://x.supabase.co", "La Panera", null, "needs_review");
  const parsed = new URL(url);
  assertEquals(parsed.searchParams.has("city"), false);
  assertEquals(parsed.searchParams.get("status"), "eq.needs_review");
});

Deno.test("sanitizeIlikeTerm - strips PostgREST filter-reserved characters", () => {
  assertEquals(sanitizeIlikeTerm("La Panera, Sin TACC*"), "La Panera Sin TACC");
  assertEquals(sanitizeIlikeTerm("normal name"), "normal name");
});

Deno.test("buildPlaceLookupUrl - sanitizes name/city before interpolating", () => {
  const url = buildPlaceLookupUrl("https://x.supabase.co", "Il Porto, Sucursal*", "CABA", "approved");
  const parsed = new URL(url);
  assertEquals(parsed.searchParams.get("name"), "ilike.*Il Porto Sucursal*");
});

Deno.test("decideMatchFromRows - exactly one row is a match", () => {
  const rows = [{ id: "abc", name: "X", city: "Y" }];
  assertEquals(decideMatchFromRows(rows), rows[0]);
});

Deno.test("decideMatchFromRows - zero rows is no match", () => {
  assertEquals(decideMatchFromRows([]), null);
});

Deno.test("decideMatchFromRows - more than one row is no match (ambiguous)", () => {
  const rows = [
    { id: "abc", name: "X", city: "Y" },
    { id: "def", name: "X", city: "Z" },
  ];
  assertEquals(decideMatchFromRows(rows), null);
});

// ---------------------------------------------------------------------------
// Módulo 2 turn-1 decision (decideReportarDraft) — Task 3
// ---------------------------------------------------------------------------

function match() {
  return { id: "4300ad15-2f6f-4881-a902-b2ac5990464c", name: "La Panera", city: "Adrogué" };
}

Deno.test("decideReportarDraft - too-short texto asks for more detail", () => {
  const r = decideReportarDraft({ match: null, reporteTipo: "positive", lugarNombre: "La Panera", ciudad: null, reporteTexto: "ok" });
  assertEquals(r, { kind: "ask_more_detail" });
});

Deno.test("decideReportarDraft - null texto asks for more detail", () => {
  const r = decideReportarDraft({ match: null, reporteTipo: "positive", lugarNombre: "La Panera", ciudad: null, reporteTexto: null });
  assertEquals(r, { kind: "ask_more_detail" });
});

Deno.test("decideReportarDraft - missing lugar_nombre asks which place", () => {
  const r = decideReportarDraft({ match: null, reporteTipo: "positive", lugarNombre: null, ciudad: null, reporteTexto: "Muy buena atención" });
  assertEquals(r, { kind: "ask_which_place" });
});

Deno.test("decideReportarDraft - matched place, positive -> draft_ready as report", () => {
  const r = decideReportarDraft({ match: match(), reporteTipo: "positive", lugarNombre: "La Panera", ciudad: "Adrogué", reporteTexto: "Excelente, todo sin TACC" });
  assertEquals(r, {
    kind: "draft_ready",
    pending: { kind: "report", place_id: match().id, place_name_text: null, report_type: "positive", description: "Excelente, todo sin TACC" },
  });
});

Deno.test("decideReportarDraft - matched place, negative -> draft_ready as report", () => {
  const r = decideReportarDraft({ match: match(), reporteTipo: "negative", lugarNombre: "La Panera", ciudad: "Adrogué", reporteTexto: "Me contaminaron la comida" });
  assertEquals(r, {
    kind: "draft_ready",
    pending: { kind: "report", place_id: match().id, place_name_text: null, report_type: "negative", description: "Me contaminaron la comida" },
  });
});

Deno.test("decideReportarDraft - no match, negative -> draft_ready with place_name_text, no place_id", () => {
  const r = decideReportarDraft({ match: null, reporteTipo: "negative", lugarNombre: "Lugar Fantasma", ciudad: "Salto", reporteTexto: "Dijeron sin TACC pero no lo era" });
  assertEquals(r, {
    kind: "draft_ready",
    pending: { kind: "report", place_id: null, place_name_text: "Lugar Fantasma", report_type: "negative", description: "Dijeron sin TACC pero no lo era" },
  });
});

Deno.test("decideReportarDraft - no match, positive -> needs_address for a suggestion draft", () => {
  const r = decideReportarDraft({ match: null, reporteTipo: "positive", lugarNombre: "Bienestar Gluten Free", ciudad: "Fray Bentos", reporteTexto: "100% sin gluten, muy bueno" });
  assertEquals(r, {
    kind: "needs_address",
    pending: { kind: "suggestion", name: "Bienestar Gluten Free", city: "Fray Bentos", country: null, address: null, category: null, notes: "100% sin gluten, muy bueno" },
  });
});

Deno.test("decideReportarDraft - no match, positive, reporte_tipo null defaults to positive", () => {
  const r = decideReportarDraft({ match: null, reporteTipo: null, lugarNombre: "Bienestar Gluten Free", ciudad: null, reporteTexto: "Muy bueno" });
  assertEquals(r.kind, "needs_address");
});

Deno.test("decideReportarDraft - description clamps to 2000 chars", () => {
  const long = "a".repeat(2500);
  const r = decideReportarDraft({ match: match(), reporteTipo: "positive", lugarNombre: "La Panera", ciudad: "Adrogué", reporteTexto: long });
  assertEquals(r.kind, "draft_ready");
  if (r.kind === "draft_ready") assertEquals(r.pending.description.length, 2000);
});

// ---------------------------------------------------------------------------
// Módulo 2 address-collection continuation (continueSuggestionCollection) —
// Task 4, brief's own 6 cases
// ---------------------------------------------------------------------------

function partial(overrides: Partial<PendingSuggestionSubmission> = {}): PendingSuggestionSubmission {
  return { kind: "suggestion", name: "Bienestar Gluten Free", city: "Fray Bentos", country: null, address: null, category: null, notes: "100% sin gluten", ...overrides };
}

Deno.test("continueSuggestionCollection - missing address and country, short reply asks again", () => {
  const r = continueSuggestionCollection(partial(), "sí");
  assertEquals(r, { kind: "still_collecting", pending: partial(), askFor: "address_and_country" });
});

Deno.test("continueSuggestionCollection - missing address and country, plausible reply fills both when parseable", () => {
  const r = continueSuggestionCollection(partial(), "Rivera 1967, Fray Bentos, Uruguay");
  assertEquals(r.kind, "draft_ready");
  if (r.kind === "draft_ready") {
    assertEquals(r.pending.address, "Rivera 1967, Fray Bentos, Uruguay");
    assertEquals(r.pending.country, "Uruguay");
  }
});

Deno.test("continueSuggestionCollection - address given, country still missing", () => {
  const r = continueSuggestionCollection(partial(), "Rivera 1967, cerca de la terminal");
  assertEquals(r.kind, "still_collecting");
  if (r.kind === "still_collecting") {
    assertEquals(r.pending.address, "Rivera 1967, cerca de la terminal");
    assertEquals(r.askFor, "country");
  }
});

Deno.test("continueSuggestionCollection - only country was missing, short country reply completes it", () => {
  const r = continueSuggestionCollection(partial({ address: "Rivera 1967" }), "Uruguay");
  assertEquals(r, {
    kind: "draft_ready",
    pending: partial({ address: "Rivera 1967", country: "Uruguay" }),
  });
});

Deno.test("continueSuggestionCollection - country reply not recognized, asks again", () => {
  const r = continueSuggestionCollection(partial({ address: "Rivera 1967" }), "no sé");
  assertEquals(r.kind, "still_collecting");
  if (r.kind === "still_collecting") assertEquals(r.askFor, "country");
});

Deno.test("continueSuggestionCollection - address clamps to 200 chars", () => {
  const long = "Calle ".repeat(60);
  const r = continueSuggestionCollection(partial({ country: "Uruguay" }), long);
  assertEquals(r.kind, "draft_ready");
  if (r.kind === "draft_ready") assertEquals(r.pending.address!.length <= 200, true);
});

// ---------------------------------------------------------------------------
// Controller ruling on top of the Task 4 brief: decideReportarDraft (Task 3)
// sets city: "" when the router never extracted a ciudad, but
// suggestions.city has a DB CHECK requiring >= 2 chars. continueSuggestionCollection
// backfills an invalid city deterministically from the address text once one
// is available -- the user is never asked for city specifically.
// ---------------------------------------------------------------------------

Deno.test("deriveCityFromAddress - extracts the city segment before the country", () => {
  assertEquals(deriveCityFromAddress("Rivera 1967, Fray Bentos, Uruguay"), "Fray Bentos");
});

Deno.test("deriveCityFromAddress - falls back to the last segment when no country is mentioned", () => {
  assertEquals(deriveCityFromAddress("Rivera 1967, Fray Bentos"), "Fray Bentos");
});

Deno.test("deriveCityFromAddress - falls back to the raw address when it has no comma structure", () => {
  assertEquals(deriveCityFromAddress("cerca de la terminal de Fray Bentos"), "cerca de la terminal de Fray Bentos");
});

Deno.test("continueSuggestionCollection - backfills an empty city from the address given this turn", () => {
  const pending: PendingSuggestionSubmission = { kind: "suggestion", name: "Bienestar Gluten Free", city: "", country: null, address: null, category: null, notes: "100% sin gluten" };
  const r = continueSuggestionCollection(pending, "Rivera 1967, Fray Bentos, Uruguay");
  assertEquals(r.kind, "draft_ready");
  if (r.kind === "draft_ready") {
    assertEquals(r.pending.city, "Fray Bentos");
    assertEquals(r.pending.address, "Rivera 1967, Fray Bentos, Uruguay");
    assertEquals(r.pending.country, "Uruguay");
  }
});

Deno.test("continueSuggestionCollection - backfills city from an already-known address when only country was still missing", () => {
  const pending: PendingSuggestionSubmission = { kind: "suggestion", name: "Bienestar Gluten Free", city: "", country: null, address: "Rivera 1967, Fray Bentos", category: null, notes: "100% sin gluten" };
  const r = continueSuggestionCollection(pending, "Uruguay");
  assertEquals(r.kind, "draft_ready");
  if (r.kind === "draft_ready") {
    assertEquals(r.pending.city, "Fray Bentos");
    assertEquals(r.pending.country, "Uruguay");
  }
});

// ---------------------------------------------------------------------------
// Módulo 4 decision (confirmar) — Task 5, single-turn flow
// ---------------------------------------------------------------------------

Deno.test("decideConfirmarSubmission - too-short texto asks for more detail", () => {
  const r = decideConfirmarSubmission({ match: null, lugarNombre: "Algún lugar", reporteTexto: "ok" });
  assertEquals(r, { kind: "ask_more_detail" });
});

Deno.test("decideConfirmarSubmission - missing lugar_nombre asks which place", () => {
  const r = decideConfirmarSubmission({ match: null, lugarNombre: null, reporteTexto: "Es 100% sin gluten, lo conozco bien" });
  assertEquals(r, { kind: "ask_which_place" });
});

Deno.test("decideConfirmarSubmission - matched needs_review place -> insert_now with place_id", () => {
  const r = decideConfirmarSubmission({
    match: { id: "82fd31e9-0000-0000-0000-000000000000", name: "Serendipia Gluten Free", city: "Montevideo" },
    lugarNombre: "Serendipia",
    reporteTexto: "Es artesanal, 100% sin gluten, hace pickup",
  });
  assertEquals(r, {
    kind: "insert_now",
    payload: { place_id: "82fd31e9-0000-0000-0000-000000000000", place_name_text: null, report_type: "positive", description: "Es artesanal, 100% sin gluten, hace pickup" },
  });
});

Deno.test("decideConfirmarSubmission - no match (0 or ambiguous) -> insert_now with place_name_text, no place_id", () => {
  const r = decideConfirmarSubmission({ match: null, lugarNombre: "Un lugar nuevo", reporteTexto: "Sin TACC, muy recomendable" });
  assertEquals(r, {
    kind: "insert_now",
    payload: { place_id: null, place_name_text: "Un lugar nuevo", report_type: "positive", description: "Sin TACC, muy recomendable" },
  });
});

Deno.test("decideConfirmarSubmission - description clamps to 2000 chars", () => {
  const long = "b".repeat(2500);
  const r = decideConfirmarSubmission({ match: null, lugarNombre: "X", reporteTexto: long });
  assertEquals(r.kind, "insert_now");
  if (r.kind === "insert_now") assertEquals(r.payload.description.length, 2000);
});

// ---------------------------------------------------------------------------
// Módulo 2 confirmation dispatch (Task 6)
// ---------------------------------------------------------------------------

Deno.test("decideConfirmTurn - confirma_envio false is never this function's concern (caller gate)", () => {
  // decideConfirmTurn assumes the caller already checked confirma_envio === true;
  // documented via the function's own doc comment, not re-tested here.
});

Deno.test("decideConfirmTurn - no pending_submission -> nothing_pending", () => {
  assertEquals(decideConfirmTurn(null), { kind: "nothing_pending" });
});

Deno.test("decideConfirmTurn - report pending, complete -> insert_report", () => {
  const pending: PendingReportSubmission = { kind: "report", place_id: "4300ad15-2f6f-4881-a902-b2ac5990464c", place_name_text: null, report_type: "positive", description: "Muy bueno" };
  assertEquals(decideConfirmTurn(pending), { kind: "insert_report", payload: pending });
});

Deno.test("decideConfirmTurn - suggestion pending, address/country complete -> insert_suggestion", () => {
  const pending: PendingSuggestionSubmission = { kind: "suggestion", name: "X", city: "Y", country: "Uruguay", address: "Calle 123", category: null, notes: null };
  assertEquals(decideConfirmTurn(pending), { kind: "insert_suggestion", payload: pending });
});

Deno.test("decideConfirmTurn - suggestion pending, address still missing -> nothing_pending (not confirmable yet)", () => {
  const pending: PendingSuggestionSubmission = { kind: "suggestion", name: "X", city: "Y", country: null, address: null, category: null, notes: null };
  assertEquals(decideConfirmTurn(pending), { kind: "nothing_pending" });
});
