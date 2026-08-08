"""Thin wrapper around the Google Places API for the Search / Updater / Social agents.

Kept small on purpose: it exposes text search, place details (optionally with
reviews), a Find Place lookup used to geocode social leads, and helpers to
normalize a raw Places result into our `places` schema and to mine review text
for gluten-free signals. Category assignment and business logic live in the
agents, not here.
"""

from __future__ import annotations

import re
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
    # Structured city/country (see GooglePlacesClient.city_country_from_components):
    # more reliable than parsing formatted_address, and this call already
    # happens for every candidate within max_detail_lookups, so this is a free
    # extra field, not a new API call.
    "address_component",
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


# Scoped to this project's Phase 1 geographic scope (CLAUDE.md: Uruguay and
# Argentina). Used only to tell a "province/department" address segment apart
# from a "city" segment when parsing formatted_address -- NOT a general-purpose
# geocoder. Revisit when the project scope expands beyond these two countries.
SUPPORTED_COUNTRIES = {"argentina": "Argentina", "uruguay": "Uruguay"}

AR_PROVINCES = {
    "buenos aires", "catamarca", "chaco", "chubut", "cordoba", "corrientes",
    "entre rios", "formosa", "jujuy", "la pampa", "la rioja", "mendoza",
    "misiones", "neuquen", "rio negro", "salta", "san juan", "san luis",
    "santa cruz", "santa fe", "santiago del estero", "tierra del fuego",
    "tucuman",
}

UY_DEPARTMENTS = {
    "artigas", "canelones", "cerro largo", "colonia", "durazno", "flores",
    "florida", "lavalleja", "maldonado", "montevideo", "paysandu",
    "rio negro", "rivera", "rocha", "salto", "san jose", "soriano",
    "tacuarembo", "treinta y tres",
}

# Argentine postal codes are either plain digits (old format, e.g. "E2820")
# or the full CPA format letter+4digits+3letters (e.g. "C1427EKC"); Uruguayan
# codes are 5 plain digits. Matches either, followed by the required space
# before the actual place name.
_POSTAL_PREFIX_RE = re.compile(r"^(?:[A-Za-z]\d{4}[A-Za-z]{3}|[A-Za-z]?\d{4,5})\s+")

# Strips an optional "Provincia de "/"Province of " prefix or " Province"
# suffix so "Provincia de Buenos Aires" / "Entre Ríos Province" both compare
# equal to the bare province name.
_PROVINCE_WRAP_RE = re.compile(
    r"^(?:provincia de |province of )?(.+?)(?: province)?$", re.IGNORECASE
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
    def parse_city_country_from_address(formatted_address: str | None) -> tuple[str | None, str | None]:
        """Best-effort (city, country) from a Google `formatted_address` string.

        Only trusted as a fallback: it's a fixed heuristic over Google's
        typical AR/UY address shape ("street, [postal]city, province,
        country" -- or without a street, or without a province line for
        C.A.B.A.), not a general parser. Returns (None, None) whenever the
        address doesn't end in a recognized country (this project's scope is
        only Argentina/Uruguay), so callers always have a safe target-based
        fallback of their own.
        """
        if not formatted_address:
            return None, None
        parts = [p.strip() for p in formatted_address.split(",") if p.strip()]
        if len(parts) < 2:
            return None, None

        country = SUPPORTED_COUNTRIES.get(_normalize_text(parts[-1]))
        if not country:
            return None, None

        provinces = AR_PROVINCES if country == "Argentina" else UY_DEPARTMENTS
        second_to_last = parts[-2]
        province_name = _PROVINCE_WRAP_RE.sub(r"\1", second_to_last).strip()

        # A real province/department segment means the city is one segment
        # further back; otherwise the segment right before the country IS
        # the city (e.g. C.A.B.A. addresses have no separate province line).
        if len(parts) >= 3 and _normalize_text(province_name) in provinces:
            city_raw = parts[-3]
        else:
            city_raw = second_to_last

        city = _POSTAL_PREFIX_RE.sub("", city_raw).strip() or None
        return city, country

    @staticmethod
    def city_country_from_components(
        address_components: list[dict[str, Any]] | None,
    ) -> tuple[str | None, str | None]:
        """(city, country) from a Place Details `address_components` list.

        Structured and Google-maintained -- the authoritative source,
        preferred over `parse_city_country_from_address` whenever a Details
        call was made. `locality` is the usual city type; a few Argentine
        addresses (e.g. some Buenos Aires Province localities) only carry
        `administrative_area_level_2`, used as a fallback for city.
        """
        if not address_components:
            return None, None
        city = None
        admin_area_2 = None
        country = None
        for component in address_components:
            types = component.get("types") or []
            if "country" in types:
                country = component.get("long_name")
            elif "locality" in types:
                city = component.get("long_name")
            elif "administrative_area_level_2" in types:
                admin_area_2 = component.get("long_name")
        return city or admin_area_2, country

    @staticmethod
    def to_candidate(result: dict[str, Any], *, country: str, city: str) -> dict:
        """Map a raw Places result to a `places` candidate (no category yet).

        `country`/`city` are the SEARCH TARGET (from config/targets.yaml) and
        are only a fallback: Google's Text Search can legitimately return a
        result located elsewhere (most visibly across an international
        border near a bridge crossing -- see CLAUDE.md's "Key risks"), so the
        result's own `formatted_address` is preferred whenever it parses to a
        recognized country.
        """
        loc = (result.get("geometry") or {}).get("location") or {}
        parsed_city, parsed_country = GooglePlacesClient.parse_city_country_from_address(
            result.get("formatted_address")
        )
        return {
            "name": result.get("name"),
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "address": result.get("formatted_address") or result.get("vicinity"),
            "external_id": result.get("place_id"),
            "source": "google_places",
            "country": parsed_country or country,
            "city": parsed_city or city,
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

        city, country = GooglePlacesClient.city_country_from_components(
            result.get("address_components")
        )
        if city:
            rich["city"] = city
        if country:
            rich["country"] = country

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
