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
    assert _parse_json('{"verdict": "approve", "confidence": 0.8}') == {
        "verdict": "approve",
        "confidence": 0.8,
    }


def test_parse_json_inside_code_fence():
    text = '```json\n{"verdict": "discard", "category": "shop"}\n```'
    assert _parse_json(text) == {"verdict": "discard", "category": "shop"}


def test_parse_json_with_surrounding_prose():
    text = 'Here is my verdict: {"verdict": "approve", "confidence": 0.5}. Thanks!'
    assert _parse_json(text)["confidence"] == 0.5


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


# --- Verdict normalization ------------------------------------------------


@pytest.mark.parametrize("verdict", ["approve", "approved", "ACCEPT", "Yes"])
def test_positive_verdicts_map_to_approved(verdict):
    agent = make_agent()
    assert agent._normalize({"verdict": verdict}, {})["approved"] is True


@pytest.mark.parametrize("verdict", ["discard", "no", "reject", ""])
def test_other_verdicts_map_to_not_approved(verdict):
    agent = make_agent()
    assert agent._normalize({"verdict": verdict}, {})["approved"] is False


def test_invalid_category_falls_back_to_place_category():
    agent = make_agent()
    out = agent._normalize({"category": "bar"}, {"category": "shop"})
    assert out["category"] == "shop"


# --- Fallback when response is malformed ----------------------------------


def test_empty_verdict_yields_conservative_defaults():
    agent = make_agent()
    place = {"category": "restaurant", "safety_level": "celiac_friendly"}
    out = agent._normalize({}, place)
    assert out == {
        "approved": False,
        "category": "restaurant",
        "safety_level": "celiac_friendly",
        "confidence": None,
        "reason": None,
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
    assert summary["discarded"] == 0
    db.update_place_validation.assert_not_called()


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
    llm.complete_json.return_value = {"verdict": "approve", "category": "cafe"}

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
    llm.complete_json.return_value = {"verdict": "approve", "category": "cafe"}

    agent = ValidatorAgent(db, llm)
    summary = agent.run()

    assert summary["approved"] == 1
