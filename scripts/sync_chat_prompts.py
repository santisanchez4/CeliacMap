#!/usr/bin/env python
"""Copy ROUTER_PROMPT / RESPONDER_PROMPT from supabase/functions/chat/prompts.ts (the source of
truth) into the two doc copies. Only the two ```xml blocks after each section heading are
rewritten; line endings of each file are preserved; everything else is left byte-identical.

  python scripts/sync_chat_prompts.py           # rewrite the copies
  python scripts/sync_chat_prompts.py --check   # exit 1 if any copy is out of date (no writes)

tests/test_chat_prompts_sync.py is the gate that proves the three copies match.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_TS = ROOT / "supabase" / "functions" / "chat" / "prompts.ts"
# (file, heading that opens the section, heading that closes it or None) — same as the sync test.
DOCS = [
    (ROOT / "prompts.md", "## 27. Chatbot RAG (ADR-006)", "## 28."),
    (ROOT / "docs" / "architecture" / "ADR-006-chatbot-rag.md", "## Los prompts del chatbot", None),
]
XML_FENCE_RE = re.compile(r"(```xml\n)(.*?)(\n```)", re.DOTALL)


def source_prompts() -> list[str]:
    text = PROMPTS_TS.read_text(encoding="utf-8").replace("\r\n", "\n")
    out = []
    for name in ("ROUTER_PROMPT", "RESPONDER_PROMPT"):
        m = re.search(r"export const " + name + r" = `(.*?)`;", text, re.DOTALL)
        if not m:
            raise SystemExit(f"{name} not found in prompts.ts")
        out.append(m.group(1))
    return out


def sync_one(path: Path, start: str, end: str | None, prompts: list[str], write: bool) -> bool:
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    i = text.index(start)
    j = text.index(end, i) if end else len(text)
    blocks = iter(prompts)
    seen = 0

    def repl(m: re.Match) -> str:
        nonlocal seen
        if seen >= 2:
            return m.group(0)
        seen += 1
        return m.group(1) + next(blocks) + m.group(3)

    new_section = XML_FENCE_RE.sub(repl, text[i:j])
    if seen < 2:
        raise SystemExit(f"{path.name}: expected two ```xml blocks after {start!r}, found {seen}")
    new_text = text[:i] + new_section + text[j:]
    changed = new_text != text
    if changed and write:
        path.write_bytes((new_text.replace("\n", "\r\n") if crlf else new_text).encode("utf-8"))
    return changed


def main() -> int:
    check = "--check" in sys.argv
    prompts = source_prompts()
    stale = [p.name for p, s, e in DOCS if sync_one(p, s, e, prompts, write=not check)]
    if check:
        print("out of date:", ", ".join(stale) if stale else "none")
        return 1 if stale else 0
    print("updated:", ", ".join(stale) if stale else "nothing (already in sync)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
