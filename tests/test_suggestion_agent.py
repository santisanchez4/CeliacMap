"""Unit tests for the Suggestion promoter (offline, all external calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

from agents.suggestion_agent import (
    DEFAULT_CATEGORY,
    DEFAULT_SAFETY_LEVEL,
    SuggestionAgent,
    promote_suggestion,
)


def make_match(place_id="ext-1", name="Cafe X", lat=-34.9, lng=-56.2):
    return {
        "place_id": place_id,
        "name": name,
        "formatted_address": "Av. Siempre Viva 123",
        "geometry": {"location": {"lat": lat, "lng": lng}},
    }


def make_db(exists=False, inserted_id="row-1"):
    db = MagicMock()
    db.place_exists_by_external_id.return_value = exists
    db.insert_place_candidate.return_value = (
        {"id": inserted_id} if inserted_id else None
    )
    return db


_DEFAULT = object()


def make_places(match=_DEFAULT):
    places = MagicMock()
    places.find_place.return_value = make_match() if match is _DEFAULT else match
    return places


# --- promote_suggestion ---------------------------------------------------


def test_promote_inserts_user_candidate():
    db, places = make_db(), make_places()
    result = promote_suggestion(
        db, places,
        name="Cafe X", city="Montevideo", country="Uruguay",
        evidence_url="https://instagram.com/cafex", notes="menú sin TACC",
    )
    assert result["outcome"] == "promoted"
    assert result["place_id"] == "row-1"
    assert result["external_id"] == "ext-1"

    candidate = db.insert_place_candidate.call_args.args[0]
    assert candidate["source"] == "user"
    assert candidate["external_id"] == "ext-1"
    assert candidate["lat"] == -34.9 and candidate["lng"] == -56.2
    assert candidate["safety_level"] == DEFAULT_SAFETY_LEVEL
    assert candidate["social_url"] == "https://instagram.com/cafex"
    assert candidate["validation_notes"] == "menú sin TACC"


def test_promote_defaults_missing_or_bad_category():
    db, places = make_db(), make_places()
    promote_suggestion(db, places, name="X", city="C", country="Uruguay")
    assert db.insert_place_candidate.call_args.args[0]["category"] == DEFAULT_CATEGORY

    db2 = make_db()
    promote_suggestion(db2, make_places(), name="X", city="C",
                       country="Uruguay", category="bar")
    assert db2.insert_place_candidate.call_args.args[0]["category"] == DEFAULT_CATEGORY


def test_promote_keeps_valid_category():
    db, places = make_db(), make_places()
    promote_suggestion(db, places, name="X", city="C",
                       country="Uruguay", category="cafe")
    assert db.insert_place_candidate.call_args.args[0]["category"] == "cafe"


def test_promote_unresolved_when_no_place_id():
    db, places = make_db(), make_places(match=None)
    result = promote_suggestion(db, places, name="Ghost", city="C", country="Uruguay")
    assert result["outcome"] == "unresolved"
    db.insert_place_candidate.assert_not_called()


def test_promote_duplicate_when_external_id_exists():
    db, places = make_db(exists=True), make_places()
    result = promote_suggestion(db, places, name="X", city="C", country="Uruguay")
    assert result["outcome"] == "duplicate"
    assert result["external_id"] == "ext-1"
    db.insert_place_candidate.assert_not_called()


def test_promote_insert_failed_when_no_row_returned():
    db, places = make_db(inserted_id=None), make_places()
    result = promote_suggestion(db, places, name="X", city="C", country="Uruguay")
    assert result["outcome"] == "insert_failed"


# --- SuggestionAgent.run --------------------------------------------------


def make_suggestion(sid="s-1", name="Cafe X", city="Montevideo", country="Uruguay",
                    category=None, evidence_url=None, notes=None):
    return {
        "id": sid, "name": name, "city": city, "country": country,
        "category": category, "evidence_url": evidence_url, "notes": notes,
    }


def test_run_promotes_and_marks_suggestion():
    db, places = make_db(), make_places()
    db.fetch_new_suggestions.return_value = [make_suggestion()]

    summary = SuggestionAgent(db, places, max_per_run=10).run()

    assert summary["seen"] == 1
    assert summary["promoted"] == 1
    assert summary["geocodes"] == 1
    db.update_suggestion_status.assert_called_once_with("s-1", "promoted", "row-1")


def test_run_marks_duplicate():
    db, places = make_db(exists=True), make_places()
    db.fetch_new_suggestions.return_value = [make_suggestion()]

    summary = SuggestionAgent(db, places, max_per_run=10).run()

    assert summary["duplicate"] == 1
    db.update_suggestion_status.assert_called_once_with("s-1", "duplicate")
    db.insert_place_candidate.assert_not_called()


def test_run_marks_unresolved_as_rejected():
    db, places = make_db(), make_places(match=None)
    db.fetch_new_suggestions.return_value = [make_suggestion()]

    summary = SuggestionAgent(db, places, max_per_run=10).run()

    assert summary["rejected"] == 1
    db.update_suggestion_status.assert_called_once_with("s-1", "rejected")


def test_run_counts_geocode_error_and_leaves_suggestion():
    db, places = make_db(), make_places()
    places.find_place.side_effect = RuntimeError("places down")
    db.fetch_new_suggestions.return_value = [make_suggestion()]

    summary = SuggestionAgent(db, places, max_per_run=10).run()

    assert summary["errors"] == 1
    assert summary["promoted"] == 0
    # A failed promotion must not flip the suggestion's status (it retries next run).
    db.update_suggestion_status.assert_not_called()


def test_run_zero_cap_does_nothing():
    db, places = make_db(), make_places()
    summary = SuggestionAgent(db, places, max_per_run=0).run()
    assert summary == {"seen": 0, "promoted": 0, "duplicate": 0,
                       "rejected": 0, "skipped": 0, "geocodes": 0, "errors": 0}
    db.fetch_new_suggestions.assert_not_called()
