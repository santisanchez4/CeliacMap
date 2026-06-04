"""Social agent — discovers gluten-free / sin TACC places from social media.

Approach: index public Instagram and Facebook business pages via the Tavily
Search API (query ``"sin TACC" "Montevideo"`` restricted to a platform domain),
then turn each promising result into a real ``places`` candidate:

1. Generate ``"<term>" "<city>"`` queries from ``config/targets.yaml`` (terms)
   crossed with the country/city list and each platform domain.
2. Run each query against Tavily, restricting results to the platform domain via
   ``include_domains`` (free tier: 1000 searches/month; capped here by
   ``max_queries`` and the pipeline's shared budget).
3. Parse each result's title/snippet with ``claude-haiku-4-5`` into
   ``{name, city, category, address}``.
4. Geocode the lead with Google Find Place (``name + city``) to obtain real
   coordinates and a canonical Google ``place_id`` — social URLs have no
   coordinates, and ``places.lat/lng`` are NOT NULL. Leads that cannot be resolved
   are skipped and logged.
5. Insert as ``status='pending'``, ``source='social'``, ``external_id`` = the
   Google ``place_id`` (so a place found both via Search and via Social is not
   duplicated), recording the social profile URL in ``validation_notes``.

Every result and a final run summary are written to ``agent_log``. The Validator
judges social candidates exactly like any other pending place.
"""

from __future__ import annotations

import logging
import urllib.parse

from agents.base import BaseAgent
from agents.clients.google_places import GooglePlacesClient
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient
from agents.clients.tavily_client import TavilySearchClient

logger = logging.getLogger("celiacmap.agent")

ALLOWED_CATEGORIES = {"restaurant", "cafe", "shop"}
DEFAULT_CATEGORY = "restaurant"
# Conservative floor; the Validator sets the real safety level later.
DEFAULT_SAFETY_LEVEL = "options_available"

# Haiku rubric: extract a structured lead from a search-result title + snippet.
PARSE_RUBRIC = """\
You extract a business lead from a single Google search result that points to a \
public Instagram or Facebook page, for a directory of gluten-free / "sin TACC" \
(celiac-safe) places in Latin America.

From the title and snippet, extract:
- "name": the business name (clean it: drop "(@handle)", "| Instagram", \
"- Facebook", follower counts, emojis). If you cannot identify a real business \
name, use null.
- "city": the city if mentioned, else null.
- "category": exactly one of "restaurant" (somewhere to eat), "cafe" (cafe, \
coffee shop, bakery, pastry shop) or "shop" (grocery, supermarket, health-food / \
dietetica). If unclear, use null.
- "address": a street address if present in the text, else null.

Respond with ONLY a JSON object, no prose, exactly:
{"name": <string|null>, "city": <string|null>,
 "category": "restaurant" | "cafe" | "shop" | null,
 "address": <string|null>}
"""


def _canonical_url(url: str | None) -> str | None:
    """Normalize a profile URL for dedup: drop scheme case, query and fragment."""
    if not url:
        return None
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return url.strip()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urllib.parse.urlunsplit((parts.scheme.lower(), netloc, path, "", ""))


class SocialAgent(BaseAgent):
    name = "social"

    def __init__(
        self,
        db: SupabaseClient,
        search_client: TavilySearchClient,
        places: GooglePlacesClient,
        llm: LLMClient,
        targets: dict,
        haiku_model: str | None = None,
        max_queries: int = 16,
        results_per_query: int = 10,
    ):
        super().__init__(db)
        self.search_client = search_client
        self.places = places
        self.llm = llm
        self.targets = targets
        self.haiku_model = haiku_model
        self.max_queries = max_queries
        self.results_per_query = results_per_query

    def _build_queries(self) -> list[dict]:
        """Generate "<term>" "<city>" queries, one per platform (data-driven).

        The platform is applied via Tavily's ``include_domains`` (Tavily does not
        honor Google's ``site:`` operator), keeping one query per platform so the
        per-run cap and budget accounting stay one-call-per-query.
        """
        social = self.targets.get("social", {}) or {}
        platforms = social.get("platforms", []) or []
        terms = social.get("search_terms", []) or []

        queries: list[dict] = []
        for country in self.targets.get("countries", []):
            country_name = country.get("name")
            for city in country.get("cities", []):
                city_name = city.get("name")
                location = (city.get("lat"), city.get("lng"))
                for platform in platforms:
                    for term in terms:
                        queries.append(
                            {
                                "q": f'"{term}" "{city_name}"',
                                "domains": [platform],
                                "country": country_name,
                                "city": city_name,
                                "location": location,
                            }
                        )
        return queries[: self.max_queries]

    def _parse_lead(self, result: dict) -> dict | None:
        """Use Haiku to extract {name, city, category, address} from a result."""
        title = result.get("title") or ""
        snippet = result.get("snippet") or ""
        user = f"title: {title}\nsnippet: {snippet}"
        try:
            verdict = self.llm.complete_json(
                PARSE_RUBRIC, user, model=self.haiku_model, max_tokens=200
            )
        except Exception:  # noqa: BLE001
            logger.exception("Haiku lead parse failed for %r", title)
            return None

        name = (verdict.get("name") or "").strip()
        if not name:
            return None
        category = verdict.get("category")
        if category not in ALLOWED_CATEGORIES:
            category = DEFAULT_CATEGORY
        return {
            "name": name,
            "city": (verdict.get("city") or "").strip() or None,
            "category": category,
            "address": (verdict.get("address") or "").strip() or None,
        }

    def run(self) -> dict:
        queries = self._build_queries()
        seen_urls: set[str] = set()
        seen_external: set[str] = set()

        queries_run = 0
        results_seen = 0
        parsed = 0
        geocoded = 0
        inserted = 0
        skipped = 0
        errors = 0

        for q in queries:
            queries_run += 1
            try:
                results = self.search_client.search(
                    q["q"], num=self.results_per_query, include_domains=q["domains"]
                )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.exception("tavily search failed for %r", q["q"])
                self.log(
                    "social_query_failed",
                    {"query": q["q"], "error": str(exc)},
                    status="error",
                )
                continue

            for result in results:
                url = _canonical_url(result.get("link"))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                results_seen += 1

                lead = self._parse_lead(result)
                if not lead:
                    skipped += 1
                    continue
                parsed += 1

                lead_city = lead["city"] or q["city"]
                try:
                    match = self.places.find_place(
                        f"{lead['name']} {lead_city}".strip(),
                        location=q["location"],
                    )
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    logger.exception("find_place failed for %r", lead["name"])
                    self.log(
                        "social_geocode_failed",
                        {"name": lead["name"], "url": url, "error": str(exc)},
                        status="error",
                    )
                    continue

                external_id = (match or {}).get("place_id")
                loc = ((match or {}).get("geometry") or {}).get("location") or {}
                lat, lng = loc.get("lat"), loc.get("lng")

                # No geocode -> no coordinates -> cannot place it on the map.
                if not external_id or lat is None or lng is None:
                    skipped += 1
                    self.log(
                        "social_unresolved",
                        {"name": lead["name"], "url": url},
                        status="success",
                    )
                    continue

                if (match or {}).get("business_status") == "CLOSED_PERMANENTLY":
                    skipped += 1
                    continue

                geocoded += 1

                # Dedup: within the run, and against any place already in the DB
                # (e.g. discovered by the Search agent) sharing this place_id.
                if external_id in seen_external:
                    skipped += 1
                    continue
                seen_external.add(external_id)
                try:
                    if self.db.place_exists_by_external_id(external_id):
                        skipped += 1
                        continue
                except Exception:  # noqa: BLE001 - dedup check must not crash run
                    logger.exception("dedup check failed for %s", external_id)

                candidate = {
                    "name": (match or {}).get("name") or lead["name"],
                    "lat": lat,
                    "lng": lng,
                    "address": (match or {}).get("formatted_address") or lead["address"],
                    "category": lead["category"],
                    "safety_level": DEFAULT_SAFETY_LEVEL,
                    "country": q["country"],
                    "city": lead_city,
                    "source": "social",
                    "external_id": external_id,
                    "validation_notes": f"Social lead: {url}",
                }
                try:
                    row = self.db.insert_place_candidate(candidate)
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    logger.exception("insert failed for %r", candidate["name"])
                    self.log(
                        "social_insert_failed",
                        {"name": candidate["name"], "url": url, "error": str(exc)},
                        status="error",
                    )
                    continue

                if row:
                    inserted += 1
                    self.log(
                        "social_candidate_inserted",
                        {"name": candidate["name"], "url": url, "city": lead_city},
                        status="success",
                    )
                else:
                    skipped += 1

        summary = {
            "queries": queries_run,
            "results_seen": results_seen,
            "parsed": parsed,
            "geocoded": geocoded,
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }
        self.log(
            "social_run_complete",
            summary,
            status="error" if errors else "success",
        )
        return summary


def main() -> int:
    """Run the Social agent standalone (manual pipeline validation)."""
    from config.settings import get_settings, load_targets

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    settings.require(
        "supabase_url",
        "supabase_service_role_key",
        "google_maps_api_key",
        "anthropic_api_key",
        "tavily_api_key",
    )

    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    search_client = TavilySearchClient(settings.tavily_api_key)
    places = GooglePlacesClient(settings.google_maps_api_key)
    llm = LLMClient(settings.anthropic_api_key, settings.haiku_model)
    agent = SocialAgent(
        db,
        search_client,
        places,
        llm,
        load_targets(),
        haiku_model=settings.haiku_model,
        max_queries=settings.max_social_queries_per_run,
    )

    summary = agent.run()
    print("Social run complete:", summary)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
