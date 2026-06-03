"""Thin Anthropic (Claude) wrapper for the agents.

Intentionally provider-agnostic at the call site: agents depend on
``complete_json`` / ``complete_text``, so OpenAI or DeepSeek could be swapped in
behind the same interface without touching agent logic.

The Validator reuses a large, fixed system rubric across every candidate in a
run, so the system prompt is sent with ``cache_control`` to benefit from prompt
caching (cheaper, faster on repeated calls).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

logger = logging.getLogger("celiacmap.llm")

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output, tolerating prose/code fences."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if match:
            return json.loads(match.group(0))
        raise


class LLMClient:
    def __init__(self, api_key: str, default_model: str):
        if not api_key:
            raise ValueError("LLMClient requires an Anthropic API key.")
        self._client = anthropic.Anthropic(api_key=api_key)
        self.default_model = default_model

    def _create(self, system: str, user: str, model: str | None, max_tokens: int):
        return self._client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            # System sent as a cacheable block — reused across a batch of candidates.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )

    @staticmethod
    def _text(resp) -> str:
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )

    def complete_text(
        self, system: str, user: str, model: str | None = None, max_tokens: int = 1024
    ) -> str:
        resp = self._create(system, user, model, max_tokens)
        if getattr(resp, "usage", None):
            logger.debug("tokens in=%s out=%s", resp.usage.input_tokens, resp.usage.output_tokens)
        return self._text(resp)

    def complete_json(
        self, system: str, user: str, model: str | None = None, max_tokens: int = 1024
    ) -> dict[str, Any]:
        """Return a parsed JSON object from the model (for structured verdicts)."""
        return _parse_json(self.complete_text(system, user, model=model, max_tokens=max_tokens))
