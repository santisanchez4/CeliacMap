"""Attribution on multi-business pages (guides, blogs, listicles), fourth round (Montevideo run 2026-09-27):

"Un Lugar Sin Gluten" was proposed as 100 with a sentence that, on the guide it came from, belongs to ANOTHER restaurant (the previous entry of the list).
E1. a page matched to the business only by its text (its title does not name it) supports a quote only if the quote is in the same sentence as the
    name or up to ~400 characters after it;
E2. a page that lists several businesses never supports a "100" on its own: at most "100 · verificar en la fuente", which is not accepted in bulk;
E3. the "posible 100" alert recognises "dedicado 100% a comidas sin gluten" (has_exclusive_signal is not touched: it is the Validator's gate).
"""
from __future__ import annotations

import json

from agents.evidence_finder import (
    EvidenceFinder,
    assess,
    build_acceptance_note,
    has_extended_signal,
    looks_like_multi_business,
    needs_source_check,
    verification_label,
)
from agents.validator_agent import ValidatorAgent

PID = "fa317252-5123-4eb1-a60e-c7e5b79bff7d"
UNLUGAR = {"id": PID, "name": "Un Lugar Sin Gluten", "city": "Montevideo", "region": "Montevideo", "country": "Uruguay", "category": "restaurant",
           "address": "Dr. Duvimioso Terra 2148, 11800 Montevideo, Departamento de Montevideo, Uruguay", "website": None, "social_url": None,
           "updated_at": "2026-09-25T03:48:44+00:00", "safety_level": "gluten_free_100"}
URL = "https://www.superprof.uy/blog/restaurantes-sin-gluten-montevideo"
GUIDE_TITLE = "Restaurantes sin gluten en Montevideo: guía para celíacos y opciones gluten free"
CHOCARA = "Aquí la seguridad es totalmente garantizada, ya que toda su cocina es 100% libre de gluten."
OWN_SENTENCE = '"Un Lugar Sin Gluten" es un restaurante y cafetería ubicado en Montevideo, dedicado 100% a comidas sin gluten.'
GUIDE = (
    "Restaurantes para celíacos en Montevideo: Chocará, Un Lugar Sin Gluten, Dalbertt, La Commedia Trattoria. "
    "Aquí no encontrarás una simple lista sino una selección de joyas. " + "Relleno de la guía sobre cocina y clases. " * 20
    + "Si hay un lugar que grita sin gluten y delicioso en Montevideo, ese es Chocará. " + CHOCARA + " "
    + "Más relleno sobre Chocará y su menú. " * 6
    + "Un Lugar Sin Gluten a veces el mejor nombre es el que va directo al grano. " + OWN_SENTENCE + " Horario de lunes a sábado."
)


class FakeTavily:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query, num=10, include_domains=None):
        return self.hits if include_domains is None else []


class FakeLLM:
    """Answers "establecimiento, about this business" for every quote it is sent."""

    def complete_json(self, system, user, model=None, max_tokens=1024):
        n = len(json.loads(user)["citas"])
        return {"citas": [{"n": i, "alcance": "establecimiento", "contradice_exclusividad": False,
                           "habla_de_este_negocio": True, "motivo": "ok"} for i in range(1, n + 1)]}


def hit(url, snippet, title=""):
    return {"title": title, "link": url, "snippet": snippet}


def run(snippet, title=GUIDE_TITLE, page=None, place=UNLUGAR, url=URL):
    fetch = (lambda u: page if u == url else "") if page is not None else (lambda u: "")
    return EvidenceFinder(FakeTavily([hit(url, snippet, title)]), llm=FakeLLM(), fetch_text=fetch).find(place)


# --- E1. proximity to the name on a page matched only by its text ---------------------------------------------------------------

def test_a_quote_far_from_the_name_on_a_page_matched_only_by_text_is_dropped_and_the_one_in_its_own_section_is_kept():
    result = run(GUIDE, page=GUIDE)
    texts = [c["text"] for c in result["citations"]]
    assert not any("seguridad es totalmente garantizada" in t for t in texts)
    assert any("dedicado 100% a comidas sin gluten" in t for t in texts)
    assert result["stats"]["quotes_dropped_far_from_name"] >= 1


def test_the_quote_that_contains_the_name_is_near_it_by_definition():
    (cite,) = [c for c in run(GUIDE, page=GUIDE)["citations"] if "dedicado 100%" in c["text"]]
    assert "Un Lugar Sin Gluten" in cite["text"]


def test_a_quote_up_to_400_characters_after_the_name_is_kept_and_further_away_is_not():
    near = "Un Lugar Sin Gluten. " + "Nada. " * 33 + "Todo es sin gluten."       # ~200 characters after the name
    far = "Un Lugar Sin Gluten. " + "Nada. " * 90 + "Todo es sin gluten."        # ~540 characters after the name
    assert [c["text"] for c in run(near, title="Guía celíaca de Montevideo")["citations"]] == ["Todo es sin gluten."]
    assert run(far, title="Guía celíaca de Montevideo")["citations"] == []


def test_a_page_whose_title_names_the_business_is_a_page_about_it_and_needs_no_proximity():
    text = "Un Lugar Sin Gluten en Montevideo. " + "Nada. " * 100 + "Toda su cocina es 100% libre de gluten."
    result = run(text, title="Un Lugar Sin Gluten | Restaurante en Montevideo")
    assert [c["text"] for c in result["citations"]] == ["Toda su cocina es 100% libre de gluten."]


def test_the_places_own_pages_need_no_proximity():
    p = dict(UNLUGAR, website="https://unlugarsingluten.uy")
    text = "Nuestra historia. " + "Nada. " * 100 + "Toda nuestra cocina es 100% libre de gluten."
    result = run(text, title="Inicio", place=p, url="https://unlugarsingluten.uy/nosotros")
    assert [c["text"] for c in result["citations"]] == ["Toda nuestra cocina es 100% libre de gluten."]


# --- E2. a guide never supports a 100 by itself -----------------------------------------------------------------------------------

def test_multi_business_pages_are_recognised_by_their_title_url_or_numbered_headings():
    assert looks_like_multi_business(GUIDE_TITLE, URL, "")
    assert looks_like_multi_business("Los mejores lugares sin gluten", "https://x.example/a", "")
    assert looks_like_multi_business("Inicio", "https://x.example/blog/algo", "")
    assert looks_like_multi_business("Inicio", "https://x.example/a", "Índice\n1 Chocará\n2 Un Lugar Sin Gluten\n3 Dalbertt\n4 Otro")
    assert not looks_like_multi_business("Matilde Gluten Free | Restaurante en San Pedro", "https://www.celimap.com.ar/lugar/matilde", "")
    assert not looks_like_multi_business("Menu - Selkkis | Comida Gluten free apta celíacos - Cordón", "https://selkkis.reorder.io", "")
    assert not looks_like_multi_business("Instagram", "https://www.instagram.com/reel/abc", "")


def test_the_name_of_the_place_does_not_make_its_own_page_a_guide():
    assert not looks_like_multi_business("Restaurantes Sin Gluten | Inicio", "https://x.example/", "", name="Restaurantes Sin Gluten")


def test_a_100_that_rests_only_on_a_guide_is_100_verificar_en_la_fuente_never_a_plain_100():
    snippet = "Un Lugar Sin Gluten: toda su cocina es 100% libre de gluten."
    result = run(snippet, page=snippet)
    (cite,) = result["citations"]
    assert cite["verificacion"] == "verificada" and cite["multi_negocio"] is True
    assert result["proposal"] == "100" and result["verify_in_source"] is True
    assert any("guía" in r for r in result["reasons"])


def test_the_same_quote_from_a_page_about_the_business_alone_is_a_plain_100():
    snippet = "Un Lugar Sin Gluten: toda su cocina es 100% libre de gluten."
    result = run(snippet, title="Un Lugar Sin Gluten | Restaurante en Montevideo", url="https://celimap.example/lugar/un-lugar-sin-gluten",
                 page=snippet)
    assert result["citations"][0]["multi_negocio"] is False
    assert result["proposal"] == "100" and result["verify_in_source"] is False


def test_the_places_own_site_is_never_a_guide_even_with_a_blog_in_its_address():
    p = dict(UNLUGAR, website="https://unlugarsingluten.uy")
    snippet = "Toda nuestra cocina es 100% libre de gluten."
    result = run(snippet, title="Blog", place=p, url="https://unlugarsingluten.uy/blog/cocina", page=snippet)
    assert result["citations"][0]["multi_negocio"] is False and result["verify_in_source"] is False


def _guide_cite(**kw):
    c = {"text": "Toda su cocina es 100% libre de gluten.", "url": URL, "source_kind": "tercero", "has_signal": True,
         "alcance": "establecimiento", "contradice": False, "verificacion": "verificada", "multi_negocio": True}
    c.update(kw)
    return c


def test_a_verified_quote_from_a_guide_does_not_lift_the_source_check_but_one_from_a_single_page_does():
    assert needs_source_check({"proposal": "100", "citations": [_guide_cite()]}) is True
    single = _guide_cite(url="https://x.example/solo", multi_negocio=False)
    assert needs_source_check({"proposal": "100", "citations": [_guide_cite(), single]}) is False
    assert assess([_guide_cite()])["verify_in_source"] is True


def test_a_guide_quote_is_never_quoted_in_the_public_note_and_its_evidence_row_says_so():
    note, store = build_acceptance_note({"proposal": "100", "citations": [_guide_cite()]})
    assert note == f"evidencia en la web para 100% sin gluten ({URL})" and "«" not in note
    assert store[0]["text"].startswith("(guía con varios negocios: sin atribución confirmada) ")


def test_a_quote_from_a_single_page_wins_the_note_over_a_guide_quote():
    single = _guide_cite(text="Somos 100% sin gluten.", url="https://x.example/solo", multi_negocio=False)
    note, _ = build_acceptance_note({"proposal": "100", "citations": [_guide_cite(), single]})
    assert "«Somos 100% sin gluten.»" in note and "https://x.example/solo" in note


def test_the_verification_label_names_the_guide():
    assert verification_label({"verificacion": "verificada", "multi_negocio": True}) == "verificada en la página · guía de varios negocios"
    assert verification_label({"verificacion": "verificada"}) == "verificada en la página"


# --- E3. the possible-100 alert -----------------------------------------------------------------------------------------------------

def test_the_alert_recognises_dedicated_phrases_and_the_validators_regex_is_untouched():
    phrase = "Un restaurante y cafetería ubicado en Montevideo, dedicado 100% a comidas sin gluten."
    assert has_extended_signal(phrase) is True
    assert ValidatorAgent.has_exclusive_signal([phrase]) is False
    assert has_extended_signal("Un local dedicado a productos sin gluten") is True
    assert has_extended_signal("100% dedicado a comidas sin gluten") is True
    assert has_extended_signal("dedicada exclusivamente a la elaboración de panificados sin gluten") is True


def test_the_alert_does_not_fire_on_options_or_on_a_negation():
    assert has_extended_signal("Dedicado a opciones sin gluten y con gluten") is False
    assert has_extended_signal("No está dedicado 100% a comidas sin gluten") is False
    assert has_extended_signal("Ofrece platos dedicados a los cumpleaños") is False


def test_the_guide_page_after_the_fix_lands_in_options_with_a_possible_100_backed_by_the_right_quote():
    result = run(GUIDE, page=GUIDE)
    assert result["proposal"] == "options" and result["possible_100"] is True
    assert "dedicado 100% a comidas sin gluten" in result["possible_100_quote"]["text"]
    assert result["possible_100_quote"]["url"] == URL
