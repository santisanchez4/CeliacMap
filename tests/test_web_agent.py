"""Unit tests for the Web discovery agent (offline, all external calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

from agents.web_agent import DEFAULT_CATEGORY, WebAgent

TARGETS = {
    "countries": [
        {
            "name": "Uruguay",
            "cities": [
                {"name": "Montevideo", "lat": -34.9, "lng": -56.2, "web": True},
                {"name": "Salto", "lat": -31.4, "lng": -57.9},  # not flagged
            ],
        },
        {
            "name": "Argentina",
            "cities": [
                {"name": "Buenos Aires", "lat": -34.6, "lng": -58.4, "web": True},
            ],
        },
    ]
}


def make_match(
    place_id="ext-1",
    name="Cafe X",
    lat=-34.9,
    lng=-56.2,
    business_status="OPERATIONAL",
):
    return {
        "place_id": place_id,
        "name": name,
        "formatted_address": "Av. Siempre Viva 123",
        "geometry": {"location": {"lat": lat, "lng": lng}},
        "business_status": business_status,
    }


def make_lead(
    name="Cafe X",
    category="cafe",
    address=None,
    source_url="https://blog.example/sin-tacc-mvd",
):
    return {
        "name": name,
        "category": category,
        "address": address,
        "evidence": "Reseña local lo recomienda como 100% sin TACC.",
        "source_url": source_url,
    }


def make_agent(targets=TARGETS, max_cities=2):
    db = MagicMock()
    db.place_exists_by_external_id.return_value = False
    db.insert_place_candidate.return_value = {"id": "row-1"}
    places = MagicMock()
    places.find_place.return_value = make_match()
    llm = MagicMock()
    llm.research_with_web_search.return_value = {"places": [make_lead()]}
    agent = WebAgent(db, places, llm, targets, max_cities=max_cities)
    return agent, db, places, llm


# --- City selection -------------------------------------------------------


def test_cities_only_flagged_web_true():
    agent, *_ = make_agent()
    cities = agent._cities()
    names = [c["city"] for c in cities]
    assert names == ["Montevideo", "Buenos Aires"]  # Salto (no flag) excluded


def test_cities_respects_cap():
    agent, *_ = make_agent(max_cities=1)
    assert len(agent._cities()) == 1


def test_cities_carry_country_and_location():
    agent, *_ = make_agent()
    mvd = agent._cities()[0]
    assert mvd["country"] == "Uruguay"
    assert mvd["location"] == (-34.9, -56.2)


# --- Lead cleaning --------------------------------------------------------


def test_clean_lead_requires_name():
    agent, *_ = make_agent()
    assert agent._clean_lead({"name": "  ", "category": "cafe"}) is None


def test_clean_lead_defaults_bad_category():
    agent, *_ = make_agent()
    lead = agent._clean_lead({"name": "Place", "category": "bar"})
    assert lead["category"] == DEFAULT_CATEGORY


def test_clean_lead_blank_url_becomes_none():
    agent, *_ = make_agent()
    lead = agent._clean_lead({"name": "Place", "category": "cafe", "source_url": ""})
    assert lead["source_url"] is None


# --- Happy path -----------------------------------------------------------


def test_successful_insert_geocoded_candidate():
    agent, db, places, _ = make_agent(max_cities=1)

    summary = agent.run()

    assert summary["cities"] == 1
    assert summary["leads_found"] == 1
    assert summary["geocoded"] == 1
    assert summary["inserted"] == 1
    candidate = db.insert_place_candidate.call_args.args[0]
    assert candidate["source"] == "web"
    assert candidate["external_id"] == "ext-1"
    assert candidate["lat"] == -34.9 and candidate["lng"] == -56.2
    assert candidate["social_url"] == "https://blog.example/sin-tacc-mvd"
    assert candidate["safety_level"] == "options_available"
    assert "validation_notes" not in candidate


def test_searches_budget_estimate_in_summary():
    agent, *_ = make_agent(max_cities=2)
    agent.max_searches_per_city = 8
    summary = agent.run()
    # Worst-case search estimate the orchestrator consumes from the budget.
    assert summary["searches"] == 2 * 8


# --- Dedup ----------------------------------------------------------------


def test_duplicate_external_id_within_run_inserted_once():
    agent, db, places, llm = make_agent(max_cities=2)
    # Same place returned for both cities -> same geocoded place_id.
    llm.research_with_web_search.return_value = {"places": [make_lead()]}

    summary = agent.run()

    assert summary["inserted"] == 1
    assert summary["skipped"] == 1
    assert db.insert_place_candidate.call_count == 1


def test_existing_external_id_is_skipped():
    agent, db, places, _ = make_agent(max_cities=1)
    db.place_exists_by_external_id.return_value = True

    summary = agent.run()

    assert summary["inserted"] == 0
    assert summary["skipped"] == 1
    db.insert_place_candidate.assert_not_called()


# --- Geocoding outcomes ---------------------------------------------------


def test_unresolved_lead_is_skipped():
    agent, db, places, _ = make_agent(max_cities=1)
    places.find_place.return_value = None

    summary = agent.run()

    assert summary["inserted"] == 0
    assert summary["skipped"] == 1
    db.insert_place_candidate.assert_not_called()


def test_closed_place_is_skipped():
    agent, db, places, _ = make_agent(max_cities=1)
    places.find_place.return_value = make_match(business_status="CLOSED_PERMANENTLY")

    summary = agent.run()

    assert summary["inserted"] == 0
    assert summary["skipped"] == 1


# --- Error handling -------------------------------------------------------


def test_research_error_is_counted_and_does_not_crash():
    agent, db, places, llm = make_agent(max_cities=1)
    llm.research_with_web_search.side_effect = RuntimeError("web search down")

    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["inserted"] == 0
    db.insert_place_candidate.assert_not_called()


def test_geocode_error_is_counted():
    agent, db, places, _ = make_agent(max_cities=1)
    places.find_place.side_effect = RuntimeError("places down")

    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["inserted"] == 0


def test_empty_places_list_is_clean():
    agent, db, places, llm = make_agent(max_cities=1)
    llm.research_with_web_search.return_value = {"places": []}

    summary = agent.run()

    assert summary["leads_found"] == 0
    assert summary["inserted"] == 0
    assert summary["errors"] == 0
    db.insert_place_candidate.assert_not_called()


def test_leads_per_city_cap():
    agent, db, places, llm = make_agent(max_cities=1)
    agent.max_leads_per_city = 2
    llm.research_with_web_search.return_value = {
        "places": [
            make_lead(name=f"Place {i}", source_url=f"https://e/{i}") for i in range(5)
        ]
    }
    # Distinct geocode per lead so dedup doesn't collapse them.
    places.find_place.side_effect = lambda text, location=None: make_match(
        place_id=text, name=text
    )

    summary = agent.run()

    assert summary["leads_found"] == 2  # capped before geocoding
