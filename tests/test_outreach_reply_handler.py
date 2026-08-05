"""Unit tests for the Outreach reply handler (offline, all external calls mocked).

ValidatorAgent itself is NOT mocked — the handler is designed to reuse its
real ._normalize()/._decide_status() unmodified, so these tests exercise the
real gates (APPROVE_THRESHOLD/REJECT_THRESHOLD) to prove that reuse actually
holds, not just that a mock was called.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agents.outreach_reply_handler import OutreachReplyHandler, _build_reply_prompt


def make_place(id="place-1", name="Cafe X", category="cafe", city="Montevideo", status="needs_review"):
    return {
        "id": id,
        "name": name,
        "category": category,
        "city": city,
        "status": status,
    }


def make_message(content="Si, tenemos opciones sin TACC certificadas."):
    return {"direction": "received", "content": content}


def make_handler():
    db = MagicMock()
    db.fetch_place_by_id.return_value = make_place()
    db.fetch_latest_received_message.return_value = make_message()
    db.fetch_reviews_for_place.return_value = []
    llm = MagicMock()
    llm.complete_json.return_value = {
        "verdict": "approved",
        "confidence_score": 0.9,
        "category": "cafe",
        "safety_level": "celiac_friendly",
        "reasoning": "Confirmado por el comercio.",
        "flags": [],
        "recommendation": "Aprobar tras revisión final.",
    }
    handler = OutreachReplyHandler(db, llm)
    return handler, db, llm


# --- Prompt building ---------------------------------------------------------


def test_build_reply_prompt_includes_reply_text():
    place = make_place()
    prompt = _build_reply_prompt(place, [], "Si, ofrecemos menu sin TACC certificado.")
    assert "Si, ofrecemos menu sin TACC certificado." in prompt
    assert place["name"] in prompt


# --- Skip cases ----------------------------------------------------------------


def test_handle_skips_unknown_place():
    handler, db, llm = make_handler()
    db.fetch_place_by_id.return_value = None

    result = handler.handle("missing-id")

    assert result == {"skipped": "place not found"}
    llm.complete_json.assert_not_called()


def test_handle_skips_place_in_wrong_status():
    handler, db, llm = make_handler()
    db.fetch_place_by_id.return_value = make_place(status="approved")

    result = handler.handle("place-1")

    assert result == {"skipped": "status=approved"}
    llm.complete_json.assert_not_called()


def test_handle_skips_when_no_reply_content():
    handler, db, llm = make_handler()
    db.fetch_latest_received_message.return_value = None

    result = handler.handle("place-1")

    assert result == {"skipped": "no reply content"}
    llm.complete_json.assert_not_called()


def test_handle_skips_when_reply_content_is_blank():
    handler, db, llm = make_handler()
    db.fetch_latest_received_message.return_value = make_message(content="   ")

    result = handler.handle("place-1")

    assert result == {"skipped": "no reply content"}
    llm.complete_json.assert_not_called()


# --- Status remap (ADR-002: never directly 'approved') --------------------------


def test_approved_verdict_maps_to_outreach_confirmed():
    handler, db, llm = make_handler()

    result = handler.handle("place-1")

    assert result == {"place_id": "place-1", "status": "outreach_confirmed"}
    db.update_place_validation.assert_called_once()
    call = db.update_place_validation.call_args
    assert call.args[0] == "place-1"
    assert call.kwargs["status"] == "outreach_confirmed"


def test_needs_review_verdict_stays_needs_review():
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {
        "verdict": "needs_review",
        "confidence_score": 0.6,
        "category": "cafe",
        "safety_level": "options_available",
        "reasoning": "Respuesta ambigua.",
        "flags": ["Descripción ambigua"],
        "recommendation": "Pedir más detalle.",
    }

    result = handler.handle("place-1")

    assert result["status"] == "needs_review"
    assert db.update_place_validation.call_args.kwargs["status"] == "needs_review"


def test_rejected_verdict_still_discards():
    # Deliberately allowed (confirmed during planning): a genuinely
    # disqualifying reply can still discard the place, not just bounce it
    # back to needs_review — ADR-001's own conservative gate, unmodified.
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {
        "verdict": "rejected",
        "confidence_score": 0.1,
        "category": "cafe",
        "safety_level": "options_available",
        "reasoning": "El comercio confirma que no tiene opciones sin TACC.",
        "flags": ["Información contradictoria"],
        "recommendation": "Descartar.",
    }

    result = handler.handle("place-1")

    assert result["status"] == "discarded"
    assert db.update_place_validation.call_args.kwargs["status"] == "discarded"


def test_low_confidence_approved_falls_back_to_needs_review():
    # Same defense-in-depth gate as the batch Validator: verdict='approved'
    # with confidence below 0.85 still can't auto-confirm.
    handler, db, llm = make_handler()
    llm.complete_json.return_value = {
        "verdict": "approved",
        "confidence_score": 0.6,
        "category": "cafe",
        "safety_level": "options_available",
        "reasoning": "Confirma pero sin detalle de protocolo.",
        "flags": [],
        "recommendation": "Confirmar protocolo de contaminación cruzada.",
    }

    result = handler.handle("place-1")

    assert result["status"] == "needs_review"


def test_outreach_confirmed_place_is_still_actionable():
    # A place already in outreach_confirmed (from an earlier reply) can
    # still be re-evaluated by a later reply in the same thread.
    handler, db, llm = make_handler()
    db.fetch_place_by_id.return_value = make_place(status="outreach_confirmed")

    result = handler.handle("place-1")

    assert result["status"] == "outreach_confirmed"
    assert llm.complete_json.call_count == 2  # opt-out classification + full eval


# --- Error handling ------------------------------------------------------------


def test_llm_failure_is_skipped_without_persisting():
    handler, db, llm = make_handler()
    llm.complete_json.side_effect = RuntimeError("boom")

    result = handler.handle("place-1")

    assert result == {"skipped": "evaluation failed"}
    db.update_place_validation.assert_not_called()


def test_persist_failure_is_skipped():
    handler, db, llm = make_handler()
    db.update_place_validation.side_effect = RuntimeError("db down")

    result = handler.handle("place-1")

    assert result == {"skipped": "persist failed"}


# --- Opt-out detection (ADR-003) -------------------------------------------------


def test_opt_out_reply_sets_flag_and_skips_full_evaluation():
    handler, db, llm = make_handler()
    db.fetch_latest_received_message.return_value = make_message(
        content="Por favor no nos contacten mas, no queremos participar."
    )
    llm.complete_json.side_effect = [
        {"is_opt_out": True, "reason": "El comercio pide no ser contactado."}
    ]

    result = handler.handle("place-1")

    assert result == {"place_id": "place-1", "opt_out": True}
    db.update_place.assert_called_once_with("place-1", {"outreach_opt_out": True})
    db.update_place_validation.assert_not_called()
    llm.complete_json.assert_called_once()  # proves the Sonnet call never fired


def test_non_opt_out_reply_continues_to_full_evaluation():
    handler, db, llm = make_handler()
    llm.complete_json.side_effect = [
        {"is_opt_out": False},
        {
            "verdict": "approved",
            "confidence_score": 0.9,
            "category": "cafe",
            "safety_level": "celiac_friendly",
            "reasoning": "Confirmado por el comercio.",
            "flags": [],
            "recommendation": "Aprobar tras revisión final.",
        },
    ]

    result = handler.handle("place-1")

    assert result == {"place_id": "place-1", "status": "outreach_confirmed"}
    assert llm.complete_json.call_count == 2
    db.update_place.assert_not_called()
    db.update_place_validation.assert_called_once()


def test_opt_out_classification_failure_defaults_to_continue():
    handler, db, llm = make_handler()
    llm.complete_json.side_effect = [
        RuntimeError("haiku boom"),
        {
            "verdict": "needs_review",
            "confidence_score": 0.6,
            "category": "cafe",
            "safety_level": "options_available",
            "reasoning": "Respuesta ambigua.",
            "flags": [],
            "recommendation": "Pedir más detalle.",
        },
    ]

    result = handler.handle("place-1")

    assert result["status"] == "needs_review"
    db.update_place.assert_not_called()
    assert llm.complete_json.call_count == 2


def test_opt_out_persist_failure_is_skipped():
    handler, db, llm = make_handler()
    db.fetch_latest_received_message.return_value = make_message(
        content="No nos contacten mas por favor."
    )
    llm.complete_json.side_effect = [{"is_opt_out": True}]
    db.update_place.side_effect = RuntimeError("db down")

    result = handler.handle("place-1")

    assert result == {"skipped": "opt-out persist failed"}
    db.update_place_validation.assert_not_called()
