"""The Validator RUBRIC lives in agents/validator_agent.py (the source of truth) and is copied, in full,
into three docs: CLAUDE.md ("The Core Prompt"), prompts.md and README.md. It is the one quality gate of a
health-sensitive product, so a copy that silently drifts is a real defect — and it did drift: the README copy
lacked a whole paragraph (`ubicacion_geocode`) for months, and the kitchen change had to be copied by hand
three times. This test demands that every doc copy equals the code, ignoring only whitespace / line wrapping.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agents.validator_agent import RUBRIC

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["CLAUDE.md", "prompts.md", "README.md"]


def _norm(text: str) -> str:
    return " ".join(text.split())


def _doc_rubric(path: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8").replace("\r\n", "\n")
    start = text.index("Eres el Validator Agent de CeliacMap")
    end = text.index("\n```", start)
    return text[start:end]


@pytest.mark.parametrize("doc", DOCS)
def test_doc_copy_of_the_rubric_matches_the_code(doc):
    doc_text, code_text = _norm(_doc_rubric(doc)), _norm(RUBRIC)
    if doc_text != code_text:
        # Point at the first difference instead of dumping two 5 KB strings.
        i = next((k for k, (a, b) in enumerate(zip(doc_text, code_text)) if a != b), min(len(doc_text), len(code_text)))
        pytest.fail(
            f"{doc} drifted from agents/validator_agent.py RUBRIC at char {i}:\n"
            f"  doc : ...{doc_text[max(0, i - 40): i + 80]!r}\n"
            f"  code: ...{code_text[max(0, i - 40): i + 80]!r}"
        )
