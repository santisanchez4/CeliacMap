"""CLAUDE.md is loaded into every Claude Code session, so its size is a budget, not a soft target.

It had grown to ~302,000 characters (the harness limit is 150,000) because every decision, phase report and
verification log was appended to it. Since 2026-09-26 the long-form text lives in docs/DECISIONS.md and CLAUDE.md
keeps only contracts, standing rules and an index. This test is the guard that keeps it that way.

Characters are counted as they are on disk (newline="" keeps the CRs of a CRLF working tree), which is what the harness
loads: on the Windows checkout that is the stricter number, on Linux CI the file is LF and a little smaller.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_CHARS = 50_000


def test_claude_md_stays_under_the_size_budget():
    with open(ROOT / "CLAUDE.md", encoding="utf-8", newline="") as f:
        size = len(f.read())
    assert size <= MAX_CHARS, (
        f"CLAUDE.md has {size:,} characters, {size - MAX_CHARS:,} over the {MAX_CHARS:,} budget. "
        "Move long-form text to docs/DECISIONS.md and leave a one-line index entry (see Documentation Rules)."
    )
