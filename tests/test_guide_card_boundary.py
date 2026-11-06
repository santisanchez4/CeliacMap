"""On a guide of several businesses, a quote belongs to a business only inside that business's card (found 2026-11-05 with GlutenGo:
"El local se presenta como 100% sin gluten." of the next card was attributed to La Carola, La Cabrona and Harta Café). And a page
that is one business's own card (findmeglutenfree /biz/, GlutenGo /lugar/, Guía Comercial /ficha/) is not a guide of several."""
from __future__ import annotations

import pytest

from agents.evidence_finder import _near_name, looks_like_multi_business

GLUTENGO = (
    "Lugares en esta guía\n"
    "Opciones SG\nRestaurante\nLa Cabrona MVD\nPocitos · Gral. Brito del Pino 1317 bis, Montevideo\n"
    "Restaurante con opciones sin gluten registrada en fuentes públicas. Confirmá menú, disponibilidad, protocolo y riesgo.\n"
    "Ver ficha en GlutenGo\n"
    "100% GF informado\nRestaurante\nOtro Local\nCentro · 18 de Julio 1000, Montevideo\n"
    "El local se presenta como 100% sin gluten.\n"
    "Ver ficha en GlutenGo\n"
)

FMGF_LIST = (
    "48.\nLa Cabrona\n(1)\nGral. Brito del Pino 1317 bis, 11300 Montevideo\nGF menu items: Nachos, Tacos\n"
    "Featured review snippet \"Todos menos las quesadillas son aptas para celíacos, los tacos son buenisimos!\"\n"
    "49.\nLa Mostaza\n(1)\nT 13, Bv. Gral. Artigas\nFeatured review snippet \"Todo es sin gluten, riquísimo\"\n"
)


def test_a_quote_of_the_next_card_of_a_guide_is_not_the_business_s():
    assert not _near_name(GLUTENGO, "El local se presenta como 100% sin gluten.", "La Cabrona MVD")


def test_the_business_s_own_card_still_counts():
    assert _near_name(GLUTENGO, "Restaurante con opciones sin gluten registrada en fuentes públicas.", "La Cabrona MVD")


def test_a_numbered_list_ends_a_card_too():
    assert _near_name(FMGF_LIST, "Todos menos las quesadillas son aptas para celíacos, los tacos son buenisimos!", "La Cabrona")
    assert not _near_name(FMGF_LIST, "Todo es sin gluten, riquísimo", "La Cabrona")


def test_without_card_markers_the_distance_rule_is_unchanged():
    text = "En Montevideo probamos La Cabrona. Nos encantó: todo sin gluten salvo las quesadillas."
    assert _near_name(text, "Nos encantó: todo sin gluten salvo las quesadillas.", "La Cabrona")
    assert not _near_name(text + " x" * 400 + " Todo sin TACC.", "Todo sin TACC.", "La Cabrona")


INE_PAGE = ("ine Boutique de cosas ricas\n2 recent ratings\nReported to be dedicated gluten-free\nPopular gluten-free menu items\n"
            "Bread/Buns\n2\nCakes\n2\nCinnamon Rolls\n2\nCheesecake\n1\nCroissants\n1\nScones\n1\n"
            "More Reviews\nTienen opciones de desayuno y merienda sin gluten muy ricas. Son aptos para celiacos\n")


@pytest.mark.parametrize("url", [
    "https://www.findmeglutenfree.com/biz/ine/6411141477171200",
    "https://glutengo.com.uy/lugar/mi-espacio-sin-tacc",
    "https://guiacomercial.uy/ficha/lumiro-sin-gluten-trinidad",
])
def test_a_page_that_is_one_business_s_own_card_is_not_a_guide(url):
    assert not looks_like_multi_business("ine Boutique de cosas ricas - Dedicated Gluten-Free Bakery in Montevideo", url, INE_PAGE,
                                         "ine Boutique de cosas ricas")


def test_a_list_page_of_the_same_site_still_is_a_guide():
    assert looks_like_multi_business("The Best Gluten-Free Restaurants in Montevideo",
                                     "https://www.findmeglutenfree.com/uy/montevideo/tacos", FMGF_LIST, "La Cabrona")
    assert looks_like_multi_business("Sin gluten en Montevideo | GlutenGo",
                                     "https://glutengo.com.uy/guias/sin-gluten-montevideo.html", GLUTENGO, "La Cabrona MVD")


# Measured on the frozen sources of the 2026-11-05 Montevideo batch 3: a Tavily snippet of the same GlutenGo guide.
SNIPPET = ("Opciones SG Restaurante\n\n## La Carola\n\nParque Rodó · Av. Gonzalo Ramírez 2225, Montevideo\n\n"
           "Restaurante con opciones sin gluten registrada en fuentes públicas. [...] 35Opciones SG\n\n## Lugares en esta guía\n\n"
           "100% GF informado Rotisería\n\n## Boom Gluten\n\nCentro · Soriano 1149\n\n"
           "El local se presenta como 100% sin gluten. Confirmá horarios y disponibilidad antes de ir.")


def test_tavily_s_chunk_separator_and_the_next_heading_end_a_card():
    assert _near_name(SNIPPET, "Restaurante con opciones sin gluten registrada en fuentes públicas.", "La Carola")
    assert not _near_name(SNIPPET, "El local se presenta como 100% sin gluten.", "La Carola")
    assert not _near_name("## La Carola\n\nUn bar.\n## Otro\n\nTodo sin TACC.", "Todo sin TACC.", "La Carola")


def test_the_card_rule_also_reads_a_text_with_an_ellipsis():
    # "…" becomes "..." when folded: the positions of the name must still be found (the real snippet had it).
    text = SNIPPET.replace("fuentes públicas.", "fuentes públicas, riesgo de contaminación cruzada…")
    assert not _near_name(text, "El local se presenta como 100% sin gluten.", "La Carola")
