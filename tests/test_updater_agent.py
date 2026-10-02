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


# --- Rich detail fields ---------------------------------------------------


@pytest.mark.parametrize("notes", [
    "APROBACIÓN MANUAL (2026-10-01): confirmado por el administrador.",
    "Nota reciente\n\n--- aprobacion manual: confirmada anteriormente.",
])
def test_manual_approval_preserves_contact_fields_but_refreshes_rating(notes):
    agent, _, _ = make_agent()
    place = {"validation_notes": notes, "website": None, "phone": "Manual",
             "opening_hours": ["Horario confirmado"], "rating": 4.0}
    patch = agent._build_patch(place, {
        "website": "https://old.example", "formatted_phone_number": "Google",
        "opening_hours": {"weekday_text": ["Horario Google"]}, "rating": 4.5,
    })
    assert patch == {"rating": 4.5}


def test_rikuras_manual_website_survives_a_real_updater_run():
    agent, db, places = make_agent()
    db.fetch_places_by_status.return_value = [{
        "id": "339efc28-af19-4ce4-96ea-a9c1aa5176d4",
        "source": "google_places", "external_id": "ext-rikuras",
        "website": "https://rikurassingluten.pidedirecto.uy/", "phone": "Old",
    }]
    places.place_details.return_value = {"status": "OK", "result": {
        "website": "https://rikurassingluten.ambit.la/",
        "formatted_phone_number": "New", "rating": 4.5,
    }}
    assert agent.run()["updated"] == 1
    db.update_place.assert_called_once_with(
        "339efc28-af19-4ce4-96ea-a9c1aa5176d4", {"phone": "New", "rating": 4.5})


def test_same_business_name_does_not_protect_another_branch():
    agent, _, _ = make_agent()
    assert agent._build_patch(
        {"id": "another-branch", "name": "Rikuras Sin Gluten", "website": "manual"},
        {"website": "https://new.example"},
    ) == {"website": "https://new.example"}


def test_geography_correction_does_not_freeze_contact_fields():
    agent, _, _ = make_agent()
    assert agent._build_patch(
        {"validation_notes": "CORRECCIÓN MANUAL: ciudad corregida."},
        {"formatted_phone_number": "New"},
    ) == {"phone": "New"}


@pytest.mark.parametrize("place_id, protected", [
    ("1e21c93a-0030-4c99-8ef1-eab8d487130f", {"phone", "website"}),
    ("7363c257-9596-4aa1-a329-29d994d2eb65", {"phone"}),
    ("03ea2fae-834c-48c0-9f7e-b43b089dc4b4", {"phone"}),
    ("d1420754-dca8-47e2-8d60-97ac779de1c2", {"phone"}),
    ("1becc778-212c-49ac-b2de-7e6417265385", {"opening_hours"}),
    ("7f145df1-b613-470b-8748-b5ee19d383ad", {"website", "opening_hours"}),
])
def test_recorded_manual_corrections_survive_even_without_approval_notes(place_id, protected):
    agent, _, _ = make_agent()
    patch = agent._build_patch({"id": place_id}, {
        "website": "https://google.example", "formatted_phone_number": "Google",
        "opening_hours": {"weekday_text": ["Google"]}, "rating": 4.5,
    })
    assert set(patch) == {"website", "phone", "opening_hours", "rating"} - protected


def test_patch_includes_rich_fields():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": "Addr 1", "category": "restaurant"}
    result = {
        "name": "Same",
        "formatted_address": "Addr 1",
        "types": ["restaurant"],
        "formatted_phone_number": "2900 1234",
        "website": "https://x.uy",
        "rating": 4.2,
        "user_ratings_total": 88,
    }
    patch = agent._build_patch(place, result)
    assert patch["phone"] == "2900 1234"
    assert patch["website"] == "https://x.uy"
    assert patch["rating"] == 4.2
    assert patch["user_ratings_total"] == 88


def test_patch_skips_unchanged_rich_fields():
    agent, _, _ = make_agent()
    place = {
        "name": "Same", "address": "Addr 1", "category": "restaurant",
        "phone": "2900 1234", "rating": 4.2,
    }
    result = {
        "name": "Same", "formatted_address": "Addr 1", "types": ["restaurant"],
        "formatted_phone_number": "2900 1234", "rating": 4.2,
    }
    assert agent._build_patch(place, result) == {}


# --- No-op when nothing changed -------------------------------------------


# --- places.region follows the address in the same patch -------------------------

MELO_ADDRESS = "Dr. Luis Alberto de Herrera 859, 37000 Melo, Departamento de Cerro Largo, Uruguay"


def test_patch_recomputes_the_region_when_the_address_moves_to_another_department():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": "Av. Italia 1, Montevideo, Departamento de Montevideo, Uruguay",
             "region": "Montevideo", "category": "restaurant"}
    result = {"name": "Same", "formatted_address": "Av. Giannattasio 1, 15800 Ciudad de la Costa, Departamento de Canelones, Uruguay",
              "types": ["restaurant"]}
    patch = agent._build_patch(place, result)
    assert patch["address"] == result["formatted_address"]
    assert patch["region"] == "Canelones"


def test_patch_fills_a_missing_region_even_when_nothing_else_changed():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": MELO_ADDRESS, "region": None, "category": "restaurant"}
    result = {"name": "Same", "formatted_address": MELO_ADDRESS, "types": ["restaurant"]}
    assert agent._build_patch(place, result) == {"region": "Cerro Largo"}


def test_patch_keeps_the_stored_region_when_the_new_address_names_none():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": MELO_ADDRESS, "region": "Cerro Largo", "category": "restaurant"}
    result = {"name": "Same", "formatted_address": "Addr 2", "types": ["restaurant"]}
    assert agent._build_patch(place, result) == {"address": "Addr 2"}


def test_patch_is_quiet_when_the_region_is_already_right():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": MELO_ADDRESS, "region": "Cerro Largo", "category": "restaurant"}
    result = {"name": "Same", "formatted_address": MELO_ADDRESS, "types": ["restaurant"]}
    assert agent._build_patch(place, result) == {}


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


# --- A social profile is never a website (2026-10-01) ----------------------


def test_patch_puts_a_social_profile_in_social_url_when_the_row_has_none():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": "Addr 1", "category": "restaurant", "website": None, "social_url": None}
    result = {"name": "Same", "formatted_address": "Addr 1", "types": ["restaurant"],
              "website": "https://www.instagram.com/mooyrealcafe/"}
    assert agent._build_patch(place, result) == {"social_url": "https://www.instagram.com/mooyrealcafe/"}


def test_patch_never_replaces_a_social_url_the_row_already_has():
    agent, _, _ = make_agent()
    place = {"name": "Same", "address": "Addr 1", "category": "restaurant",
             "website": None, "social_url": "https://www.instagram.com/croc"}
    result = {"name": "Same", "formatted_address": "Addr 1", "types": ["restaurant"],
              "website": "https://www.facebook.com/croc"}
    assert agent._build_patch(place, result) == {}
