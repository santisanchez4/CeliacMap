"""Community reports — automatic re-evaluation trigger (ADR-004).

Triggered by a GitHub repository_dispatch event fired from the Supabase
Edge Function (supabase/functions/place-report-created/) when a negative
community report lands on an already-approved place — never by the
monthly cron, and never for 'positive' reports (see ADR-004). Also driven
directly by .sweep(), the monthly pipeline stage that re-drives anything
the real-time webhook path left stuck (Supabase Database Webhooks do not
auto-retry on a non-2xx response or a timeout).

Re-evaluates a single approved place after a negative report arrives,
combining the original evidence with the report through the *same*
Validator rubric (RUBRIC, ValidatorAgent._normalize) — zero duplicated
rubric/gate logic, same reuse pattern as outreach_reply_handler.py.
Per ADR-004, the Validator's own verdict is trusted directly — approved
stays approved (confirmed), needs_review downgrades, discarded
discards — unlike outreach's ADR-002 special case, since the place
already passed this gate once and this is the same gate reconsidering
it with new evidence, not a new source trying to fast-track approval.
"""

from __future__ import annotations

import argparse
import logging

from agents.base import BaseAgent
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient
from agents.validator_agent import RUBRIC, ValidatorAgent

logger = logging.getLogger("celiacmap.agent")

# Only an approved place can be automatically re-evaluated by a report
# (ADR-004 point 2). A place already moved by an earlier report in the
# same batch (needs_review/discarded) is left alone — no re-triggering.
ACTIONABLE_STATUSES = ("approved",)


def _build_report_prompt(place: dict, reviews: list[dict], report_description: str) -> str:
    base = ValidatorAgent._build_user_prompt(place, reviews)
    return (
        f"{base}\n\n"
        "Reporte directo de la comunidad (no verificado; puede ser un caso "
        "aislado, un error, o mal intencionado — pesar con la misma cautela "
        "que cualquier fuente sin verificar, nunca como confirmación "
        "automática):\n"
        f"{report_description}"
    )


class ReviewHandler(BaseAgent):
    name = "review_handler"

    def __init__(self, db: SupabaseClient, llm: LLMClient, model: str | None = None):
        super().__init__(db)
        self.llm = llm
        self.model = model
        self.validator = ValidatorAgent(db, llm)  # reused only for ._normalize()

    def handle(self, place_id: str, report_id: str) -> dict:
        # Atomic claim (CAS: status new/dispatched -> processing). This is
        # the ONE guard that makes the real-time webhook path and the
        # monthly sweep (see .sweep() below) safe to race against each
        # other: whichever call reaches this UPDATE first wins and
        # proceeds; the other gets False back and exits immediately,
        # never calling the LLM or touching `places`.
        if not self.db.claim_place_report(report_id):
            self.log(
                "review_already_claimed",
                {"place_id": place_id, "report_id": report_id},
                status="success",
                place_id=place_id,
            )
            return {"skipped": "already claimed"}

        place = self.db.fetch_place_by_id(place_id)
        if not place:
            self.log("review_unknown_place", {"place_id": place_id}, status="error")
            return {"skipped": "place not found"}

        if place.get("status") not in ACTIONABLE_STATUSES:
            self.db.update_place_report_status(report_id, "skipped")
            self.log(
                "review_skipped_wrong_status",
                {"place_id": place_id, "report_id": report_id, "status": place.get("status")},
                status="success",
                place_id=place_id,
            )
            return {"skipped": f"status={place.get('status')}"}

        report = self.db.fetch_place_report_by_id(report_id)
        if not report:
            self.db.update_place_report_status(report_id, "error")
            self.log(
                "review_no_report_content",
                {"place_id": place_id, "report_id": report_id},
                status="error",
                place_id=place_id,
            )
            return {"skipped": "no report content"}

        # Defense in depth, mirrors ACTIONABLE_STATUSES above: the Edge
        # Function and the sweep's own SQL filter already restrict dispatch
        # to report_type='negative', but this handler re-checks it too
        # rather than trusting the caller blindly (same precedent as the
        # redundant place.status check just above).
        report_type = report.get("report_type")
        if report_type != "negative":
            self.db.update_place_report_status(report_id, "skipped")
            self.log(
                "review_skipped_wrong_report_type",
                {"place_id": place_id, "report_id": report_id, "report_type": report_type},
                status="success",
                place_id=place_id,
            )
            return {"skipped": f"report_type={report_type}"}

        description = (report.get("description") or "").strip()
        if not description:
            self.db.update_place_report_status(report_id, "error")
            self.log(
                "review_no_report_content",
                {"place_id": place_id, "report_id": report_id},
                status="error",
                place_id=place_id,
            )
            return {"skipped": "no report content"}

        try:
            reviews = self.db.fetch_reviews_for_place(place_id)
        except Exception:  # noqa: BLE001 - review context is best-effort
            logger.exception("fetching review context failed for %s", place_id)
            reviews = []

        prompt = _build_report_prompt(place, reviews, description)

        try:
            raw_verdict = self.llm.complete_json(RUBRIC, prompt, model=self.model)
            v = self.validator._normalize(raw_verdict, place)
        except Exception as exc:  # noqa: BLE001
            self.db.update_place_report_status(report_id, "error")
            logger.exception("report re-evaluation failed for %s", place_id)
            self.log(
                "review_evaluate_failed",
                {"place_id": place_id, "report_id": report_id, "error": str(exc)},
                status="error",
                place_id=place_id,
            )
            return {"skipped": "evaluation failed"}

        # No remapping (unlike ADR-002's outreach_confirmed): the place
        # already passed this gate once, so its own verdict is trusted as-is.
        db_status = v["status"]

        try:
            self.db.update_place_validation(
                place_id,
                status=db_status,
                confidence=v["confidence"],
                notes=v["reason"],
                category=v["category"],
                safety_level=v["safety_level"],
                flags=v["flags"],
                recommendation=v["recommendation"],
            )
            self.db.update_place_report_status(report_id, "processed")
        except Exception as exc:  # noqa: BLE001
            logger.exception("persisting report verdict failed for %s", place_id)
            self.log(
                "review_persist_failed",
                {"place_id": place_id, "report_id": report_id, "error": str(exc)},
                status="error",
                place_id=place_id,
            )
            return {"skipped": "persist failed"}

        self.log(
            "review_evaluated",
            {"place_id": place_id, "report_id": report_id, "verdict": v["verdict"], "status": db_status},
            status="success",
            place_id=place_id,
        )
        return {"place_id": place_id, "status": db_status}

    def sweep(self, limit: int = 50) -> dict:
        """Monthly safety net (8th pipeline stage): re-drive any negative
        report left stuck in 'new' or 'dispatched' because the real-time
        webhook path (Edge Function -> repository_dispatch -> this same
        handle()) never reached 'processed' — Supabase Database Webhooks
        do not auto-retry on a non-2xx response or a timeout, unlike the
        Resend webhook Etapa 2 of outreach relies on.

        Safe to call unconditionally on every monthly run, including when
        nothing is stuck (the common case): calling handle() on a report
        the real-time path already finished is a no-op, because
        claim_place_report() only succeeds from 'new'/'dispatched' — a
        'processed'/'skipped'/'error' report can't be re-claimed. Whether
        the associated place is still 'approved' is re-checked inside
        handle() itself (ACTIONABLE_STATUSES), so this sweep does not
        need its own place-status filter.
        """
        stuck = self.db.fetch_stuck_negative_reports(limit)
        processed = skipped = errors = already_claimed = 0
        for r in stuck:
            result = self.handle(r["place_id"], r["id"])
            if result.get("skipped") == "already claimed":
                # The real-time path won the race in between the sweep's
                # fetch and this call — not a sweep outcome, just a sign
                # the real-time path is working.
                already_claimed += 1
            elif "status" in result:
                processed += 1
            elif "skipped" in result:
                skipped += 1
            else:
                errors += 1

        summary = {
            "stuck_seen": len(stuck),
            "processed": processed,
            "skipped": skipped,
            "already_claimed": already_claimed,
            "errors": errors,
        }
        self.log("review_sweep_complete", summary, status="success")
        return summary


def main() -> int:
    """Run the review handler for one place (invoked by the GitHub Actions
    workflow triggered from the Supabase Edge Function)."""
    from config.settings import get_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--place-id", required=True)
    parser.add_argument("--report-id", required=True)
    args = parser.parse_args()

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key", "anthropic_api_key")
    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    llm = LLMClient(settings.anthropic_api_key, settings.validator_model)

    result = ReviewHandler(db, llm).handle(args.place_id, args.report_id)
    print("Review handled:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
