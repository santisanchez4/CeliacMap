"""Unit tests for `places.region` (the department / province of a place), derived offline.

The region is what lets the chatbot answer "lugares en Cerro Largo" when every place there is filed
under a smaller city (Melo). It is derived from Google's own address, never from the search target,
and never guessed: an address that does not name its region gives None. The address shapes below are
real ones from the production table (audit 2026-09-26: 422 of 422 approved places are recoverable).
"""

from __future__ import annotations

import pytest

from agents.clients.google_places import (
    AR_PROVINCES,
    AR_REGION_NAMES,
    CABA_REGION,
    UY_DEPARTMENTS,
    UY_REGION_NAMES,
    GooglePlacesClient,
)

region_from_address = GooglePlacesClient.region_from_address
region_from_components = GooglePlacesClient.region_from_components


# --- the canonical names --------------------------------------------------------


def test_canonical_names_cover_every_province_and_department_with_their_accents():
    assert len(AR_REGION_NAMES) == 23 and set(AR_REGION_NAMES) == AR_PROVINCES
    assert len(UY_REGION_NAMES) == 19 and set(UY_REGION_NAMES) == UY_DEPARTMENTS
    assert AR_REGION_NAMES["cordoba"] == "Córdoba"
    assert AR_REGION_NAMES["entre rios"] == "Entre Ríos"
    assert AR_REGION_NAMES["tucuman"] == "Tucumán"
    assert UY_REGION_NAMES["paysandu"] == "Paysandú"
    assert UY_REGION_NAMES["san jose"] == "San José"
    assert UY_REGION_NAMES["treinta y tres"] == "Treinta y Tres"
    assert CABA_REGION == "Ciudad Autónoma de Buenos Aires"


# --- region_from_address: addresses that name their region ----------------------


@pytest.mark.parametrize(
    "address, expected",
    [
        # Uruguay: "Departamento de X", and the English "X Department".
        ("Dr. Luis Alberto de Herrera 859, 37000 Melo, Departamento de Cerro Largo, Uruguay", "Cerro Largo"),
        ("43P6+R2Q, 20400 Maldonado, Maldonado Department, Uruguay", "Maldonado"),
        ("Paysandú 1846 bis, 11200 Montevideo, Departamento de Montevideo, Uruguay", "Montevideo"),
        # A street named like ANOTHER region must not win over the real region line.
        ("Rio Negro 1185, 75100 Dolores, Departamento de Soriano, Uruguay", "Soriano"),
        ("Gral. Fructuoso Rivera 1967, 65000 Fray Bentos, Departamento de Río Negro, Uruguay", "Río Negro"),
        # Argentina: the province line, with and without the "Provincia de" wrapper.
        ("Alvaro Barros 256, R8500 Viedma, Río Negro, Argentina", "Río Negro"),
        ("Los Ciruelos 125, E3100 Oro Verde, Entre Ríos, Argentina", "Entre Ríos"),
        ("25 de Mayo 12, B1642 Buenos Aires, Provincia de Buenos Aires, Argentina", "Buenos Aires"),
        ("Blas Parera 1118, B1682BQL Villa Bosch, Provincia de Buenos Aires, Argentina", "Buenos Aires"),
        ("Belgrano 100, Villa Carlos Paz, Provincia de Córdoba", "Córdoba"),
        # No province line: the city IS the province's namesake (Córdoba capital), which still means Córdoba.
        ("Av. Duarte Quirós 53, X5022 Córdoba, Argentina", "Córdoba"),
        ("X5000 Córdoba, Córdoba Province, Argentina", "Córdoba"),
        ("Montevideo, Uruguay", "Montevideo"),
        # CABA is its own region, never the province of the same name.
        ("Av. Corrientes 4508, C1195AAR Cdad. Autónoma de Buenos Aires, Argentina", CABA_REGION),
        ("Av. Córdoba 1429, C1055 Cdad. Autónoma de Buenos Aires, Argentina", CABA_REGION),
        ("Salta 529, C1074 Cdad. Autónoma de Buenos Aires, Argentina", CABA_REGION),
    ],
)
def test_region_from_address_reads_the_region_line(address, expected):
    assert region_from_address(address) == expected


# --- region_from_address: never guess -------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        None,
        "",
        "Solo una parte",
        # Out of scope: Brazil and Chile have no region we track.
        "R. Schiller, 1960 - Hugo Lange, Curitiba - PR, 80040-160, Brazil",
        "San Patricio 4270, 7630275 Vitacura, Región Metropolitana, Chile",
        # A bare "Buenos Aires" with no "Provincia de" is CABA in English results and the province in others.
        "Florida 1, C1005 Buenos Aires, Argentina",
        # A city that is not a department of the country in the address.
        "Rivera 1967, Fray Bentos, Uruguay",
        "Ruta 1, Salto, Argentina",
    ],
)
def test_region_from_address_is_none_when_the_address_does_not_name_a_region(address):
    assert region_from_address(address) is None


def test_rio_negro_is_the_same_string_in_both_countries_the_row_country_tells_them_apart():
    assert region_from_address("Foo 1, Río Negro") == "Río Negro"
    assert region_from_address("Foo 1, Río Negro", "Uruguay") == "Río Negro"
    assert region_from_address("Foo 1, Río Negro", "Argentina") == "Río Negro"


def test_region_from_address_ignores_a_region_of_the_other_country():
    # Artigas is a Uruguayan department, not an Argentine province: by the address's own country line
    # or by the hint, it is not a region there.
    assert region_from_address("Foo 1, Artigas, Argentina") is None
    assert region_from_address("Foo 1, Artigas", "Argentina") is None


def test_region_from_address_is_none_when_the_address_country_contradicts_the_known_country():
    # 11 discarded production rows say country=Uruguay but carry an Argentine address (pre-fix stamping
    # from the search target). Conflicting evidence gives no region rather than an incoherent pair.
    assert region_from_address("Río Horcones 874, M5504 Godoy Cruz, Mendoza, Argentina", "Uruguay") is None
    assert region_from_address("Av. Córdoba 1429, C1055 Cdad. Autónoma de Buenos Aires, Argentina", "Uruguay") is None
    assert region_from_address("Río Horcones 874, M5504 Godoy Cruz, Mendoza, Argentina", "Argentina") == "Mendoza"


def test_region_from_address_is_none_for_a_country_we_do_not_cover():
    assert region_from_address("Foo 1, Salta", "Chile") is None


# --- region_from_components -----------------------------------------------------


def _component(long_name, *types, short_name=None):
    return {"long_name": long_name, "short_name": short_name or long_name, "types": list(types)}


def test_region_from_components_reads_administrative_area_level_1():
    components = [
        _component("Melo", "locality", "political"),
        _component("Departamento de Cerro Largo", "administrative_area_level_1", "political"),
        _component("Uruguay", "country", "political"),
    ]
    assert region_from_components(components) == "Cerro Largo"
    assert region_from_components(
        [_component("Córdoba", "administrative_area_level_1"), _component("Argentina", "country")]
    ) == "Córdoba"


def test_region_from_components_tells_caba_from_the_province():
    argentina = _component("Argentina", "country")
    caba_long = [_component("Ciudad Autónoma de Buenos Aires", "administrative_area_level_1"), argentina]
    caba_short = [_component("Buenos Aires", "administrative_area_level_1", short_name="CABA"), argentina]
    province = [_component("Provincia de Buenos Aires", "administrative_area_level_1"), argentina]
    assert region_from_components(caba_long) == CABA_REGION
    assert region_from_components(caba_short) == CABA_REGION
    assert region_from_components(province) == "Buenos Aires"


def test_region_from_components_is_none_when_ambiguous_or_missing():
    argentina = _component("Argentina", "country")
    assert region_from_components([_component("Buenos Aires", "administrative_area_level_1", short_name="BA"), argentina]) is None
    assert region_from_components([_component("Región Metropolitana", "administrative_area_level_1"), _component("Chile", "country")]) is None
    assert region_from_components([_component("Melo", "locality")]) is None
    assert region_from_components(None) is None
    assert region_from_components([]) is None


# --- Search: to_candidate -------------------------------------------------------


def test_to_candidate_carries_the_region_of_the_result_address():
    result = {
        "name": "Mi espacio sin TACC",
        "place_id": "ext-1",
        "formatted_address": "Rio Negro 1185, 75100 Dolores, Departamento de Soriano, Uruguay",
        "geometry": {"location": {"lat": -33.54, "lng": -58.22}},
    }
    candidate = GooglePlacesClient.to_candidate(result, city="Fray Bentos")
    assert candidate["region"] == "Soriano"
    assert candidate["country"] == "Uruguay"


def test_to_candidate_omits_the_region_when_the_address_does_not_name_one():
    result = {
        "name": "Bienestar",
        "place_id": "ext-2",
        "formatted_address": "Rivera 1967, Fray Bentos, Uruguay",
        "geometry": {"location": {"lat": -33.12, "lng": -58.3}},
    }
    candidate = GooglePlacesClient.to_candidate(result, city="Fray Bentos")
    assert candidate is not None and "region" not in candidate


# --- the enrichment / Updater merge path: extract_rich_fields --------------------


def test_extract_rich_fields_derives_the_region_from_the_address_first():
    rich = GooglePlacesClient.extract_rich_fields(
        {"formatted_address": "Dr. Luis Alberto de Herrera 859, 37000 Melo, Departamento de Cerro Largo, Uruguay"}
    )
    assert rich["region"] == "Cerro Largo"


def test_extract_rich_fields_falls_back_to_the_components():
    rich = GooglePlacesClient.extract_rich_fields(
        {
            "formatted_address": "Rivera 1967, Fray Bentos, Uruguay",
            "address_components": [
                _component("Departamento de Río Negro", "administrative_area_level_1"),
                _component("Uruguay", "country"),
            ],
        }
    )
    assert rich["region"] == "Río Negro"


def test_extract_rich_fields_has_no_region_key_when_nothing_names_one():
    assert "region" not in GooglePlacesClient.extract_rich_fields({"formatted_address": "Addr 1"})
