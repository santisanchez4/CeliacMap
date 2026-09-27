"""Freezing what a run retrieved (search hits and downloaded pages) so it can be replayed offline, deterministically and for free."""
from __future__ import annotations

import json

from agents.evidence_freeze import RecordingFetch, RecordingSearch, ReplayFetch, ReplaySearch, build_freeze, load_freeze

HITS = [{"title": "Guía", "link": "https://blog.example/g", "snippet": "Panadería X en Rosario: todo es sin gluten."}]


class Search:
    def __init__(self):
        self.calls = []

    def search(self, query, num=10, include_domains=None):
        self.calls.append((query, num, include_domains))
        return HITS if include_domains is None else []


def test_the_recording_search_passes_the_hits_through_and_records_every_call():
    inner = Search()
    rec = RecordingSearch(inner)
    assert rec.search("q1", num=5, include_domains=None) == HITS
    assert rec.search("q2", num=5, include_domains=["instagram.com", "facebook.com"]) == []
    assert inner.calls == [("q1", 5, None), ("q2", 5, ["instagram.com", "facebook.com"])]
    assert rec.calls == [{"query": "q1", "domains": None, "hits": HITS},
                         {"query": "q2", "domains": ["instagram.com", "facebook.com"], "hits": []}]


def test_a_failed_search_is_not_recorded_and_still_raises():
    class Boom:
        def search(self, *a, **k):
            raise RuntimeError("Tavily search failed")

    rec = RecordingSearch(Boom())
    try:
        rec.search("q", num=5, include_domains=None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("the error must reach the finder, which counts it")
    assert rec.calls == []


def test_the_recording_fetch_keeps_each_page_once_including_the_ones_that_could_not_be_downloaded():
    seen = []

    def fetch(url):
        seen.append(url)
        return "texto de la página" if "ok" in url else ""

    rec = RecordingFetch(fetch)
    assert rec("https://ok.example") == "texto de la página" and rec("https://down.example") == ""
    assert rec("https://ok.example") == "texto de la página"
    assert seen == ["https://ok.example", "https://down.example"]  # the second read of a page is served from the record
    assert rec.pages == {"https://ok.example": "texto de la página", "https://down.example": ""}


def test_the_replay_returns_what_was_recorded_and_counts_what_was_not():
    freeze = {"searches": [{"query": "q1", "domains": None, "hits": HITS},
                           {"query": "q2", "domains": ["instagram.com", "facebook.com"], "hits": []}],
              "pages": {"https://ok.example": "texto"}}
    search, fetch = ReplaySearch(freeze), ReplayFetch(freeze)
    assert search.search("q1", num=5, include_domains=None) == HITS
    assert search.search("q2", num=5, include_domains=("instagram.com", "facebook.com")) == []
    assert search.misses == 0
    assert search.search("never asked", num=5, include_domains=None) == [] and search.misses == 1
    assert fetch("https://ok.example") == "texto" and fetch("https://not.recorded") == "" and fetch.misses == 1


def test_a_freeze_survives_json_and_replays_the_same_answers():
    inner, fetcher = Search(), RecordingFetch(lambda url: "página")
    rec = RecordingSearch(inner)
    rec.search("q1", num=5, include_domains=None)
    fetcher("https://blog.example/g")
    text = json.dumps(build_freeze(rec, fetcher, {"created_at": "2026-09-27"}), ensure_ascii=False)
    freeze = load_freeze(json.loads(text))
    assert ReplaySearch(freeze).search("q1", num=5, include_domains=None) == HITS
    assert ReplayFetch(freeze)("https://blog.example/g") == "página"


def test_a_file_that_is_not_a_freeze_is_refused():
    for bad in (None, [], {}, {"searches": "x", "pages": {}}, {"searches": [], "pages": []}):
        try:
            load_freeze(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad!r}")
