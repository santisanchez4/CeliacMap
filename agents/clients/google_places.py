"""Thin wrapper around the Google Places API for the Search / Updater / Social agents.

Kept small on purpose: it exposes text search, place details (optionally with
reviews), a Find Place lookup used to geocode social leads, and helpers to
normalize a raw Places result into our `places` schema and to mine review text
for gluten-free signals. Category assignment and business logic live in the
agents, not here.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import googlemaps

# Fields requested for a place-details lookup (keep minimal to limit cost).
# NOTE: the Place Details endpoint wants the field name "type" (singular); the
# Find Place endpoint below wants "types" (plural). The googlemaps library
# validates each against a different allow-list, so this asymmetry is required.
DEFAULT_DETAIL_FIELDS = [
    "place_id",
    "name",
    "formatted_address",
    "geometry/location",
    "type",
    "business_status",
    # Rich detail fields surfaced in the frontend place panel.
    "formatted_phone_number",
    "website",
    "opening_hours",
    "rating",
    "user_ratings_total",
]

# Extra fields requested when we also want community reviews for enrichment.
REVIEW_DETAIL_FIELDS = DEFAULT_DETAIL_FIELDS + [
    "review",
    "rating",
    "user_ratings_total",
]

# Fields requested from Find Place when geocoding a social lead (name + city).
# NOTE: Find Place wants "types" (plural) — unlike Place Details above ("type").
FIND_PLACE_FIELDS = [
    "place_id",
    "name",
    "formatted_address",
    "geometry/location",
    "business_status",
    "types",
]

# Gluten-free / celiac signals we look for inside review text. Accent- and
# case-insensitive matching is applied, so the un-accented forms are enough.
GF_KEYWORDS = (
    "sin tacc",
    "sin gluten",
    "gluten free",
    "gluten-free",
    "libre de gluten",
    "celiaco",
    "celiaca",
    "apto celiaco",
    "apto celiacos",
)


def _normalize_text(text: str) -> str:
    """Lower-case and strip accents for robust keyword matching."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower()


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
        # language='es' so opening_hours.weekday_text reads in Spanish.
        return self._client.place(
            place_id=place_id, fields=fields or DEFAULT_DETAIL_FIELDS, language="es"
        )

    def place_details_with_reviews(self, place_id: str) -> dict:
        """Place details including up to ~5 community reviews (for enrichment)."""
        return self._client.place(
            place_id=place_id, fields=REVIEW_DETAIL_FIELDS, language="es"
        )

    def find_place(
        self, text: str, location: tuple[float, float] | None = None
    ) -> dict | None:
        """Resolve a free-text lead (e.g. "Cafe X Montevideo") to one place.

        Used by the Social agent to geocode a social-media lead into real
        coordinates + a canonical Google ``place_id``. Returns the first
        candidate's raw result, or ``None`` if nothing matched.
        """
        kwargs: dict[str, Any] = {
            "input": text,
            "input_type": "textquery",
            "fields": FIND_PLACE_FIELDS,
        }
        if location is not None:
            lat, lng = location
            kwargs["location_bias"] = f"point:{lat},{lng}"
        resp = self._client.find_place(**kwargs)
        candidates = resp.get("candidates") or []
        return candidates[0] if candidates else None

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

    @staticmethod
    def extract_rich_fields(result: dict[str, Any]) -> dict:
        """Pull the optional detail fields shown in the frontend place panel.

        Only includes keys that are actually present (non-empty), so callers can
        merge the result into an update patch without clobbering existing data
        with nulls. ``opening_hours`` is stored as the localized ``weekday_text``
        list (``open_now`` is intentionally dropped — it would go stale).
        """
        rich: dict[str, Any] = {}

        phone = (result.get("formatted_phone_number") or "").strip()
        if phone:
            rich["phone"] = phone

        website = (result.get("website") or "").strip()
        if website:
            rich["website"] = website

        weekday_text = (result.get("opening_hours") or {}).get("weekday_text")
        if weekday_text:
            rich["opening_hours"] = weekday_text

        rating = result.get("rating")
        if isinstance(rating, (int, float)):
            rich["rating"] = float(rating)

        total = result.get("user_ratings_total")
        if isinstance(total, int):
            rich["user_ratings_total"] = total

        return rich

    @staticmethod
    def extract_gf_snippets(reviews: list[dict[str, Any]] | None) -> list[dict]:
        """Keep only reviews that mention a gluten-free / celiac signal.

        Returns ``[{text, rating}]`` for each matching review (text trimmed,
        rating coerced to an int in 1..5 when present).
        """
        snippets: list[dict] = []
        for review in reviews or []:
            text = (review.get("text") or "").strip()
            if not text:
                continue
            normalized = _normalize_text(text)
            if not any(keyword in normalized for keyword in GF_KEYWORDS):
                continue
            rating = review.get("rating")
            try:
                rating = int(rating) if rating is not None else None
            except (TypeError, ValueError):
                rating = None
            if rating is not None and not (1 <= rating <= 5):
                rating = None
            snippets.append({"text": text, "rating": rating})
        return snippets
