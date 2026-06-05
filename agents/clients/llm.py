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

# Anthropic server-side web tools (run on Anthropic's infrastructure). web_search
# lets Claude write its own queries; web_fetch lets it read a full page (forum,
# blog, community post). Used by the Web discovery agent (v3).
WEB_SEARCH_TOOL_TYPE = "web_search_20260209"
WEB_FETCH_TOOL_TYPE = "web_fetch_20260209"


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

    def research_with_web_search(
        self,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = 4096,
        max_searches: int = 8,
        max_continuations: int = 6,
    ) -> dict[str, Any]:
        """Run an agentic web-search turn and return the model's final JSON.

        The model is given Anthropic's server-side web_search + web_fetch tools
        and reasons freely about how to find candidates (no predefined queries).
        Anthropic runs the tool loop server-side; when it hits its per-turn tool
        limit it returns ``stop_reason='pause_turn'``, which we resume by re-sending
        the accumulated messages (bounded by ``max_continuations``). The final
        assistant text is parsed as JSON (tolerating prose / code fences).
        """
        tools = [
            {"type": WEB_SEARCH_TOOL_TYPE, "name": "web_search", "max_uses": max_searches},
            {"type": WEB_FETCH_TOOL_TYPE, "name": "web_fetch"},
        ]
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        resp = None
        for _ in range(max_continuations + 1):
            resp = self._client.messages.create(
                model=model or self.default_model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
                tools=tools,
            )
            if getattr(resp, "usage", None):
                logger.debug(
                    "tokens in=%s out=%s", resp.usage.input_tokens, resp.usage.output_tokens
                )
            if resp.stop_reason != "pause_turn":
                break
            # Server paused its tool loop — re-send so it resumes where it left off.
            messages.append({"role": "assistant", "content": resp.content})
        return _parse_json(self._text(resp))
