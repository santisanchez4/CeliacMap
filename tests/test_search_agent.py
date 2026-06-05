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
):
    return {
        "place_id": place_id,
        "name": name,
        "types": types if types is not None else ["restaurant"],
        "business_status": business_status,
        "geometry": {"location": {"lat": lat, "lng": lng}},
        "formatted_address": "Av. Siempre Viva 123",
    }


def make_agent(targets=TARGETS, max_review_enrichments=0, max_detail_lookups=0):
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
