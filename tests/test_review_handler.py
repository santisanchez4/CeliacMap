"""Unit tests for the community-report handler (offline, all external calls mocked).

ValidatorAgent itself is NOT mocked — the handler is designed to reuse its real
._normalize()/._decide_status() unmodified, so these tests exercise the real gates
(APPROVE_THRESHOLD/REJECT_THRESHOLD) to prove that reuse actually holds, not just
that a mock was called. Same rigor as test_outreach_reply_handler.py.

Per ADR-004, the verdict is used AS-IS (no remap like outreach's outreach_confirmed):
the place is already approved, so 'approved' stays 'approved'.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.review_handler import ReviewHandler, _build_report_prompt


def make_place(id="place-1", name="Cafe X", category="cafe", city="Montevideo", status="approved"):
    return {
        "id": id,
        "name": name,
        "category": category,
        "city": city,
        "status": status,
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


# --- Real _decide_status output, no remap (ADR-004) ---------------------------


def test_approved_verdict_stays_approved():
    handler, db, llm = make_handler()

    result = handler.handle("place-1", "report-1")

    assert result == {"place_id": "place-1", "status": "approved"}
    db.update_place_validation.assert_called_once()
    call = db.update_place_validation.call_args
    assert call.args[0] == "place-1"
    assert call.kwargs["status"] == "approved"


def test_needs_review_verdict_downgrades_to_needs_review():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {
        "verdict": "needs_review",
        "confidence_score": 0.6,
        "category": "cafe",
        "safety_level": "options_available",
        "reasoning": "Reporte ambiguo, requiere confirmación humana.",
        "flags": ["Descripción ambigua"],
        "recommendation": "Revisar manualmente.",
    }

    result = handler.handle("place-1", "report-1")

    assert result["status"] == "needs_review"
    assert db.update_place_validation.call_args.kwargs["status"] == "needs_review"


def test_rejected_verdict_discards():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {
        "verdict": "rejected",
        "confidence_score": 0.1,
        "category": "cafe",
        "safety_level": "options_available",
        "reasoning": "El reporte confirma que ya no ofrecen opciones sin TACC.",
        "flags": ["Información contradictoria"],
        "recommendation": "Descartar.",
    }

    result = handler.handle("place-1", "report-1")

    assert result["status"] == "discarded"
    assert db.update_place_validation.call_args.kwargs["status"] == "discarded"


def test_low_confidence_approved_falls_back_to_needs_review():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {
        "verdict": "approved",
        "confidence_score": 0.6,
        "category": "cafe",
        "safety_level": "options_available",
        "reasoning": "El reporte no alcanza para confirmar con certeza.",
        "flags": [],
        "recommendation": "Confirmar protocolo de contaminación cruzada.",
    }

    result = handler.handle("place-1", "report-1")

    assert result["status"] == "needs_review"


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
    db.update_place_validation.side_effect = RuntimeError("db down")

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
