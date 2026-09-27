"""LLMClient remembers the token usage of its last call (the evidence finder reports it)."""
from __future__ import annotations

from types import SimpleNamespace

from agents.clients.llm import LLMClient


class FakeMessages:
    def create(self, **kwargs):
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"ok": true}')],
            usage=SimpleNamespace(input_tokens=123, output_tokens=45),
        )


def make():
    client = LLMClient.__new__(LLMClient)
    client._client = SimpleNamespace(messages=FakeMessages())
    client.default_model = "claude-haiku-4-5"
    return client


def test_the_usage_of_the_last_call_is_kept():
    client = make()
    assert client.complete_json("system", "user") == {"ok": True}
    assert client.last_usage == {"input": 123, "output": 45}
