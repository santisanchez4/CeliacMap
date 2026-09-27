"""What the admin's acceptance writes: the note (public), the evidence rows (server-only) and when a place needs the admin to open the link.

Rules (docs/runbooks/evidence-finder.md): a quote is put in the public note only when it was verified on the page itself; a "100" whose
only support is a search snippet or a social profile is "100 · verificar en la fuente" and is never accepted in bulk.
"""
from __future__ import annotations

import pytest

from agents.evidence_finder import build_acceptance_note, needs_source_check

PID = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10"

OWN = {"text": "Somos 100% sin gluten desde 2015.", "url": "https://tiempolibre.com.ar", "source_kind": "propia",
       "has_signal": True, "alcance": "establecimiento", "contradice": False, "verificacion": "verificada"}
BLOG = {"text": "Todo es sin gluten.", "url": "https://blog.example/guia", "source_kind": "tercero",
        "has_signal": True, "alcance": "establecimiento", "contradice": False, "verificacion": "solo_snippet"}
INSTA = {"text": "100% libre de gluten, 100% libre de gluten de San Nicolás.", "url": "https://www.instagram.com/apto.libredegluten",
         "source_kind": "tercero", "has_signal": True, "alcance": "establecimiento", "contradice": False, "verificacion": "no_verificable"}
OPT = {"text": "Tenemos opciones sin TACC.", "url": "https://x.example", "source_kind": "tercero", "has_signal": False,
       "alcance": "opciones", "contradice": False, "verificacion": "verificada"}


def entry(proposal="100", citations=None):
    return {"place_id": PID, "proposal": proposal, "citations": [BLOG, OWN] if citations is None else citations}


# --- when the admin must open the link ------------------------------------------------------------------------------------

def test_a_100_needs_the_source_check_unless_a_verified_exclusivity_quote_supports_it():
    assert needs_source_check(entry("100", [OWN])) is False
    assert needs_source_check(entry("100", [BLOG, OWN])) is False  # one verified quote is enough
    assert needs_source_check(entry("100", [BLOG])) is True
    assert needs_source_check(entry("100", [INSTA])) is True
    assert needs_source_check(entry("100", [BLOG, INSTA])) is True


def test_a_verified_quote_that_is_not_an_exclusivity_claim_does_not_lift_the_source_check():
    weak = dict(OWN, has_signal=False)
    assert needs_source_check(entry("100", [BLOG, weak])) is True
    product = dict(OWN, alcance="producto_o_linea")
    assert needs_source_check(entry("100", [INSTA, product])) is True


def test_options_and_insuficiente_never_need_the_source_check():
    assert needs_source_check(entry("options", [BLOG])) is False
    assert needs_source_check(entry("insuficiente", [])) is False


def test_an_old_report_without_verification_labels_is_read_as_unverified():
    legacy = {k: v for k, v in OWN.items() if k != "verificacion"}
    assert needs_source_check(entry("100", [legacy])) is True


# --- the public note ------------------------------------------------------------------------------------------------------

def test_a_verified_quote_is_cited_in_the_note_and_the_best_source_comes_first():
    note, store = build_acceptance_note(entry())
    assert note == "evidencia pública para 100% sin gluten: «Somos 100% sin gluten desde 2015.» (https://tiempolibre.com.ar)"
    assert [s["source"] for s in store] == ["web", "web"] and store[0]["url"] == "https://tiempolibre.com.ar"


def test_a_verified_quote_wins_over_a_better_ranked_unverified_one():
    own_unverified = dict(OWN, verificacion="solo_snippet")
    third_verified = dict(BLOG, verificacion="verificada")
    note, _ = build_acceptance_note(entry("100", [own_unverified, third_verified]))
    assert "«Todo es sin gluten.»" in note and "https://blog.example/guia" in note


def test_an_unverified_social_source_is_never_quoted_in_the_public_note():
    note, store = build_acceptance_note(entry("100", [INSTA]))
    assert note == "evidencia en redes del local para 100% sin gluten (https://www.instagram.com/apto.libredegluten)"
    assert "libre de gluten" not in note and "«" not in note
    assert len(store) == 1


def test_an_unverified_snippet_from_a_web_page_is_not_quoted_either():
    note, _ = build_acceptance_note(entry("100", [BLOG]))
    assert note == "evidencia en la web para 100% sin gluten (https://blog.example/guia)" and "«" not in note


def test_the_evidence_rows_of_an_unverified_citation_say_so_in_their_text():
    _, store = build_acceptance_note(entry("100", [INSTA, OWN]))
    by_url = {s["url"]: s["text"] for s in store}
    assert by_url["https://tiempolibre.com.ar"] == OWN["text"]
    assert by_url["https://www.instagram.com/apto.libredegluten"].startswith("(sin verificar en la página) ")
    assert INSTA["text"] in by_url["https://www.instagram.com/apto.libredegluten"]
    assert all(len(text) <= 1000 for text in by_url.values())


def test_the_quote_in_the_public_note_never_exceeds_160_characters_and_stays_a_prefix_of_the_citation():
    long_quote = "Nuestra cocina es " + ("exclusiva y dedicada " * 20) + "sin gluten."
    note, _ = build_acceptance_note(entry(citations=[dict(OWN, text=long_quote)]))
    quoted = note.split("«", 1)[1].split("»", 1)[0]
    assert len(quoted) <= 160 and quoted.endswith("…")
    assert long_quote.startswith(quoted[:-1].rstrip())


def test_a_citation_that_ties_a_person_to_celiac_disease_refuses_the_note_verified_or_not():
    sick = "La dueña es celíaca y todo es sin gluten."
    assert build_acceptance_note(entry(citations=[dict(OWN, text=sick)])) is None
    assert build_acceptance_note(entry(citations=[dict(INSTA, text=sick)])) is None


def test_options_proposals_cite_a_verified_quote_and_have_no_signal_requirement():
    note, store = build_acceptance_note(entry("options", [OPT]))
    assert note == "evidencia pública para opciones sin TACC: «Tenemos opciones sin TACC.» (https://x.example)" and len(store) == 1


def test_an_unverified_options_citation_is_not_quoted():
    note, _ = build_acceptance_note(entry("options", [dict(OPT, verificacion="solo_snippet")]))
    assert note == "evidencia en la web para opciones sin TACC (https://x.example)"


def test_insuficiente_has_no_note():
    assert build_acceptance_note(entry("insuficiente", [])) is None


@pytest.mark.parametrize("bad", [None, {}, {"proposal": "100"}])
def test_a_malformed_entry_is_refused(bad):
    assert build_acceptance_note(bad) is None
