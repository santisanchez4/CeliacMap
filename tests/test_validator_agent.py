"""Unit tests for the Validator agent and the JSON parsing it relies on."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from agents.clients.llm import _parse_json
from agents.validator_agent import DEFAULT_SAFETY_LEVEL, ValidatorAgent


def make_agent():
    return ValidatorAgent(MagicMock(), MagicMock())


# --- JSON response parsing from Claude ------------------------------------


def test_parse_plain_json():
    assert _parse_json('{"verdict": "approved", "confidence_score": 0.8}') == {
        "verdict": "approved",
        "confidence_score": 0.8,
    }


def test_parse_json_inside_code_fence():
    text = '```json\n{"verdict": "rejected", "category": "shop"}\n```'
    assert _parse_json(text) == {"verdict": "rejected", "category": "shop"}


def test_parse_json_with_surrounding_prose():
    text = 'Mi veredicto: {"verdict": "needs_review", "confidence_score": 0.5}. Gracias!'
    assert _parse_json(text)["confidence_score"] == 0.5


def test_parse_json_raises_on_garbage():
    with pytest.raises(json.JSONDecodeError):
        _parse_json("no json object here at all")


# --- Confidence clamping --------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (0.5, 0.5),
        (1.5, 1.0),
        (-0.3, 0.0),
        (1, 1.0),
        (0, 0.0),
        ("0.7", 0.7),
    ],
)
def test_confidence_clamped_into_unit_range(raw, expected):
    assert ValidatorAgent._clamp_confidence(raw) == expected


@pytest.mark.parametrize("raw", [None, "abc", "", [1, 2]])
def test_confidence_invalid_becomes_none(raw):
    assert ValidatorAgent._clamp_confidence(raw) is None


# --- Conservative safety floor logic --------------------------------------


def test_invalid_safety_falls_back_to_place_value():
    agent = make_agent()
    place = {"category": "cafe", "safety_level": "celiac_friendly"}
    out = agent._normalize({"safety_level": "ultra_safe"}, place)
    assert out["safety_level"] == "celiac_friendly"


def test_invalid_safety_with_no_place_value_uses_default_floor():
    agent = make_agent()
    out = agent._normalize({"safety_level": "ultra_safe"}, {"category": "cafe"})
    assert out["safety_level"] == DEFAULT_SAFETY_LEVEL == "options_available"


def test_valid_safety_passes_through():
    agent = make_agent()
    out = agent._normalize({"safety_level": "gluten_free_100"}, {})
    assert out["safety_level"] == "gluten_free_100"


# --- Confidence gates → DB status (defense in depth) ----------------------


@pytest.mark.parametrize(
    "verdict, conf, expected",
    [
        ("approved", 0.85, "approved"),       # at the approve threshold
        ("approved", 0.84, "needs_review"),   # just below → held for a human
        ("approved", 0.50, "needs_review"),   # mid band
        ("approved", 0.49, "discarded"),      # below reject threshold
        ("approved", None, "discarded"),      # missing confidence → 0.0
        ("needs_review", 0.95, "needs_review"),  # model caution respected
        ("rejected", 0.99, "discarded"),      # explicit reject, any confidence
    ],
)
def test_decide_status_gates(verdict, conf, expected):
    assert ValidatorAgent._decide_status(verdict, conf) == expected


# --- Verdict normalization ------------------------------------------------


def test_approved_with_high_confidence_maps_to_approved():
    agent = make_agent()
    out = agent._normalize({"verdict": "approved", "confidence_score": 0.9}, {})
    assert out["verdict"] == "approved"
    assert out["status"] == "approved"


def test_approved_but_low_confidence_falls_back_to_needs_review():
    # Golden rule: weak confidence can never auto-approve.
    agent = make_agent()
    out = agent._normalize({"verdict": "approved", "confidence_score": 0.6}, {})
    assert out["status"] == "needs_review"


def test_rejected_maps_to_discarded():
    agent = make_agent()
    out = agent._normalize({"verdict": "rejected", "confidence_score": 0.9}, {})
    assert out["status"] == "discarded"


@pytest.mark.parametrize("verdict", ["maybe", "", "ACCEPT", "yes"])
def test_unknown_verdict_label_defaults_to_needs_review(verdict):
    # Anything outside the allowed set is treated as the cautious middle tier.
    agent = make_agent()
    out = agent._normalize({"verdict": verdict, "confidence_score": 0.9}, {})
    assert out["verdict"] == "needs_review"
    assert out["status"] == "needs_review"


def test_invalid_category_falls_back_to_place_category():
    agent = make_agent()
    out = agent._normalize({"category": "bar"}, {"category": "shop"})
    assert out["category"] == "shop"


# --- Flags + recommendation extraction ------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (["sin TACC no mencionado", "sin certificación"], ["sin TACC no mencionado", "sin certificación"]),
        ("solo un flag", ["solo un flag"]),
        (None, []),
        ([], []),
        ([" x ", "", "y"], ["x", "y"]),
        (123, []),
    ],
)
def test_flags_coercion(raw, expected):
    assert ValidatorAgent._coerce_flags(raw) == expected


def test_reasoning_and_recommendation_are_trimmed():
    agent = make_agent()
    out = agent._normalize(
        {
            "verdict": "approved",
            "confidence_score": 0.9,
            "reasoning": "  menciona sin TACC  ",
            "recommendation": " publicar ",
            "flags": ["sin certificación"],
        },
        {},
    )
    assert out["reason"] == "menciona sin TACC"
    assert out["recommendation"] == "publicar"
    assert out["flags"] == ["sin certificación"]


# --- Fallback when response is malformed ----------------------------------


def test_empty_verdict_yields_conservative_defaults():
    agent = make_agent()
    place = {"category": "restaurant", "safety_level": "celiac_friendly"}
    out = agent._normalize({}, place)
    assert out == {
        "verdict": "needs_review",
        "status": "discarded",  # no confidence → 0.0 → below reject threshold
        "category": "restaurant",
        "safety_level": "celiac_friendly",
        "confidence": None,
        "reason": None,
        "flags": [],
        "recommendation": None,
    }


def test_malformed_llm_response_is_caught_in_run():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_reviews_for_place.return_value = []
    llm = MagicMock()
    llm.complete_json.side_effect = json.JSONDecodeError("boom", "doc", 0)

    agent = ValidatorAgent(db, llm)
    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["approved"] == 0
    assert summary["needs_review"] == 0
    assert summary["discarded"] == 0
    db.update_place_validation.assert_not_called()


def test_run_persists_needs_review_status():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [
        {"id": "p1", "name": "Cafe X", "category": "cafe"}
    ]
    db.fetch_reviews_for_place.return_value = []
    llm = MagicMock()
    llm.complete_json.return_value = {
        "verdict": "needs_review",
        "confidence_score": 0.6,
        "category": "cafe",
        "safety_level": "options_available",
    }

    agent = ValidatorAgent(db, llm)
    summary = agent.run()

    assert summary["needs_review"] == 1
    assert summary["approved"] == 0 and summary["discarded"] == 0
    _, kwargs = db.update_place_validation.call_args
    assert kwargs["status"] == "needs_review"


# --- Review snippets as validator context ---------------------------------


def test_user_prompt_includes_review_snippets():
    place = {"name": "Cafe X", "city": "Montevideo"}
    reviews = [{"text": "Tienen opciones sin TACC"}, {"text": ""}]
    prompt = ValidatorAgent._build_user_prompt(place, reviews)
    assert "Community review signals:" in prompt
    assert "Tienen opciones sin TACC" in prompt


def test_user_prompt_without_reviews_has_no_signals_section():
    prompt = ValidatorAgent._build_user_prompt({"name": "Cafe X"}, [])
    assert "Community review signals:" not in prompt


def test_run_feeds_reviews_into_prompt():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_reviews_for_place.return_value = [{"text": "menu apto celiacos"}]
    llm = MagicMock()
    llm.complete_json.return_value = {
        "verdict": "approved",
        "confidence_score": 0.9,
        "category": "cafe",
    }

    agent = ValidatorAgent(db, llm)
    agent.run()

    db.fetch_reviews_for_place.assert_called_once_with("p1")
    user_prompt = llm.complete_json.call_args.args[1]
    assert "menu apto celiacos" in user_prompt


def test_run_survives_review_fetch_failure():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_reviews_for_place.side_effect = RuntimeError("db down")
    llm = MagicMock()
    llm.complete_json.return_value = {
        "verdict": "approved",
        "confidence_score": 0.9,
        "category": "cafe",
    }

    agent = ValidatorAgent(db, llm)
    summary = agent.run()

    assert summary["approved"] == 1
