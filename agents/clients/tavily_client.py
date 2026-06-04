"""Thin wrapper around the Tavily Search API for the Social agent.

Replaces the former Google Custom Search client: as of January 2026 Google
Programmable Search Engines can no longer be configured to "search the entire
web", which broke the social-discovery use case. Tavily is purpose-built for AI
agents (cleaner result text) and has a generous free tier (1000 searches/month).

Domain filtering uses Tavily's ``include_domains`` parameter rather than Google's
``site:`` operator (which Tavily does not honor). Results are normalized to the
same ``{title, link, snippet}`` shape the Social agent already consumes, so the
downstream parsing / geocoding / dedup logic is unchanged.
"""

from __future__ import annotations

import logging
from typing import Any

from tavily import TavilyClient

logger = logging.getLogger("celiacmap.agent")

# Keep result counts modest: the Social agent only needs a handful of leads per
# query, and smaller responses are cheaper to parse with Haiku downstream.
MAX_NUM = 10


class TavilySearchClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("TavilySearchClient requires an API key.")
        self._client = TavilyClient(api_key=api_key)

    def search(
        self,
        query: str,
        num: int = MAX_NUM,
        include_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run one Tavily search. Returns a list of ``{title, link, snippet}``.

        Raises on transport / quota / decode errors so the caller can log and
        continue, matching the previous Custom Search client's contract.
        """
        try:
            response = self._client.search(
                query=query,
                search_depth="basic",
                max_results=max(1, min(num, MAX_NUM)),
                include_domains=include_domains or None,
            )
        except Exception as exc:  # noqa: BLE001 - normalize any SDK/transport error
            raise RuntimeError(f"Tavily search failed for {query!r}: {exc}") from exc

        items = response.get("results") or []
        return [
            {
                "title": item.get("title"),
                "link": item.get("url"),
                "snippet": item.get("content"),
            }
            for item in items
        ]
