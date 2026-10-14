"""Map scope rules (decided 2026-10-13): what never belongs on the map, whatever its gluten-free offer.

1a. General retail: supermarket, hypermarket, self-service and pharmacy chains (their offer changes from branch to branch and
    cannot be verified), and an independent self-service shop or supermarket whose only gluten-free offer is a shelf (decided by
    the admin on 2026-10-14).
1b. Places that teach or inform without selling or serving food or products to the public: cooking schools, workshops, blogs,
    recipe accounts, information pages and a platform's topic pages.

The criterion is the line of business (general retail vs. food service or a specialised shop), never the number of branches: a
food or specialised chain (Zero Helados, Ramona, Mi Cocina Sin Gluten) is evaluated branch by branch like any other place.

This module is the ONLY place where scope is decided: the discovery agents create no candidate and the Validator makes no model
call. The Validator's RUBRIC knows nothing about scope: six wordings measured against the real model (2026-10-13/14) all moved
safety verdicts of places that do apply, so scope was taken out of the prompt (docs/DECISIONS.md, "Map scope rules"). A platform's topic page is handled where it appears, in the Social agent, not here. The brand lists are examples that help, not the rule: anything they miss is judged by the Validator's RUBRIC, which
states the criterion. When a name is ambiguous this layer says nothing.
"""

from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple
from urllib.parse import urlparse

CHAIN = "chain"
NOT_A_SELLER = "not_a_seller"

NOTE_PREFIX = "No aplica al mapa: "
_FLAG_PREFIX = "no aplica al mapa"
_FLAG_TEXT = {CHAIN: "comercio general", NOT_A_SELLER: "no vende ni sirve al público"}


class ScopeExclusion(NamedTuple):
    kind: str    # CHAIN (general retail: a chain, or an independent shop with only a shelf) | NOT_A_SELLER
    detail: str  # the reason, in Spanish, as it is stored in validation_notes


def scope_flag(kind: str | None) -> str:
    text = _FLAG_TEXT.get(kind)
    return f"{_FLAG_PREFIX}: {text}" if text else _FLAG_PREFIX


def scope_note(kind: str | None, detail: str | None) -> str:
    detail = (detail or "").strip() or _FLAG_TEXT.get(kind, "fuera del alcance del mapa")
    return NOTE_PREFIX + detail


def _norm(text) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


# Brands that name a general retail chain wherever they appear in a name. Normalised form -> the name shown in the note.
_DISTINCTIVE_BRANDS = {
    # Uruguay
    "geant": "Géant", "tienda inglesa": "Tienda Inglesa", "devoto": "Devoto", "ta ta": "Ta-Ta", "macromercado": "Macromercado",
    "multi ahorro": "Multi Ahorro", "farmashop": "Farmashop",
    # Argentina
    "carrefour": "Carrefour", "jumbo": "Jumbo", "chango mas": "Chango Más", "walmart": "Walmart", "makro": "Makro",
    "farmacity": "Farmacity",
}
# Brands that are also everyday words ("día", "disco", "vea", "coto", "tata"): they count only when the name is the brand itself, or
# starts with it and carries a branch or retail marker, or a Google type confirms the line of business.
_AMBIGUOUS_BRANDS = {
    "tata": "Ta-Ta", "disco": "Disco", "dia": "Día", "vea": "Vea", "coto": "Coto", "el dorado": "El Dorado",
    "la anonima": "La Anónima", "san roque": "San Roque",
}
_RETAIL_WORDS = frozenset(
    "supermercado supermercados hipermercado hipermercados autoservicio autoservicios farmacia farmacias express market maxi mini "
    "hiper sucursal suc local n nro no".split()
)
# A food-service or specialised word in the name keeps the place in scope: "Disco Bar", "Tata Panadería", "Día Verde Almacén Natural".
_FOOD_WORDS = frozenset(
    "panaderia panificadora pasteleria confiteria reposteria heladeria helados restaurante restaurant resto restobar bar cafe "
    "cafeteria parrilla pizzeria pizza burger burgers hamburgueseria rotiseria empanadas pastas sushi bistro deli bakery "
    "cerveceria dietetica almacen natural naturales organico saludable fabrica cocina".split()
)
_RETAIL_TYPES = frozenset({"supermarket", "pharmacy", "drugstore", "department_store"})
# The chains' own sites: a row whose website is one of these is a branch of the chain, whatever its listing is called.
_CHAIN_DOMAINS = {
    "geant.com.uy": "Géant", "tata.com.uy": "Ta-Ta", "devoto.com.uy": "Devoto", "disco.com.uy": "Disco",
    "tiendainglesa.com.uy": "Tienda Inglesa", "eldorado.com.uy": "El Dorado", "macromercado.com.uy": "Macromercado",
    "multiahorro.com.uy": "Multi Ahorro", "farmashop.com.uy": "Farmashop", "sanroque.com.uy": "San Roque",
    "carrefour.com.ar": "Carrefour", "coto.com.ar": "Coto", "cotodigital.com.ar": "Coto", "cotodigital3.com.ar": "Coto",
    "jumbo.com.ar": "Jumbo", "supermercadosdia.com.ar": "Día", "vea.com.ar": "Vea", "disco.com.ar": "Disco",
    "masonline.com.ar": "Chango Más", "walmart.com.ar": "Walmart", "laanonima.com.ar": "La Anónima", "makro.com.ar": "Makro",
    "farmacity.com": "Farmacity",
}

# 1b by the name. Anchored at the start, so "Panadería La Escuela" or "Café del Taller" stay in scope.
_TEACHES_RE = re.compile(
    r"^(?:escuela|academia|instituto)\b"
    r"|^(?:curso|cursos|taller|talleres|clases) de (?:cocina|pasteleria|panaderia|reposteria|panificados|gastronomia)\b"
    r"|^recetas (?:sin gluten|sin tacc|gluten free|libres de gluten|para celiacos|aptas|saludables)\b"
)
_BUSINESS_WORDS = _FOOD_WORDS - {"cocina", "natural", "naturales", "organico", "saludable"}
# 1a for an independent shop, by the name: it starts with one of these words. "Minimarket" is deliberately not here: Minimarket La
# Isla has a dedicated, verifiable gluten-free offer and stays on the map (admin decision, 2026-10-14).
_GENERAL_RETAIL_START = frozenset("autoservicio autoservicios minimercado minimercados supermercado supermercados".split())
# Any of these in the name says the shop is specialised, so the name rule does not apply: "Supermercado Natural", "Autoservicio Sin
# Gluten". The Validator still judges its safety.
_SPECIALISED_WORDS = _FOOD_WORDS | frozenset(
    "saludables sano sana sanos organica organicos organicas integral vegano vegana veganos veganas vegetariano keto gluten tacc "
    "celiaco celiaca celiacos celiacas glutenfree healthy herboristeria macrobiotica dieteticas".split()
)
_SCHOOL_TYPES = frozenset({"school", "university", "primary_school", "secondary_school"})
_FOOD_TYPES = frozenset(
    "restaurant cafe bakery food meal_takeaway meal_delivery bar store grocery_or_supermarket supermarket health".split()
)


def _has_phrase(tokens: list[str], phrase: str) -> bool:
    words = phrase.split()
    return any(tokens[i:i + len(words)] == words for i in range(len(tokens) - len(words) + 1))


def _chain_by_name(tokens: list[str], types: frozenset[str]) -> str | None:
    if not tokens or _FOOD_WORDS & set(tokens):
        return None
    for brand, label in _DISTINCTIVE_BRANDS.items():
        if _has_phrase(tokens, brand):
            return label
    # Leading retail words are not part of the brand: "Supermercado Disco", "Farmacia San Roque".
    core = list(tokens)
    while core and core[0] in _RETAIL_WORDS:
        core.pop(0)
    for brand, label in _AMBIGUOUS_BRANDS.items():
        words = brand.split()
        if core[:len(words)] != words:
            continue
        rest = core[len(words):]
        marked = any(t in _RETAIL_WORDS or t.isdigit() for t in tokens)
        if not [t for t in rest if t not in _RETAIL_WORDS and not t.isdigit()] or marked or types & _RETAIL_TYPES:
            return label
    return None


def _chain_by_site(website: str | None) -> str | None:
    if not website:
        return None
    host = (urlparse(website if "//" in website else "//" + website).netloc or "").lower().split("@")[-1].split(":")[0]
    return next((label for domain, label in _CHAIN_DOMAINS.items() if host == domain or host.endswith("." + domain)), None)


def out_of_scope_reason(name, *, types=(), website: str | None = None) -> ScopeExclusion | None:
    """Why a place does not belong on the map, or None when this layer has nothing to say (the usual case).

    ``types`` are the Google place types, when the caller has them (the Search agent does; a stored row does not).

    A row's ``social_url`` is deliberately not looked at: a topic page there says where the lead came from, not what the place
    is. The audit of 2026-10-13 found 20 rows with one, nearly all real businesses (a 100% gluten-free bakery among them). The
    Social agent drops a topic page before it becomes a lead, which is where that rule belongs.
    """
    tokens = _norm(name).split()
    types = frozenset(types or ())

    label = _chain_by_name(tokens, types) or _chain_by_site(website)
    if label:
        return ScopeExclusion(
            CHAIN,
            f"cadena de comercio general ({label}); su oferta sin gluten varía por sucursal y no se puede verificar.",
        )
    if tokens and tokens[0] in _GENERAL_RETAIL_START and not _SPECIALISED_WORDS & set(tokens):
        return ScopeExclusion(
            CHAIN,
            "comercio general (autoservicio, minimercado o supermercado sin rubro especializado en el nombre); una góndola sin "
            "gluten no lo hace un lugar del mapa.",
        )

    if _TEACHES_RE.search(" ".join(tokens)) or ("blog" in tokens and not _BUSINESS_WORDS & set(tokens)):
        return ScopeExclusion(
            NOT_A_SELLER,
            "el nombre indica que enseña o informa (escuela, cursos, blog o recetas); no es un local que venda o sirva al público.",
        )
    if types & _SCHOOL_TYPES and not types & _FOOD_TYPES:
        return ScopeExclusion(
            NOT_A_SELLER, "la ficha de Google es de una institución educativa, sin rubro de comida ni de comercio."
        )
    return None
