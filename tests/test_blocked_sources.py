"""Sites whose terms forbid automated access are never searched, downloaded or used as evidence (2026-11-06: findmeglutenfree.com,
whose robots.txt disallows /biz and /uy for AI agents and whose terms forbid any robot, spider or automated retrieval)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.clients import tavily_client, website_scraper
from agents.clients.tavily_client import TavilySearchClient
from agents.clients.website_scraper import BLOCKED_DOMAINS, WebsiteScraperClient, fetch_page_text, fetch_social_links, is_blocked_url
from agents.evidence_finder import EvidenceFinder

FMGF = "https://www.findmeglutenfree.com/biz/taqueria-ejemplo/2222222222222222"


def test_findmeglutenfree_is_blocked_with_or_without_www():
    assert "findmeglutenfree.com" in BLOCKED_DOMAINS
    for url in (FMGF, "https://findmeglutenfree.com/uy/montevideo", "http://es.findmeglutenfree.com/x"):
        assert is_blocked_url(url)
    assert not is_blocked_url("https://glutengo.com.uy/lugar/x")
    assert not is_blocked_url("https://notfindmeglutenfree.com/")


@pytest.fixture
def no_network(monkeypatch):
    calls = []
    monkeypatch.setattr(website_scraper.requests, "get", lambda *a, **k: calls.append(a) or pytest.fail("no request expected"))
    return calls


def test_the_scraper_never_downloads_a_blocked_site(no_network):
    assert fetch_page_text(FMGF) == ""
    assert fetch_social_links(FMGF) == []
    assert WebsiteScraperClient().find_email(FMGF) is None
    assert no_network == []


def _tavily(results):
    client = TavilySearchClient.__new__(TavilySearchClient)
    client._client = MagicMock()
    client._client.search.return_value = {"results": results}
    return client


def test_every_tavily_search_excludes_the_blocked_sites_and_drops_any_that_slips_through():
    client = _tavily([{"url": FMGF, "title": "Taquería Ejemplo", "content": "Casi toda la carta es apta para celíacos…"},
                      {"url": "https://glutengo.com.uy/lugar/x", "title": "X", "content": "sin gluten"}])
    hits = client.search("Taquería Ejemplo Montevideo", include_domains=["instagram.com"])
    kwargs = client._client.search.call_args.kwargs
    assert set(BLOCKED_DOMAINS) <= set(kwargs["exclude_domains"])
    assert [h["link"] for h in hits] == ["https://glutengo.com.uy/lugar/x"]


def test_the_evidence_finder_ignores_a_blocked_hit_even_from_a_frozen_replay():
    class Search:
        def search(self, query, num=10, include_domains=None):
            return [{"title": "Taquería Ejemplo - Montevideo", "link": FMGF,
                     "snippet": "Taquería Ejemplo, Montevideo. Casi toda la carta es apta para celíacos."}]

    finder = EvidenceFinder(Search(), llm=None, fetch_text=lambda u: "")
    result = finder.find({"id": "p", "name": "Taquería Ejemplo", "city": "Montevideo", "country": "Uruguay"})
    assert result["citations"] == [] and result["unattributed"] == []
    assert all(d["url"] != FMGF for d in result["discarded_sources"])
