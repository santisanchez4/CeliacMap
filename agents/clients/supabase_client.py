"""Supabase access for the agents (server-side, service_role key).

The service_role key bypasses Row Level Security, so this client can insert
candidates, change place status, and write the agent log. It must only run
server-side (local .env or CI) — never in the browser.
"""

from __future__ import annotations

from typing import Any

from supabase import Client, create_client


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
        (source, external_id) index for dedup; conflicts are ignored."""
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
