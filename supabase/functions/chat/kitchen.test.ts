// Tests for the kitchen declarations in the chatbot (spec 2026-09-24-kitchen-info-design.md, 8).
// Run with: deno test --no-lock -A supabase/functions/chat/
import { assertEquals, assertStringIncludes } from "jsr:@std/assert@1";
import {
  applyKitchenStep,
  hasKitchenFacts,
  kitchenFactsFromRouter,
  mergeKitchenFacts,
  normalizeKitchenFacts,
  validatePendingSubmission,
  type PendingReportSubmission,
  type PendingSuggestionSubmission,
} from "./index.ts";
import { parseRouterOutput } from "./index.ts";
import { buildPlaceReportInsertPayload, buildSuggestionInsertPayload, decideConfirmarSubmission } from "./index.ts";
import {
  decideKitchenAnswer,
  envioBaseForPending,
  kitchenEnvioExtras,
  moduloCuatroEnvioExtras,
  withConfirmFacts,
  type ConfirmTurnResult,
} from "./index.ts";

const NO_FACTS = { kitchen_exclusive: null, celiac_prep: null, owner_celiac: null };
const NO_ROUTER_FACTS = { cocina_exclusiva: null, preparacion_celiaca: null, dueno_celiaco: null } as const;

function suggestion(over: Partial<PendingSuggestionSubmission> = {}): PendingSuggestionSubmission {
  return {
    kind: "suggestion", name: "Pan Justo", city: "Rosario", country: "Argentina",
    address: "Corrientes 100, Rosario", category: null, notes: "Cocinan de todo", ...over,
  };
}
function report(over: Partial<PendingReportSubmission> = {}): PendingReportSubmission {
  return {
    kind: "report", place_id: "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10", place_name_text: null,
    place_name: "Café Sol", report_type: "positive", description: "Muy buena atención", ...over,
  };
}

// ---- normalizeKitchenFacts ---------------------------------------------------

Deno.test("normalizeKitchenFacts - celiac_prep only survives when the kitchen is NOT exclusive", () => {
  assertEquals(normalizeKitchenFacts({ kitchen_exclusive: false, celiac_prep: "separate_kitchen" }).celiac_prep, "separate_kitchen");
  assertEquals(normalizeKitchenFacts({ kitchen_exclusive: true, celiac_prep: "separate_kitchen" }).celiac_prep, null);
  assertEquals(normalizeKitchenFacts({ celiac_prep: "separate_kitchen" }).celiac_prep, null);
  assertEquals(normalizeKitchenFacts({ kitchen_exclusive: false, celiac_prep: "hackeado" }).celiac_prep, null);
});

Deno.test("normalizeKitchenFacts - non-boolean input becomes null, never truthy-coerced", () => {
  assertEquals(normalizeKitchenFacts({ kitchen_exclusive: "true", owner_celiac: 1 }), NO_FACTS);
  assertEquals(hasKitchenFacts(NO_FACTS), false);
  assertEquals(hasKitchenFacts({ ...NO_FACTS, owner_celiac: false }), true);
});

// ---- kitchenFactsFromRouter ----------------------------------------------------

Deno.test("kitchenFactsFromRouter - maps the router words; a preparation method implies 'not exclusive'", () => {
  assertEquals(
    kitchenFactsFromRouter({ cocina_exclusiva: "si", preparacion_celiaca: null, dueno_celiaco: "si" }),
    { kitchen_exclusive: true, celiac_prep: null, owner_celiac: true },
  );
  assertEquals(
    kitchenFactsFromRouter({ cocina_exclusiva: null, preparacion_celiaca: "cocina_separada", dueno_celiaco: null }),
    { kitchen_exclusive: false, celiac_prep: "separate_kitchen", owner_celiac: null },
  );
  assertEquals(
    kitchenFactsFromRouter({ cocina_exclusiva: null, preparacion_celiaca: "preparacion_aparte", dueno_celiaco: "no" }),
    { kitchen_exclusive: false, celiac_prep: "separate_prep", owner_celiac: false },
  );
  // Contradiction from the model: exclusive AND a preparation method -> exclusive wins, the method is dropped.
  assertEquals(
    kitchenFactsFromRouter({ cocina_exclusiva: "si", preparacion_celiaca: "misma_cocina", dueno_celiaco: null }),
    { kitchen_exclusive: true, celiac_prep: null, owner_celiac: null },
  );
  assertEquals(kitchenFactsFromRouter(NO_ROUTER_FACTS), NO_FACTS);
});

// ---- mergeKitchenFacts -------------------------------------------------------

Deno.test("mergeKitchenFacts - no facts keeps the draft's exact shape", () => {
  const p = suggestion();
  assertEquals(mergeKitchenFacts(p, NO_FACTS), p);
});

Deno.test("mergeKitchenFacts - new non-null values win and the merge is coherent", () => {
  const p = suggestion({ kitchen_exclusive: false, celiac_prep: "shared_kitchen", owner_celiac: false });
  const merged = mergeKitchenFacts(p, { kitchen_exclusive: true, celiac_prep: null, owner_celiac: null });
  assertEquals(merged.kitchen_exclusive, true);
  assertEquals("celiac_prep" in merged, false); // exclusive kitchen -> preparation method dropped
  assertEquals(merged.owner_celiac, false); // untouched
});

Deno.test("mergeKitchenFacts - a negative report never carries kitchen facts", () => {
  const merged = mergeKitchenFacts(report({ report_type: "negative" }), { kitchen_exclusive: true, celiac_prep: null, owner_celiac: true });
  assertEquals("kitchen_exclusive" in merged, false);
  assertEquals("owner_celiac" in merged, false);
});

// ---- applyKitchenStep --------------------------------------------------------

Deno.test("applyKitchenStep - asks once, when the draft is complete and nothing was said", () => {
  const first = applyKitchenStep(suggestion(), NO_ROUTER_FACTS, { complete: true });
  assertEquals(first.preguntarCocina, true);
  assertEquals(first.pending.kitchen_asked, true);
  const again = applyKitchenStep(first.pending, NO_ROUTER_FACTS, { complete: true });
  assertEquals(again.preguntarCocina, false); // never twice
});

Deno.test("applyKitchenStep - does not ask while the draft is incomplete", () => {
  const step = applyKitchenStep(suggestion({ address: null }), NO_ROUTER_FACTS, { complete: false });
  assertEquals(step.preguntarCocina, false);
  assertEquals("kitchen_asked" in step.pending, false);
});

Deno.test("applyKitchenStep - does not ask when the person already volunteered facts, and keeps them", () => {
  const step = applyKitchenStep(report(), { cocina_exclusiva: "si", preparacion_celiaca: null, dueno_celiaco: "si" }, { complete: true });
  assertEquals(step.preguntarCocina, false);
  assertEquals(step.pending.kitchen_exclusive, true);
  assertEquals(step.pending.owner_celiac, true);
});

Deno.test("applyKitchenStep - never asks about a negative report", () => {
  const step = applyKitchenStep(report({ report_type: "negative" }), NO_ROUTER_FACTS, { complete: true });
  assertEquals(step.preguntarCocina, false);
  assertEquals("kitchen_asked" in step.pending, false);
});

// ---- validatePendingSubmission: sparse shape, clamp, round-trip -----------------

Deno.test("validatePendingSubmission - a draft without kitchen data keeps its exact pre-existing shape", () => {
  const p = suggestion();
  assertEquals(validatePendingSubmission(p), p);
  const r = report();
  assertEquals(validatePendingSubmission(r), r);
});

Deno.test("validatePendingSubmission - keeps valid kitchen data and the asked marker", () => {
  const p = suggestion({ kitchen_exclusive: false, celiac_prep: "separate_prep", owner_celiac: true, kitchen_asked: true });
  assertEquals(validatePendingSubmission(p), p);
});

Deno.test("validatePendingSubmission - a hand-crafted echo is CLAMPED, never rejected (the draft survives)", () => {
  const dirty = { ...suggestion(), kitchen_exclusive: true, celiac_prep: "separate_kitchen", owner_celiac: "si", kitchen_asked: "yes" };
  const clean = validatePendingSubmission(dirty) as PendingSuggestionSubmission;
  assertEquals(clean.kitchen_exclusive, true);
  assertEquals("celiac_prep" in clean, false);
  assertEquals("owner_celiac" in clean, false);
  assertEquals("kitchen_asked" in clean, false);
  assertEquals(clean.name, "Pan Justo"); // the draft itself is intact
});

Deno.test("validatePendingSubmission - kitchen data on a negative report is dropped, not fatal", () => {
  const dirty = { ...report({ report_type: "negative" }), kitchen_exclusive: true, owner_celiac: true };
  const clean = validatePendingSubmission(dirty) as PendingReportSubmission;
  assertEquals(clean.report_type, "negative");
  assertEquals("kitchen_exclusive" in clean, false);
});

Deno.test("producer -> JSON -> validator round-trips every draft shape unchanged (Fase C lesson)", () => {
  const drafts = [
    applyKitchenStep(suggestion(), NO_ROUTER_FACTS, { complete: true }).pending,
    applyKitchenStep(report(), { cocina_exclusiva: "no", preparacion_celiaca: "cocina_separada", dueno_celiaco: "si" }, { complete: true }).pending,
    applyKitchenStep(suggestion({ address: null }), { cocina_exclusiva: null, preparacion_celiaca: null, dueno_celiaco: "no" }, { complete: false }).pending,
    mergeKitchenFacts(suggestion({ kitchen_asked: true }), { kitchen_exclusive: true, celiac_prep: null, owner_celiac: null }),
  ];
  for (const d of drafts) {
    assertEquals(validatePendingSubmission(JSON.parse(JSON.stringify(d))), d);
  }
  assertStringIncludes(JSON.stringify(drafts[0]), "kitchen_asked");
});

// ---- parseRouterOutput: the router's kitchen fields ---------------------------

Deno.test("parseRouterOutput - kitchen fields default to null / false when absent", () => {
  const out = parseRouterOutput(JSON.stringify({ modulo: "reportar" }));
  assertEquals(out.cocina_exclusiva, null);
  assertEquals(out.preparacion_celiaca, null);
  assertEquals(out.dueno_celiaco, null);
  assertEquals(out.cocina_respuesta, false);
});

Deno.test("parseRouterOutput - accepts the kitchen vocabulary", () => {
  const out = parseRouterOutput(JSON.stringify({
    modulo: "reportar", cocina_exclusiva: "no", preparacion_celiaca: "preparacion_aparte",
    dueno_celiaco: "si", cocina_respuesta: true,
  }));
  assertEquals(out.cocina_exclusiva, "no");
  assertEquals(out.preparacion_celiaca, "preparacion_aparte");
  assertEquals(out.dueno_celiaco, "si");
  assertEquals(out.cocina_respuesta, true);
});

Deno.test("parseRouterOutput - anything outside the vocabulary becomes null; cocina_respuesta needs a real true", () => {
  const out = parseRouterOutput(JSON.stringify({
    modulo: "reportar", cocina_exclusiva: "quizás", preparacion_celiaca: "separate_kitchen",
    dueno_celiaco: true, cocina_respuesta: "true",
  }));
  assertEquals(out.cocina_exclusiva, null);
  assertEquals(out.preparacion_celiaca, null);
  assertEquals(out.dueno_celiaco, null);
  assertEquals(out.cocina_respuesta, false);
});

// ---- write payloads + Módulo 4 -------------------------------------------------

Deno.test("buildSuggestionInsertPayload - no kitchen data => exactly today's row shape", () => {
  assertEquals(
    Object.keys(buildSuggestionInsertPayload(suggestion())).sort(),
    ["address", "category", "city", "country", "evidence_url", "name", "notes", "origin"],
  );
});

Deno.test("buildSuggestionInsertPayload - carries only the answered keys and never kitchen_asked", () => {
  const p = suggestion({ kitchen_exclusive: false, celiac_prep: "separate_prep", owner_celiac: true, kitchen_asked: true });
  const payload = buildSuggestionInsertPayload(p);
  assertEquals(payload.kitchen_exclusive, false);
  assertEquals(payload.celiac_prep, "separate_prep");
  assertEquals(payload.owner_celiac, true);
  assertEquals("kitchen_asked" in payload, false);
});

Deno.test("buildPlaceReportInsertPayload - positive carries the facts; negative never does; asked never leaks", () => {
  const positive = buildPlaceReportInsertPayload(report({ kitchen_exclusive: true, owner_celiac: false, kitchen_asked: true }));
  assertEquals(positive.kitchen_exclusive, true);
  assertEquals(positive.owner_celiac, false);
  assertEquals("kitchen_asked" in positive, false);
  const negative = buildPlaceReportInsertPayload(report({ report_type: "negative", kitchen_exclusive: true }));
  assertEquals("kitchen_exclusive" in negative, false);
  assertEquals(
    Object.keys(buildPlaceReportInsertPayload(report())).sort(),
    ["description", "place_id", "place_name_text", "report_type"],
  );
});

Deno.test("decideConfirmarSubmission (Módulo 4) - facts volunteered in the message are stored; none => today's payload", () => {
  const withFacts = decideConfirmarSubmission({
    match: { id: "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10", name: "Café Sol" } as never,
    lugarNombre: "Café Sol",
    reporteTexto: "todo sin gluten, la dueña es celíaca",
    facts: { kitchen_exclusive: true, celiac_prep: null, owner_celiac: true },
  });
  assertEquals(withFacts.kind, "insert_now");
  if (withFacts.kind === "insert_now") {
    assertEquals(withFacts.payload.kitchen_exclusive, true);
    assertEquals(withFacts.payload.owner_celiac, true);
    assertEquals("celiac_prep" in withFacts.payload, false);
  }
  const plain = decideConfirmarSubmission({ match: null, lugarNombre: "Café Sol", reporteTexto: "lo conozco, es sin tacc" });
  assertEquals(plain.kind, "insert_now");
  if (plain.kind === "insert_now") {
    assertEquals(Object.keys(plain.payload).sort(), ["description", "place_id", "place_name_text", "report_type"]);
  }
});

// ---- turn logic: answer gate, confirm merge, <envio> extras --------------------

const ANSWER = { modulo: "reportar", cocina_respuesta: true, confirma_envio: false } as const;

Deno.test("decideKitchenAnswer - a complete draft already asked owns the turn when the router says it was answered", () => {
  const asked = suggestion({ kitchen_asked: true });
  assertEquals(decideKitchenAnswer(ANSWER, asked), asked);
  const askedReport = report({ kitchen_asked: true });
  assertEquals(decideKitchenAnswer(ANSWER, askedReport), askedReport);
});

Deno.test("decideKitchenAnswer - never when: not asked, not an answer, a confirmation, out of scope, courtesy, incomplete, negative", () => {
  const asked = suggestion({ kitchen_asked: true });
  assertEquals(decideKitchenAnswer(ANSWER, suggestion()), null); // never asked
  assertEquals(decideKitchenAnswer({ ...ANSWER, cocina_respuesta: false }, asked), null);
  assertEquals(decideKitchenAnswer({ ...ANSWER, confirma_envio: true }, asked), null); // the confirm branch merges instead
  assertEquals(decideKitchenAnswer({ ...ANSWER, modulo: "fuera_de_alcance" }, asked), null);
  assertEquals(decideKitchenAnswer({ ...ANSWER, modulo: "cortesia" }, asked), null);
  assertEquals(decideKitchenAnswer(ANSWER, suggestion({ address: null, kitchen_asked: true })), null);
  assertEquals(decideKitchenAnswer(ANSWER, report({ report_type: "negative", kitchen_asked: true })), null);
  assertEquals(decideKitchenAnswer(ANSWER, null), null);
});

Deno.test("withConfirmFacts - facts said in the confirming message are merged before the insert", () => {
  const confirm: ConfirmTurnResult = { kind: "insert_suggestion", payload: suggestion({ kitchen_asked: true }) };
  const merged = withConfirmFacts(confirm, { kitchen_exclusive: false, celiac_prep: "separate_kitchen", owner_celiac: null });
  assertEquals(merged.kind, "insert_suggestion");
  if (merged.kind === "insert_suggestion") {
    assertEquals(merged.payload.kitchen_exclusive, false);
    assertEquals(merged.payload.celiac_prep, "separate_kitchen");
  }
  assertEquals(withConfirmFacts({ kind: "nothing_pending" }, { kitchen_exclusive: true, celiac_prep: null, owner_celiac: null }), { kind: "nothing_pending" });
});

Deno.test("kitchenEnvioExtras - the question flag and the recap use the router's words", () => {
  assertEquals(kitchenEnvioExtras(suggestion(), true), { preguntar_cocina: true });
  assertEquals(kitchenEnvioExtras(suggestion(), false), {});
  assertEquals(
    kitchenEnvioExtras(suggestion({ kitchen_exclusive: false, celiac_prep: "separate_prep", owner_celiac: true }), false),
    { cocina: { exclusiva: "no", preparacion: "preparacion_aparte", dueno_celiaco: "si" } },
  );
});

Deno.test("moduloCuatroEnvioExtras - facts present => recap; none => invite to add them", () => {
  assertEquals(moduloCuatroEnvioExtras({}), { invitar_cocina: true });
  assertEquals(
    moduloCuatroEnvioExtras({ kitchen_exclusive: true }),
    { cocina: { exclusiva: "si", preparacion: null, dueno_celiaco: null } },
  );
});

Deno.test("envioBaseForPending - identifies the draft without router data", () => {
  assertEquals(envioBaseForPending(report()), { lugar_nombre: "Café Sol", report_type: "positive", texto: "Muy buena atención" });
  assertEquals(envioBaseForPending(suggestion()), {
    lugar_nombre: "Pan Justo", ciudad: "Rosario", direccion: "Corrientes 100, Rosario", pais: "Argentina", texto: "Cocinan de todo",
  });
});
