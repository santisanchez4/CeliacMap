"""Updater agent — keeps already-approved places current.

Re-checks every ``approved`` place that came from Google Places (by its
``external_id``) and reconciles our row with reality:

- **Closed** (``CLOSED_PERMANENTLY`` / ``permanently_closed``) -> discarded, so it
  drops off the public map immediately (closed places are not safe to surface).
- **Name / address / category change** -> the row is patched in place.
- **Gone** (``NOT_FOUND``) or a details error -> flagged for human review via
  ``agent_log``; the row is left untouched (could be transient).

Deterministic by design (no LLM by default). Haiku is used **only** as a narrow
fallback to assign a category when the Google ``types`` map to none of ours —
the one genuinely ambiguous text signal. Manual/seed places (no ``external_id``)
are skipped, and the number of places re-checked per run is capped to stay within
the API budget. Every check — and a run summary — is written to ``agent_log``.
"""

from __future__ import annotations

import logging

from agents.base import BaseAgent
from agents.clients.google_places import GooglePlacesClient
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient

logger = logging.getLogger("celiacmap.agent")

ALLOWED_CATEGORIES = {"restaurant", "cafe", "shop"}

# Narrow Haiku rubric: used only when Google types map to no category of ours.
CATEGORY_RUBRIC = """\
You classify a place into exactly one of three categories for a gluten-free \
directory:
- "restaurant": somewhere to eat a meal (restaurant, takeaway).
- "cafe": coffee shop, cafe, bakery or pastry shop.
- "shop": grocery, supermarket, or health-food / dietetica shop.
Respond with ONLY a JSON object: {"category": "restaurant" | "cafe" | "shop"}.
"""


class UpdaterAgent(BaseAgent):
    name = "updater"

    def __init__(
        self,
        db: SupabaseClient,
        places: GooglePlacesClient,
        targets: dict,
        max_checks_per_run: int = 50,
        llm: LLMClient | None = None,
        haiku_model: str | None = None,
    ):
        super().__init__(db)
        self.places = places
        self.max_checks_per_run = max_checks_per_run
        self.llm = llm
        self.haiku_model = haiku_model
        self._category_by_type = self._build_type_index(targets.get("categories", {}))

    @staticmethod
    def _build_type_index(categories: dict) -> dict[str, str]:
        index: dict[str, str] = {}
        for category, gtypes in (categories or {}).items():
            for gtype in gtypes or []:
                index[gtype] = category
        return index

    def _category_from_types(self, types: list[str]) -> str | None:
        """Deterministic category from Google types; None if none map."""
        for gtype in types or []:
            if gtype in self._category_by_type:
                return self._category_by_type[gtype]
        return None

    def _category_with_llm(self, name: str, types: list[str]) -> str | None:
        """Haiku fallback for the ambiguous case (types map to nothing)."""
        if not self.llm:
            return None
        try:
            user = f"name: {name}\ntypes: {', '.join(types or [])}"
            verdict = self.llm.complete_json(
                CATEGORY_RUBRIC, user, model=self.haiku_model, max_tokens=64
            )
        except Exception:  # noqa: BLE001
            logger.exception("Haiku category fallback failed for %r", name)
            return None
        category = verdict.get("category")
        return category if category in ALLOWED_CATEGORIES else None

    @staticmethod
    def _is_closed(result: dict) -> bool:
        return (
            result.get("business_status") == "CLOSED_PERMANENTLY"
            or result.get("permanently_closed") is True
        )

    def _build_patch(self, place: dict, result: dict) -> dict:
        """Deterministic field diff (no status changes here)."""
        patch: dict = {}

        new_name = (result.get("name") or "").strip()
        if new_name and new_name != (place.get("name") or "").strip():
            patch["name"] = new_name

        new_address = (result.get("formatted_address") or "").strip()
        if new_address and new_address != (place.get("address") or "").strip():
            patch["address"] = new_address

        types = result.get("types") or []
        new_category = self._category_from_types(types)
        if new_category is None:
            new_category = self._category_with_llm(new_name or place.get("name"), types)
        if new_category and new_category != place.get("category"):
            patch["category"] = new_category

        # Rich panel fields (phone/website/hours/rating). Only patch a field when
        # Google has a value and it differs from what we already store.
        for key, value in GooglePlacesClient.extract_rich_fields(result).items():
            if value not in (None, "", []) and value != place.get(key):
                patch[key] = value

        return patch

    def run(self) -> dict:
        approved = self.db.fetch_places_by_status(
            "approved", limit=self.max_checks_per_run
        )
        checked = 0
        updated = 0
        closed = 0
        unchanged = 0
        flagged = 0
        errors = 0

        for place in approved:
            place_id = place.get("id")
            external_id = place.get("external_id")

            # Manual/seed places have no Google id — nothing to re-check.
            if place.get("source") != "google_places" or not external_id:
                continue

            checked += 1
            try:
                details = self.places.place_details(external_id)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.exception("place_details failed for %s", external_id)
                self.log(
                    "update_check_failed",
                    {"name": place.get("name"), "error": str(exc)},
                    status="error",
                    place_id=place_id,
                )
                continue

            api_status = details.get("status")
            result = details.get("result") or {}

            # Listing gone — flag for human review, do not auto-change the row.
            if api_status == "NOT_FOUND" or (api_status and api_status != "OK"):
                flagged += 1
                self.log(
                    "flagged_for_review",
                    {"name": place.get("name"), "api_status": api_status},
                    status="error",
                    place_id=place_id,
                )
                continue

            try:
                if self._is_closed(result):
                    self.db.update_place_validation(
                        place_id,
                        status="discarded",
                        notes="Updater: permanently closed (Google Places).",
                    )
                    closed += 1
                    self.log(
                        "closed_discarded",
                        {"name": place.get("name")},
                        status="success",
                        place_id=place_id,
                    )
                    continue

                patch = self._build_patch(place, result)
                if patch:
                    self.db.update_place(place_id, patch)
                    updated += 1
                    self.log(
                        "updated",
                        {"name": place.get("name"), "changes": patch},
                        status="success",
                        place_id=place_id,
                    )
                else:
                    unchanged += 1
                    self.log(
                        "unchanged",
                        {"name": place.get("name")},
                        status="success",
                        place_id=place_id,
                    )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.exception("applying update failed for %s", place_id)
                self.log(
                    "update_persist_failed",
                    {"name": place.get("name"), "error": str(exc)},
                    status="error",
                    place_id=place_id,
                )

        summary = {
            "approved_seen": len(approved),
            "checked": checked,
            "updated": updated,
            "closed": closed,
            "unchanged": unchanged,
            "flagged": flagged,
            "errors": errors,
        }
        self.log(
            "updater_run_complete",
            summary,
            status="error" if errors else "success",
        )
        return summary


def main() -> int:
    """Run the Updater agent standalone (manual pipeline validation)."""
    from config.settings import get_settings, load_targets

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    settings.require(
        "supabase_url", "supabase_service_role_key", "google_maps_api_key"
    )

    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    places = GooglePlacesClient(settings.google_maps_api_key)

    # Haiku is optional: only wired when an Anthropic key is present, and even
    # then it is invoked only for the ambiguous-category fallback.
    llm = (
        LLMClient(settings.anthropic_api_key, settings.haiku_model)
        if settings.anthropic_api_key
        else None
    )

    agent = UpdaterAgent(
        db,
        places,
        load_targets(),
        max_checks_per_run=settings.max_updates_per_run,
        llm=llm,
        haiku_model=settings.haiku_model,
    )

    summary = agent.run()
    print("Updater run complete:", summary)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
