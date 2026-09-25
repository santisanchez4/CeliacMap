"""Unit tests for the community-report handler (offline, all external calls mocked).

ValidatorAgent itself is NOT mocked — the handler is designed to reuse its real
._normalize()/._decide_status() unmodified, so these tests exercise the real gates
(APPROVE_THRESHOLD/REJECT_THRESHOLD) to prove that reuse actually holds, not just
that a mock was called. Same rigor as test_outreach_reply_handler.py.

What a report does to the map follows the owner decision of 2026-09-24 (audit plan
step 7): 1-2 distinct reports in 30 days -> public warning, the place stays; 3, or one
credible contamination report -> needs_review (off the map). A report never raises the
level and never erases or overturns an admin's manual decision (step 3).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.review_handler import ReviewHandler, _build_report_prompt


def make_place(
    id="place-1", name="Cafe X", category="cafe", city="Montevideo", status="approved",
    safety_level="celiac_friendly", validation_notes=None,
):
    return {
        "id": id,
        "name": name,
        "category": category,
        "city": city,
        "status": status,
        "safety_level": safety_level,
        "validation_notes": validation_notes,
    }


def make_report(
    id="report-1",
    place_id="place-1",
    report_type="negative",
    description="Fui la semana pasada y ya no tienen menu sin TACC.",
):
    return {
        "id": id,
        "place_id": place_id,
        "report_type": report_type,
        "description": description,
    }


def make_handler():
    db = MagicMock()
    db.claim_place_report.return_value = True
    db.fetch_place_by_id.return_value = make_place()
    db.fetch_place_report_by_id.return_value = make_report()
    db.fetch_reviews_for_place.return_value = []
    db.fetch_place_evidence.return_value = []
    db.fetch_recent_negative_report_count.return_value = 1
    llm = MagicMock()
    llm.complete_json.return_value = {
        "verdict": "approved",
        "confidence_score": 0.9,
        "category": "cafe",
        "safety_level": "celiac_friendly",
        "reasoning": "El reporte no aporta evidencia suficiente para bajar la confianza.",
        "flags": [],
        "recommendation": "Mantener aprobado.",
    }
    handler = ReviewHandler(db, llm)
    return handler, db, llm


# --- Prompt building ---------------------------------------------------------


def test_build_report_prompt_includes_report_description():
    place = make_place()
    prompt = _build_report_prompt(place, [], "Ya no tienen protocolo sin TACC.")
    assert "Ya no tienen protocolo sin TACC." in prompt
    assert place["name"] in prompt


# --- Idempotency (the central guard) -----------------------------------------


def test_handle_returns_early_when_claim_fails():
    handler, db, llm = make_handler()
    db.claim_place_report.return_value = False

    result = handler.handle("place-1", "report-1")

    assert result == {"skipped": "already claimed"}
    db.fetch_place_by_id.assert_not_called()
    db.fetch_place_report_by_id.assert_not_called()
    llm.complete_json.assert_not_called()
    db.update_place_validation.assert_not_called()
    db.update_place_report_status.assert_not_called()


# --- Report-type guard (defense in depth, mirrors ACTIONABLE_STATUSES) -------


def test_handle_skips_positive_report_type():
    handler, db, llm = make_handler()
    db.fetch_place_report_by_id.return_value = make_report(report_type="positive")

    result = handler.handle("place-1", "report-1")

    assert result == {"skipped": "report_type=positive"}
    db.update_place_report_status.assert_called_once_with("report-1", "skipped")
    llm.complete_json.assert_not_called()
    db.update_place_validation.assert_not_called()


# --- Unknown place / null place_id -------------------------------------------


def test_handle_skips_unknown_place():
    handler, db, llm = make_handler()
    db.fetch_place_by_id.return_value = None

    result = handler.handle("missing-id", "report-1")

    assert result == {"skipped": "place not found"}
    llm.complete_json.assert_not_called()


def test_handle_with_none_place_id_is_treated_as_unknown_place():
    handler, db, llm = make_handler()
    db.fetch_place_by_id.return_value = None

    result = handler.handle(None, "report-1")

    assert result == {"skipped": "place not found"}
    db.fetch_place_by_id.assert_called_once_with(None)
    llm.complete_json.assert_not_called()


# --- Wrong place status -------------------------------------------------------


@pytest.mark.parametrize(
    "status", ["pending", "needs_review", "discarded", "outreach_confirmed"]
)
def test_handle_skips_place_not_approved(status):
    handler, db, llm = make_handler()
    db.fetch_place_by_id.return_value = make_place(status=status)

    result = handler.handle("place-1", "report-1")

    assert result == {"skipped": f"status={status}"}
    db.update_place_report_status.assert_called_once_with("report-1", "skipped")
    llm.complete_json.assert_not_called()


# --- Missing/blank report -----------------------------------------------------


def test_handle_skips_when_report_not_found():
    handler, db, llm = make_handler()
    db.fetch_place_report_by_id.return_value = None

    result = handler.handle("place-1", "report-1")

    assert result == {"skipped": "no report content"}
    llm.complete_json.assert_not_called()


def test_handle_skips_when_report_description_is_blank():
    handler, db, llm = make_handler()
    db.fetch_place_report_by_id.return_value = make_report(description="   ")

    result = handler.handle("place-1", "report-1")

    assert result == {"skipped": "no report content"}
    llm.complete_json.assert_not_called()


# --- Warning vs off the map (owner decision 2026-09-24) -------------------------

HIDING_VERDICT = {
    "verdict": "needs_review",
    "confidence_score": 0.52,
    "category": "cafe",
    "safety_level": "options_available",
    "reasoning": "El reporte describe contaminación concreta.",
    "flags": ["Reseñas negativas de celíacos"],
    "recommendation": "Revisar con el comercio.",
    "reporte_contaminacion_creible": True,
}


def test_first_report_only_sets_the_public_warning():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {**HIDING_VERDICT, "reporte_contaminacion_creible": False}

    result = handler.handle("place-1", "report-1")

    assert result == {"place_id": "place-1", "status": "approved", "outcome": "warning"}
    db.set_community_warning.assert_called_once()
    assert db.set_community_warning.call_args.args[0] == "place-1"
    db.update_place_validation.assert_not_called()  # the place stays exactly as it was
    db.update_place_report_status.assert_called_once_with("report-1", "processed")


def test_even_a_rejected_verdict_only_warns_below_the_threshold():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {**HIDING_VERDICT, "verdict": "rejected", "confidence_score": 0.1,
                                      "reporte_contaminacion_creible": False}

    assert handler.handle("place-1", "report-1")["outcome"] == "warning"
    db.update_place_validation.assert_not_called()


@pytest.mark.parametrize("count, outcome", [(1, "warning"), (2, "warning"), (3, "hidden"), (5, "hidden")])
def test_the_third_distinct_report_hides_the_place(count, outcome):
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {**HIDING_VERDICT, "reporte_contaminacion_creible": False}
    db.fetch_recent_negative_report_count.return_value = count

    assert handler.handle("place-1", "report-1")["outcome"] == outcome
    db.fetch_recent_negative_report_count.assert_called_once_with("place-1", days=30)
    if outcome == "hidden":
        assert db.update_place_validation.call_args.kwargs["status"] == "needs_review"


def test_one_credible_contamination_report_hides_the_place():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = HIDING_VERDICT

    result = handler.handle("place-1", "report-1")

    assert result == {"place_id": "place-1", "status": "needs_review", "outcome": "hidden"}
    kwargs = db.update_place_validation.call_args.kwargs
    assert kwargs["status"] == "needs_review"
    assert kwargs["notes"].startswith("RETIRADO DEL MAPA POR REPORTES")
    assert "contaminación" in kwargs["notes"]
    db.set_community_warning.assert_not_called()


def test_contamination_must_be_literally_true():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {**HIDING_VERDICT, "reporte_contaminacion_creible": "true"}

    assert handler.handle("place-1", "report-1")["outcome"] == "warning"


def test_prompt_asks_for_the_contamination_field():
    prompt = _build_report_prompt(make_place(), [], "me contaminé")
    assert '"reporte_contaminacion_creible"' in prompt


def test_count_failure_counts_this_report_once():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {**HIDING_VERDICT, "reporte_contaminacion_creible": False}
    db.fetch_recent_negative_report_count.side_effect = RuntimeError("db down")

    assert handler.handle("place-1", "report-1")["outcome"] == "warning"


# --- A report never raises the level, never overturns the admin (step 3) ------


def test_hiding_never_raises_the_safety_level():
    handler, db, llm = make_handler()
    db.fetch_place_by_id.return_value = make_place(safety_level="options_available")
    llm.complete_json.return_value = {**HIDING_VERDICT, "safety_level": "celiac_friendly"}

    handler.handle("place-1", "report-1")

    assert db.update_place_validation.call_args.kwargs["safety_level"] == "options_available"


def test_hiding_can_lower_the_safety_level():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = HIDING_VERDICT  # celiac_friendly -> options_available

    handler.handle("place-1", "report-1")

    assert db.update_place_validation.call_args.kwargs["safety_level"] == "options_available"


def test_hiding_a_manual_override_keeps_the_admin_record_and_level():
    handler, db, llm = make_handler()
    notes = "CORRECCIÓN MANUAL 2026-09-24: cocina exclusivamente sin gluten (admin)."
    db.fetch_place_by_id.return_value = make_place(safety_level="gluten_free_100", validation_notes=notes)
    llm.complete_json.return_value = HIDING_VERDICT

    handler.handle("place-1", "report-1")

    kwargs = db.update_place_validation.call_args.kwargs
    assert kwargs["status"] == "needs_review"  # off the map until the admin looks
    assert kwargs["safety_level"] is None  # the admin's 100% is not overwritten
    assert kwargs["confidence"] is None and kwargs["category"] is None
    assert kwargs["notes"].endswith(notes)  # the override record is kept below the new header


# --- Error handling ------------------------------------------------------------


def test_llm_failure_is_skipped_without_persisting():
    handler, db, llm = make_handler()
    llm.complete_json.side_effect = RuntimeError("boom")

    result = handler.handle("place-1", "report-1")

    assert result == {"skipped": "evaluation failed"}
    db.update_place_validation.assert_not_called()
    db.update_place_report_status.assert_called_once_with("report-1", "error")


def test_persist_failure_is_skipped():
    handler, db, llm = make_handler()
    db.set_community_warning.side_effect = RuntimeError("db down")

    result = handler.handle("place-1", "report-1")

    assert result == {"skipped": "persist failed"}


def test_report_status_marked_processed_on_successful_evaluation():
    handler, db, llm = make_handler()

    handler.handle("place-1", "report-1")

    db.update_place_report_status.assert_called_once_with("report-1", "processed")


# --- .sweep() ------------------------------------------------------------------


def test_sweep_calls_handle_for_each_stuck_report():
    handler, db, llm = make_handler()
    db.fetch_stuck_negative_reports.return_value = [
        {"place_id": "place-1", "id": "report-1"},
        {"place_id": "place-2", "id": "report-2"},
    ]
    handler.handle = MagicMock(return_value={"place_id": "place-1", "status": "approved"})

    handler.sweep()

    assert handler.handle.call_count == 2
    handler.handle.assert_any_call("place-1", "report-1")
    handler.handle.assert_any_call("place-2", "report-2")


def test_sweep_counts_already_claimed_separately_from_processed():
    handler, db, llm = make_handler()
    db.fetch_stuck_negative_reports.return_value = [
        {"place_id": "place-1", "id": "report-1"},
        {"place_id": "place-2", "id": "report-2"},
    ]
    handler.handle = MagicMock(
        side_effect=[
            {"place_id": "place-1", "status": "approved"},
            {"skipped": "already claimed"},
        ]
    )

    summary = handler.sweep()

    assert summary["processed"] == 1
    assert summary["already_claimed"] == 1
    assert summary["errors"] == 0


def test_sweep_returns_zero_counts_when_nothing_stuck():
    handler, db, llm = make_handler()
    db.fetch_stuck_negative_reports.return_value = []
    handler.handle = MagicMock()

    summary = handler.sweep()

    handler.handle.assert_not_called()
    assert summary == {
        "stuck_seen": 0,
        "processed": 0,
        "skipped": 0,
        "already_claimed": 0,
        "errors": 0,
    }


def test_sweep_logs_summary():
    handler, db, llm = make_handler()
    db.fetch_stuck_negative_reports.return_value = [
        {"place_id": "place-1", "id": "report-1"},
    ]
    handler.handle = MagicMock(return_value={"place_id": "place-1", "status": "approved"})
    handler.log = MagicMock()

    summary = handler.sweep()

    handler.log.assert_called_once_with(
        "review_sweep_complete", summary, status="success"
    )


# --- Community kitchen claims -------------------------------------------------


def test_build_report_prompt_includes_unverified_kitchen_claims():
    claims = [{"kitchen_exclusive": True, "celiac_prep": None, "owner_celiac": True}]
    prompt = _build_report_prompt(make_place(), [], "Ya no tienen protocolo sin TACC.", claims)
    assert "declaraciones_comunidad (NO verificadas):" in prompt
    assert "Ya no tienen protocolo sin TACC." in prompt


def test_handle_passes_claims_to_prompt_and_reads_them_best_effort():
    handler, db, llm = make_handler()
    db.fetch_community_claims.return_value = [{"kitchen_exclusive": False, "celiac_prep": "shared_kitchen"}]

    handler.handle("place-1", "report-1")

    db.fetch_community_claims.assert_called_once_with("place-1")
    assert "misma cocina" in llm.complete_json.call_args.args[1]


def test_handle_survives_claims_fetch_failure():
    handler, db, llm = make_handler()
    db.fetch_community_claims.side_effect = RuntimeError("db down")

    result = handler.handle("place-1", "report-1")

    assert "skipped" not in result
    llm.complete_json.assert_called_once()
