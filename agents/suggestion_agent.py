"""Suggestion promoter — turns public "Suggest a Place" form submissions into
real, mappable `places` candidates.

The public form (anon key) can only write RAW user input into the `suggestions`
table — it has no coordinates, and `places.lat/lng` are NOT NULL while geocoding
needs the secret Google key (which must never reach the browser). This agent runs
inside the daily pipeline, reads each new suggestion, and promotes it exactly like
the MCP ``suggest_place`` tool does:

1. Geocode the lead with Google Find Place (``name + city``) to obtain real
   coordinates and a canonical Google ``place_id``. Leads that cannot be resolved
   are marked ``rejected`` (a strong natural spam filter: junk that isn't a real
   place never reaches the map).
2. Dedup against any existing place sharing that ``place_id`` (a place suggested by
   a user that the Search/Social/Web agents already found) → ``duplicate``.
3. Otherwise insert a ``places`` candidate (``source='user'``, ``status='pending'``)
   for the Validator to judge, and mark the suggestion ``promoted`` with the new
   place id.

The geocode→dedup→insert core lives in :func:`promote_suggestion`, shared verbatim
with ``mcp_server/server.py::suggest_place`` so the on-demand MCP tool and the daily
batch never diverge (the same pattern the MCP ``validate_place`` tool uses to reuse
the canonical Validator ``RUBRIC``).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from agents.base import BaseAgent
from agents.clients.google_places import GooglePlacesClient
from agents.clients.supabase_client import SupabaseClient

logger = logging.getLogger("celiacmap.agent")

ALLOWED_CATEGORIES = {"restaurant", "cafe", "shop"}
# Provisional defaults; the Validator assigns the real category / safety level.
DEFAULT_CATEGORY = "restaurant"
DEFAULT_SAFETY_LEVEL = "options_available"  # conservative floor when evidence is thin


def promote_suggestion(
    db: SupabaseClient,
    places: GooglePlacesClient,
    *,
    name: str,
    city: str,
    country: str,
    category: Optional[str] = None,
    evidence_url: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Geocode a suggested lead and promote it into ``places`` as a pending candidate.

    Shared by the MCP ``suggest_place`` tool (on-demand) and :class:`SuggestionAgent`
    (daily batch). Always makes exactly one Google Find Place call.

    Returns a result dict::

        {"outcome": "promoted" | "duplicate" | "unresolved" | "insert_failed",
         "place_id": <uuid|None>, "external_id": <google place_id|None>, "name": name}
    """
    resolved = places.find_place(f"{name} {city}".strip())
    if not resolved or not resolved.get("place_id"):
        return {"outcome": "unresolved", "place_id": None, "external_id": None, "name": name}

    external_id = resolved["place_id"]
    if db.place_exists_by_external_id(external_id):
        return {
            "outcome": "duplicate",
            "place_id": None,
            "external_id": external_id,
            "name": name,
        }

    candidate = GooglePlacesClient.to_candidate(resolved, country=country, city=city)
    candidate.update(
        {
            "source": "user",
            "category": category if category in ALLOWED_CATEGORIES else DEFAULT_CATEGORY,
            "safety_level": DEFAULT_SAFETY_LEVEL,
            # Keep the user's reference URL apart from validation_notes (which the
            # Validator overwrites with its rationale), like the Social/Web agents.
            "social_url": evidence_url,
            "validation_notes": notes,
        }
    )

    inserted = db.insert_place_candidate(candidate)
    if inserted:
        return {
            "outcome": "promoted",
            "place_id": inserted.get("id"),
            "external_id": external_id,
            "name": name,
        }
    return {
        "outcome": "insert_failed",
        "place_id": None,
        "external_id": external_id,
        "name": name,
    }


class SuggestionAgent(BaseAgent):
    name = "suggestion"

    def __init__(
        self,
        db: SupabaseClient,
        places: GooglePlacesClient,
        max_per_run: int = 50,
    ):
        super().__init__(db)
        self.places = places
        self.max_per_run = max_per_run

    def run(self) -> dict:
        if self.max_per_run <= 0:
            return {"seen": 0, "promoted": 0, "duplicate": 0, "rejected": 0,
                    "skipped": 0, "geocodes": 0, "errors": 0}

        suggestions = self.db.fetch_new_suggestions(limit=self.max_per_run)

        seen = promoted = duplicate = rejected = skipped = geocodes = errors = 0

        for s in suggestions:
            seen += 1
            try:
                result = promote_suggestion(
                    self.db,
                    self.places,
                    name=s["name"],
                    city=s["city"],
                    country=s["country"],
                    category=s.get("category"),
                    evidence_url=s.get("evidence_url"),
                    notes=s.get("notes"),
                )
            except Exception as exc:  # noqa: BLE001 - one bad lead must not abort the run
                errors += 1
                logger.exception("promote failed for suggestion %s", s.get("id"))
                self.log(
                    "suggestion_promote_failed",
                    {"id": s.get("id"), "name": s.get("name"), "error": str(exc)},
                    status="error",
                )
                continue

            geocodes += 1  # promote_suggestion always made one Find Place call
            outcome = result["outcome"]

            if outcome == "promoted":
                promoted += 1
                self.db.update_suggestion_status(s["id"], "promoted", result["place_id"])
                self.log(
                    "suggestion_promoted",
                    {"name": result["name"], "place_id": result["place_id"]},
                    status="success",
                    place_id=result["place_id"],
                )
            elif outcome == "duplicate":
                duplicate += 1
                self.db.update_suggestion_status(s["id"], "duplicate")
                self.log(
                    "suggestion_duplicate",
                    {"name": result["name"], "external_id": result["external_id"]},
                    status="success",
                )
            elif outcome == "unresolved":
                rejected += 1
                self.db.update_suggestion_status(s["id"], "rejected")
                self.log(
                    "suggestion_unresolved",
                    {"name": result["name"]},
                    status="success",
                )
            else:  # insert_failed — the upsert returned no row (an ignored
                # (source, external_id) conflict, or a dry-run no-op). Not a hard
                # error: leave the suggestion 'new' so a real transient failure
                # retries next run, and a dry-run stays clean.
                skipped += 1
                self.log(
                    "suggestion_insert_skipped",
                    {"name": result["name"], "external_id": result["external_id"]},
                    status="success",
                )

        summary = {
            "seen": seen,
            "promoted": promoted,
            "duplicate": duplicate,
            "rejected": rejected,
            "skipped": skipped,
            "geocodes": geocodes,
            "errors": errors,
        }
        self.log(
            "suggestion_run_complete",
            summary,
            status="error" if errors else "success",
        )
        return summary


def main() -> int:
    """Run the Suggestion promoter standalone (manual pipeline validation)."""
    from config.settings import get_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    settings.require(
        "supabase_url",
        "supabase_service_role_key",
        "google_maps_api_key",
    )

    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    places = GooglePlacesClient(settings.google_maps_api_key)
    agent = SuggestionAgent(
        db, places, max_per_run=settings.max_suggestions_per_run
    )

    summary = agent.run()
    print("Suggestion run complete:", summary)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
