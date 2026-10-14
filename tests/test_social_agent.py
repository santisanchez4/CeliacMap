"""Unit tests for the Social agent (offline, all external calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

from agents.clients.google_places import ResolvedLocation
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
    city="Montevideo",
    country="Uruguay",
    formatted_address="Av. Siempre Viva 123",
    geocode_method="find_place",
):
    """A ResolvedLocation as GooglePlacesClient.resolve_location would return."""
    return ResolvedLocation(
        place_id=place_id,
        lat=lat,
        lng=lng,
        formatted_address=formatted_address,
        name=name,
        city=city,
        country=country,
        geocode_method=geocode_method,
        business_status=business_status,
    )


def make_agent(targets=TARGETS, max_queries=16, max_geocodes=40):
    db = MagicMock()
    db.place_exists_by_external_id.return_value = False
    db.insert_place_candidate.return_value = {"id": "row-1"}
    search_client = MagicMock()
    places = MagicMock()
    places.resolve_location.return_value = make_match()
    llm = MagicMock()
    llm.complete_json.return_value = {
        "name": "Cafe X",
        "city": "Montevideo",
        "category": "cafe",
        "address": None,
    }
    agent = SocialAgent(
        db, search_client, places, llm, targets,
        max_queries=max_queries, max_geocodes=max_geocodes,
    )
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
    assert candidate["geocode_method"] == "find_place"
    assert "validation_notes" not in candidate


def test_candidate_propagates_resolved_country_city():
    """The candidate's country/city come from the ResolvedLocation, which
    resolve_location derives from Google's own address (a social post about
    "Montevideo" can point to a business anywhere — Tavily has no geographic
    filter; the address-vs-target parsing itself is covered in
    tests/test_google_places.py)."""
    agent, db, search, places, _ = make_agent(max_queries=1)
    search.search.return_value = [
        {"title": "Cafe X | Instagram", "link": "https://instagram.com/cafex",
         "snippet": "sin TACC en Montevideo"}
    ]
    places.resolve_location.return_value = make_match(
        name="CRAIG Bistro",
        city="Cdad. Autónoma de Buenos Aires",
        country="Argentina",
    )

    agent.run()

    candidate = db.insert_place_candidate.call_args.args[0]
    assert candidate["country"] == "Argentina"
    assert candidate["city"] == "Cdad. Autónoma de Buenos Aires"
    assert candidate["name"] == "CRAIG Bistro"


def test_address_only_geocode_method_propagates():
    """A lead resolved only by geocoding its address is inserted with
    geocode_method='address_only' so the Validator can weigh it as weaker."""
    agent, db, search, places, _ = make_agent(max_queries=1)
    search.search.return_value = [
        {"title": "Bienestar | Instagram", "link": "https://instagram.com/bienestar",
         "snippet": "productos sin TACC"}
    ]
    places.resolve_location.return_value = make_match(
        place_id="addr-1", name=None, geocode_method="address_only"
    )

    agent.run()

    candidate = db.insert_place_candidate.call_args.args[0]
    assert candidate["geocode_method"] == "address_only"
    assert candidate["external_id"] == "addr-1"
    # name falls back to the parsed lead name when the geocode has none.
    assert candidate["name"] == "Cafe X"


# --- Geocode budget cap -----------------------------------------------------


def test_geocode_cap_stops_calling_resolve_once_exhausted():
    """Regression test for the real 2026-08-19 production incident: a single
    Tavily query returned enough leads to fan out into far more geocode
    calls than the query cap alone would suggest (25 queries -> 102
    geocodes). max_geocodes must independently stop new resolve_location
    calls once hit, within the very first (and only) query here."""
    agent, db, search, places, _ = make_agent(max_queries=1, max_geocodes=2)
    search.search.return_value = [
        {"title": "A", "link": "https://instagram.com/a", "snippet": "sin TACC"},
        {"title": "B", "link": "https://instagram.com/b", "snippet": "sin TACC"},
        {"title": "C", "link": "https://instagram.com/c", "snippet": "sin TACC"},
    ]
    # All 3 leads parse to the same {name, city} (the mocked Haiku response is
    # fixed), so a fixed place_id would collide with the dedup-by-external_id
    # check. Vary it by call so the 2 that do geocode are counted as distinct
    # new places, isolating the geocode cap from that unrelated dedup path.
    geocode_calls = {"n": 0}

    def fake_resolve(name, address, city, country, location=None):
        geocode_calls["n"] += 1
        return make_match(place_id=f"ext-{geocode_calls['n']}", name=f"Place {geocode_calls['n']}")

    places.resolve_location.side_effect = fake_resolve

    summary = agent.run()

    # Only 2 of the 3 leads ever reach the paid Google API call.
    assert places.resolve_location.call_count == 2
    assert summary["inserted"] == 2
    assert summary["skipped"] == 1

    actions = [call.args[1] for call in db.insert_agent_log.call_args_list]
    assert "social_geocode_budget_exhausted" in actions


def test_geocode_cap_does_not_limit_query_count():
    """The geocode cap and the query cap are independent: a low geocode cap
    must not stop Tavily queries from running, only geocoding calls — even
    across queries, once the geocode budget is spent, later queries' leads
    are still parsed but never geocoded."""
    agent, db, search, places, _ = make_agent(max_queries=3, max_geocodes=1)
    calls = {"n": 0}

    def fake_search(q, num=None, include_domains=None):
        calls["n"] += 1
        return [{
            "title": "A",
            "link": f"https://instagram.com/a{calls['n']}",
            "snippet": "sin TACC",
        }]

    search.search.side_effect = fake_search
    places.resolve_location.side_effect = lambda name, address, city, country, location=None: make_match(
        place_id=name, name=name
    )

    summary = agent.run()

    # All 3 queries ran (independent Tavily cap), but only the first lead
    # across them ever got geocoded.
    assert summary["queries"] == 3
    assert places.resolve_location.call_count == 1


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
    places.resolve_location.return_value = None
    search.search.return_value = [
        {"title": "A", "link": "https://instagram.com/cafex", "snippet": "sin TACC"}
    ]

    summary = agent.run()

    assert summary["inserted"] == 0
    assert summary["skipped"] == 1
    db.insert_place_candidate.assert_not_called()


def test_closed_place_is_skipped():
    agent, db, search, places, _ = make_agent(max_queries=1)
    places.resolve_location.return_value = make_match(business_status="CLOSED_PERMANENTLY")
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
    places.resolve_location.side_effect = RuntimeError("places down")
    search.search.return_value = [
        {"title": "A", "link": "https://instagram.com/cafex", "snippet": "sin TACC"}
    ]

    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["inserted"] == 0


# --- Audit plan step 1: the post text is kept as evidence for the Validator ----


def test_inserted_candidate_keeps_title_and_snippet_as_evidence():
    agent, db, search, _, _ = make_agent(max_queries=1)
    search.search.return_value = [
        {"title": "Cafe X | Instagram", "link": "https://instagram.com/cafex",
         "snippet": "Cocina 100% sin TACC en Pocitos"}
    ]

    agent.run()

    db.add_place_evidence.assert_called_once_with(
        "row-1", "social", "Cafe X | Instagram — Cocina 100% sin TACC en Pocitos", "https://instagram.com/cafex"
    )


def test_evidence_write_failure_does_not_undo_the_insert():
    agent, db, search, _, _ = make_agent(max_queries=1)
    db.add_place_evidence.side_effect = RuntimeError("boom")
    search.search.return_value = [
        {"title": "Cafe X", "link": "https://instagram.com/cafex", "snippet": "sin TACC"}
    ]

    summary = agent.run()

    assert summary["inserted"] == 1 and summary["errors"] == 0


# --- A post is not a profile, and a topic page is not a lead (2026-10-13) ------------------------------------------------------

def _run_with(link, title="Cafe X | Instagram", snippet="Cocina 100% sin TACC en Pocitos"):
    agent, db, search, places, llm = make_agent(max_queries=1)
    search.search.return_value = [{"title": title, "link": link, "snippet": snippet}]
    summary = agent.run()
    return summary, db, places, llm


def test_a_profile_page_is_stored_as_the_profile_and_its_text_as_plain_evidence():
    summary, db, _, _ = _run_with("https://www.instagram.com/cafex/?hl=es")
    assert summary["inserted"] == 1
    assert db.insert_place_candidate.call_args[0][0]["social_url"] == "https://www.instagram.com/cafex"
    assert db.add_place_evidence.call_args[0][2] == "Cafe X | Instagram — Cocina 100% sin TACC en Pocitos"


def test_a_reel_is_not_stored_as_the_profile_and_its_text_is_marked_not_attributable():
    from agents.validator_agent import UNATTRIBUTED_ROW_PREFIX

    summary, db, _, _ = _run_with("https://www.instagram.com/reel/DTrDA7ogJOF")
    assert summary["inserted"] == 1
    assert db.insert_place_candidate.call_args[0][0]["social_url"] is None
    row_id, source, text, url = db.add_place_evidence.call_args[0]
    assert text == UNATTRIBUTED_ROW_PREFIX + "Cafe X | Instagram — Cocina 100% sin TACC en Pocitos"
    assert url == "https://www.instagram.com/reel/DTrDA7ogJOF"  # where the lead came from stays on record


def test_a_post_of_some_account_is_not_the_leads_profile_either():
    from agents.validator_agent import UNATTRIBUTED_ROW_PREFIX

    for link in ("https://www.instagram.com/guia.celiaca/p/C9xyz", "https://www.facebook.com/cooperativahelix/posts/pizza/822278316261044",
                 "https://www.facebook.com/profile.php"):
        _, db, _, _ = _run_with(link)
        assert db.insert_place_candidate.call_args[0][0]["social_url"] is None, link
        assert db.add_place_evidence.call_args[0][2].startswith(UNATTRIBUTED_ROW_PREFIX), link


def test_a_topic_page_is_not_a_lead_and_costs_no_model_or_geocoding_call():
    summary, db, places, llm = _run_with("https://www.instagram.com/popular/pan-sin-gluten-en-panetera",
                                         title="Pan Sin Gluten En Panetera", snippet="Watch short videos about pan sin gluten")
    assert summary["inserted"] == 0 and summary["skipped"] == 1
    db.insert_place_candidate.assert_not_called()
    llm.complete_json.assert_not_called()
    places.resolve_location.assert_not_called()
    assert any(call.args[1] == "social_not_a_source" for call in db.insert_agent_log.call_args_list)


def test_social_page_kind():
    from agents.evidence_finder import social_page_kind

    assert social_page_kind("https://www.instagram.com/cafex") == "profile"
    assert social_page_kind("https://www.instagram.com/cafex/reels") == "post"
    assert social_page_kind("https://www.instagram.com/cafex/p/C9xyz") == "post"
    assert social_page_kind("https://www.instagram.com/reel/DTrDA7ogJOF") == "post"
    assert social_page_kind("https://www.facebook.com/cafex") == "profile"
    assert social_page_kind("https://www.facebook.com/cafex/about") == "profile"
    assert social_page_kind("https://www.facebook.com/people/Cafe-X/100064") == "post"
    assert social_page_kind("https://www.instagram.com/explore/tags/singluten") == "topic"
    assert social_page_kind("https://www.instagram.com/") == "topic"
    assert social_page_kind("https://cafex.example/instagram") is None


# --- Map scope rules (2026-10-13): no candidate for a chain, a blog, a recipe account or a school ---


def _scope_run(parsed, resolved_name="Cafe X"):
    agent, db, search, places, llm = make_agent(max_queries=1)
    llm.complete_json.return_value = {"name": "Cafe X", "city": "Montevideo", "category": "cafe", "address": None, **parsed}
    places.resolve_location.return_value = make_match(name=resolved_name)
    search.search.return_value = [{"title": "t", "link": "https://www.instagram.com/cuenta", "snippet": "sin TACC"}]
    return agent.run(), db, places


def test_a_page_that_does_not_sell_to_the_public_is_not_a_lead():
    summary, db, places = _scope_run({"name": "Celíaca y Feliz", "sells_to_public": False})
    assert summary["inserted"] == 0 and summary["not_for_map"] == 1
    db.insert_place_candidate.assert_not_called()
    places.resolve_location.assert_not_called()  # no geocoding spent on it
    assert any(c.args[1] == "social_not_for_map" for c in db.insert_agent_log.call_args_list)


def test_a_chain_or_a_blog_by_its_name_is_not_a_lead():
    for name in ("Tienda Inglesa", "Supermercados Disco", "Blog Celíaco Feliz", "Recetas Sin Gluten Uruguay"):
        summary, db, places = _scope_run({"name": name, "sells_to_public": True})
        assert summary["not_for_map"] == 1, name
        db.insert_place_candidate.assert_not_called()
        places.resolve_location.assert_not_called()


def test_a_lead_that_resolves_to_a_chain_branch_is_not_inserted():
    summary, db, _ = _scope_run({"name": "Fresh Market"}, resolved_name="Géant Fresh Market")
    assert summary["not_for_map"] == 1 and summary["inserted"] == 0
    db.insert_place_candidate.assert_not_called()


def test_a_food_chain_or_an_unknown_answer_is_still_a_lead():
    for parsed in ({"name": "Zero Helados", "sells_to_public": True}, {"name": "Ramona"}, {"name": "Mi Cocina Sin Gluten", "sells_to_public": None}):
        summary, db, _ = _scope_run(parsed, resolved_name=parsed["name"])
        assert summary["inserted"] == 1 and summary["not_for_map"] == 0, parsed


def test_a_place_the_admin_kept_on_the_map_is_still_a_lead():
    for name in ("EntreSano Healthy Supermarket", "Minimarket La Isla 24 hours.", "La Molienda - Carrasco"):
        summary, db, _ = _scope_run({"name": name, "category": "shop", "sells_to_public": True}, resolved_name=name)
        assert summary["inserted"] == 1 and summary["not_for_map"] == 0, name


def test_parse_rubric_asks_whether_the_page_sells_to_the_public():
    from agents.social_agent import PARSE_RUBRIC

    assert '"sells_to_public"' in PARSE_RUBRIC
    assert "supermarket" not in PARSE_RUBRIC
