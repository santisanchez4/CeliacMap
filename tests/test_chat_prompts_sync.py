"""The chatbot's two system prompts (ROUTER + REDACTOR) live in three places:

    supabase/functions/chat/prompts.ts   -- the source of truth (what actually runs)
    prompts.md                           -- section 27
    docs/architecture/ADR-006-chatbot-rag.md -- "Los prompts del chatbot"

Same copy discipline as the Validator RUBRIC: they are the only gate
between a user's message and what the bot does or says on a health-sensitive
product, so a copy that silently drifts is a real defect. This test extracts the
prompt from every location and demands exact equality with prompts.ts.

CLAUDE.md used to carry a fourth copy; it was removed on 2026-09-26 and now only points at prompts.ts.

Line endings are normalised (the working tree is CRLF on Windows, git stores LF);
everything else -- every character of every instruction and example -- must match.
"""
import difflib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

PROMPTS_TS = ROOT / "supabase" / "functions" / "chat" / "prompts.ts"

# (file, heading that opens the prompt section, heading that closes it or None)
DOCS = [
    (ROOT / "prompts.md", "## 27. Chatbot RAG (ADR-006)", "## 28."),
    (ROOT / "docs" / "architecture" / "ADR-006-chatbot-rag.md", "## Los prompts del chatbot", None),
]

XML_FENCE_RE = re.compile(r"```xml\n(.*?)\n```", re.DOTALL)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _source_prompts() -> dict[str, str]:
    text = _read(PROMPTS_TS)
    out = {}
    for name in ("ROUTER_PROMPT", "RESPONDER_PROMPT"):
        m = re.search(r"export const " + name + r" = `(.*?)`;", text, re.DOTALL)
        assert m, f"{name} not found in prompts.ts"
        out[name] = m.group(1)
    return out


def _doc_prompts(path: Path, start: str, end: str | None) -> dict[str, str]:
    text = _read(path)
    i = text.index(start)
    j = text.index(end, i) if end else len(text)
    blocks = XML_FENCE_RE.findall(text[i:j])
    assert len(blocks) >= 2, f"{path.name}: expected the ROUTER and REDACTOR ```xml blocks after {start!r}"
    router, responder = blocks[0], blocks[1]
    # Guard against picking the wrong fence if a doc ever gains another xml block first.
    assert "clasificador de intención" in router, f"{path.name}: first xml block is not the ROUTER prompt"
    assert "Sos el asistente de CeliacMap" in responder, f"{path.name}: second xml block is not the REDACTOR prompt"
    return {"ROUTER_PROMPT": router, "RESPONDER_PROMPT": responder}


def _diff(expected: str, actual: str, label: str) -> str:
    lines = difflib.unified_diff(
        expected.splitlines(), actual.splitlines(), "prompts.ts", label, lineterm="", n=1
    )
    return "\n".join(list(lines)[:40])


@pytest.mark.parametrize("name", ["ROUTER_PROMPT", "RESPONDER_PROMPT"])
@pytest.mark.parametrize("path,start,end", DOCS, ids=[d[0].name for d in DOCS])
def test_prompt_copy_matches_prompts_ts(path, start, end, name):
    source = _source_prompts()[name]
    copy = _doc_prompts(path, start, end)[name]
    assert copy == source, f"{path.name} {name} drifted from prompts.ts:\n" + _diff(source, copy, path.name)
