"""Evidence finder for the admin-pending "100%" queue (docs/runbooks/evidence-finder.md).

For a place the admin has not yet confirmed as "Espacio 100% sin gluten", look for PUBLIC evidence about that business
(its own site, Instagram / Facebook, ACELU / ACELA / ACA, other pages) and propose ``"100"``, ``"options"`` or
``"insuficiente"`` with the quotes that back it. The admin decides; nothing here changes a place.

What makes it safe, by construction rather than by prompt:

* The finder receives no database (see ``EvidenceFinder.__init__``): it cannot write anything.
* A quote is a literal sentence of text this code retrieved, with the URL this code got. The model never writes one. Each quote is
  then checked against the page itself when the page can be downloaded (``verificacion``): a search snippet is not always literal on
  the page, and Instagram / Facebook cannot be downloaded at all.
* A source counts only if it is about THAT business (name and city, or the place's own URL). The model's own knowledge of
  a business is never an input: it sees numbered quotes and nothing else.
* Sentences that tie a person (an owner) to celiac disease are dropped before anything else sees them (ADR-007).
* The model can only take a place OUT of "100": it needs an explicit exclusivity phrase (``has_exclusive_signal``) plus a
  scope of "the whole establishment" from the model, and any contradicting quote blocks it. A "100" that rests only on snippets or
  social profiles is "100 · verificar en la fuente": the admin opens the link before accepting it.
* "insuficiente" never proposes to discard anything.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

from agents.clients.website_scraper import fetch_page_text, is_social_url
from agents.validator_agent import _OWNER_HEALTH_RE, ValidatorAgent

logger = logging.getLogger("celiacmap.agent")

ASSOCIATION_DOMAINS = ("acelu.org", "acela.org.ar", "celiaco.org.ar")
SOCIAL_SEARCH_DOMAINS = ("instagram.com", "facebook.com")
PROPOSALS = ("100", "options", "insuficiente")
LINK_KINDS = ("website", "red social", "nada")
SCOPES = ("establecimiento", "producto_o_linea", "opciones", "irrelevante")
VERIFICATIONS = ("verificada", "solo_snippet", "no_verificable")
VERIFICATION_LABELS = {
    "verificada": "verificada en la página",
    "solo_snippet": "solo snippet",
    "no_verificable": "red social: no verificable",
}
UNVERIFIED_ROW_PREFIX = "(sin verificar en la página) "

RESULTS_PER_QUERY = 5
QUOTE_MAX = 300  # characters of one stored quote
NOTE_QUOTE_MAX = 160  # characters of the quote in the public validation_notes
REASON_MAX = 240  # characters of the model's reason kept per quote
CONTEXT_MAX = 200  # characters of each neighbouring sentence the model gets as context
MAX_CANDIDATE_QUOTES = 8  # quotes one place sends to the model
MAX_STORED_EVIDENCE = 5  # place_evidence rows one acceptance writes (the Validator reads five)
MAX_DISCARDED_SOURCES = 10
HAIKU_USD_PER_MTOK = (1.0, 5.0)  # (input, output): the price the cost estimate uses

# Words of a business name that say what it sells, not which business it is.
GENERIC_WORDS = frozenset(
    "sin gluten tacc celiaco celiacos celiaca free libre gf sg panaderia pasteleria cafe cafeteria restaurante resto "
    "restobar bar dietetica almacen tienda casa vegano vegana natural saludable food foods market shop bakery "
    "de del la el los las y e en the and para con".split()
)

# What the model returns when it was not asked, failed, or left a quote out: never a route to "100".
UNKNOWN_SCOPE = {"alcance": "desconocido", "contradice": True, "habla": False, "motivo": ""}
UNCLASSIFIED = {"alcance": "desconocido", "contradice": False, "habla": True, "motivo": ""}

SCOPE_RUBRIC = """\
Eres el clasificador de alcance de la herramienta de evidencia de CeliacMap, un directorio de lugares sin TACC / gluten free \
en Uruguay y Argentina. Recibes UN lugar (nombre, ciudad, categoría) y citas textuales numeradas tomadas de páginas públicas que \
el sistema YA verificó como sobre este negocio (por su dirección web, o porque su título nombra al negocio y menciona su ciudad \
o región). Cada cita trae "fuente" (el tipo de página y su título) y las oraciones vecinas "antes" y "despues" de la misma página, \
solo como contexto. Tu única tarea es decir, para cada cita, qué afirma. NO decides si el lugar es seguro ni si es 100% sin \
gluten: eso lo decide una persona.

Basate SOLO en el texto que recibís. No uses lo que creas saber del negocio. Que el nombre del lugar diga "sin gluten" no \
prueba nada, y que no lo diga tampoco.

Como la página ya fue verificada, una oración suelta de esa página cuenta como del negocio aunque no repita su nombre. Solo \
podés VETAR: marcá "habla_de_este_negocio": false únicamente si la oración misma habla de OTRO lugar (otro nombre, otro \
comercio, una lista de varios lugares) o no tiene relación con la oferta de un negocio. También vetá cuando las oraciones \
vecinas muestren que la cita pertenece a OTRO negocio, con un nombre distinto al del lugar. Nunca aceptes ni agregues nada que \
no esté en las citas recibidas.

Para cada cita responde:
- "alcance": exactamente uno de
  - "establecimiento": la cita afirma que TODO lo que el negocio cocina o vende es sin gluten / sin TACC / apto para celíacos, \
o que el local es exclusivamente sin gluten.
  - "producto_o_linea": afirma que ALGUNOS productos, una línea, un menú, un plato o una sección son sin gluten (por ejemplo \
"nuestras tortas son 100% sin gluten" en un lugar que también vende otros productos).
  - "opciones": ofrece opciones sin gluten o atiende a celíacos sin decir que todo lo es.
  - "irrelevante": no afirma nada sobre la oferta sin gluten de un negocio (un encabezado, un menú de navegación, una guía \
genérica).
- "contradice_exclusividad": true si la cita dice o deja entender que el negocio también cocina o vende con gluten (cocina \
compartida, "también tenemos", opciones con gluten, preparación aparte en la misma cocina).
- "habla_de_este_negocio": true en cualquier caso, salvo que la oración misma hable de OTRO lugar (véase arriba).
- "motivo": UNA frase corta (máximo 200 caracteres) que explique esa clasificación usando solo lo que dice la cita.

Ante la duda, en "alcance" y "contradice_exclusividad" usa el valor más conservador: "producto_o_linea" u "opciones" en vez de \
"establecimiento", y true en contradice_exclusividad. En "habla_de_este_negocio", ante la duda usa true: el sistema ya verificó \
la página. No incluyas en tu respuesta datos de salud de ninguna persona.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, exactamente con esta forma:
{"citas": [{"n": <número de la cita>, "alcance": "establecimiento" | "producto_o_linea" | "opciones" | "irrelevante", \
"contradice_exclusividad": <true|false>, "habla_de_este_negocio": <true|false>, "motivo": "<una frase>"}]}
"""


# --- text helpers --------------------------------------------------------------------------------------------------------

def normalize(text: str | None) -> str:
    """Lower-case, accent-free, punctuation collapsed to single spaces."""
    stripped = "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()


def distinctive_tokens(name: str | None) -> list[str]:
    """The words of a name that identify the business ("Panadería Tiempo Libre" -> ["tiempo"])."""
    return [t for t in normalize(name).split() if t not in GENERIC_WORDS and len(t) > 1]


def _has_phrase(haystack: str, phrase: str) -> bool:
    return bool(phrase) and f" {phrase} " in f" {haystack} "


def quote_is_literal(quote: str, text: str) -> bool:
    """True if ``quote`` is a literal piece of ``text`` (accent, case, punctuation and spacing blind)."""
    q = normalize(quote)
    return bool(q) and q in normalize(text)


# --- which links a place has / which source is about it ---------------------------------------------------------------

def link_kind(place: dict) -> str:
    """"website" (a site of its own), "red social" (only Instagram / Facebook / a link-in-bio) or "nada"."""
    site = (place.get("website") or "").strip()
    social = (place.get("social_url") or "").strip()
    if site and not is_social_url(site):
        return "website"
    return "red social" if (social or site) else "nada"


def _url_parts(url: str) -> tuple[str, list[str]]:
    parsed = urlparse(url if "//" in url else "//" + url)
    host = re.sub(r"^(?:www|m|l)\.", "", (parsed.netloc or "").lower().split("@")[-1].split(":")[0])
    return host, [seg for seg in parsed.path.split("/") if seg]


def _is_own_url(place: dict, url: str) -> bool:
    host, segs = _url_parts(url or "")
    for own in (place.get("website"), place.get("social_url")):
        if not own:
            continue
        own_host, own_segs = _url_parts(own)
        if not own_host or own_host != host:
            continue
        if not is_social_url(own):
            return True
        if own_segs and segs and own_segs[0].lower() == segs[0].lower():
            return True
    return False


def source_kind(url: str, place: dict) -> str:
    """"propia" (the business's own site or profile), "asociacion" (ACELU / ACELA / ACA) or "tercero"."""
    if _is_own_url(place, url):
        return "propia"
    host, _ = _url_parts(url or "")
    if any(host == d or host.endswith("." + d) for d in ASSOCIATION_DOMAINS):
        return "asociacion"
    return "tercero"


def _text_mentions(place: dict, source: dict) -> tuple[bool, bool]:
    """(the city appears, the business name appears) in the source's title, text or URL."""
    haystack = normalize(" ".join((source.get("title") or "", source.get("text") or "", source.get("url") or "")))
    tokens = distinctive_tokens(place.get("name"))
    name = normalize(place.get("name"))
    has_city = _has_phrase(haystack, normalize(place.get("city")))
    has_name = _has_phrase(haystack, name) or (len(tokens) >= 2 and _has_phrase(haystack, " ".join(tokens)))
    return has_city, has_name


def _identity_tokens(place: dict) -> list[str]:
    """The distinctive words of the name that are not also words of the place (its city, region or address): a name made only of
    place words ("Concepción sin TACC" in Concepción del Uruguay) identifies no business, since every business there shares them."""
    place_words = set(normalize(" ".join(str(place.get(k) or "") for k in ("city", "region", "address"))).split())
    return [t for t in distinctive_tokens(place.get("name")) if t not in place_words]


def _title_url_has_every_token(place: dict, source: dict) -> bool:
    """Every distinctive word of the name is a whole word of the source's title or URL (not just some, not just the body), and at
    least one of them is a word of identity, not a word of the place."""
    tokens = distinctive_tokens(place.get("name"))
    haystack = normalize((source.get("title") or "") + " " + (source.get("url") or ""))
    return bool(tokens) and bool(_identity_tokens(place)) and all(_has_phrase(haystack, t) for t in tokens)


def _place_mentioned(place: dict, source: dict) -> bool:
    """The city or the region (places.region) of the place appears in the source's title, text or URL."""
    haystack = normalize(" ".join((source.get("title") or "", source.get("text") or "", source.get("url") or "")))
    return any(_has_phrase(haystack, normalize(place.get(key))) for key in ("city", "region"))


def match_reason(place: dict, source: dict) -> str | None:
    """Why ``source`` is about THIS business, decided by the code and never by the name alone:

    * "own_url": its URL is the place's own website / social profile;
    * "name_and_city": the whole name and the city appear together in the text;
    * "title_tokens_and_place": its title or URL holds every distinctive word of the name AND the city or the region appears.

    A generic name ("Sin Gluten") is never enough on its own: it only matches through the place's own URL.
    """
    if _is_own_url(place, source.get("url") or ""):
        return "own_url"
    if not distinctive_tokens(place.get("name")):
        return None
    has_city, has_name = _text_mentions(place, source)
    if has_city and has_name:
        return "name_and_city"
    if _title_url_has_every_token(place, source) and _place_mentioned(place, source):
        return "title_tokens_and_place"
    return None


def why_not_about_place(place: dict, source: dict) -> str:
    """The reason a source was not taken as being about this business (for the report of an insuficiente)."""
    if not distinctive_tokens(place.get("name")):
        return "nombre genérico: solo vale la URL propia"
    if not _identity_tokens(place):
        return "el nombre solo tiene palabras genéricas o de lugar: hace falta el nombre completo con la ciudad, o la URL propia"
    if _title_url_has_every_token(place, source) and not _place_mentioned(place, source):
        return "el título tiene el nombre pero no menciona la ciudad ni la región"
    has_city, has_name = _text_mentions(place, source)
    if not has_city and not has_name:
        return "no menciona ni el nombre ni la ciudad"
    return "no menciona el nombre" if has_city else "no menciona la ciudad"


# --- quotes ---------------------------------------------------------------------------------------------------------------

_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+|\s*(?:\.\.\.|…)\s*")
_GF_RE = re.compile(r"sin\s+(?:gluten|tacc)|libre\s+de\s+gluten|gluten[\s-]?free|cel[ií]ac|apto\s+para\s+cel", re.IGNORECASE)
# Instagram / Facebook auto-generated alt text and captions: text of the platform, not a statement of the business.
_NOISE_RE = re.compile(
    r"^\W*(?:may be (?:an?|the) (?:image|photo|picture)\b|image may contain\b|no photo description available\b"
    r"|puede ser (?:una|un) (?:imagen|foto)\b|photo by\b)",
    re.IGNORECASE,
)


def _window(sentence: str, start: int, end: int) -> str:
    """A piece of a long sentence, at most QUOTE_MAX characters, that still contains the match."""
    lo = max(0, min(start - QUOTE_MAX // 3, len(sentence) - QUOTE_MAX))
    hi = min(len(sentence), lo + QUOTE_MAX)
    if lo > 0:
        nxt = sentence.find(" ", lo)
        if 0 <= nxt < start:
            lo = nxt + 1
    if hi < len(sentence):
        prv = sentence.rfind(" ", lo, hi)
        if prv >= end:
            hi = prv
    return sentence[lo:hi].strip()


def _fold(text: str | None) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower()


def _name_spans(text: str, name: str | None) -> list[tuple[int, int]]:
    """Where the business name appears in ``text``: exact occurrences of its words (accent and case blind), as whole words."""
    tokens = re.findall(r"[a-z0-9]+", _fold(name))
    folded = _fold(text)
    if not tokens or len(folded) != len(text):  # a character that changes length when folded: no reliable positions, no masking
        return []
    pattern = r"(?<![a-z0-9])" + r"[^a-z0-9]+".join(re.escape(t) for t in tokens) + r"(?![a-z0-9])"
    return [m.span() for m in re.finditer(pattern, folded)]


def mask_name(text: str | None, name: str | None) -> str:
    """``text`` with every exact occurrence of the business name replaced by "[negocio]": a name that says "sin gluten" proves nothing."""
    text = text or ""
    for start, end in reversed(_name_spans(text, name)):
        text = text[:start] + "[negocio]" + text[end:]
    return text


def _real_gf_match(sentence: str, name: str | None):
    """The first gluten-free phrase that is not (part of) the business name."""
    spans = _name_spans(sentence, name)
    for match in _GF_RE.finditer(sentence):
        if not any(match.start() < end and start < match.end() for start, end in spans):
            return match
    return None


def extract_quotes_with_context(text: str | None, name: str | None = None) -> list[dict]:
    """Literal sentences about gluten-free / celiac food, each with the sentence before and after it on the same page.

    The business ``name`` is masked before looking for gluten phrases (a sentence that is only the name is not a quote). Sentences
    that tie a person to celiac disease are dropped, and so is the alt text Instagram and Facebook generate for images.
    """
    parts = [p for p in (" ".join((raw or "").split()) for raw in _SPLIT_RE.split(text or "")) if p]
    quotes: list[dict] = []
    seen: set[str] = set()
    for index, sentence in enumerate(parts):
        match = _real_gf_match(sentence, name)
        if not match or _NOISE_RE.search(sentence) or _OWNER_HEALTH_RE.search(sentence):
            continue
        if len(sentence) > QUOTE_MAX:
            sentence = _window(sentence, match.start(), match.end())
        key = normalize(sentence)
        if key and key not in seen:
            seen.add(key)
            quotes.append({"text": sentence,
                           "before": _clip(parts[index - 1], CONTEXT_MAX) if index else "",
                           "after": _clip(parts[index + 1], CONTEXT_MAX) if index + 1 < len(parts) else ""})
    return quotes


def extract_quotes(text: str | None, name: str | None = None) -> list[str]:
    return [q["text"] for q in extract_quotes_with_context(text, name)]


# Exclusivity phrases the Validator's regex (has_exclusive_signal) does not recognise. They only raise an alert in the report
# ("posible 100"); they never make a proposal of 100 by themselves.
_EXTENDED_SIGNAL_RE = re.compile(
    r"exclusiv\w*\s+(?:para|de)\s+(?:los\s+|las\s+)?celiac"
    r"|(?:solo|solamente|unicamente)\s+para\s+(?:los\s+|las\s+)?celiac"
    r"|todo\s+(?:el\s+local\s+)?(?:es\s+)?apto\s+para\s+celiac"
)
_NEGATION_BEFORE_RE = re.compile(r"\bno\s+(?:es\s+|son\s+|tiene\s+)?$")


def has_extended_signal(text: str | None) -> bool:
    norm = normalize(text)
    return any(not _NEGATION_BEFORE_RE.search(norm[max(0, m.start() - 20): m.start()]) for m in _EXTENDED_SIGNAL_RE.finditer(norm))


# --- the model's classification (a filter that can only lower) ----------------------------------------------------------

def _clean_reason(value) -> str:
    """The model's one-line reason: bounded, on one line, and never carrying health data."""
    if not isinstance(value, str):
        return ""
    reason = " ".join(value.split())[:REASON_MAX]
    return "(motivo omitido: mencionaba datos de salud)" if _OWNER_HEALTH_RE.search(reason) else reason


def parse_scope(raw, n: int) -> list[dict]:
    """One conservative classification per quote. Anything unexpected reads as the safest value."""
    out = [dict(UNKNOWN_SCOPE) for _ in range(n)]
    items = raw.get("citas") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        k = item.get("n")
        if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= n:
            continue
        out[k - 1] = {
            "alcance": item.get("alcance") if item.get("alcance") in SCOPES else "desconocido",
            "contradice": item.get("contradice_exclusividad") is not False,
            "habla": item.get("habla_de_este_negocio") is True,
            "motivo": _clean_reason(item.get("motivo")),
        }
    return out


def decide(quotes: list[dict]) -> tuple[str, list[str]]:
    """The proposal for a place, from its kept quotes (each already about this business).

    "100" needs an explicit exclusivity phrase scoped to the whole establishment and nothing that contradicts or hedges it.
    """
    if not quotes:
        return "insuficiente", ["sin citas sobre el negocio"]
    signals = [q for q in quotes if q["has_signal"]]
    establishment = [q for q in signals if q["alcance"] == "establecimiento" and not q["contradice"]]
    blocking = [q for q in quotes if q["contradice"] or q["alcance"] == "opciones"]
    if establishment and not blocking:
        return "100", [f"{len(establishment)} cita(s) con exclusividad explícita del establecimiento"]
    reasons: list[str] = []
    if signals and not establishment:
        scopes = sorted({q["alcance"] for q in signals})
        reasons.append("señal de exclusividad vetada: alcance " + "/".join(scopes))
    if establishment and blocking:
        reasons.append("hay citas que contradicen o relativizan la exclusividad")
    if not signals:
        reasons.append("ninguna cita afirma exclusividad con una frase explícita")
    return "options", reasons


def _vetoes(quotes: list[dict]) -> list[dict]:
    """What the model took away from a place that had an explicit exclusivity phrase, with its reason and the quote that caused it.

    A quote the model did not read (scope "desconocido": no model, or it failed) is not a veto.
    """
    if not any(q["has_signal"] for q in quotes):
        return []
    out = []
    for index, q in enumerate(quotes, start=1):
        if q["has_signal"] and q["alcance"] not in ("establecimiento", "desconocido"):
            kind = "alcance"
        elif q["contradice"] and q["alcance"] != "desconocido":
            kind = "contradice"
        elif q["alcance"] == "opciones":
            kind = "opciones"
        else:
            continue
        out.append({"tipo": kind, "cita": index, "texto": q["text"], "url": q["url"], "motivo_modelo": q.get("motivo", "")})
    return out


def assess(quotes: list[dict]) -> dict:
    """The proposal plus what the admin needs to weigh it: whether the "100" must be checked at the source, a possible 100 the
    Validator's regex missed, and the vetoes the model applied."""
    proposal, reasons = decide(quotes)
    establishment = [q for q in quotes if q["has_signal"] and q["alcance"] == "establecimiento" and not q["contradice"]]
    verify = proposal == "100" and not any(q.get("verificacion") == "verificada" for q in establishment)
    possible = None
    if proposal == "options":
        possible = next((q for q in quotes if not q["has_signal"] and q["alcance"] == "establecimiento" and not q["contradice"]
                         and (q["has_extended"] if "has_extended" in q else has_extended_signal(q["text"]))), None)
    return {"proposal": proposal, "reasons": reasons, "verify_in_source": verify, "possible_100": possible is not None,
            "possible_100_quote": {"text": possible["text"], "url": possible["url"]} if possible else None,
            "vetoes": _vetoes(quotes)}


def needs_source_check(entry) -> bool:
    """A "100" is block-acceptable only if a quote verified on its page states the exclusivity of the whole establishment."""
    if not isinstance(entry, dict) or entry.get("proposal") != "100":
        return False
    return not any(
        isinstance(c, dict) and c.get("verificacion") == "verificada" and c.get("has_signal")
        and c.get("alcance") == "establecimiento" and not c.get("contradice")
        for c in entry.get("citations") or []
    )


def proposal_label(result: dict) -> str:
    proposal = result["proposal"]
    if proposal == "100":
        verify = result["verify_in_source"] if "verify_in_source" in result else needs_source_check(result)
        return "100 · verificar en la fuente" if verify else "100"
    if proposal == "options" and result.get("possible_100"):
        return "options · posible 100"
    return proposal


def verification_label(citation: dict) -> str:
    return VERIFICATION_LABELS.get(citation.get("verificacion"), "sin verificar")


# --- search ---------------------------------------------------------------------------------------------------------------

def build_queries(place: dict) -> list[tuple[str, tuple[str, ...] | None]]:
    name, city = place.get("name") or "", place.get("city") or ""
    return [
        (f'"{name}" {city} sin gluten sin TACC celíacos', None),
        (f'"{name}" {city} sin gluten', SOCIAL_SEARCH_DOMAINS),
        (f'"{name}" {city}', ASSOCIATION_DOMAINS),
    ]


_KIND_RANK = {"propia": 0, "asociacion": 1, "tercero": 2}


class EvidenceFinder:
    """Searches and quotes; never writes. ``search`` is a TavilySearchClient, ``llm`` an LLMClient (or None)."""

    def __init__(self, search, llm=None, model: str | None = None, fetch_text=fetch_page_text,
                 queries: int = 2, results_per_query: int = RESULTS_PER_QUERY):
        if queries not in (2, 3):
            raise ValueError("queries must be 2 (open web + social) or 3 (+ associations)")
        self.search = search
        self.llm = llm
        self.model = model
        self.fetch_text = fetch_text
        self.queries = queries
        self.results_per_query = results_per_query
        self.searches_used = 0
        self.llm_tokens = {"input": 0, "output": 0}

    # -- one place ------------------------------------------------------------------------------------------------------
    def find(self, place: dict) -> dict:
        stats = {"searches": 0, "search_errors": 0, "sources_seen": 0, "sources_about_place": 0,
                 "quotes_candidate": 0, "quotes_dropped_by_llm": 0, "llm_error": False,
                 "llm_tokens": {"input": 0, "output": 0}}
        sources: dict[str, dict] = {}
        for query, domains in build_queries(place)[: self.queries]:
            self.searches_used += 1
            stats["searches"] += 1
            try:
                hits = self.search.search(query, num=self.results_per_query, include_domains=list(domains) if domains else None)
            except Exception:  # noqa: BLE001 - one failed search must not lose the place
                stats["search_errors"] += 1
                logger.exception("evidence search failed for %r", query)
                continue
            for hit in hits or []:
                url = (hit.get("link") or "").strip()
                if url and url not in sources:
                    sources[url] = {"url": url, "title": hit.get("title") or "", "text": hit.get("snippet") or "", "origin": "search"}
        site = (place.get("website") or "").strip()
        if site and site not in sources:
            text = self.fetch_text(site)  # "" for a social profile or any failure
            if text:
                sources[site] = {"url": site, "title": "", "text": text, "origin": "fetch"}
        stats["sources_seen"] = len(sources)

        candidates: list[dict] = []
        seen: set[str] = set()
        discarded: list[dict] = []
        for source in sources.values():
            reason = match_reason(place, source)
            if not reason:
                discarded.append({"url": source["url"], "title": source["title"], "why": why_not_about_place(place, source)})
                continue
            stats["sources_about_place"] += 1
            kind = source_kind(source["url"], place)
            found = 0
            for item in extract_quotes_with_context(source["text"], place.get("name")):
                text = item["text"]
                key = normalize(text)
                if key in seen or not quote_is_literal(text, source["text"]):
                    continue
                seen.add(key)
                found += 1
                masked = mask_name(text, place.get("name"))  # the name never makes a quote an exclusivity claim
                candidates.append({"text": text, "url": source["url"], "source_kind": kind, "matched_by": reason,
                                   "has_signal": ValidatorAgent.has_exclusive_signal([masked]),
                                   "has_extended": has_extended_signal(masked), "origin": source["origin"],
                                   "title": source["title"], "before": item["before"], "after": item["after"]})
            if not found:
                discarded.append({"url": source["url"], "title": source["title"],
                                  "why": "sobre el negocio, pero sin frases sobre gluten o celíacos"})
        candidates.sort(key=lambda c: (not c["has_signal"], _KIND_RANK.get(c["source_kind"], 3)))
        candidates = candidates[:MAX_CANDIDATE_QUOTES]
        stats["quotes_candidate"] = len(candidates)

        pages: dict[str, str] = {}
        for candidate in candidates:
            candidate["verificacion"] = self._verify(candidate, pages)

        scopes = self._classify(place, candidates, stats)
        kept: list[dict] = []
        dropped: list[dict] = []
        for candidate, scope in zip(candidates, scopes):
            if scope["alcance"] == "irrelevante" or not scope["habla"]:
                stats["quotes_dropped_by_llm"] += 1
                dropped.append({"text": candidate["text"], "url": candidate["url"], "motivo": scope["motivo"],
                                "razon": "irrelevante" if scope["alcance"] == "irrelevante" else "no habla de este negocio"})
                continue
            kept.append({"text": candidate["text"], "url": candidate["url"], "source_kind": candidate["source_kind"],
                         "matched_by": candidate["matched_by"], "has_signal": candidate["has_signal"],
                         "has_extended": candidate["has_extended"], "verificacion": candidate["verificacion"], "alcance": scope["alcance"],
                         "contradice": scope["contradice"], "motivo": scope["motivo"]})

        verdict = assess(kept)
        return {
            "place_id": place.get("id"), "name": place.get("name"), "city": place.get("city"), "country": place.get("country"),
            "category": place.get("category"), "website": place.get("website"), "social_url": place.get("social_url"),
            "safety_level": place.get("safety_level"), "updated_at": place.get("updated_at"), "link_kind": link_kind(place),
            **verdict, "citations": kept, "dropped_by_model": dropped,
            "discarded_sources": discarded[:MAX_DISCARDED_SOURCES] if verdict["proposal"] == "insuficiente" else [],
            "stats": stats, "found_at": datetime.now(timezone.utc).isoformat(),
        }

    def _verify(self, candidate: dict, pages: dict[str, str]) -> str:
        """Is this quote literal on its page? A social profile cannot be downloaded; a snippet the page does not contain, or a page
        that cannot be fetched, leaves it a snippet. The place's own site was fetched to get the text, so it is verified by construction."""
        url = candidate["url"]
        if candidate["origin"] == "fetch":
            return "verificada"
        if is_social_url(url):
            return "no_verificable"
        if url not in pages:
            pages[url] = self.fetch_text(url) or ""
        return "verificada" if pages[url] and quote_is_literal(candidate["text"], pages[url]) else "solo_snippet"

    def _classify(self, place: dict, candidates: list[dict], stats: dict) -> list[dict]:
        """The model's reading of each quote; without a model (or if it fails) nothing is vetoed and nothing is raised."""
        if not candidates:
            return []
        if self.llm is None:
            return [dict(UNCLASSIFIED) for _ in candidates]
        payload = {
            "lugar": {"nombre": place.get("name"), "ciudad": place.get("city"), "categoria": place.get("category")},
            "citas": [{"n": i + 1, "fuente": {"tipo": c["source_kind"], "titulo": (c["title"] or "")[:120]},
                       "antes": c["before"], "texto": c["text"], "despues": c["after"]} for i, c in enumerate(candidates)],
        }
        try:
            raw = self.llm.complete_json(SCOPE_RUBRIC, json.dumps(payload, ensure_ascii=False), model=self.model, max_tokens=800)
        except Exception:  # noqa: BLE001 - a model failure must not lose the place
            stats["llm_error"] = True
            logger.exception("evidence scope classification failed for %s", place.get("id"))
            return [dict(UNCLASSIFIED) for _ in candidates]
        self._count_tokens(stats)
        return parse_scope(raw, len(candidates))

    def _count_tokens(self, stats: dict) -> None:
        usage = getattr(self.llm, "last_usage", None)
        if not isinstance(usage, dict):
            return
        for key in ("input", "output"):
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                stats["llm_tokens"][key] += value
                self.llm_tokens[key] += value

    # -- many places, under a search cap ----------------------------------------------------------------------------------
    def find_many(self, places: list[dict], max_searches: int | None = None) -> tuple[list[dict], list[dict]]:
        """(results, skipped). Stops before a place that would pass the cap; a skipped place is never labelled."""
        results: list[dict] = []
        for index, place in enumerate(places):
            if max_searches is not None and self.searches_used + self.queries > max_searches:
                return results, list(places[index:])
            results.append(self.find(place))
        return results, []


# --- summary, pilot, acceptance ---------------------------------------------------------------------------------------------

def haiku_cost_usd(tokens: dict) -> float:
    return round(tokens.get("input", 0) * HAIKU_USD_PER_MTOK[0] / 1e6 + tokens.get("output", 0) * HAIKU_USD_PER_MTOK[1] / 1e6, 6)


def summarize(results: list[dict]) -> dict:
    proposals = {k: 0 for k in PROPOSALS}
    links = {k: 0 for k in LINK_KINDS}
    with_signal = searches = verify = possible = vetoed = 0
    for r in results:
        proposals[r["proposal"]] += 1
        if r["proposal"] == "100" and (r["verify_in_source"] if "verify_in_source" in r else needs_source_check(r)):
            verify += 1
        if r["proposal"] == "insuficiente":
            links[r.get("link_kind") or "nada"] += 1
        if r.get("possible_100"):
            possible += 1
        if r.get("vetoes"):
            vetoed += 1
        if any(c.get("has_signal") for c in r.get("citations") or []):
            with_signal += 1
        searches += (r.get("stats") or {}).get("searches", 0)
    return {"total": len(results), "por_propuesta": proposals, "insuficientes_por_link": links,
            "con_senal_de_exclusividad": with_signal, "cien_verificar_en_la_fuente": verify, "posible_100": possible,
            "con_veto_del_modelo": vetoed, "busquedas": searches}


def pick_pilot(places: list[dict], n: int = 10) -> list[dict]:
    """A deterministic sample: distinct cities, a fixed mix of link kinds (3 website, 3 red social, 4 nada for n = 10)
    and as many categories as the pool has. Independent of the order the places arrive in."""
    ordered = sorted(places, key=lambda p: hashlib.sha1(str(p.get("id")).encode()).hexdigest())
    third = n * 3 // 10
    want = {"website": third, "red social": third, "nada": n - 2 * third}
    picked: list[dict] = []
    used_ids: set = set()
    cities: set[str] = set()
    categories: set = set()

    def take(place: dict) -> None:
        picked.append(place)
        used_ids.add(place.get("id"))
        cities.add(normalize(place.get("city")))
        categories.add(place.get("category"))

    def free(place: dict) -> bool:
        return place.get("id") not in used_ids and normalize(place.get("city")) not in cities

    for kind, count in want.items():
        got = 0
        for want_new_category in (True, False):
            for place in ordered:
                if got >= count:
                    break
                if link_kind(place) != kind or not free(place):
                    continue
                if want_new_category and place.get("category") in categories:
                    continue
                take(place)
                got += 1
    for place in ordered:
        if len(picked) >= n:
            break
        if free(place):
            take(place)
    return picked[:n]


def _clip(text: str, limit: int = NOTE_QUOTE_MAX) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:") + "…"


def _evidence_row(citation: dict) -> dict | None:
    text = citation["text"]
    if _OWNER_HEALTH_RE.search(text):
        return None
    if citation.get("verificacion") != "verificada":
        text = UNVERIFIED_ROW_PREFIX + text
    return {"source": "web", "text": text[:1000], "url": citation["url"]}


def build_acceptance_note(entry) -> tuple[str, list[dict]] | None:
    """(the note for the public ``validation_notes``, the ``place_evidence`` rows to save), or None if there is nothing
    citable or it would carry health data.

    The note quotes (at most NOTE_QUOTE_MAX characters) only a quote verified on its page. Otherwise it names where the evidence is
    and gives the URL, without the snippet: "evidencia en redes del local (URL)" / "evidencia en la web (URL)". The evidence rows keep
    every citation, the unverified ones marked as such in their text.
    """
    if not isinstance(entry, dict) or entry.get("proposal") not in ("100", "options"):
        return None
    cites = [c for c in (entry.get("citations") or []) if isinstance(c, dict) and c.get("text") and c.get("url")]
    if entry["proposal"] == "100":
        pool = [c for c in cites if c.get("has_signal") and c.get("alcance") == "establecimiento" and not c.get("contradice")]
        label = "100% sin gluten"
    else:
        pool, label = cites, "opciones sin TACC"
    if not pool:
        return None

    def rank(c: dict) -> tuple[int, int]:
        return (0 if c.get("verificacion") == "verificada" else 1, _KIND_RANK.get(c.get("source_kind"), 3))

    main = sorted(pool, key=rank)
    rest = sorted((c for c in cites if c not in main), key=rank)
    top = main[0]
    if _OWNER_HEALTH_RE.search(top["text"]):
        return None
    if top.get("verificacion") == "verificada":
        note = f"evidencia pública para {label}: «{_clip(top['text'])}» ({top['url']})"
    else:
        where = "en redes del local" if is_social_url(top["url"]) else "en la web"
        note = f"evidencia {where} para {label} ({top['url']})"
    if _OWNER_HEALTH_RE.search(note):
        return None
    store = [row for row in (_evidence_row(c) for c in (main + rest)[:MAX_STORED_EVIDENCE]) if row]
    return note, store
