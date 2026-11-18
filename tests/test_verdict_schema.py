"""The Validator asks for its verdict as a structured output (2026-11-18), so a malformed reply cannot reach _normalize."""
from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import MagicMock

from agents.clients.llm import LLMClient
from agents.validator_agent import (
    ALLOWED_CATEGORIES, ALLOWED_SAFETY, ALLOWED_VERDICTS, RUBRIC, VERDICT_SCHEMA, ValidatorAgent,
)


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"ok": true}')], usage=None)


def client():
    c = LLMClient.__new__(LLMClient)
    c._client = SimpleNamespace(messages=FakeMessages())
    c.default_model = "claude-sonnet-4-6"
    return c


def test_a_schema_is_sent_as_a_json_schema_output_format():
    c = client()
    assert c.complete_json("system", "user", schema={"type": "object"}) == {"ok": True}
    assert c._client.messages.calls[0]["output_config"] == {"format": {"type": "json_schema", "schema": {"type": "object"}}}


def test_without_a_schema_the_request_is_unchanged():
    c = client()
    c.complete_json("system", "user")
    assert "output_config" not in c._client.messages.calls[0]


def test_the_validator_always_asks_for_the_verdict_schema():
    llm = MagicMock()
    llm.complete_json.return_value = {"verdict": "needs_review", "confidence_score": 0.6, "category": "cafe",
                                      "safety_level": "options_available", "reasoning": "", "flags": [], "recommendation": ""}
    ValidatorAgent(None, llm).evaluate({"name": "Café X", "city": "Montevideo", "country": "Uruguay"})
    assert llm.complete_json.call_args.kwargs["schema"] is VERDICT_SCHEMA


def test_the_schema_allows_exactly_what_normalize_accepts():
    props = VERDICT_SCHEMA["properties"]
    assert set(props["verdict"]["enum"]) == ALLOWED_VERDICTS
    assert set(props["category"]["enum"]) == ALLOWED_CATEGORIES
    assert set(props["safety_level"]["enum"]) == ALLOWED_SAFETY
    assert VERDICT_SCHEMA["additionalProperties"] is False
    assert set(VERDICT_SCHEMA["required"]) == set(props)


def test_the_schema_has_the_keys_the_rubric_asks_for():
    shape = RUBRIC[RUBRIC.index("exactamente con esta forma"):]
    assert set(re.findall(r'^\{?\s*"(\w+)":', shape, re.MULTILINE)) == set(VERDICT_SCHEMA["properties"])


def test_the_schema_uses_no_unsupported_constraint():
    text = repr(VERDICT_SCHEMA)
    for keyword in ("minimum", "maximum", "minLength", "maxLength", "multipleOf"):
        assert keyword not in text
