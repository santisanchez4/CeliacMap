"""The Web agent's research turn declares its server tools as direct calls.

The 20260209 web_search / web_fetch tools default to a caller that needs programmatic tool calling, which claude-haiku-4-5
(the default WEB_SEARCH_MODEL) does not support: the API answered 400 to every research turn (seen 2026-10-13).
"""
from __future__ import annotations

from types import SimpleNamespace

from agents.clients.llm import LLMClient


class RecordingMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"places": []}')],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            stop_reason="end_turn",
        )


def make():
    client = LLMClient.__new__(LLMClient)
    client._client = SimpleNamespace(messages=RecordingMessages())
    client.default_model = "claude-haiku-4-5"
    return client


def test_web_tools_are_declared_as_direct_calls():
    client = make()

    assert client.research_with_web_search("system", "user", max_searches=3) == {"places": []}

    tools = {t["name"]: t for t in client._client.messages.calls[0]["tools"]}
    assert set(tools) == {"web_search", "web_fetch"}
    for tool in tools.values():
        assert tool["allowed_callers"] == ["direct"], tool
    assert tools["web_search"]["max_uses"] == 3
