"""Map scope rules (2026-10-13): what never belongs on the map, whatever its gluten-free offer.

1a. General retail chains (supermarkets, hypermarkets, self-service stores, pharmacy chains).
1b. Places that teach or inform without selling or serving food to the public.
The deterministic layer is high precision on purpose: a food or specialised chain is never excluded by it.
"""

from __future__ import annotations

import pytest

from scope_fixtures import IN_SCOPE, OUT_OF_SCOPE, label
from agents.map_scope import CHAIN, NOT_A_SELLER, out_of_scope_reason, scope_flag, scope_note


@pytest.mark.parametrize(
    "name",
    [
        "Géant Fresh Market",
        "Geant",
        "Tata",
        "Ta-Ta Pocitos",
        "Supermercados Ta-Ta",
        "Devoto Express Punta Carretas",
        "Disco",
        "Disco N° 5 Pocitos",
        "Supermercado Disco",
        "Tienda Inglesa",
        "Tienda Inglesa Montevideo Shopping",
        "Carrefour Market",
        "Hipermercado Carrefour",
        "Coto",
        "Coto Sucursal 64",
        "Jumbo Palermo",
        "Día",
        "Supermercados DIA",
        "Dia %",
        "Vea",
        "Farmashop 12",
        "Farmacity",
    ],
)
def test_a_general_retail_chain_is_out_of_scope(name):
    reason = out_of_scope_reason(name)
    assert reason is not None, name
    assert reason.kind == CHAIN


@pytest.mark.parametrize(
    "name",
    [
        "Zero Helados",
        "Zero Helados Pocitos",
        "Ramona",
        "Ramona Sin Gluten",
        "Mi Cocina Sin Gluten",
        "Pan de Cada Día",
        "La Tata",
        "Tata Panadería",
        "Disco Bar",
        "Disco Natural Dietética",
        "Día Verde Almacén Natural",
        "El Coto de Caza Parrilla",
        "Almacén Vea Bien",
        "Jumbo Burger",
        "Dietética La Inglesa",
        "Café Devoto",
        "Cafe X",
        "By Gessi Cocina Inclusiva",  # the name does not say it is a school: the model decides, from the evidence
        "",
        None,
    ],
)
def test_a_food_or_specialised_business_is_never_excluded_by_the_name_list(name):
    assert out_of_scope_reason(name) is None, name


# Admin decision 2026-10-13: three real places the audit listed as doubtful stay on the map. A name with "supermarket" or
# "minimarket", a Google type of general retail or a brand with several branches does not make a specialised shop a chain.
ADMIN_IN_SCOPE = [
    ("EntreSano Healthy Supermarket", "https://entresano.com/"),
    ("EntreSano Av. Colon", "http://www.entresano.com/"),
    ("Minimarket La Isla 24 hours.", "https://www.laisla247.com/"),
    ("La Molienda - Carrasco", "https://www.lamolienda.uy/tiendas"),
    ("La Molienda - ACJ (Colonia)", None),
    ("La Molienda - Costa Urbana", None),
]


@pytest.mark.parametrize("name, website", ADMIN_IN_SCOPE)
@pytest.mark.parametrize("types", [(), ("supermarket", "grocery_or_supermarket", "store"), ("convenience_store", "food", "store")])
def test_the_places_the_admin_kept_on_the_map_are_never_excluded(name, website, types):
    assert out_of_scope_reason(name, types=types, website=website) is None, name


@pytest.mark.parametrize(
    "website",
    ["https://www.geant.com.uy/", "http://tata.com.uy/sucursales", "https://www.carrefour.com.ar", "https://diaonline.supermercadosdia.com.ar/"],
)
def test_the_chains_own_site_is_enough(website):
    reason = out_of_scope_reason("Fresh Market", website=website)
    assert reason is not None and reason.kind == CHAIN


def test_an_ambiguous_brand_is_confirmed_by_the_google_type():
    # "Vea Palermo" could be anything; a supermarket type settles it. The type alone never excludes.
    assert out_of_scope_reason("Vea Palermo", types=["supermarket", "store"]).kind == CHAIN
    assert out_of_scope_reason("Dietética Palermo", types=["grocery_or_supermarket", "store"]) is None


@pytest.mark.parametrize(
    "name",
    [
        "Escuela de Cocina Sin Gluten",
        "Academia de Pastelería Sin TACC",
        "Cursos de cocina sin gluten",
        "Taller de cocina apta celíacos",
        "Blog Celíaco Feliz",
        "Recetas Sin Gluten Uruguay",
    ],
)
def test_a_school_a_blog_or_a_recipe_account_is_out_of_scope(name):
    reason = out_of_scope_reason(name)
    assert reason is not None, name
    assert reason.kind == NOT_A_SELLER


def test_a_rows_topic_page_address_does_not_exclude_it():
    """Audit of 2026-10-13: 20 rows carry a topic page in ``social_url`` and nearly all are real businesses (the lead came from that
    page; the business was then resolved on Google). The topic page itself is dropped by the Social agent, before it is a lead."""
    import inspect

    assert "social_url" not in inspect.signature(out_of_scope_reason).parameters


def test_a_school_by_google_type_is_out_of_scope_unless_it_is_also_a_food_place():
    assert out_of_scope_reason("By Gessi", types=["school", "point_of_interest", "establishment"]).kind == NOT_A_SELLER
    assert out_of_scope_reason("By Gessi", types=["school", "bakery", "food"]) is None


@pytest.mark.parametrize("name", ["Panadería La Escuela", "Café del Taller", "Restaurante Recetas de la Abuela", "Heladería Blog"])
def test_a_food_word_in_the_name_keeps_it_in_scope(name):
    assert out_of_scope_reason(name) is None, name


def test_the_note_and_the_flag_say_it_does_not_apply_and_why():
    reason = out_of_scope_reason("Géant Fresh Market")
    assert scope_note(reason.kind, reason.detail).startswith("No aplica al mapa: ")
    assert "Géant" in scope_note(reason.kind, reason.detail)
    assert scope_flag(CHAIN) == "no aplica al mapa: comercio general"
    assert scope_flag(NOT_A_SELLER) == "no aplica al mapa: no vende ni sirve al público"


@pytest.mark.parametrize("place", OUT_OF_SCOPE, ids=label)
def test_the_ab_places_out_of_scope_are_excluded(place):
    reason = out_of_scope_reason(place["name"], website=place.get("website"))
    assert reason is not None and reason.kind == CHAIN, place["name"]


@pytest.mark.parametrize("place", IN_SCOPE, ids=label)
@pytest.mark.parametrize("types", [(), ("supermarket", "grocery_or_supermarket", "store", "food")])
def test_the_ab_places_in_scope_are_never_excluded(place, types):
    assert out_of_scope_reason(place["name"], types=types, website=place.get("website")) is None, place["name"]


@pytest.mark.parametrize(
    "name", ["Autoservicio El Trébol", "Autoservicio Los Pinos", "Minimercado Lo de Pepe", "Supermercado El Ahorro", "Supermercados Toledo"]
)
def test_an_independent_self_service_shop_or_supermarket_is_general_retail(name):
    reason = out_of_scope_reason(name)
    assert reason is not None and reason.kind == CHAIN, name
    assert reason.detail.startswith("comercio general")


@pytest.mark.parametrize(
    "name",
    [
        "Minimarket La Isla 24 hours.",   # "minimarket" is deliberately not a general retail word
        "Supermercado Natural Vida",
        "Autoservicio Sin Gluten",
        "Supermercado Celíaco",
        "Minimercado Dietética San José",
        "Supermercado Saludable Verde",
        "Autoservicio y Panadería La Familia",
        "El Autoservicio de la Esquina",  # the rule looks only at the first word
        "EntreSano Healthy Supermarket",
    ],
)
def test_a_specialised_word_or_another_first_word_keeps_the_shop_in_scope(name):
    assert out_of_scope_reason(name) is None, name
