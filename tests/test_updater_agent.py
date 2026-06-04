"""Unit tests for the Updater agent (offline, all external calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.updater_agent import UpdaterAgent

TARGETS = {
    "categories": {
        "cafe": ["cafe", "bakery"],
        "shop": ["store"],
        "restaurant": ["restaurant"],
    }
}


def make_agent(targets=TARGETS, llm=None):
    db = MagicMock()
    places = MagicMock()
    agent = UpdaterAgent(db, places, targets, llm=llm)
    return agent, db, places


# --- Closure detection ----------------------------------------------------


def test_is_closed_detects_business_status():
    assert UpdaterAgent._is_closed({"business_status": "CLOSED_PERMANENTLY"}) is True


def test_is_closed_detects_permanently_closed_flag():
    assert UpdaterAgent._is_closed({"permanently_closed": True}) is True


def test_is_closed_false_for_operational():
    assert UpdaterAgent._is_closed({"business_status": "OPERATIONAL"}) is False
    assert UpdaterAgent._is_closed({}) is False


def test_closed_place_is_discarded_on_run():
    agent, db, places = make_agent()
    db.fetch_places_by_status.return_value = [
        {
            "id": "p1",
            "name": "Old Cafe",
            "source": "google_places",
            "external_id": "ext-1",
        }
    ]
    places.place_details.return_value = {
        "status": "OK",
        "result": {"business_status": "CLOSED_PERMANENTLY"},
    }

    summary = agent.run()

    assert summary["closed"] == 1
    assert summary["updated"] == 0
    _, kwargs = db.update_place_validation.call_args
    assert kwargs["status"] == "discarded"
    db.update_place.assert_not_called()


# --- Name / address change detection --------------------------------------


def test_patch_detects_name_change():
    agent, _, _ = make_agent()
    place = {"name": "Old", "address": "Addr 1", "category": "restaurant"}
    result = {"name": "New", "formatted_address": "Addr 1", "types": ["restaurant"]}
    assert agent._build_patch(place, result) == {"name": "New"}


def test_patch_detects_address_change():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": "Addr 1", "category": "restaurant"}
    result = {"name": "Same", "formatted_address": "Addr 2", "types": ["restaurant"]}
    assert agent._build_patch(place, result) == {"address": "Addr 2"}


def test_patch_detects_category_change():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": "Addr 1", "category": "restaurant"}
    result = {"name": "Same", "formatted_address": "Addr 1", "types": ["bakery"]}
    assert agent._build_patch(place, result) == {"category": "cafe"}


def test_patch_combines_multiple_changes():
    agent, _, _ = make_agent()
    place = {"name": "Old", "address": "Addr 1", "category": "restaurant"}
    result = {"name": "New", "formatted_address": "Addr 2", "types": ["store"]}
    assert agent._build_patch(place, result) == {
        "name": "New",
        "address": "Addr 2",
        "category": "shop",
    }


# --- No-op when nothing changed -------------------------------------------


def test_patch_is_empty_when_nothing_changed():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": "Addr 1", "category": "restaurant"}
    result = {"name": "Same", "formatted_address": "Addr 1", "types": ["restaurant"]}
    assert agent._build_patch(place, result) == {}


def test_patch_ignores_blank_incoming_fields():
    agent, _, _ = make_agent()
    place = {"name": "Keep", "address": "Addr 1", "category": "restaurant"}
    result = {"name": "", "formatted_address": "", "types": ["restaurant"]}
    assert agent._build_patch(place, result) == {}


def test_unchanged_place_is_a_noop_on_run():
    agent, db, places = make_agent()
    db.fetch_places_by_status.return_value = [
        {
            "id": "p1",
            "name": "Same",
            "address": "Addr 1",
            "category": "restaurant",
            "source": "google_places",
            "external_id": "ext-1",
        }
    ]
    places.place_details.return_value = {
        "status": "OK",
        "result": {
            "business_status": "OPERATIONAL",
            "name": "Same",
            "formatted_address": "Addr 1",
            "types": ["restaurant"],
        },
    }

    summary = agent.run()

    assert summary["unchanged"] == 1
    assert summary["updated"] == 0
    assert summary["closed"] == 0
    db.update_place.assert_not_called()
    db.update_place_validation.assert_not_called()


def test_manual_seed_places_are_skipped():
    agent, db, places = make_agent()
    db.fetch_places_by_status.return_value = [
        {"id": "p1", "name": "Seed", "source": "seed", "external_id": None}
    ]

    summary = agent.run()

    assert summary["checked"] == 0
    places.place_details.assert_not_called()
