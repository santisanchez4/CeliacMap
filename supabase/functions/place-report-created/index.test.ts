// Unit tests for the pure/testable logic in index.ts (auto-revaluation gating).
// Run with: deno test supabase/functions/place-report-created/
//
// Does NOT exercise Deno.serve, secret verification, or any network call
// (Supabase/GitHub) — those require a real deployed environment and are
// covered by live verification instead, same scope as
// supabase/functions/outreach-reply/index.test.ts.

import { assertEquals } from "jsr:@std/assert@1";
import { isAutoRevaluationCandidate } from "./index.ts";

const PLACE_ID = "7707c9e1-9837-4410-8c45-57f94fec8bb4";

Deno.test("isAutoRevaluationCandidate is true for a negative report with a place_id", () => {
  const result = isAutoRevaluationCandidate({ report_type: "negative", place_id: PLACE_ID });
  assertEquals(result, true);
});

Deno.test("isAutoRevaluationCandidate is false for a positive report", () => {
  const result = isAutoRevaluationCandidate({ report_type: "positive", place_id: PLACE_ID });
  assertEquals(result, false);
});

Deno.test("isAutoRevaluationCandidate is false when place_id is null", () => {
  const result = isAutoRevaluationCandidate({ report_type: "negative", place_id: null });
  assertEquals(result, false);
});

Deno.test("isAutoRevaluationCandidate is false when place_id is undefined", () => {
  const result = isAutoRevaluationCandidate({ report_type: "negative" });
  assertEquals(result, false);
});

Deno.test("isAutoRevaluationCandidate is false for an absent report_type", () => {
  const result = isAutoRevaluationCandidate({ place_id: PLACE_ID });
  assertEquals(result, false);
});

Deno.test("isAutoRevaluationCandidate is false for an unknown report_type", () => {
  const result = isAutoRevaluationCandidate({ report_type: "spam", place_id: PLACE_ID });
  assertEquals(result, false);
});
