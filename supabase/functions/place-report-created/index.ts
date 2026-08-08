// CeliacMap — Community reports: place_reports webhook receiver.
//
// Receives a Supabase Database Webhook fired on INSERT into public.place_reports
// (see docs/architecture/ADR-004-community-reports-evidence-not-direct-action.md
// and docs/plans/PLAN-community-reviews.md §3). This function does webhook
// mechanics ONLY — secret verification, deciding whether the report is
// auto-actionable, checking the place is still 'approved', and firing
// repository_dispatch — and never calls an LLM itself. The actual re-evaluation
// against the Validator rubric happens in Python (agents/review_handler.py),
// reusing RUBRIC and ValidatorAgent._normalize unmodified, exactly like Outreach
// Etapa 2 (supabase/functions/outreach-reply/).
//
// Unlike outreach-reply (which verifies a Resend webhook signed with Svix HMAC),
// Supabase Database Webhooks do not sign their payload at all — this function
// verifies a simple shared secret instead, checked as either a custom header
// (`x-webhook-secret`) or a `?secret=` query-string fallback, since the
// Dashboard's custom-header support for Database Webhooks wasn't confirmed ahead
// of time (see PLAN-community-reviews.md Fase 0(c)). timingSafeEqual is
// duplicated from outreach-reply/index.ts rather than shared — each Edge
// Function is its own isolated deploy, and there is no shared module in this
// repo today.
//
// Response codes:
//   401 - secret verification failed. No writes, no dispatch.
//   200 - verified but not actionable (positive/unmatched report, unknown place,
//         or place not 'approved'). Not a retry signal — Database Webhooks don't
//         redeliver on non-2xx anyway (confirmed, no built-in retry), which is
//         exactly why ReviewHandler.sweep() exists as the monthly safety net.
//   500 - verified and actionable but a step failed. Logged for visibility only,
//         NOT a real retry signal here (unlike outreach-reply's use of 500 for
//         Resend's automatic redelivery).
//
// Required secrets (`supabase secrets set`, separate from .env / GitHub Actions
// secrets): PLACE_REPORTS_WEBHOOK_SECRET, GITHUB_DISPATCH_TOKEN (the same
// fine-grained PAT already used by outreach-reply/). SUPABASE_URL and
// SUPABASE_SERVICE_ROLE_KEY are auto-injected by the platform.

import { createClient } from "npm:@supabase/supabase-js@2";

const GITHUB_REPO = "santisanchez4/CeliacMap";

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** ADR-004 points 2-4: only a negative report against a matched place can
 * automatically trigger a re-evaluation. Positive reports and unmatched
 * reports (place_name_text only, no place_id) are left for manual review. */
export function isAutoRevaluationCandidate(
  record: { report_type?: string; place_id?: string | null },
): boolean {
  return record.report_type === "negative" && !!record.place_id;
}

async function triggerReviewHandler(
  placeId: string,
  reportId: string,
  token: string,
): Promise<void> {
  const res = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      event_type: "place_report_received",
      client_payload: { place_id: placeId, report_id: reportId },
    }),
  });
  if (!res.ok) {
    throw new Error(`GitHub dispatch failed: ${res.status} ${await res.text()}`);
  }
}

export async function handleRequest(req: Request): Promise<Response> {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const configuredSecret = Deno.env.get("PLACE_REPORTS_WEBHOOK_SECRET") ?? "";
  const url = new URL(req.url);
  const providedSecret = req.headers.get("x-webhook-secret") ?? url.searchParams.get("secret") ?? "";
  if (!configuredSecret || !timingSafeEqual(providedSecret, configuredSecret)) {
    return new Response("Invalid secret", { status: 401 });
  }

  let payload: {
    type?: string;
    table?: string;
    record?: { id?: string; place_id?: string | null; report_type?: string };
  };
  try {
    payload = JSON.parse(await req.text());
  } catch {
    return new Response("Bad payload", { status: 200 }); // not actionable, not retryable
  }

  const record = payload.record;
  if (payload.type !== "INSERT" || payload.table !== "place_reports" || !record?.id) {
    return new Response("Ignored event", { status: 200 });
  }

  if (!isAutoRevaluationCandidate(record)) {
    return new Response("Not actionable", { status: 200 });
  }

  const placeId = record.place_id as string;
  const reportId = record.id;

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, supabaseKey);

  const { data: place, error: placeError } = await supabase
    .from("places")
    .select("id, status")
    .eq("id", placeId)
    .maybeSingle();

  if (placeError) {
    return new Response(`Supabase read failed: ${placeError.message}`, { status: 500 });
  }
  if (!place) {
    return new Response("Unknown place_id", { status: 200 });
  }
  if (place.status !== "approved") {
    // ADR-004 point 2 is explicit: only an approved place is auto-actionable.
    return new Response(`Place not approved (status=${place.status})`, { status: 200 });
  }

  const { error: updateError } = await supabase
    .from("place_reports")
    .update({ status: "dispatched" })
    .eq("id", reportId);
  if (updateError) {
    return new Response(`Updating report status failed: ${updateError.message}`, { status: 500 });
  }

  const githubToken = Deno.env.get("GITHUB_DISPATCH_TOKEN") ?? "";
  try {
    await triggerReviewHandler(placeId, reportId, githubToken);
  } catch (err) {
    return new Response(`Dispatch failed: ${err}`, { status: 500 });
  }

  return new Response("OK", { status: 200 });
}

// Only start the HTTP server when this file is run directly (the real Edge
// Function entrypoint) — not when it's imported, e.g. by index.test.ts, which
// would otherwise try to bind a port under the test runner's sandbox.
if (import.meta.main) {
  Deno.serve(handleRequest);
}
