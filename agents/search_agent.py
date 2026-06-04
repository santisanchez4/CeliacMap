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
    ):
        super().__init__(db)
        self.places = places
        self.targets = targets
        self.max_results_per_query = max_results_per_query
        # Review enrichment is opt-in (costs one details call per new candidate).
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

    def _enrich_reviews(self, place_id: str, external_id: str) -> int:
        """Fetch the place's reviews and store any with a gluten-free signal.

        Returns the number of snippets stored. Failures are logged but never
        crash the search run (enrichment is best-effort context for the Validator).
        """
        try:
            details = self.places.place_details_with_reviews(external_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("review fetch failed for %s", external_id)
            self.log(
                "review_enrich_failed",
                {"external_id": external_id, "error": str(exc)},
                status="error",
                place_id=place_id,
            )
            return 0

        result = details.get("result") or {}
        snippets = GooglePlacesClient.extract_gf_snippets(result.get("reviews"))
        stored = 0
        for snippet in snippets:
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
        return stored

    def run(self) -> dict:
        search_terms = self.targets.get("search_terms", [])
        seen: set[str] = set()
        queries = 0
        candidates_found = 0
        inserted = 0
        skipped = 0
        errors = 0
        reviews_enriched = 0
        review_snippets = 0

        for country in self.targets.get("countries", []):
            country_name = country.get("name")
            for city in country.get("cities", []):
                city_name = city.get("name")
                location = (city.get("lat"), city.get("lng"))
                radius_m = city.get("radius_m")

                for term in search_terms:
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
                            # Best-effort review enrichment, capped per run.
                            if reviews_enriched < self.max_review_enrichments:
                                stored = self._enrich_reviews(row.get("id"), external_id)
                                if stored:
                                    reviews_enriched += 1
                                    review_snippets += stored

        summary = {
            "queries": queries,
            "candidates_found": candidates_found,
            "unique_candidates": len(seen),
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
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
    )

    summary = agent.run()
    print("Search run complete:", summary)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
