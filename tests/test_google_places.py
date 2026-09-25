"""Unit tests for GooglePlacesClient.resolve_location (offline, client mocked).

resolve_location is the shared geocode entrypoint for the Social, Web and
Suggestion agents: Find Place first, then the Geocoding API on the street
address alone as an ``address_only`` fallback (see CLAUDE.md Decisions Log —
"geocode-gate: address fallback").
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agents.clients.google_places import GooglePlacesClient

# googlemaps.Client validates the key *shape* at construction (must look like a
# real "AIza..." key), so tests use a shaped-but-fake key and swap _client.
_FAKE_KEY = "AIza" + "x" * 35


def make_client():
    client = GooglePlacesClient(_FAKE_KEY)
    client._client = MagicMock()
    client._client.find_place.return_value = {"candidates": []}
    client._client.geocode.return_value = []
    return client


def find_place_candidate(
    place_id="biz-1",
    name="Café X",
    lat=-34.9,
    lng=-56.2,
    formatted_address="Av. 18 de Julio 1234, Montevideo, Uruguay",
    business_status="OPERATIONAL",
):
    return {
        "candidates": [
            {
                "place_id": place_id,
                "name": name,
                "formatted_address": formatted_address,
                "geometry": {"location": {"lat": lat, "lng": lng}},
                "business_status": business_status,
            }
        ]
    }


def geocode_result(
    place_id="addr-1",
    lat=-33.1248446,
    lng=-58.2984276,
    location_type="ROOFTOP",
    country="Uruguay",
    city="Fray Bentos",
    formatted_address="Gral. Fructuoso Rivera 1967, 65000 Fray Bentos, Uruguay",
):
    components = [{"long_name": country, "types": ["country"]}]
    if city:
        components.append({"long_name": city, "types": ["locality"]})
    return [
        {
            "place_id": place_id,
            "formatted_address": formatted_address,
            "geometry": {
                "location": {"lat": lat, "lng": lng},
                "location_type": location_type,
            },
            "address_components": components,
        }
    ]


# --- 1. Find Place wins -------------------------------------------------------


def test_resolve_uses_find_place_when_business_matches():
    client = make_client()
    client._client.find_place.return_value = find_place_candidate()

    resolved = client.resolve_location(
        "Café X", "Av. 18 de Julio 1234", "Montevideo", "Uruguay"
    )

    assert resolved is not None
    assert resolved.geocode_method == "find_place"
    assert resolved.place_id == "biz-1"
    assert resolved.name == "Café X"
    assert (resolved.lat, resolved.lng) == (-34.9, -56.2)
    assert resolved.country == "Uruguay"
    # The address fallback must not even be attempted when Find Place matched.
    client._client.geocode.assert_not_called()


def test_resolve_find_place_query_combines_name_address_city():
    client = make_client()
    client._client.find_place.return_value = find_place_candidate()

    client.resolve_location("Café X", "Av. 18 de Julio 1234", "Montevideo", "Uruguay")

    sent = client._client.find_place.call_args.kwargs["input"]
    assert "Café X" in sent and "Av. 18 de Julio 1234" in sent and "Montevideo" in sent


# --- 2. Address-only fallback (the "Bienestar Gluten Free" case) -------------


def test_resolve_falls_back_to_geocode_when_find_place_empty():
    client = make_client()
    client._client.find_place.return_value = {"candidates": []}
    client._client.geocode.return_value = geocode_result()

    resolved = client.resolve_location(
        "Bienestar Gluten Free", "Rivera 1967", "Fray Bentos", "Uruguay"
    )

    assert resolved is not None
    assert resolved.geocode_method == "address_only"
    assert resolved.place_id == "addr-1"
    assert (resolved.lat, resolved.lng) == (-33.1248446, -58.2984276)
    assert resolved.city == "Fray Bentos"
    assert resolved.country == "Uruguay"
    assert resolved.name is None
    assert resolved.business_status is None
    # Scope guard: the Geocoding call is restricted to the country server-side.
    assert client._client.geocode.call_args.kwargs["components"] == {"country": "UY"}


# --- 3. Reject a geocode outside Uruguay/Argentina --------------------------


def test_resolve_rejects_geocode_outside_scope():
    client = make_client()
    client._client.find_place.return_value = {"candidates": []}
    client._client.geocode.return_value = geocode_result(country="Brazil", city="Chuí")

    resolved = client.resolve_location(
        "Ghost Place", "Rua 1", "Chuí", "Brazil"
    )

    assert resolved is None


# --- 4. Reject an APPROXIMATE (centroid-level) geocode ---------------------


def test_resolve_rejects_geocode_approximate():
    client = make_client()
    client._client.find_place.return_value = {"candidates": []}
    client._client.geocode.return_value = geocode_result(location_type="APPROXIMATE")

    resolved = client.resolve_location(
        "Bienestar Gluten Free", "Rivera 1967", "Fray Bentos", "Uruguay"
    )

    assert resolved is None


def test_resolve_accepts_range_interpolated_and_geometric_center():
    for loc_type in ("RANGE_INTERPOLATED", "GEOMETRIC_CENTER"):
        client = make_client()
        client._client.find_place.return_value = {"candidates": []}
        client._client.geocode.return_value = geocode_result(location_type=loc_type)
        resolved = client.resolve_location(
            "Bienestar Gluten Free", "Rivera 1967", "Fray Bentos", "Uruguay"
        )
        assert resolved is not None, loc_type
        assert resolved.geocode_method == "address_only"


# --- 5. No address -> no fallback, stays unresolved ------------------------


def test_resolve_none_when_no_address():
    client = make_client()
    client._client.find_place.return_value = {"candidates": []}

    resolved = client.resolve_location("Ghost", None, "Montevideo", "Uruguay")

    assert resolved is None
    client._client.geocode.assert_not_called()


# --- extra: a geocode error degrades to unresolved, never raises ----------


def test_resolve_geocode_error_returns_none():
    client = make_client()
    client._client.find_place.return_value = {"candidates": []}
    client._client.geocode.side_effect = RuntimeError("geocoding api down")

    resolved = client.resolve_location(
        "Bienestar Gluten Free", "Rivera 1967", "Fray Bentos", "Uruguay"
    )

    assert resolved is None


# --- Name check: Find Place must return the business we searched for ----------

import pytest  # noqa: E402

from agents.clients.google_places import names_match  # noqa: E402


@pytest.mark.parametrize(
    "searched, found",
    [
        ("Los Leños", "Los Leños Parrilla"),
        ("Dalbertt", "Dalbert Pastas"),  # one typo in a long word
        ("Café Ramona", "Ramona Café - Centro"),
        ("viaSana", "Via Sana"),
        ("Pastas Lo de Flor", "Lo de Flor"),
        ("Casa & Dispensa", "Casa y Dispensa"),
        ("La Espiga", "Panadería La Espiga Sin TACC"),
        ("Glúten Pra Quê?", "Gluten Pra Que"),
    ],
)
def test_names_match_same_business(searched, found):
    assert names_match(searched, found)


@pytest.mark.parametrize(
    "searched, found",
    [
        ("Bienestar Gluten Free", "víaSana"),  # the real 2026-09-01 mis-match
        ("Serendipia Gluten Free", "Selkkis Gluten Free"),
        ("Serendipia Gluten Free", "Delirio Sin Gluten"),
        ("Sin Gluten Palermo", "Sin Gluten Belgrano"),  # generic words don't count
    ],
)
def test_names_match_different_business(searched, found):
    assert not names_match(searched, found)


def test_names_match_unknown_name_is_accepted():
    assert names_match("Café X", None)
    assert names_match(None, "Café X")


def test_resolve_drops_find_place_match_with_another_name_and_geocodes_address():
    client = make_client()
    client._client.find_place.return_value = find_place_candidate(
        place_id="viasana", name="víaSana", formatted_address="Rivera 500, Rivera, Uruguay"
    )
    client._client.geocode.return_value = geocode_result()

    resolved = client.resolve_location(
        "Bienestar Gluten Free", "Rivera 1967", "Fray Bentos", "Uruguay"
    )

    assert resolved.geocode_method == "address_only"
    assert resolved.place_id == "addr-1"
    assert resolved.city == "Fray Bentos"


def test_resolve_drops_mismatched_find_place_and_returns_none_without_address():
    client = make_client()
    client._client.find_place.return_value = find_place_candidate(name="víaSana")

    assert client.resolve_location("Bienestar Gluten Free", None, "Fray Bentos", "Uruguay") is None
    client._client.geocode.assert_not_called()
