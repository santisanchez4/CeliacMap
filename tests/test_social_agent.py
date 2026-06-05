"""Unit tests for the Social agent (offline, all external calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

from agents.social_agent import DEFAULT_CATEGORY, SocialAgent, _canonical_url

TARGETS = {
    "social": {
        "platforms": ["instagram.com", "facebook.com"],
        "search_terms": ["sin TACC", "gluten free"],
    },
    "countries": [
        {
            "name": "Uruguay",
            "cities": [{"name": "Montevideo", "lat": -34.9, "lng": -56.2}],
        }
    ],
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


def make_agent(targets=TARGETS, max_queries=16):
    db = MagicMock()
    db.place_exists_by_external_id.return_value = False
    db.insert_place_candidate.return_value = {"id": "row-1"}
    search_client = MagicMock()
    places = MagicMock()
    places.find_place.return_value = make_match()
    llm = MagicMock()
    llm.complete_json.return_value = {
        "name": "Cafe X",
        "city": "Montevideo",
        "category": "cafe",
        "address": None,
    }
    agent = SocialAgent(db, search_client, places, llm, targets, max_queries=max_queries)
    return agent, db, search_client, places, llm


# --- URL canonicalization -------------------------------------------------


def test_canonical_url_strips_query_fragment_and_trailing_slash():
    assert (
        _canonical_url("https://Instagram.com/CafeX/?hl=es#top")
        == "https://instagram.com/CafeX"
    )


def test_canonical_url_handles_none():
    assert _canonical_url(None) is None
    assert _canonical_url("") is None


# --- Query generation -----------------------------------------------------


def test_build_queries_matrix():
    agent, *_ = make_agent()
    queries = agent._build_queries()
    qs = [q["q"] for q in queries]
    # 2 platforms x 2 terms x 1 city = 4 queries.
    assert len(qs) == 4
    assert '"sin TACC" "Montevideo"' in qs
    assert '"gluten free" "Montevideo"' in qs
    # The platform is carried as a Tavily include_domains restriction.
    domains = {tuple(q["domains"]) for q in queries}
    assert domains == {("instagram.com",), ("facebook.com",)}


def test_build_queries_respects_cap():
    agent, *_ = make_agent(max_queries=2)
    assert len(agent._build_queries()) == 2


def test_build_queries_includes_social_hashtags():
    targets = {
        "social": {
            "platforms": ["instagram.com"],
            "search_terms": ["sin TACC"],
            "social_hashtags": ["#sintacc", "#glutenfree"],
        },
        "countries": [
            {"name": "Uruguay", "cities": [{"name": "Montevideo", "lat": 0, "lng": 0}]}
        ],
    }
    agent, *_ = make_agent(targets=targets)
    qs = [q["q"] for q in agent._build_queries()]
    # 1 platform x (1 term + 2 hashtags) x 1 city = 3 queries.
    assert len(qs) == 3
    assert '"#sintacc" "Montevideo"' in qs
    assert '"#glutenfree" "Montevideo"' in qs


# --- Lead parsing / normalization -----------------------------------------


def test_parse_lead_requires_name():
    agent, _, _, _, llm = make_agent()
    llm.complete_json.return_value = {"name": "", "category": "cafe"}
    assert agent._parse_lead({"title": "x", "snippet": "y"}) is None


def test_parse_lead_defaults_bad_category():
    agent, _, _, _, llm = make_agent()
    llm.complete_json.return_value = {"name": "Place", "category": "bar"}
    lead = agent._parse_lead({"title": "x", "snippet": "y"})
    assert lead["category"] == DEFAULT_CATEGORY


def test_parse_lead_returns_none_on_llm_error():
    agent, _, _, _, llm = make_agent()
    llm.complete_json.side_effect = RuntimeError("boom")
    assert agent._parse_lead({"title": "x", "snippet": "y"}) is None


# --- Happy path -----------------------------------------------------------


def test_successful_insert_geocoded_candidate():
    agent, db, search, places, _ = make_agent(max_queries=1)
    search.search.return_value = [
        {"title": "Cafe X | Instagram", "link": "https://instagram.com/cafex",
         "snippet": "sin TACC en Montevideo"}
    ]

    summary = agent.run()

    assert summary["inserted"] == 1
    assert summary["geocoded"] == 1
    candidate = db.insert_place_candidate.call_args.args[0]
    assert candidate["source"] == "social"
    assert candidate["external_id"] == "ext-1"
    assert candidate["lat"] == -34.9 and candidate["lng"] == -56.2
    assert candidate["social_url"] == "https://instagram.com/cafex"
    assert "validation_notes" not in candidate


# --- Dedup ----------------------------------------------------------------


def test_duplicate_url_processed_once():
    agent, db, search, places, _ = make_agent(max_queries=1)
    search.search.return_value = [
        {"title": "A", "link": "https://instagram.com/cafex/", "snippet": "sin TACC"},
        {"title": "A", "link": "https://instagram.com/cafex", "snippet": "sin TACC"},
    ]

    summary = agent.run()

    # Same canonical URL -> parsed/geocoded once.
    assert summary["results_seen"] == 1
    assert db.insert_place_candidate.call_count == 1


def test_existing_external_id_is_skipped():
    agent, db, search, places, _ = make_agent(max_queries=1)
    db.place_exists_by_external_id.return_value = True
    search.search.return_value = [
        {"title": "A", "link": "https://instagram.com/cafex", "snippet": "sin TACC"}
    ]

    summary = agent.run()

    assert summary["inserted"] == 0
    assert summary["skipped"] == 1
    db.insert_place_candidate.assert_not_called()


# --- Geocoding outcomes ---------------------------------------------------


def test_unresolved_lead_is_skipped():
    agent, db, search, places, _ = make_agent(max_queries=1)
    places.find_place.return_value = None
    search.search.return_value = [
        {"title": "A", "link": "https://instagram.com/cafex", "snippet": "sin TACC"}
    ]

    summary = agent.run()

    assert summary["inserted"] == 0
    assert summary["skipped"] == 1
    db.insert_place_candidate.assert_not_called()


def test_closed_place_is_skipped():
    agent, db, search, places, _ = make_agent(max_queries=1)
    places.find_place.return_value = make_match(business_status="CLOSED_PERMANENTLY")
    search.search.return_value = [
        {"title": "A", "link": "https://instagram.com/cafex", "snippet": "sin TACC"}
    ]

    summary = agent.run()

    assert summary["inserted"] == 0
    assert summary["skipped"] == 1


# --- Error handling -------------------------------------------------------


def test_tavily_search_error_is_counted_and_does_not_crash():
    agent, db, search, places, _ = make_agent(max_queries=1)
    search.search.side_effect = RuntimeError("quota exceeded")

    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["inserted"] == 0
    db.insert_place_candidate.assert_not_called()


def test_geocode_error_is_counted():
    agent, db, search, places, _ = make_agent(max_queries=1)
    places.find_place.side_effect = RuntimeError("places down")
    search.search.return_value = [
        {"title": "A", "link": "https://instagram.com/cafex", "snippet": "sin TACC"}
    ]

    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["inserted"] == 0
