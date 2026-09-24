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
