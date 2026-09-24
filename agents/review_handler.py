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
What the report DOES to the map (owner decision 2026-09-24, audit plan step 7)
no longer follows the model's verdict directly — one anonymous report could hide
any place:

- 1 or 2 distinct negative reports in 30 days: the place stays on the map with a
  public warning (``places.community_warning_at``, "reportado por la comunidad").
- 3 distinct reports in 30 days (``REPORTS_TO_HIDE``), or ONE report the model judges
  a credible contamination / symptoms report: ``status='needs_review'`` (off the map)
  until the admin reviews it.

The re-evaluation also never raises the safety level, and never erases or overturns an
admin's manual decision (audit plan step 3).
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone

from agents.base import BaseAgent
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient
from agents.manual_overrides import manual_override_marker
from agents.validator_agent import RUBRIC, ValidatorAgent

logger = logging.getLogger("celiacmap.agent")

# Only an approved place can be automatically re-evaluated by a report
# (ADR-004 point 2). A place already moved by an earlier report in the
# same batch (needs_review/discarded) is left alone — no re-triggering.
ACTIONABLE_STATUSES = ("approved",)

# Owner decision 2026-09-24: the third distinct negative report in 30 days hides a place.
REPORTS_TO_HIDE = 3
REPORT_WINDOW_DAYS = 30
# Lowest -> highest. A report can only keep or LOWER a place's level.
SAFETY_ORDER = ("options_available", "celiac_friendly", "gluten_free_100")


def _build_report_prompt(
    place: dict,
    reviews: list[dict],
    report_description: str,
    claims: list[dict] | None = None,
    evidence: list[dict] | None = None,
) -> str:
    base = ValidatorAgent._build_user_prompt(place, reviews, claims, evidence)
    return (
        f"{base}\n\n"
        "Reporte directo de la comunidad (no verificado; puede ser un caso "
        "aislado, un error, o mal intencionado — pesar con la misma cautela "
        "que cualquier fuente sin verificar, nunca como confirmación "
        "automática):\n"
        f"{report_description}\n\n"
        "Además de los campos pedidos, agregá al JSON el campo "
        '"reporte_contaminacion_creible": true si el reporte describe contaminación '
        "con gluten o síntomas después de comer en el lugar Y te resulta creíble "
        "(concreto, coherente con el resto de la evidencia); en cualquier otro caso, false."
    )


def _lower_level(current: str | None, proposed: str | None) -> str | None:
    """The lower of two safety levels; an unknown value never wins."""
    if current not in SAFETY_ORDER:
        return proposed
    if proposed not in SAFETY_ORDER:
        return current
    return min(current, proposed, key=SAFETY_ORDER.index)


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

        try:
            claims = list(self.db.fetch_community_claims(place_id) or [])
        except Exception:  # noqa: BLE001 - claims context is best-effort
            logger.exception("fetching community claims failed for %s", place_id)
            claims = []

        try:
            evidence = list(self.db.fetch_place_evidence(place_id) or [])
        except Exception:  # noqa: BLE001 - evidence context is best-effort
            logger.exception("fetching evidence failed for %s", place_id)
            evidence = []

        prompt = _build_report_prompt(place, reviews, description, claims, evidence)

        try:
            raw_verdict = self.llm.complete_json(RUBRIC, prompt, model=self.model)
            v = self.validator._normalize(
                raw_verdict, place, claims, reviews=reviews, evidence=evidence
            )
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

        contamination = raw_verdict.get("reporte_contaminacion_creible") is True
        try:
            distinct_reports = int(
                self.db.fetch_recent_negative_report_count(place_id, days=REPORT_WINDOW_DAYS)
            )
        except Exception:  # noqa: BLE001 - count once, conservatively, if the read fails
            logger.exception("counting recent reports failed for %s", place_id)
            distinct_reports = 1
        hide = contamination or distinct_reports >= REPORTS_TO_HIDE
        manual = manual_override_marker(place.get("validation_notes"))

        try:
            if hide:
                reason = (
                    "reporte creíble de contaminación o síntomas"
                    if contamination
                    else f"{distinct_reports} reportes negativos distintos en {REPORT_WINDOW_DAYS} días"
                )
                header = (
                    f"RETIRADO DEL MAPA POR REPORTES ({date.today().isoformat()}): {reason}. "
                    f"Re-evaluación del Validator: {v['reason'] or 'sin detalle'}"
                )
                old_notes = (place.get("validation_notes") or "").strip()
                self.db.update_place_validation(
                    place_id,
                    status="needs_review",
                    # An admin's number stays the admin's (never deflated to match the report).
                    confidence=None if manual else v["confidence"],
                    # The previous notes (and any manual-override record) are kept below.
                    notes=f"{header}\n\n{old_notes}" if old_notes else header,
                    category=None if manual else v["category"],
                    safety_level=(
                        None if manual else _lower_level(place.get("safety_level"), v["safety_level"])
                    ),
                    flags=v["flags"],
                    recommendation=v["recommendation"],
                )
                db_status = "needs_review"
            else:
                # Stays on the map, with the public warning. The model's assessment is kept
                # in agent_log for the admin; the place's validation columns are untouched.
                self.db.set_community_warning(place_id, datetime.now(timezone.utc).isoformat())
                db_status = place.get("status") or "approved"
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
            {
                "place_id": place_id,
                "report_id": report_id,
                "verdict": v["verdict"],
                "status": db_status,
                "outcome": "hidden" if hide else "warning",
                "contamination_credible": contamination,
                "distinct_reports_30d": distinct_reports,
                "manual_override": bool(manual),
                "reasoning": v["reason"],
                "flags": v["flags"],
                "recommendation": v["recommendation"],
            },
            status="success",
            place_id=place_id,
        )
        return {"place_id": place_id, "status": db_status, "outcome": "hidden" if hide else "warning"}

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
