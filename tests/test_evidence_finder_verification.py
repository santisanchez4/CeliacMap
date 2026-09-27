"""Evidence finder, second round (pilot 2026-09-27): quotes are verified against their page and labelled; a possible 100 is flagged but never
proposed; Instagram alt-text is not a quote; the model's reason for a veto is kept with the quote that caused it; discarded sources and
Haiku tokens are reported.
"""
from __future__ import annotations

from agents.evidence_finder import (
    EvidenceFinder,
    assess,
    extract_quotes,
    has_extended_signal,
    proposal_label,
    summarize,
)
from agents.validator_agent import ValidatorAgent

PID = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10"
SNIPPET = "Panadería Tiempo Libre en Rosario: todo es sin gluten, cocina exclusiva."


def place(**kw):
    base = {"id": PID, "name": "Panadería Tiempo Libre", "city": "Rosario", "country": "Argentina", "category": "cafe",
            "website": None, "social_url": None, "updated_at": "2026-09-20T10:00:00+00:00", "safety_level": "gluten_free_100"}
    base.update(kw)
    return base


def hit(url, snippet, title=""):
    return {"title": title, "link": url, "snippet": snippet}


class FakeTavily:
    def __init__(self, table=None):
        self.table, self.calls = table or {}, []

    def search(self, query, num=10, include_domains=None):
        key = tuple(include_domains) if include_domains else None
        self.calls.append((query, key))
        return self.table.get(key, [])


class FakeLLM:
    def __init__(self, answer=None, usage=None):
        self.answer, self.usage, self.calls = answer, usage, 0

    def complete_json(self, system, user, model=None, max_tokens=1024):
        self.calls += 1
        if self.usage:
            self.last_usage = dict(self.usage)
        return self.answer


def scope(n=1, alcance="establecimiento", contradice=False, habla=True, motivo=""):
    return {"citas": [{"n": n, "alcance": alcance, "contradice_exclusividad": contradice,
                       "habla_de_este_negocio": habla, "motivo": motivo}]}


def finder(tavily=None, llm=None, fetch_text=lambda url: "", **kw):
    return EvidenceFinder(tavily or FakeTavily({None: [hit("https://blog.example/guia", SNIPPET)]}), llm=llm, fetch_text=fetch_text, **kw)


def q(text="Todo es sin gluten.", signal=True, alcance="establecimiento", contradice=False, kind="propia",
      verificacion="verificada", motivo="", url="https://x.example/p"):
    return {"text": text, "url": url, "source_kind": kind, "matched_by": "own_url", "has_signal": signal,
            "alcance": alcance, "contradice": contradice, "verificacion": verificacion, "motivo": motivo}


# --- Instagram / Facebook boilerplate ---------------------------------------------------------------------------------------

def test_instagram_and_facebook_auto_alt_text_is_not_a_quote():
    text = ("May be an image of cake, tart, pie and text that says 'SIN LACTOSA SIN AZUCAR SIN GLUTEN'. "
            "Image may contain: food, text that says sin tacc. Puede ser una imagen de pan y texto que dice 'sin gluten'. "
            "No photo description available. Todo es sin gluten.")
    assert extract_quotes(text) == ["Todo es sin gluten."]


# --- the extended exclusivity signal (report only) --------------------------------------------------------------------------

def test_the_extended_signal_recognises_exclusivity_phrases_the_validator_regex_misses():
    text = "Panadería y Confitería exclusivamente para celíacos."
    assert has_extended_signal(text) is True
    assert ValidatorAgent.has_exclusive_signal([text]) is False  # the gap the pilot found; the Validator's gate is not changed here
    assert has_extended_signal("Un local solo para celíacos") is True
    assert has_extended_signal("Vichenzo, una vida sin Gluten") is False
    assert has_extended_signal("Tenemos opciones sin TACC para celíacos") is False
    assert has_extended_signal("Menú para celíacos") is False


# --- assess: proposal + source check + possible 100 + vetoes ----------------------------------------------------------------

def test_a_100_backed_by_a_verified_exclusivity_quote_needs_no_source_check():
    a = assess([q()])
    assert a["proposal"] == "100" and a["verify_in_source"] is False and a["possible_100"] is False and a["vetoes"] == []


def test_a_100_resting_only_on_a_snippet_or_a_social_profile_is_100_verificar_en_la_fuente():
    for verificacion in ("solo_snippet", "no_verificable"):
        a = assess([q(verificacion=verificacion)])
        assert a["proposal"] == "100" and a["verify_in_source"] is True


def test_a_possible_100_is_flagged_but_never_proposed():
    quote = q(text="Panadería y Confitería exclusivamente para celíacos.", signal=False, kind="tercero",
              verificacion="no_verificable", url="https://www.facebook.com/x")
    a = assess([quote])
    assert a["proposal"] == "options" and a["possible_100"] is True
    assert a["possible_100_quote"] == {"text": quote["text"], "url": "https://www.facebook.com/x"}


def test_there_is_no_possible_100_when_the_quote_is_scoped_to_a_line_or_contradicted():
    phrase = "Confitería exclusivamente para celíacos."
    assert assess([q(text=phrase, signal=False, alcance="producto_o_linea")])["possible_100"] is False
    assert assess([q(text=phrase, signal=False, contradice=True)])["possible_100"] is False
    assert assess([q(text=phrase, signal=False, alcance="desconocido")])["possible_100"] is False


def test_a_vetoed_signal_carries_the_models_reason_and_the_quote_that_caused_it():
    a = assess([q(text="Somos 100% sin gluten.", alcance="producto_o_linea", motivo="Habla solo de las tortas.", url="https://a.example/1")])
    assert a["proposal"] == "options"
    assert a["vetoes"] == [{"tipo": "alcance", "cita": 1, "texto": "Somos 100% sin gluten.", "url": "https://a.example/1",
                            "motivo_modelo": "Habla solo de las tortas."}]


def test_a_contradicting_or_hedging_quote_is_a_veto_with_its_reason():
    quotes = [q(), q(text="También hacemos con gluten.", signal=False, contradice=True, motivo="Dice que también cocina con gluten."),
              q(text="Tienen opciones sin gluten.", signal=False, alcance="opciones", motivo="Habla de opciones.")]
    a = assess(quotes)
    assert a["proposal"] == "options"
    assert [(v["tipo"], v["cita"], v["motivo_modelo"]) for v in a["vetoes"]] == [
        ("contradice", 2, "Dice que también cocina con gluten."), ("opciones", 3, "Habla de opciones.")]


def test_without_the_models_reading_or_without_a_signal_there_is_no_veto_to_report():
    assert assess([q(alcance="desconocido")])["vetoes"] == []
    assert assess([q(text="Tienen opciones sin gluten.", signal=False, alcance="opciones")])["vetoes"] == []


def test_proposal_labels():
    assert proposal_label({"proposal": "100", "verify_in_source": False}) == "100"
    assert proposal_label({"proposal": "100", "verify_in_source": True}) == "100 · verificar en la fuente"
    assert proposal_label({"proposal": "options", "possible_100": True}) == "options · posible 100"
    assert proposal_label({"proposal": "options"}) == "options"
    assert proposal_label({"proposal": "insuficiente"}) == "insuficiente"


# --- verification against the page --------------------------------------------------------------------------------------------

def test_a_quote_found_verbatim_on_its_page_is_verified():
    fetch = lambda url: ("Bienvenidos. " + SNIPPET + " Abrimos de lunes a sábado.") if url == "https://blog.example/guia" else ""  # noqa: E731
    result = finder(llm=FakeLLM(scope()), fetch_text=fetch).find(place())
    assert result["citations"][0]["verificacion"] == "verificada"
    assert result["proposal"] == "100" and result["verify_in_source"] is False


def test_a_quote_the_page_does_not_contain_stays_a_snippet():
    result = finder(llm=FakeLLM(scope()), fetch_text=lambda url: "Otra cosa por completo.").find(place())
    assert result["citations"][0]["verificacion"] == "solo_snippet" and result["verify_in_source"] is True


def test_a_page_that_cannot_be_downloaded_leaves_the_quote_a_snippet():
    result = finder(llm=FakeLLM(scope()), fetch_text=lambda url: "").find(place())
    assert result["citations"][0]["verificacion"] == "solo_snippet"


def test_a_social_snippet_is_not_verifiable_and_its_page_is_never_downloaded():
    tavily = FakeTavily({("instagram.com", "facebook.com"): [hit("https://www.instagram.com/reel/abc", "Panadería Tiempo Libre en Rosario. 100% sin gluten.")]})
    fetched = []

    def fetch(url):
        fetched.append(url)
        return ""

    result = finder(tavily=tavily, llm=FakeLLM(scope()), fetch_text=fetch).find(place())
    assert result["citations"][0]["verificacion"] == "no_verificable" and fetched == []
    assert result["proposal"] == "100" and result["verify_in_source"] is True


def test_the_own_website_text_is_verified_by_construction_and_each_page_is_downloaded_once():
    fetched = []

    def fetch(url):
        fetched.append(url)
        return "Bienvenidos. Somos una panadería 100% sin gluten desde 2015. Todo es sin gluten."

    tavily = FakeTavily({None: [hit("https://blog.example/guia", "Panadería Tiempo Libre en Rosario. Todo es sin gluten. También hacemos opciones sin TACC.")]})
    result = finder(tavily=tavily, llm=None, fetch_text=fetch).find(place(website="https://tiempolibre.com.ar"))
    kinds = {c["url"]: c["verificacion"] for c in result["citations"]}
    assert kinds["https://tiempolibre.com.ar"] == "verificada"
    assert fetched.count("https://blog.example/guia") == 1 and fetched.count("https://tiempolibre.com.ar") == 1


# --- the model's reason, kept ---------------------------------------------------------------------------------------------------

def test_the_result_carries_the_models_reason_for_a_veto_and_the_quote_that_caused_it():
    result = finder(llm=FakeLLM(scope(alcance="producto_o_linea", motivo="Habla solo de la línea de tortas."))).find(place())
    assert result["proposal"] == "options"
    (veto,) = result["vetoes"]
    assert (veto["tipo"], veto["cita"], veto["motivo_modelo"]) == ("alcance", 1, "Habla solo de la línea de tortas.")
    assert veto["url"] == "https://blog.example/guia" and veto["texto"] == result["citations"][0]["text"]
    assert result["citations"][0]["motivo"] == "Habla solo de la línea de tortas."


def test_quotes_the_model_drops_are_kept_with_its_reason():
    result = finder(llm=FakeLLM(scope(alcance="irrelevante", motivo="Es una guía genérica."))).find(place())
    assert result["citations"] == [] and result["proposal"] == "insuficiente"
    (dropped,) = result["dropped_by_model"]
    assert dropped["motivo"] == "Es una guía genérica." and dropped["url"] == "https://blog.example/guia" and "todo es sin gluten" in dropped["text"].lower()


# --- discarded sources of an insuficiente ------------------------------------------------------------------------------------------

def test_an_insuficiente_lists_the_sources_it_discarded_and_why():
    tavily = FakeTavily({None: [hit("https://blog.example/otra", "Una panadería de Mendoza con tortas sin gluten.", "Guía Mendoza"),
                                hit("https://blog.example/rosario", "Panadería sin gluten en Rosario, rica.")]})
    result = finder(tavily=tavily, llm=FakeLLM(scope())).find(place())
    assert result["proposal"] == "insuficiente"
    why = {s["url"]: s["why"] for s in result["discarded_sources"]}
    assert why["https://blog.example/otra"] == "no menciona ni el nombre ni la ciudad"
    assert why["https://blog.example/rosario"] == "no menciona el nombre"
    assert {"url", "title", "why"} <= set(result["discarded_sources"][0])


def test_a_source_about_the_place_without_gluten_sentences_is_listed_too():
    tavily = FakeTavily({None: [hit("https://blog.example/x", "Panadería Tiempo Libre en Rosario. Abrimos de lunes a sábado.")]})
    result = finder(tavily=tavily).find(place())
    assert result["discarded_sources"][0]["why"] == "sobre el negocio, pero sin frases sobre gluten o celíacos"


def test_a_place_with_a_proposal_carries_no_discarded_sources():
    assert finder(llm=FakeLLM(scope())).find(place())["discarded_sources"] == []


def test_a_generic_name_says_only_its_own_url_can_match():
    tavily = FakeTavily({None: [hit("https://blog.example/x", "Sin Gluten en Rosario, todo sin gluten.")]})
    result = finder(tavily=tavily).find(place(name="Sin Gluten"))
    assert result["discarded_sources"][0]["why"] == "nombre genérico: solo vale la URL propia"


# --- Haiku tokens ------------------------------------------------------------------------------------------------------------------------

def test_haiku_tokens_are_counted_per_place_and_in_total():
    f = finder(llm=FakeLLM(scope(), usage={"input": 120, "output": 30}))
    first = f.find(place())
    assert first["stats"]["llm_tokens"] == {"input": 120, "output": 30}
    f.find(place(id="other"))
    assert f.llm_tokens == {"input": 240, "output": 60}


def test_a_place_without_quotes_makes_no_model_call_and_a_model_without_usage_counts_zero():
    llm = FakeLLM(scope(), usage={"input": 120, "output": 30})
    f = finder(tavily=FakeTavily(), llm=llm)
    assert f.find(place())["stats"]["llm_tokens"] == {"input": 0, "output": 0} and llm.calls == 0
    quiet = finder(llm=FakeLLM(scope()))
    assert quiet.find(place())["stats"]["llm_tokens"] == {"input": 0, "output": 0}


# --- summary ---------------------------------------------------------------------------------------------------------------------------------

def test_summarize_counts_the_source_check_possible_100_and_vetoes():
    def row(proposal, verify=False, possible=False, vetoes=(), link="nada"):
        return {"proposal": proposal, "verify_in_source": verify, "possible_100": possible, "vetoes": list(vetoes),
                "link_kind": link, "stats": {"searches": 2}, "citations": []}

    rows = [row("100"), row("100", verify=True), row("options", possible=True), row("options", vetoes=[{"tipo": "alcance"}]), row("insuficiente")]
    s = summarize(rows)
    assert s["por_propuesta"] == {"100": 2, "options": 2, "insuficiente": 1}
    assert s["cien_verificar_en_la_fuente"] == 1 and s["posible_100"] == 1 and s["con_veto_del_modelo"] == 1
