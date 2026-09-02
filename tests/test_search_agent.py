"""Unit tests for the Search agent (offline, all external calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.clients.google_places import GooglePlacesClient
from agents.search_agent import DEFAULT_CATEGORY, SearchAgent

TARGETS = {
    "search_terms": ["sin tacc"],
    "countries": [
        {
            "name": "Uruguay",
            "cities": [
                {"name": "Montevideo", "lat": -34.9, "lng": -56.2, "radius_m": 5000}
            ],
        }
    ],
    "categories": {
        "cafe": ["cafe", "bakery"],
        "shop": ["grocery_or_supermarket", "store"],
        "restaurant": ["restaurant"],
    },
}


def make_result(
    place_id,
    name="Some Place",
    types=None,
    business_status="OPERATIONAL",
    lat=-34.9,
    lng=-56.2,
    formatted_address="Sarandí 600, Ciudad Vieja, Montevideo, Uruguay",
):
    # Default address is a parseable in-scope (Uruguay) one: to_candidate()
    # now discards a result whose own address does not resolve to
    # Uruguay/Argentina, so every result that should be inserted needs a
    # real UY/AR address.
    return {
        "place_id": place_id,
        "name": name,
        "types": types if types is not None else ["restaurant"],
        "business_status": business_status,
        "geometry": {"location": {"lat": lat, "lng": lng}},
        "formatted_address": formatted_address,
    }


def make_agent(
    targets=TARGETS,
    max_review_enrichments=0,
    max_detail_lookups=0,
    max_queries_per_run=0,
):
    db = MagicMock()
    # A truthy row means "inserted" in the agent's accounting.
    db.insert_place_candidate.return_value = {"id": "row-1"}
    places = MagicMock()
    agent = SearchAgent(
        db,
        places,
        targets,
        max_review_enrichments=max_review_enrichments,
        max_detail_lookups=max_detail_lookups,
        max_queries_per_run=max_queries_per_run,
    )
    return agent, db, places


# --- Deduplication --------------------------------------------------------


def test_duplicate_external_id_inserted_once_within_response():
    agent, db, places = make_agent()
    places.text_search.return_value = {
        "results": [make_result("DUP"), make_result("DUP"), make_result("UNIQUE")]
    }

    summary = agent.run()

    assert db.insert_place_candidate.call_count == 2
    assert summary["unique_candidates"] == 2
    assert summary["inserted"] == 2


def test_duplicate_external_id_dedup_across_queries():
    two_terms = {**TARGETS, "search_terms": ["sin tacc", "gluten free"]}
    agent, db, places = make_agent(two_terms)
    # Both queries return the very same two places.
    places.text_search.return_value = {
        "results": [make_result("X"), make_result("Y")]
    }

    summary = agent.run()

    assert places.text_search.call_count == 2  # two search terms
    assert db.insert_place_candidate.call_count == 2  # deduped across both
    assert summary["unique_candidates"] == 2


def test_result_without_place_id_is_skipped():
    agent, db, places = make_agent()
    no_id = make_result("X")
    no_id.pop("place_id")
    places.text_search.return_value = {"results": [no_id, make_result("Y")]}

    agent.run()

    assert db.insert_place_candidate.call_count == 1


# --- Per-run query cap ----------------------------------------------------

CAP_TARGETS = {
    "search_terms": ["t1", "t2", "t3"],
    "countries": [
        {
            "name": "UY",
            "cities": [
                {"name": "A", "lat": -34.9, "lng": -56.2, "radius_m": 5000},
                {"name": "B", "lat": -34.8, "lng": -56.1, "radius_m": 5000},
            ],
        }
    ],
    "categories": {},
}


def test_search_queries_capped_per_run():
    agent, db, places = make_agent(CAP_TARGETS, max_queries_per_run=3)
    places.text_search.return_value = {"results": []}

    summary = agent.run()

    # 2 cities x 3 terms = 6 jobs, capped to 3.
    assert summary["queries"] == 3
    assert places.text_search.call_count == 3


def test_search_jobs_are_term_major():
    agent, _, places = make_agent(CAP_TARGETS, max_queries_per_run=2)
    places.text_search.return_value = {"results": []}

    agent.run()

    # Term-major: the first term is applied across both cities before term 2.
    queries = [c.kwargs["query"] for c in places.text_search.call_args_list]
    assert queries == ["t1 A", "t1 B"]


def test_search_uncapped_when_zero():
    agent, _, places = make_agent(CAP_TARGETS, max_queries_per_run=0)
    places.text_search.return_value = {"results": []}

    summary = agent.run()

    assert summary["queries"] == 6  # all jobs run


def test_search_query_uses_search_as_override_when_present():
    # A city whose plain name is ambiguous ("Paraná" = an Argentine city AND
    # a Brazilian state) can carry a `search_as` in targets.yaml that
    # disambiguates the Text Search query, while `name` stays the label.
    targets = {
        "search_terms": ["sin tacc"],
        "countries": [
            {
                "name": "Argentina",
                "cities": [
                    {
                        "name": "Paraná",
                        "search_as": "Paraná, Entre Ríos, Argentina",
                        "lat": -31.7333,
                        "lng": -60.5333,
                        "radius_m": 10000,
                    }
                ],
            }
        ],
        "categories": {},
    }
    agent, db, places = make_agent(targets)
    places.text_search.return_value = {
        "results": [
            make_result(
                "P",
                formatted_address="San Martín 100, Paraná, Entre Ríos, Argentina",
                lat=-31.73,
                lng=-60.53,
            )
        ]
    }

    agent.run()

    assert places.text_search.call_args.kwargs["query"] == "sin tacc Paraná, Entre Ríos, Argentina"
    inserted = db.insert_place_candidate.call_args.args[0]
    assert inserted["city"] == "Paraná"          # from the result's own address
    assert inserted["country"] == "Argentina"


# --- Category mapping -----------------------------------------------------


def test_category_mapping_from_google_types():
    agent, _, _ = make_agent()
    assert agent._category_for({"types": ["bakery"]}) == "cafe"
    assert agent._category_for({"types": ["cafe"]}) == "cafe"
    assert agent._category_for({"types": ["store"]}) == "shop"
    assert agent._category_for({"types": ["restaurant"]}) == "restaurant"


def test_category_mapping_first_match_wins():
    agent, _, _ = make_agent()
    # "store" -> shop appears before "restaurant" in the types list.
    assert agent._category_for({"types": ["store", "restaurant"]}) == "shop"


def test_category_mapping_falls_back_to_default():
    agent, _, _ = make_agent()
    assert agent._category_for({"types": ["pharmacy"]}) == DEFAULT_CATEGORY
    assert agent._category_for({"types": []}) == DEFAULT_CATEGORY
    assert agent._category_for({}) == DEFAULT_CATEGORY


def test_category_written_onto_inserted_candidate():
    agent, db, places = make_agent()
    places.text_search.return_value = {
        "results": [make_result("B", types=["bakery"])]
    }

    agent.run()

    candidate = db.insert_place_candidate.call_args.args[0]
    assert candidate["category"] == "cafe"
    assert candidate["safety_level"] == "options_available"


# --- Skipping permanently closed places -----------------------------------


def test_permanently_closed_place_is_skipped():
    agent, db, places = make_agent()
    places.text_search.return_value = {
        "results": [
            make_result("CLOSED", business_status="CLOSED_PERMANENTLY"),
            make_result("OPEN"),
        ]
    }

    summary = agent.run()

    assert db.insert_place_candidate.call_count == 1
    inserted = db.insert_place_candidate.call_args.args[0]
    assert inserted["external_id"] == "OPEN"
    assert summary["skipped"] == 1
    assert summary["inserted"] == 1


def test_text_search_error_is_counted_and_does_not_crash():
    agent, db, places = make_agent()
    places.text_search.side_effect = RuntimeError("API down")

    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["inserted"] == 0
    db.insert_place_candidate.assert_not_called()


def test_run_discards_out_of_scope_result_and_counts_it():
    # A biased "Paraná" query returns a Curitiba (Brazil) business alongside a
    # legitimate in-scope one -- only the in-scope one is inserted.
    agent, db, places = make_agent()
    places.text_search.return_value = {
        "results": [
            make_result(
                "BR",
                formatted_address="R. Schiller, 1960 - Hugo Lange, Curitiba - PR, 80040-160, Brazil",
                lat=-25.4178097,
                lng=-49.2490747,
            ),
            make_result("UY"),  # default address is a real Montevideo one
        ]
    }

    summary = agent.run()

    assert db.insert_place_candidate.call_count == 1
    assert db.insert_place_candidate.call_args.args[0]["external_id"] == "UY"
    assert summary["out_of_scope"] == 1
    assert summary["inserted"] == 1


# --- Gluten-free review snippet filtering ---------------------------------


def test_extract_gf_snippets_keeps_only_matches():
    reviews = [
        {"text": "Great coffee and they have sin TACC options!", "rating": 5},
        {"text": "Lovely place, nice staff", "rating": 4},
        {"text": "Tienen menu apto celiacos", "rating": 5},
        {"text": "", "rating": 3},
    ]
    snippets = GooglePlacesClient.extract_gf_snippets(reviews)
    assert len(snippets) == 2
    assert snippets[0]["rating"] == 5


def test_extract_gf_snippets_is_accent_insensitive():
    reviews = [{"text": "Excelente, totalmente libre de gluten", "rating": 5}]
    assert len(GooglePlacesClient.extract_gf_snippets(reviews)) == 1


def test_extract_gf_snippets_clamps_invalid_rating():
    reviews = [{"text": "sin gluten", "rating": 9}]
    assert GooglePlacesClient.extract_gf_snippets(reviews)[0]["rating"] is None


def test_extract_gf_snippets_handles_none():
    assert GooglePlacesClient.extract_gf_snippets(None) == []


# --- city/country derivation (CLAUDE.md "Key risks": Search agent stamps
# city/country from the query target, not the result) ----------------------


def test_to_candidate_derives_country_from_result_address_not_target():
    # Regression for the real production bug: searching "Fray Bentos,
    # Uruguay" can legitimately return a business actually located across
    # the border in Gualeguaychú, Argentina (confirmed live for 16 rows,
    # see CLAUDE.md). to_candidate must reflect the RESULT's own address,
    # never the query target it happened to be searched under.
    result = {
        "name": "San Felipa - Sin gluten",
        "formatted_address": "Italia 38, E2820 Gualeguaychú, Entre Ríos, Argentina",
        "geometry": {"location": {"lat": -33.0092671, "lng": -58.5152646}},
        "place_id": "ChIJ_test_san_felipa",
    }

    candidate = GooglePlacesClient.to_candidate(result, city="Fray Bentos")

    assert candidate["country"] == "Argentina"
    assert candidate["city"] == "Gualeguaychú"


def test_parse_address_handles_missing_province_segment():
    # C.A.B.A. addresses have no separate province line (unlike "...Entre
    # Ríos, Argentina") -- the segment right before the country IS the city,
    # not a province to skip past.
    address = "Concepción Arenal 3519, C1427EKC Cdad. Autónoma de Buenos Aires, Argentina"
    city, country = GooglePlacesClient.parse_city_country_from_address(address)
    assert country == "Argentina"
    assert city == "Cdad. Autónoma de Buenos Aires"


def test_parse_address_strips_postal_code_prefix():
    city, country = GooglePlacesClient.parse_city_country_from_address(
        "Rocamora 257, E2820 Gualeguaychú, Entre Ríos, Argentina"
    )
    assert city == "Gualeguaychú"
    assert country == "Argentina"


def test_parse_address_returns_none_for_unrecognized_country():
    # Outside this project's Phase 1 scope (Uruguay/Argentina) -- refuse to
    # guess rather than fabricate a value.
    city, country = GooglePlacesClient.parse_city_country_from_address(
        "Av. Paulista 1000, São Paulo, Brazil"
    )
    assert (city, country) == (None, None)


def test_parse_address_returns_none_for_empty_address():
    assert GooglePlacesClient.parse_city_country_from_address("") == (None, None)
    assert GooglePlacesClient.parse_city_country_from_address(None) == (None, None)


def test_to_candidate_discards_result_outside_uy_ar():
    # CLAUDE.md "Brazil out-of-scope places — Curitiba cluster": Google Text
    # Search is location-BIASED, not bounded, so a query for an ambiguous
    # city name ("Paraná" = an Argentine city AND a Brazilian state) can
    # return a business in another country. to_candidate() must DISCARD it,
    # never fall back to the search target's city/country.
    result = {
        "name": "LEVAIN GLÚTEN FREE",
        "formatted_address": "R. Ver. Washington Mansur, 332 - Ahú, Curitiba - PR, 80540-210, Brazil",
        "geometry": {"location": {"lat": -25.4011981, "lng": -49.2592645}},
        "place_id": "ChIJ_curitiba_levain",
    }
    assert GooglePlacesClient.to_candidate(result, city="Paraná") is None


def test_to_candidate_discards_result_with_unparseable_address():
    # No recognizable country segment at all -> we cannot confirm the result
    # is in Uruguay/Argentina, so it is dropped rather than trusted to the
    # (possibly wrong) search target.
    result = {
        "name": "X",
        "formatted_address": "Av. Siempre Viva 123",
        "geometry": {"location": {"lat": -34.9, "lng": -56.2}},
        "place_id": "X",
    }
    assert GooglePlacesClient.to_candidate(result, city="Montevideo") is None


def test_to_candidate_keeps_normal_uy_ar_result():
    # Regression guard: an in-scope result is unaffected by the discard rule
    # and still derives its country/city from its own address.
    result = {
        "name": "Café Sano",
        "formatted_address": "Sarandí 600, Ciudad Vieja, Montevideo, Uruguay",
        "geometry": {"location": {"lat": -34.9055, "lng": -56.201}},
        "place_id": "ok-1",
    }
    candidate = GooglePlacesClient.to_candidate(result, city="Montevideo")
    assert candidate is not None
    assert candidate["country"] == "Uruguay"
    assert candidate["city"] == "Ciudad Vieja"
    assert candidate["name"] == "Café Sano"


# --- Review enrichment in the run -----------------------------------------


def test_review_enrichment_stores_matching_snippets():
    agent, db, places = make_agent(max_review_enrichments=5, max_detail_lookups=5)
    places.text_search.return_value = {"results": [make_result("A")]}
    places.place_details_with_reviews.return_value = {
        "result": {
            "reviews": [
                {"text": "Has sin TACC menu", "rating": 5},
                {"text": "unrelated", "rating": 4},
            ]
        }
    }

    summary = agent.run()

    places.place_details_with_reviews.assert_called_once_with("A")
    db.insert_review.assert_called_once()
    assert summary["reviews_enriched"] == 1
    assert summary["review_snippets"] == 1


def test_review_enrichment_disabled_by_default():
    agent, db, places = make_agent()  # max_detail_lookups=0 -> no details call
    places.text_search.return_value = {"results": [make_result("A")]}

    summary = agent.run()

    places.place_details_with_reviews.assert_not_called()
    db.insert_review.assert_not_called()
    assert summary["reviews_enriched"] == 0


def test_review_enrichment_error_does_not_crash_run():
    agent, db, places = make_agent(max_review_enrichments=5, max_detail_lookups=5)
    places.text_search.return_value = {"results": [make_result("A")]}
    places.place_details_with_reviews.side_effect = RuntimeError("details down")

    summary = agent.run()

    # The candidate is still inserted; enrichment failure is best-effort.
    assert summary["inserted"] == 1
    assert summary["reviews_enriched"] == 0


# --- Rich detail fields (phone/website/hours/rating) ----------------------


def test_extract_rich_fields_maps_present_values():
    result = {
        "formatted_phone_number": "2900 1234",
        "website": "https://example.uy",
        "opening_hours": {"open_now": True, "weekday_text": ["lunes: 9–18"]},
        "rating": 4.6,
        "user_ratings_total": 213,
    }
    rich = GooglePlacesClient.extract_rich_fields(result)
    assert rich == {
        "phone": "2900 1234",
        "website": "https://example.uy",
        "opening_hours": ["lunes: 9–18"],   # weekday_text only; open_now dropped
        "rating": 4.6,
        "user_ratings_total": 213,
    }


def test_extract_rich_fields_omits_missing():
    assert GooglePlacesClient.extract_rich_fields({}) == {}
    assert GooglePlacesClient.extract_rich_fields({"website": ""}) == {}


def test_extract_rich_fields_includes_city_country_from_address_components():
    result = {
        "address_components": [
            {"long_name": "Gualeguaychú", "short_name": "Gualeguaychú", "types": ["locality", "political"]},
            {"long_name": "Entre Ríos", "short_name": "Entre Ríos", "types": ["administrative_area_level_1", "political"]},
            {"long_name": "Argentina", "short_name": "AR", "types": ["country", "political"]},
        ]
    }
    rich = GooglePlacesClient.extract_rich_fields(result)
    assert rich["city"] == "Gualeguaychú"
    assert rich["country"] == "Argentina"


def test_extract_rich_fields_omits_city_country_when_components_absent():
    # No address_components in the Details response -> don't add the keys at
    # all, so update_place() never clobbers the value to_candidate() already
    # set with an empty/None patch.
    rich = GooglePlacesClient.extract_rich_fields({"rating": 4.5})
    assert "city" not in rich
    assert "country" not in rich


def test_city_country_from_components_rejects_postal_code_fragment_locality():
    # Regression: Google returned locality="CFX" (the trailing 3-letter
    # suffix of an Argentine CPA postal code) for "Palluzzi Libre de
    # gluten", corrected by hand in production to "Berisso" via
    # administrative_area_level_2. The fallback here reproduces that fix.
    city, country = GooglePlacesClient.city_country_from_components([
        {"long_name": "CFX", "types": ["locality", "political"]},
        {"long_name": "Berisso", "types": ["administrative_area_level_2", "political"]},
        {"long_name": "Argentina", "types": ["country", "political"]},
    ])
    assert city == "Berisso"
    assert country == "Argentina"


def test_city_country_from_components_accepts_normal_locality():
    # A real locality (Title Case, not a short all-caps fragment) is used
    # as-is -- confirms the sanity check doesn't reject legitimate cities.
    city, country = GooglePlacesClient.city_country_from_components([
        {"long_name": "Berisso", "types": ["locality", "political"]},
        {"long_name": "Buenos Aires", "types": ["administrative_area_level_2", "political"]},
        {"long_name": "Argentina", "types": ["country", "political"]},
    ])
    assert city == "Berisso"
    assert country == "Argentina"


def test_rich_fields_applied_to_inserted_candidate():
    agent, db, places = make_agent(max_detail_lookups=5)
    places.text_search.return_value = {"results": [make_result("A")]}
    places.place_details_with_reviews.return_value = {
        "result": {
            "formatted_phone_number": "2900 1234",
            "website": "https://example.uy",
            "rating": 4.6,
            "user_ratings_total": 50,
        }
    }

    summary = agent.run()

    places.place_details_with_reviews.assert_called_once_with("A")
    patch = db.update_place.call_args.args[1]
    assert patch["phone"] == "2900 1234"
    assert patch["website"] == "https://example.uy"
    assert patch["rating"] == 4.6
    assert summary["details_fetched"] == 1
    assert summary["rich_updated"] == 1


def test_run_patches_city_country_via_details_when_available():
    # End-to-end: the initial insert uses to_candidate()'s formatted_address
    # fallback (target was wrong: Uruguay/Fray Bentos), then the Details call
    # -- already happening for rich fields, no new API call -- corrects it
    # via the structured address_components, same update_place() patch.
    agent, db, places = make_agent(max_detail_lookups=5)
    result = make_result("A")
    result["formatted_address"] = "Italia 38, E2820 Gualeguaychú, Entre Ríos, Argentina"
    places.text_search.return_value = {"results": [result]}
    places.place_details_with_reviews.return_value = {
        "result": {
            "address_components": [
                {"long_name": "Gualeguaychú", "types": ["locality", "political"]},
                {"long_name": "Argentina", "types": ["country", "political"]},
            ]
        }
    }

    agent.run()

    insert_payload = db.insert_place_candidate.call_args.args[0]
    assert insert_payload["country"] == "Argentina"  # fallback already got it right
    assert insert_payload["city"] == "Gualeguaychú"

    patch = db.update_place.call_args.args[1]
    assert patch["city"] == "Gualeguaychú"
    assert patch["country"] == "Argentina"


def test_details_lookup_capped():
    agent, db, places = make_agent(max_detail_lookups=1)
    places.text_search.return_value = {
        "results": [make_result("A"), make_result("B")]
    }
    places.place_details_with_reviews.return_value = {"result": {"rating": 4.0}}

    summary = agent.run()

    assert summary["inserted"] == 2
    assert summary["details_fetched"] == 1   # capped at 1
    assert places.place_details_with_reviews.call_count == 1
