"""Attribution in the evidence finder, third round (pilot 2026-09-27, replayed on frozen sources):

A. the business name never makes a quote (nor an exclusivity claim): it is masked before gluten phrases are looked for;
B. whether a source is about the business is decided by the code, at source level; the model gets the context and can only VETO a quote;
D. a source is about the business when its title or URL holds every distinctive word of the name AND the city or region appears
   (or its URL is the place's own website / social profile): never by the name alone.
"""
from __future__ import annotations

import json

from agents.evidence_finder import SCOPE_RUBRIC, EvidenceFinder, extract_quotes, mask_name, match_reason, why_not_about_place

PID = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10"


def place(**kw):
    base = {"id": PID, "name": "Panadería Tiempo Libre", "city": "Rosario", "region": "Santa Fe", "country": "Argentina",
            "category": "cafe", "website": None, "social_url": None, "updated_at": "2026-09-20T10:00:00+00:00",
            "safety_level": "gluten_free_100"}
    base.update(kw)
    return base


def hit(url, snippet, title=""):
    return {"title": title, "link": url, "snippet": snippet}


class FakeTavily:
    def __init__(self, hits=None):
        self.hits = hits or []

    def search(self, query, num=10, include_domains=None):
        return self.hits if include_domains is None else []


class FakeLLM:
    """Answers "establecimiento, about this business" for every quote and remembers what it was sent."""

    def __init__(self, answer=None):
        self.answer, self.users, self.systems = answer, [], []

    def complete_json(self, system, user, model=None, max_tokens=1024):
        self.systems.append(system)
        self.users.append(json.loads(user))
        if self.answer is not None:
            return self.answer
        n = len(self.users[-1]["citas"])
        return {"citas": [{"n": i, "alcance": "establecimiento", "contradice_exclusividad": False,
                           "habla_de_este_negocio": True, "motivo": "ok"} for i in range(1, n + 1)]}


def finder(hits, llm=None, **kw):
    return EvidenceFinder(FakeTavily(hits), llm=llm, fetch_text=lambda url: "", **kw)


# --- A. the name is masked ----------------------------------------------------------------------------------------------------

def test_a_sentence_that_is_only_the_business_name_is_not_a_quote():
    assert extract_quotes("Concepción sin TACC", "Concepción sin TACC") == []
    assert extract_quotes("CONCEPCION SIN TACC.", "Concepción sin TACC") == []  # case and accents do not matter
    assert extract_quotes("# Vichenzo Sin Tacc Monserrat", "Vichenzo Sin Tacc Monserrat") == []
    assert extract_quotes("Vichenzo Sin Tacc Monserrat 1", "Vichenzo Sin Tacc Monserrat") == []


def test_without_a_name_the_extraction_is_what_it_was():
    assert extract_quotes("Concepción sin TACC") == ["Concepción sin TACC"]


def test_only_the_exact_name_is_masked_a_gluten_phrase_next_to_it_or_a_different_one_still_counts():
    name = "Concepción sin TACC"
    assert extract_quotes("Concepción sin TACC: todo es sin gluten.", name) == ["Concepción sin TACC: todo es sin gluten."]
    assert extract_quotes("Concepción sin gluten", name) == ["Concepción sin gluten"]  # not the exact name


def test_a_short_name_is_masked_only_as_a_whole_word_sequence():
    assert extract_quotes("Solar sin gluten", "Sol Sin Gluten") == ["Solar sin gluten"]
    assert extract_quotes("Sol sin gluten", "Sol Sin Gluten") == []


def test_the_window_of_a_long_sentence_is_centred_on_the_real_match_not_on_the_name():
    name = "Tiempo Libre sin gluten"
    text = name + " " + ("palabra " * 80) + "todo es sin gluten " + ("relleno " * 80) + "."
    (quote,) = extract_quotes(text, name)
    assert "todo es sin gluten" in quote and len(quote) <= 300


def test_mask_name_replaces_the_exact_occurrences_and_nothing_else():
    assert mask_name("Visitá Mundo 100% Sin Gluten, tenemos opciones sin TACC.", "Mundo 100% Sin Gluten") == \
        "Visitá [negocio], tenemos opciones sin TACC."
    assert mask_name("Nada que enmascarar.", "Mundo 100% Sin Gluten") == "Nada que enmascarar."
    assert mask_name("Texto", None) == "Texto"


def test_the_name_never_makes_a_quote_an_exclusivity_claim():
    p = place(name="Mundo 100% Sin Gluten")
    hits = [hit("https://blog.example/g", "Mundo 100% Sin Gluten en Rosario: tenemos opciones sin TACC.")]
    result = finder(hits, llm=FakeLLM()).find(p)
    (cite,) = result["citations"]
    assert cite["has_signal"] is False and result["proposal"] == "options"


# --- D. the source filter -------------------------------------------------------------------------------------------------------

MICHELA = place(name="Michela Sin Gluten Guaymallen", city="Mendoza", region="Mendoza")


def src(url, title="", text=""):
    return {"url": url, "title": title, "text": text}


def test_the_michela_profile_is_about_the_place_by_its_title_words_and_the_city():
    s = src("https://www.instagram.com/michela.singluten?hl=en", "MICHELA (@michela.singluten) · Guaymallén, Mendoza", "Panadería sin gluten")
    assert match_reason(MICHELA, s) == "title_tokens_and_place"


def test_the_same_profile_without_the_city_or_region_is_not_accepted_never_by_the_name_alone():
    s = src("https://www.instagram.com/michela.singluten?hl=en", "MICHELA (@michela.singluten) · Guaymallén, Argentina", "Panadería sin gluten")
    assert match_reason(MICHELA, s) is None
    assert why_not_about_place(MICHELA, s) == "el título tiene el nombre pero no menciona la ciudad ni la región"


def test_the_region_of_the_place_counts_as_much_as_its_city():
    p = place(name="Almacén Doña Rosa", city="Fraile Muerto", region="Cerro Largo")
    assert match_reason(p, src("https://blog.example/dona-rosa", "Doña Rosa | Cerro Largo", "productos sin gluten")) == "title_tokens_and_place"
    assert match_reason(p, src("https://blog.example/dona-rosa", "Doña Rosa", "un almacén de Fraile Muerto")) is not None  # the city, as before
    assert match_reason(p, src("https://blog.example/dona-rosa", "Doña Rosa", "un almacén de Salto")) is None  # neither


def test_all_the_distinctive_words_must_be_in_the_title_or_url_not_just_some_or_the_body():
    p = place(name="Serendipia Palermo Gluten Free", city="Buenos Aires", region="Ciudad Autónoma de Buenos Aires")
    # a namesake in the same city: shares one word, not the other
    assert match_reason(p, src("https://cea.example", "Serendipia - CEA", "Centro de estudios en Buenos Aires")) is None
    # the words are in the body only: that is the old name-and-city rule's job, and it needs the whole name
    assert match_reason(p, src("https://blog.example/x", "Guía", "serendipia y palermo, Buenos Aires")) is None


def test_a_namesake_in_another_city_is_not_the_place():
    p = place(name="Serendipia Sin Gluten", city="Melo", region="Cerro Largo")
    assert match_reason(p, src("https://cea.example", "Serendipia - CEA", "Centro de estudios en Rocha")) is None


def test_a_same_city_namesake_passes_the_source_filter_and_only_the_models_veto_stands_between_it_and_a_citation():
    p = place(name="Serendipia Sin Gluten", city="Melo", region="Cerro Largo")
    hits = [hit("https://cea.example/x", "Todo es sin gluten en nuestro comedor de Melo.", "Serendipia - CEA")]
    assert match_reason(p, src(hits[0]["link"], hits[0]["title"], hits[0]["snippet"])) == "title_tokens_and_place"
    veto = {"citas": [{"n": 1, "alcance": "irrelevante", "contradice_exclusividad": False, "habla_de_este_negocio": False,
                       "motivo": "Habla de otro lugar: Serendipia - CEA."}]}
    result = finder(hits, llm=FakeLLM(veto)).find(p)
    assert result["proposal"] == "insuficiente" and result["citations"] == []
    assert result["dropped_by_model"][0]["motivo"] == "Habla de otro lugar: Serendipia - CEA."


def test_a_generic_name_still_matches_only_through_its_own_url():
    p = place(name="Sin Gluten", city="Rosario", website="https://singluten.com.ar")
    assert match_reason(p, src("https://blog.example/x", "Sin Gluten Rosario", "Rosario")) is None
    assert match_reason(p, src("https://singluten.com.ar/menu")) == "own_url"


# --- D. a name made only of place words identifies nothing (replay on frozen sources: "Concepción sin TACC" vs "Quinta Gluten Free") ---

CONCEPCION = place(name="Concepción sin TACC", city="Concepción del Uruguay", region="Entre Ríos",
                   address="Blvd. los Constituyentes 39, Concepción del Uruguay, Entre Ríos, Argentina",
                   social_url="https://instagram.com/panaderia.sintacc")
QUINTA_REEL = ("https://www.instagram.com/reel/C_X5QD1RJAg", "¡Descubrí la primera cocina libre de gluten en Concepción ...",
               "¡Descubrí la primera cocina libre de gluten en Concepción del Uruguay! En Quinta Gluten Free te invitamos. "
               "Un desayuno elaborado en nuestra cocina 100% libre de gluten.")


def test_a_name_made_only_of_place_words_matches_only_through_its_full_name_and_city_or_its_own_url():
    other = src(*QUINTA_REEL)
    assert match_reason(CONCEPCION, other) is None
    assert why_not_about_place(CONCEPCION, other) ==         "el nombre solo tiene palabras genéricas o de lugar: hace falta el nombre completo con la ciudad, o la URL propia"
    assert match_reason(CONCEPCION, src("https://blog.example/x", "Concepción sin TACC",
                                        "Concepción sin TACC, panadería en Concepción del Uruguay")) == "name_and_city"
    assert match_reason(CONCEPCION, src("https://instagram.com/panaderia.sintacc/reel/1")) == "own_url"


def test_a_barrio_in_the_address_is_a_place_word_too():
    p = place(name="Sin Gluten Palermo", city="Buenos Aires", region="Ciudad Autónoma de Buenos Aires",
              address="Av. Santa Fe 3000, Palermo, Buenos Aires")
    assert match_reason(p, src("https://blog.example/otro", "Celíacos en Palermo", "Palermo, Buenos Aires: locales sin gluten")) is None


def test_a_locality_word_of_the_name_still_counts_when_the_name_has_a_word_of_identity():
    p = place(name="Michela Sin Gluten Guaymallen", city="Mendoza", region="Mendoza", address="Calle Falsa 123, Guaymallén, Mendoza")
    s = src("https://www.instagram.com/michela.singluten?hl=en", "MICHELA (@michela.singluten) · Guaymallén, Mendoza", "Panadería")
    assert match_reason(p, s) == "title_tokens_and_place"


def test_the_finder_does_not_cite_another_business_of_the_same_city_for_a_name_of_place_words():
    hits = [hit(QUINTA_REEL[0], QUINTA_REEL[2], QUINTA_REEL[1])]
    llm = FakeLLM()
    result = finder(hits, llm=llm).find(CONCEPCION)
    assert result["proposal"] == "insuficiente" and result["citations"] == [] and llm.users == []


def test_the_prompt_asks_the_model_to_veto_when_the_neighbouring_sentences_name_another_business():
    rubric = " ".join(SCOPE_RUBRIC.split())
    assert "pertenece a OTRO negocio" in rubric


# --- B. the code attributes, the model can only veto -----------------------------------------------------------------------------

def test_a_quote_from_a_source_the_code_rejected_cannot_support_a_100_whatever_the_model_says():
    hits = [hit("https://blog.example/otra", "Una panadería de Mendoza: todo es sin gluten, cocina exclusiva.")]
    llm = FakeLLM()
    result = finder(hits, llm=llm).find(place())
    assert result["proposal"] == "insuficiente" and result["citations"] == [] and llm.users == []  # the model was never even asked


def test_the_model_only_sees_quotes_of_the_sources_the_code_accepted():
    hits = [hit("https://blog.example/guia", "Panadería Tiempo Libre en Rosario: todo es sin gluten."),
            hit("https://blog.example/otra", "Una panadería de Mendoza: todos sus panes son sin gluten.")]
    llm = FakeLLM()
    finder(hits, llm=llm).find(place())
    sent = json.dumps(llm.users[0], ensure_ascii=False)
    assert "todo es sin gluten" in sent and "Mendoza" not in sent


def test_the_model_cannot_add_a_quote_it_can_only_veto_the_ones_it_was_sent():
    answer = {"citas": [{"n": 1, "alcance": "establecimiento", "contradice_exclusividad": False, "habla_de_este_negocio": True, "motivo": "ok"},
                        {"n": 2, "alcance": "establecimiento", "contradice_exclusividad": False, "habla_de_este_negocio": True, "motivo": "inventada"},
                        {"n": 99, "alcance": "establecimiento", "contradice_exclusividad": False, "habla_de_este_negocio": True, "motivo": "inventada"}]}
    hits = [hit("https://blog.example/guia", "Panadería Tiempo Libre en Rosario: todo es sin gluten.")]
    result = finder(hits, llm=FakeLLM(answer)).find(place())
    assert len(result["citations"]) == 1 and all(c["motivo"] != "inventada" for c in result["citations"])


def test_a_statement_that_does_not_repeat_the_name_still_counts_when_its_source_was_accepted():
    hits = [hit("https://www.celimap.com.ar/lugar/tiempo-libre", "Panadería Tiempo Libre - Rosario. Clasificado 100% Sin TACC.")]
    result = finder(hits, llm=FakeLLM()).find(place())
    assert [c["text"] for c in result["citations"]] == ["Clasificado 100% Sin TACC."]
    assert result["proposal"] == "100"


def test_the_model_receives_the_neighbouring_sentences_the_page_title_and_the_source_type():
    hits = [hit("https://blog.example/guia", "Panadería Tiempo Libre en Rosario. Todo es sin gluten. Abrimos de lunes a sábado.", "Guía celíaca de Rosario")]
    llm = FakeLLM()
    finder(hits, llm=llm).find(place())
    (cite,) = llm.users[0]["citas"]
    assert cite["texto"] == "Todo es sin gluten."
    assert cite["antes"] == "Panadería Tiempo Libre en Rosario." and cite["despues"] == "Abrimos de lunes a sábado."
    assert cite["fuente"] == {"tipo": "tercero", "titulo": "Guía celíaca de Rosario"}
    assert "url" not in json.dumps(cite).lower()  # the model never sees an address: nothing to recognise the business by


def test_the_prompt_says_the_pages_were_already_verified_and_that_the_model_may_only_veto():
    rubric = " ".join(SCOPE_RUBRIC.split())
    assert "YA verificó" in rubric and "Solo podés VETAR" in rubric
    assert "OTRO lugar" in rubric and "Nunca aceptes" in rubric
