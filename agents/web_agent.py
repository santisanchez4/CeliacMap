"""Web discovery agent (v3) — autonomous, web-search-driven candidate discovery.

The evolution of discovery: v1 (Google Places tags) → v2 (Tavily social) → v3
(this agent). Instead of a fixed query matrix, it hands Claude the Anthropic
server-side **web search** + **web fetch** tools and a single city/country, and
lets the model reason freely about how to find gluten-free / "sin TACC" places —
reading forums, blogs, Facebook groups, Instagram, news, etc. — that the other
agents miss.

Each lead the model returns is then resolved into a real ``places`` row exactly
like the Social agent does:

1. Pick the cities to research from ``config/targets.yaml`` — only those flagged
   ``web: true`` (capped by ``max_cities`` and the pipeline's shared budget), so
   v3 can be rolled out one city at a time.
2. Ask the model (default ``claude-sonnet-4-6``) for candidates with supporting
   evidence + a source URL (no coordinates — web mentions have none).
3. Geocode each lead with Google Find Place (``name + city``) to obtain real
   coordinates and a canonical Google ``place_id``. Leads that cannot be resolved
   are skipped and logged (``places.lat/lng`` are NOT NULL).
4. Insert as ``status='pending'``, ``source='web'``, ``external_id`` = the Google
   ``place_id`` (so a place found via Search/Social/Web is not duplicated), with
   the source URL kept in its own ``social_url`` column.

Every result and a final run summary are written to ``agent_log``. The Validator
judges web candidates exactly like any other pending place — this agent only
changes *discovery*, never the quality gate.
"""

from __future__ import annotations

import logging

from agents.base import BaseAgent
from agents.clients.google_places import GooglePlacesClient
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient

logger = logging.getLogger("celiacmap.agent")

ALLOWED_CATEGORIES = {"restaurant", "cafe", "shop"}
DEFAULT_CATEGORY = "restaurant"
# Conservative floor; the Validator sets the real safety level later.
DEFAULT_SAFETY_LEVEL = "options_available"

# Research rubric: how to hunt, what counts, and the exact output shape. Fixed
# across cities in a run, so it is sent as a cached system block.
RESEARCH_RUBRIC = """\
You are the Web Researcher for CeliacMap, a curated directory of gluten-free / \
"sin TACC" (celiac-safe) places in Latin America. Given one city and country, use \
web search to find real, currently-operating places that serve or sell \
gluten-free / celiac-safe food: restaurants, cafes/bakeries, and shops \
(dietéticas, health-food stores, supermarkets with GF products).

Reason freely about how to find them. Do not rely on a single query — search the \
way a celiac local would: community blogs and forums, Facebook groups, Instagram \
posts and roundups, local news and "dónde comer sin TACC" guides, and celiac \
association listings. Prioritise places that are discussed by the community but \
may not be obvious on the map. Fetch pages when a snippet looks promising but \
incomplete.

For every place you are reasonably confident is real and gluten-free relevant, \
collect:
- "name": the business name, cleaned (drop handles, emojis, "| Instagram", etc.).
- "category": exactly one of "restaurant" (somewhere to eat), "cafe" (cafe, \
coffee shop, bakery, pastry shop) or "shop" (grocery, supermarket, health-food / \
dietetica). If unclear, use your best single guess.
- "address": a street address if you find one, else null.
- "evidence": one short sentence on why this place is gluten-free relevant \
(what the source actually says).
- "source_url": the URL of the page that supports this place.

Rules:
- Only include places physically in the requested city/country.
- Do NOT invent places. If you cannot find a real source, leave it out.
- Prefer fewer, well-supported places over many weak guesses.
- A later validator and a geocoding step will verify each place, so it is fine if \
some are later discarded — but never fabricate a name or a URL.

When done, respond with ONLY a JSON object, no prose, in exactly this shape:
{"places": [
  {"name": <string>,
   "category": "restaurant" | "cafe" | "shop",
   "address": <string|null>,
   "evidence": <string>,
   "source_url": <string>}
]}
If you find nothing, return {"places": []}.
"""


class WebAgent(BaseAgent):
    name = "web"

    def __init__(
        self,
        db: SupabaseClient,
        places: GooglePlacesClient,
        llm: LLMClient,
        targets: dict,
        model: str | None = None,
        max_cities: int = 2,
        max_searches_per_city: int = 8,
        max_leads_per_city: int = 25,
    ):
        super().__init__(db)
        self.places = places
        self.llm = llm
        self.targets = targets
        self.model = model  # None -> LLMClient.default_model
        self.max_cities = max_cities
        self.max_searches_per_city = max_searches_per_city
        self.max_leads_per_city = max_leads_per_city

    def _cities(self) -> list[dict]:
        """Cities flagged ``web: true`` in targets.yaml, capped at max_cities.

        The opt-in flag lets v3 roll out one city at a time; a city carries its
        country name and center coordinates (used to bias geocoding).
        """
        selected: list[dict] = []
        for country in self.targets.get("countries", []):
            country_name = country.get("name")
            for city in country.get("cities", []):
                if not city.get("web"):
                    continue
                selected.append(
                    {
                        "country": country_name,
                        "city": city.get("name"),
                        "location": (city.get("lat"), city.get("lng")),
                    }
                )
        return selected[: self.max_cities]

    @staticmethod
    def _user_prompt(country: str, city: str) -> str:
        return f"Find gluten-free / sin TACC places in {city}, {country}."

    def _clean_lead(self, lead: dict) -> dict | None:
        """Validate/normalize one model lead; None if it has no usable name."""
        name = (lead.get("name") or "").strip()
        if not name:
            return None
        category = lead.get("category")
        if category not in ALLOWED_CATEGORIES:
            category = DEFAULT_CATEGORY
        return {
            "name": name,
            "category": category,
            "address": (lead.get("address") or "").strip() or None,
            "source_url": (lead.get("source_url") or "").strip() or None,
        }

    def run(self) -> dict:
        cities = self._cities()
        seen_external: set[str] = set()

        cities_done = 0
        leads_found = 0
        geocoded = 0
        inserted = 0
        skipped = 0
        errors = 0

        for entry in cities:
            country = entry["country"]
            city = entry["city"]
            location = entry["location"]
            cities_done += 1

            try:
                result = self.llm.research_with_web_search(
                    RESEARCH_RUBRIC,
                    self._user_prompt(country, city),
                    model=self.model,
                    max_searches=self.max_searches_per_city,
                )
            except Exception as exc:  # noqa: BLE001 - one city's failure must not abort the run
                errors += 1
                logger.exception("web research failed for %s", city)
                self.log(
                    "web_research_failed",
                    {"city": city, "country": country, "error": str(exc)},
                    status="error",
                )
                continue

            leads = (result or {}).get("places") or []
            for raw in leads[: self.max_leads_per_city]:
                lead = self._clean_lead(raw)
                if not lead:
                    skipped += 1
                    continue
                leads_found += 1

                try:
                    match = self.places.find_place(
                        f"{lead['name']} {city}".strip(), location=location
                    )
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    logger.exception("find_place failed for %r", lead["name"])
                    self.log(
                        "web_geocode_failed",
                        {"name": lead["name"], "city": city, "error": str(exc)},
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
                        "web_unresolved",
                        {"name": lead["name"], "city": city, "url": lead["source_url"]},
                        status="success",
                    )
                    continue

                if (match or {}).get("business_status") == "CLOSED_PERMANENTLY":
                    skipped += 1
                    continue

                geocoded += 1

                # Dedup: within the run, and against any place already in the DB
                # (found by Search/Social/Web) sharing this place_id.
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
                    "country": country,
                    "city": city,
                    "source": "web",
                    "external_id": external_id,
                    # Kept in its own column so the Validator (which overwrites
                    # validation_notes) can't clobber the provenance URL.
                    "social_url": lead["source_url"],
                }
                try:
                    row = self.db.insert_place_candidate(candidate)
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    logger.exception("insert failed for %r", candidate["name"])
                    self.log(
                        "web_insert_failed",
                        {"name": candidate["name"], "city": city, "error": str(exc)},
                        status="error",
                    )
                    continue

                if row:
                    inserted += 1
                    self.log(
                        "web_candidate_inserted",
                        {
                            "name": candidate["name"],
                            "city": city,
                            "url": lead["source_url"],
                        },
                        status="success",
                    )
                else:
                    skipped += 1

        summary = {
            "cities": cities_done,
            # Worst-case search count, for the pipeline's shared budget accounting.
            "searches": cities_done * self.max_searches_per_city,
            "leads_found": leads_found,
            "geocoded": geocoded,
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }
        self.log(
            "web_run_complete",
            summary,
            status="error" if errors else "success",
        )
        return summary


def main() -> int:
    """Run the Web discovery agent standalone (manual pipeline validation)."""
    from config.settings import get_settings, load_targets

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    settings.require(
        "supabase_url",
        "supabase_service_role_key",
        "google_maps_api_key",
        "anthropic_api_key",
    )

    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    places = GooglePlacesClient(settings.google_maps_api_key)
    llm = LLMClient(settings.anthropic_api_key, settings.web_search_model)
    agent = WebAgent(
        db,
        places,
        llm,
        load_targets(),
        model=settings.web_search_model,
        max_cities=settings.max_web_cities_per_run,
        max_searches_per_city=settings.max_web_searches_per_city,
    )

    summary = agent.run()
    print("Web run complete:", summary)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
