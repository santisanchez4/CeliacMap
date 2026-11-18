"""The model reads «sin gluten» where a review or a piece of evidence says «sin TACC» (2026-11-18): measured against the real
model, no RUBRIC wording made it weigh both terms equally. Stored texts, the name and Tope C keep the original wording."""
from __future__ import annotations

import pytest

from agents.validator_agent import ValidatorAgent, canonical_wording


@pytest.mark.parametrize("text, expected", [
    ("Tienen carta sin TACC", "Tienen carta sin gluten"),
    ("Productos SIN TACC", "Productos sin gluten"),
    ("100% sin T.A.C.C.", "100% sin gluten"),
    ("libre de TACC", "libre de gluten"),
    ("Productos libres de T.A.C.C. y sin lactosa", "Productos libres de gluten y sin lactosa"),
    ("#sintacc #celiacos", "#singluten #celiacos"),
    ("Pan sintacc", "Pan singluten"),
    ("Panadería 100% sin TACC. Todo es apto", "Panadería 100% sin gluten. Todo es apto"),
    ("Productos sin T.A.C.C. Todo es apto", "Productos sin gluten Todo es apto"),
    ("sin gluten", "sin gluten"),
    ("bajo en gluten", "bajo en gluten"),
    ("Taccuino sin taccos", "Taccuino sin taccos"),
    ("", ""),
])
def test_every_tacc_spelling_reads_as_gluten(text, expected):
    assert canonical_wording(text) == expected


PLACE = {"name": "La Fábrica Sin TACC", "city": "Montevideo", "country": "Uruguay"}


def test_the_model_reads_one_wording_in_reviews_and_evidence_but_the_name_is_kept():
    prompt = ValidatorAgent._build_user_prompt(
        PLACE, [{"text": "Carta sin TACC con protocolo"}], None,
        [{"source": "web", "text": "Todo es 100% sin T.A.C.C.", "url": "https://x.example"}])
    assert "Carta sin gluten con protocolo" in prompt and "Todo es 100% sin gluten" in prompt
    assert "La Fábrica Sin TACC" in prompt
    assert "TACC" not in prompt.replace("La Fábrica Sin TACC", "")


def test_both_wordings_give_the_model_the_same_prompt():
    tacc = ValidatorAgent._build_user_prompt({**PLACE, "name": "Café X"}, [{"text": "Menú sin TACC"}], None, [])
    gluten = ValidatorAgent._build_user_prompt({**PLACE, "name": "Café X"}, [{"text": "Menú sin gluten"}], None, [])
    assert tacc == gluten


def test_tope_c_still_reads_the_original_texts():
    assert ValidatorAgent.has_exclusive_signal(["100% sin T.A.C.C."]) is True
