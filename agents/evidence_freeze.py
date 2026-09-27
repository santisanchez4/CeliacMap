"""Freeze what an evidence run retrieved (search hits and downloaded pages) so it can be replayed offline.

A replay feeds the same hits and pages back into the finder, so a change of logic can be compared on exactly the same sources, without
spending Tavily searches and without the web changing underneath. The recorders wrap the real clients; the replays stand in for them.
Anything a replay is asked for that was not recorded returns nothing and is counted (``misses``).
"""

from __future__ import annotations


class RecordingSearch:
    """Wraps a search client and records every successful call. A failed call is not recorded and still raises."""

    def __init__(self, inner):
        self.inner = inner
        self.calls: list[dict] = []

    def search(self, query, num=10, include_domains=None):
        hits = self.inner.search(query, num=num, include_domains=include_domains)
        self.calls.append({"query": query, "domains": list(include_domains) if include_domains else None, "hits": hits})
        return hits


class RecordingFetch:
    """Wraps a page fetcher and keeps each page once, including the ones that could not be downloaded (as "")."""

    def __init__(self, inner):
        self.inner = inner
        self.pages: dict[str, str] = {}

    def __call__(self, url):
        if url not in self.pages:
            self.pages[url] = self.inner(url) or ""
        return self.pages[url]


def build_freeze(search: RecordingSearch, fetch: RecordingFetch, meta: dict) -> dict:
    return {"created_at": meta.get("created_at"), "meta": meta, "searches": search.calls, "pages": fetch.pages}


def load_freeze(data) -> dict:
    """The freeze itself, or ValueError if ``data`` is not one."""
    if not isinstance(data, dict) or not isinstance(data.get("searches"), list) or not isinstance(data.get("pages"), dict):
        raise ValueError("no es un congelado de scripts/find_evidence (falta 'searches' o 'pages')")
    return data


class ReplaySearch:
    def __init__(self, freeze: dict):
        self.index = {(c["query"], tuple(c["domains"]) if c.get("domains") else None): c.get("hits") or [] for c in freeze["searches"]}
        self.misses = 0

    def search(self, query, num=10, include_domains=None):
        key = (query, tuple(include_domains) if include_domains else None)
        if key not in self.index:
            self.misses += 1
            return []
        return self.index[key]


class ReplayFetch:
    def __init__(self, freeze: dict):
        self.pages = freeze["pages"]
        self.misses = 0

    def __call__(self, url):
        if url not in self.pages:
            self.misses += 1
            return ""
        return self.pages[url] or ""
