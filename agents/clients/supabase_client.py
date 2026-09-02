"""Supabase access for the agents (server-side, service_role key).

The service_role key bypasses Row Level Security, so this client can insert
candidates, change place status, and write the agent log. It must only run
server-side (local .env or CI) — never in the browser.
"""

from __future__ import annotations

import logging
from typing import Any

from supabase import Client, create_client

logger = logging.getLogger("celiacmap.agent")

# Approximate bounding box for Uruguay + Argentina at full national extent,
# with margin for cities not yet in config/targets.yaml. Used as a last-resort,
# source-agnostic guard in insert_place_candidate() against a place landing far
# outside the project's geographic scope — e.g. a location-biased Google Text
# Search, or a mis-matched Find Place result, that slipped past to_candidate()
# / resolve_location(). NOT a precise border test: Argentina's shape means a
# rectangle cannot exclude Chile / Paraguay / Brazilian border towns — the
# address-country checks upstream and the Validator handle those.
UY_AR_LAT_MIN = -56.0   # south of Tierra del Fuego
UY_AR_LAT_MAX = -21.0   # north of Jujuy / the Argentina–Bolivia border
UY_AR_LNG_MIN = -74.5   # west of the Andes / the Argentina–Chile border
UY_AR_LNG_MAX = -53.0   # east of Misiones and the Uruguayan Atlantic coast


def coordinates_in_scope(lat: Any, lng: Any) -> bool:
    """True if (lat, lng) falls inside the approximate Uruguay+Argentina box.

    A missing or non-numeric coordinate is treated as out of scope: places.lat
    / places.lng are NOT NULL, so such a candidate could not be inserted anyway.
    """
    if isinstance(lat, bool) or isinstance(lng, bool):
        return False
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return False
    return (
        UY_AR_LAT_MIN <= lat <= UY_AR_LAT_MAX
        and UY_AR_LNG_MIN <= lng <= UY_AR_LNG_MAX
    )


class SupabaseClient:
    def __init__(self, url: str, service_role_key: str):
        if not url or not service_role_key:
            raise ValueError("SupabaseClient requires a URL and service_role key.")
        self._db: Client = create_client(url, service_role_key)

    # --- health -------------------------------------------------------
    def health_check(self) -> int:
        """Return the total number of rows in places (proves connectivity)."""
        res = self._db.table("places").select("id", count="exact").limit(1).execute()
        return res.count or 0

    # --- places -------------------------------------------------------
    def insert_place_candidate(self, candidate: dict[str, Any]) -> dict | None:
        """Insert a new candidate as status='pending'. Relies on the unique
        (source, external_id) index for dedup; conflicts are ignored.

        Returns ``None`` (nothing written) for a candidate whose coordinates
        fall outside the approximate Uruguay+Argentina bounding box — a
        source-agnostic backstop, see ``coordinates_in_scope``.
        """
        lat, lng = candidate.get("lat"), candidate.get("lng")
        if not coordinates_in_scope(lat, lng):
            logger.warning(
                "rejecting out-of-scope place candidate %r (source=%s): "
                "(%s, %s) is outside the Uruguay/Argentina bounding box",
                candidate.get("name"),
                candidate.get("source"),
                lat,
                lng,
            )
            return None
        payload = {**candidate, "status": "pending"}
        res = (
            self._db.table("places")
            .upsert(payload, on_conflict="source,external_id", ignore_duplicates=True)
            .execute()
        )
        return res.data[0] if res.data else None

    def place_exists_by_external_id(self, external_id: str) -> bool:
        """True if any place (any source) already has this external_id.

        Lets the Social agent dedup a geocoded lead against a place the Search
        agent already discovered, since they share the Google place_id but use
        different ``source`` values (so the unique constraint alone won't catch it).
        """
        if not external_id:
            return False
        res = (
            self._db.table("places")
            .select("id")
            .eq("external_id", external_id)
            .limit(1)
            .execute()
        )
        return bool(res.data)

    def fetch_places_by_status(self, status: str, limit: int = 100) -> list[dict]:
        res = (
            self._db.table("places")
            .select("*")
            .eq("status", status)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def fetch_place_by_id(self, place_id: str) -> dict | None:
        res = (
            self._db.table("places")
            .select("*")
            .eq("id", place_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def fetch_needs_review_for_outreach(self, limit: int = 100) -> list[dict]:
        """Oldest needs_review places not yet contacted (used by the Outreach agent).

        outreach_opt_out=False is enforced here (primary, cheap) and again in
        OutreachAgent._select_candidates (defense in depth, ADR-003) — a place
        that asked not to be contacted again must never be reselected,
        regardless of outreach_status.
        """
        res = (
            self._db.table("places")
            .select("*")
            .eq("status", "needs_review")
            .eq("outreach_status", "not_sent")
            .eq("outreach_opt_out", False)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return res.data or []

    def update_place(self, place_id: str, patch: dict[str, Any]) -> None:
        """Apply an arbitrary field patch to a place (used by the Updater).

        The updated_at trigger keeps that column fresh; a no-op patch is skipped.
        """
        if not patch:
            return
        self._db.table("places").update(patch).eq("id", place_id).execute()

    def update_place_validation(
        self,
        place_id: str,
        *,
        status: str,
        confidence: float | None = None,
        notes: str | None = None,
        verified: bool | None = None,
        category: str | None = None,
        safety_level: str | None = None,
        flags: list[str] | None = None,
        recommendation: str | None = None,
    ) -> None:
        patch: dict[str, Any] = {"status": status}
        if confidence is not None:
            patch["validation_confidence"] = confidence
        if notes is not None:
            patch["validation_notes"] = notes
        if verified is not None:
            patch["verified"] = verified
        if category is not None:
            patch["category"] = category
        if safety_level is not None:
            patch["safety_level"] = safety_level
        if flags is not None:
            patch["flags"] = flags
        if recommendation is not None:
            patch["recommendation"] = recommendation
        self._db.table("places").update(patch).eq("id", place_id).execute()

    # --- reviews ------------------------------------------------------
    def insert_review(
        self,
        place_id: str,
        text: str,
        *,
        rating: int | None = None,
        source: str = "google",
    ) -> dict | None:
        """Insert a review snippet for a place (used by review enrichment)."""
        payload: dict[str, Any] = {
            "place_id": place_id,
            "text": text,
            "rating": rating,
            "source": source,
        }
        res = self._db.table("reviews").insert(payload).execute()
        return res.data[0] if res.data else None

    def fetch_reviews_for_place(self, place_id: str, limit: int = 5) -> list[dict]:
        res = (
            self._db.table("reviews")
            .select("text, rating, source")
            .eq("place_id", place_id)
            .limit(limit)
            .execute()
        )
        return res.data or []

    # --- suggestions --------------------------------------------------
    def fetch_new_suggestions(self, limit: int = 50) -> list[dict]:
        """Return public-form suggestions awaiting promotion (status='new')."""
        res = (
            self._db.table("suggestions")
            .select("*")
            .eq("status", "new")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return res.data or []

    def update_suggestion_status(
        self,
        suggestion_id: str,
        status: str,
        promoted_place_id: str | None = None,
    ) -> None:
        """Mark a suggestion as promoted / duplicate / rejected by the promoter."""
        patch: dict[str, Any] = {"status": status}
        if promoted_place_id is not None:
            patch["promoted_place_id"] = promoted_place_id
        self._db.table("suggestions").update(patch).eq("id", suggestion_id).execute()

    # --- outreach_messages ---------------------------------------------
    def insert_outreach_message(
        self,
        place_id: str,
        *,
        direction: str,
        channel: str,
        content: str,
    ) -> dict | None:
        """Record one message in the outreach send/reply thread for a place."""
        res = (
            self._db.table("outreach_messages")
            .insert(
                {
                    "place_id": place_id,
                    "direction": direction,
                    "channel": channel,
                    "content": content,
                }
            )
            .execute()
        )
        return res.data[0] if res.data else None

    def fetch_latest_received_message(self, place_id: str) -> dict | None:
        """Most recent business reply on file for a place (Outreach Etapa 2)."""
        res = (
            self._db.table("outreach_messages")
            .select("*")
            .eq("place_id", place_id)
            .eq("direction", "received")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    # --- place_reports --------------------------------------------------
    def fetch_place_report_by_id(self, report_id: str) -> dict | None:
        res = (
            self._db.table("place_reports")
            .select("*")
            .eq("id", report_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def update_place_report_status(self, report_id: str, status: str) -> None:
        self._db.table("place_reports").update({"status": status}).eq("id", report_id).execute()

    def claim_place_report(self, report_id: str) -> bool:
        """Atomic claim (compare-and-swap on status) — the idempotency guard
        shared by the real-time webhook path and the monthly sweep. Returns
        True only if this call transitioned the row from 'new'/'dispatched'
        to 'processing'; False means another call already claimed or
        finished it, and the caller MUST NOT proceed (no LLM call, no writes
        to `places`).
        """
        res = (
            self._db.table("place_reports")
            .update({"status": "processing"})
            .eq("id", report_id)
            .in_("status", ["new", "dispatched"])
            .execute()
        )
        return bool(res.data)

    def fetch_stuck_negative_reports(self, limit: int = 50) -> list[dict]:
        """Negative reports still in 'new'/'dispatched' — candidates for the
        monthly sweep (ReviewHandler.sweep()). Whether the place is still
        'approved' is intentionally NOT filtered here: handle() re-checks it
        via ACTIONABLE_STATUSES, so filtering twice would just duplicate
        logic without changing the outcome.
        """
        res = (
            self._db.table("place_reports")
            .select("id, place_id")
            .eq("report_type", "negative")
            .in_("status", ["new", "dispatched"])
            .not_.is_("place_id", "null")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return res.data or []

    # --- agent_log ----------------------------------------------------
    def insert_agent_log(
        self,
        agent: str,
        action: str,
        result: dict | None = None,
        status: str = "success",
        place_id: str | None = None,
    ) -> None:
        self._db.table("agent_log").insert(
            {
                "agent": agent,
                "action": action,
                "result": result,
                "status": status,
                "place_id": place_id,
            }
        ).execute()
