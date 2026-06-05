"""Search agent — discovers gluten-free / sin TACC candidates via Google Places.

Deterministic (no LLM). For every city in ``config/targets.yaml`` crossed with
every search term, it runs a Google Places text search, maps each result onto our
``places`` schema, assigns a provisional category from the Google place types,
deduplicates by ``external_id`` (within the run, and via the DB's unique
``(source, external_id)`` index across runs), and inserts new candidates as
``status='pending'`` for the Validator to judge. Each run is summarized to
``agent_log``.
"""

from __future__ import annotations

import logging

from agents.base import BaseAgent
from agents.clients.google_places import GooglePlacesClient
from agents.clients.supabase_client import SupabaseClient

logger = logging.getLogger("celiacmap.agent")

# Provisional values written at insert time; the Validator sets the real ones.
# safety_level defaults to the most conservative (lowest) level on purpose.
DEFAULT_CATEGORY = "restaurant"
DEFAULT_SAFETY_LEVEL = "options_available"


class SearchAgent(BaseAgent):
    name = "search"

    def __init__(
        self,
        db: SupabaseClient,
        places: GooglePlacesClient,
        targets: dict,
        max_results_per_query: int = 20,
        max_review_enrichments: int = 0,
        max_detail_lookups: int = 0,
        max_queries_per_run: int = 0,
    ):
        super().__init__(db)
        self.places = places
        self.targets = targets
        self.max_results_per_query = max_results_per_query
        # Cap on text-search queries per run (0 = unlimited). The city x term
        # matrix grows with coverage; this keeps a run within the daily budget.
        self.max_queries_per_run = max_queries_per_run
        # One Place Details call per new candidate populates the rich panel fields
        # (phone/website/hours/rating); the same call also feeds GF review
        # enrichment. Both are capped per run to stay within the API budget.
        self.max_detail_lookups = max_detail_lookups
        self.max_review_enrichments = max_review_enrichments
        self._category_by_type = self._build_type_index(targets.get("categories", {}))

    @staticmethod
    def _build_type_index(categories: dict) -> dict[str, str]:
        """Invert ``category -> [google types]`` into ``google type -> category``."""
        index: dict[str, str] = {}
        for category, gtypes in (categories or {}).items():
            for gtype in gtypes or []:
                index[gtype] = category
        return index

    def _category_for(self, result: dict) -> str:
        """Pick our category from the result's Google types (first match wins)."""
        for gtype in result.get("types", []):
            if gtype in self._category_by_type:
                return self._category_by_type[gtype]
        return DEFAULT_CATEGORY

    def _apply_place_details(
        self, place_id: str, external_id: str, *, store_reviews: bool
    ) -> dict:
        """Fetch Place Details once; use it for rich fields (+ optional reviews).

        Returns ``{"rich": bool, "snippets": int}``. Best-effort: any failure is
        logged but never crashes the run.
        """
        try:
            details = self.places.place_details_with_reviews(external_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("details fetch failed for %s", external_id)
            self.log(
                "details_fetch_failed",
                {"external_id": external_id, "error": str(exc)},
                status="error",
                place_id=place_id,
            )
            return {"rich": False, "snippets": 0}

        result = details.get("result") or {}

        rich = GooglePlacesClient.extract_rich_fields(result)
        applied = False
        if rich:
            try:
                self.db.update_place(place_id, rich)
                applied = True
            except Exception:  # noqa: BLE001
                logger.exception("applying rich fields failed for %s", place_id)

        stored = 0
        if store_reviews:
            for snippet in GooglePlacesClient.extract_gf_snippets(result.get("reviews")):
                try:
                    self.db.insert_review(
                        place_id,
                        snippet["text"],
                        rating=snippet.get("rating"),
                        source="google",
                    )
                    stored += 1
                except Exception:  # noqa: BLE001
                    logger.exception("storing review failed for %s", place_id)
            if stored:
                self.log(
                    "reviews_enriched",
                    {"external_id": external_id, "snippets": stored},
                    status="success",
                    place_id=place_id,
                )
        return {"rich": applied, "snippets": stored}

    def run(self) -> dict:
        search_terms = self.targets.get("search_terms", [])
        seen: set[str] = set()
        queries = 0
        candidates_found = 0
        inserted = 0
        skipped = 0
        errors = 0
        details_fetched = 0
        rich_updated = 0
        reviews_enriched = 0
        review_snippets = 0

        # Term-major job list: apply each search term across ALL cities before the
        # next term, so a run capped by max_queries_per_run still spans every city
        # with the strongest terms first (search_terms are ordered by signal).
        jobs = [
            (country.get("name"), city, term)
            for term in search_terms
            for country in self.targets.get("countries", [])
            for city in country.get("cities", [])
        ]
        if self.max_queries_per_run:
            jobs = jobs[: self.max_queries_per_run]

        for country_name, city, term in jobs:
            city_name = city.get("name")
            location = (city.get("lat"), city.get("lng"))
            radius_m = city.get("radius_m")
            query = f"{term} {city_name}".strip()
            queries += 1
            try:
                resp = self.places.text_search(
                    query=query, location=location, radius_m=radius_m
                )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.exception("text_search failed for %r", query)
                self.log(
                    "search_query_failed",
                    {"query": query, "error": str(exc)},
                    status="error",
                )
                continue

            results = (resp.get("results") or [])[: self.max_results_per_query]
            for result in results:
                external_id = result.get("place_id")
                if not external_id or external_id in seen:
                    continue
                seen.add(external_id)

                if result.get("business_status") == "CLOSED_PERMANENTLY":
                    skipped += 1
                    continue

                candidate = GooglePlacesClient.to_candidate(
                    result, country=country_name, city=city_name
                )
                if not candidate.get("name") or candidate.get("lat") is None:
                    skipped += 1
                    continue

                candidate["category"] = self._category_for(result)
                candidate["safety_level"] = DEFAULT_SAFETY_LEVEL
                candidates_found += 1

                try:
                    row = self.db.insert_place_candidate(candidate)
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    logger.exception(
                        "insert failed for %r (%s)", candidate.get("name"), external_id
                    )
                    self.log(
                        "candidate_insert_failed",
                        {"external_id": external_id, "error": str(exc)},
                        status="error",
                    )
                    continue
                if row:
                    inserted += 1
                    # One Details call per new candidate: rich panel fields
                    # always, GF review snippets while under their own cap.
                    if details_fetched < self.max_detail_lookups:
                        details_fetched += 1
                        out = self._apply_place_details(
                            row.get("id"),
                            external_id,
                            store_reviews=reviews_enriched < self.max_review_enrichments,
                        )
                        if out["rich"]:
                            rich_updated += 1
                        if out["snippets"]:
                            reviews_enriched += 1
                            review_snippets += out["snippets"]

        summary = {
            "queries": queries,
            "candidates_found": candidates_found,
            "unique_candidates": len(seen),
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
            "details_fetched": details_fetched,
            "rich_updated": rich_updated,
            "reviews_enriched": reviews_enriched,
            "review_snippets": review_snippets,
        }
        self.log(
            "search_run_complete",
            summary,
            status="error" if errors else "success",
        )
        return summary


def main() -> int:
    """Run the Search agent standalone (manual pipeline validation)."""
    import sys

    from config.settings import get_settings, load_targets

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    settings.require(
        "supabase_url", "supabase_service_role_key", "google_maps_api_key"
    )

    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    places = GooglePlacesClient(settings.google_maps_api_key)
    agent = SearchAgent(
        db,
        places,
        load_targets(),
        max_results_per_query=settings.max_search_results_per_query,
        max_review_enrichments=settings.max_review_enrichments_per_run,
        max_detail_lookups=settings.max_detail_lookups_per_run,
        max_queries_per_run=settings.max_search_queries_per_run,
    )

    summary = agent.run()
    print("Search run complete:", summary)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
