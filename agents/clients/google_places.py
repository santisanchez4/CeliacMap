"""Thin wrapper around the Google Places API for the Search / Updater agents.

Kept small on purpose: it exposes text search + place details and a helper to
normalize a raw Places result into our `places` schema. Category assignment and
business logic live in the agents, not here.
"""

from __future__ import annotations

from typing import Any

import googlemaps

# Fields requested for a place-details lookup (keep minimal to limit cost).
DEFAULT_DETAIL_FIELDS = [
    "place_id",
    "name",
    "formatted_address",
    "geometry/location",
    "type",
    "business_status",
]


class GooglePlacesClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GooglePlacesClient requires an API key.")
        self._client = googlemaps.Client(key=api_key)

    def text_search(
        self,
        query: str,
        location: tuple[float, float] | None = None,
        radius_m: int | None = None,
        page_token: str | None = None,
    ) -> dict:
        """Run a Places text search. Returns the raw API response."""
        return self._client.places(
            query=query, location=location, radius=radius_m, page_token=page_token
        )

    def place_details(self, place_id: str, fields: list[str] | None = None) -> dict:
        return self._client.place(place_id=place_id, fields=fields or DEFAULT_DETAIL_FIELDS)

    @staticmethod
    def to_candidate(result: dict[str, Any], *, country: str, city: str) -> dict:
        """Map a raw Places result to a `places` candidate (no category yet)."""
        loc = (result.get("geometry") or {}).get("location") or {}
        return {
            "name": result.get("name"),
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "address": result.get("formatted_address") or result.get("vicinity"),
            "external_id": result.get("place_id"),
            "source": "google_places",
            "country": country,
            "city": city,
        }
