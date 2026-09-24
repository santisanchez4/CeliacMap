"""Supabase access for the agents (server-side, service_role key).

The service_role key bypasses Row Level Security, so this client can insert
candidates, change place status, and write the agent log. It must only run
server-side (local .env or CI) — never in the browser.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
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

    def fetch_places_for_revalidation(
        self, *, max_confidence: float, limit: int = 500
    ) -> list[dict]:
        """Approved places whose stored validation_confidence is below
        max_confidence, worst first.

        The retroactive re-validation target set: places approved under the old
        binary rubric, before the three-tier confidence gates existed. NULL
        confidence is excluded (``< x`` is never true for NULL, and it is a
        separate cohort anyway — seed / pre-column rows).
        """
        res = (
            self._db.table("places")
            .select("*")
            .eq("status", "approved")
            .lt("validation_confidence", max_confidence)
            .not_.is_("validation_confidence", "null")
            .order("validation_confidence")
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

    # owner_celiac is deliberately absent: it is a named third party's health condition and must never
    # reach the Validator (whose free-text output is stored in publicly readable places columns).
    _CLAIM_FACTS = ("kitchen_exclusive", "celiac_prep")

    def fetch_community_claims(self, place_id: str, limit: int = 5) -> list[dict]:
        """Community kitchen declarations about a place (UNVERIFIED evidence).

        Reads the server-only intake tables: the suggestion that was promoted to this
        place and its positive reports (a negative report cannot carry kitchen data).
        Rows with no kitchen datum at all are dropped; newest first, at most ``limit``.
        The caller (Validator) treats these as context to weigh, never as proof.
        """
        columns = "kitchen_exclusive, celiac_prep, created_at"
        rows: list[dict] = []
        suggestions = (
            self._db.table("suggestions")
            .select(columns)
            .eq("promoted_place_id", place_id)
            .execute()
        )
        rows.extend(suggestions.data or [])
        reports = (
            self._db.table("place_reports")
            .select(columns)
            .eq("place_id", place_id)
            .eq("report_type", "positive")
            .execute()
        )
        rows.extend(reports.data or [])
        claims = [r for r in rows if any(r.get(k) is not None for k in self._CLAIM_FACTS)]
        claims.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return claims[:limit]

    # --- place_evidence (server-only) -------------------------------
    EVIDENCE_TEXT_MAX = 1000
    EVIDENCE_URL_MAX = 500

    def add_place_evidence(
        self, place_id: str, source: str, text: str | None = None, url: str | None = None
    ) -> None:
        """Keep what a discovery agent / person told us about a place (audit plan step 1).

        Clamped to the table's CHECK bounds on the way in; a row with neither text nor URL
        is skipped rather than rejected by the database.
        """
        text = (text or "").strip()[: self.EVIDENCE_TEXT_MAX] or None
        url = (url or "").strip()[: self.EVIDENCE_URL_MAX] or None
        if not text and not url:
            return
        self._db.table("place_evidence").insert(
            {"place_id": place_id, "source": source, "text": text, "url": url}
        ).execute()

    def fetch_place_evidence(self, place_id: str, limit: int = 5) -> list[dict]:
        """Newest-first evidence rows for a place (``source``, ``text``, ``url``)."""
        res = (
            self._db.table("place_evidence")
            .select("source, text, url, created_at")
            .eq("place_id", place_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def fetch_unpublished_opinions(self, limit: int = 100) -> list[dict]:
        """Positive reports waiting for moderation: not published yet, about a place that is
        currently ``approved``. Oldest first. The full ``description`` is returned on purpose --
        the admin reads everything before publishing."""
        res = (
            self._db.table("place_reports")
            .select("id, description, author_name, created_at, place_id, places!inner(name, city, country, status, safety_level)")
            .eq("report_type", "positive")
            .is_("published_at", "null")
            .eq("places.status", "approved")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return res.data or []

    def set_opinions_published(self, ids: list[str], published: bool) -> list[dict]:
        """Publish (``published_at = now``) or hide (``null``) positive reports. Returns the rows
        changed. Only positive reports are touched (the table CHECK forbids publishing a negative)."""
        if not ids:
            return []
        stamp = datetime.now(timezone.utc).isoformat() if published else None
        res = (
            self._db.table("place_reports")
            .update({"published_at": stamp})
            .in_("id", ids)
            .eq("report_type", "positive")
            .execute()
        )
        return res.data or []

    def delete_expired_google_reviews(self, cutoff_days: int = 30) -> list[str]:
        """Delete source='google' review snippets older than cutoff_days.

        Google's Places API policy exempts only the place ID from its caching
        restrictions -- reviews must be requested live, not stored indefinitely
        (see CLAUDE.md Decisions Log). source='seed' rows are hand-curated, not
        cached from the API, and are never touched (the filter is hardcoded to
        'google', not "everything").

        Returns the distinct place_id values whose reviews were just deleted, so
        the caller (SearchAgent._refresh_expired_reviews) can re-fetch fresh
        snippets for them.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=cutoff_days)
        ).isoformat()
        res = (
            self._db.table("reviews")
            .delete()
            .eq("source", "google")
            .lt("created_at", cutoff)
            .execute()
        )
        return sorted({r["place_id"] for r in (res.data or []) if r.get("place_id")})

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

    def fetch_recent_negative_report_count(self, place_id: str, days: int = 30) -> int:
        """Distinct negative reports about a place in the last ``days`` (audit plan step 7).

        "Distinct" = by ``reporter_token`` (one per browser); a report without a token (the
        chatbot, older rows) counts on its own. A weak defense — the token lives in the
        browser — backed by the threshold and the admin's review.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        res = (
            self._db.table("place_reports")
            .select("id, reporter_token")
            .eq("place_id", place_id)
            .eq("report_type", "negative")
            .gte("created_at", cutoff)
            .execute()
        )
        return len({r.get("reporter_token") or f"id:{r.get('id')}" for r in (res.data or [])})

    def set_community_warning(self, place_id: str, at: str | None) -> None:
        """Set (ISO timestamp) or clear (None) the public "reportado por la comunidad" warning."""
        self._db.table("places").update({"community_warning_at": at}).eq("id", place_id).execute()

    # --- admin review queue (scripts/review_queue.py, audit plan step 6) ---------
    ADMIN_PLACE_COLUMNS = (
        "id, name, city, country, address, category, safety_level, status, source, lat, lng, "
        "geocode_method, social_url, website, validation_confidence, validation_notes, flags, "
        "recommendation, community_warning_at, created_at"
    )

    def fetch_places_for_admin(
        self,
        status: str | None = None,
        *,
        city: str | None = None,
        flag: str | None = None,
        warned_since: str | None = None,
        safety_level: str | None = None,
        limit: int = 15,
    ) -> list[dict]:
        """Places for the admin to review, oldest first. ``flag`` matches a value inside the
        ``flags`` jsonb list; ``warned_since`` keeps only places with a community warning set
        at or after that ISO timestamp."""
        q = self._db.table("places").select(self.ADMIN_PLACE_COLUMNS)
        if status:
            q = q.eq("status", status)
        if city:
            q = q.ilike("city", f"%{city}%")
        if flag:
            q = q.contains("flags", [flag])
        if warned_since:
            q = q.gte("community_warning_at", warned_since)
        if safety_level:
            q = q.eq("safety_level", safety_level)
        res = q.order("created_at").limit(limit).execute()
        return res.data or []

    def fetch_suggestions_by_status(self, status: str, limit: int = 50) -> list[dict]:
        res = (
            self._db.table("suggestions")
            .select("*")
            .eq("status", status)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return res.data or []

    def fetch_suggestion_by_id(self, suggestion_id: str) -> dict | None:
        res = self._db.table("suggestions").select("*").eq("id", suggestion_id).limit(1).execute()
        return res.data[0] if res.data else None

    def fetch_suggestion_for_place(self, place_id: str) -> dict | None:
        """The community suggestion that was promoted into this place, if any (admin only:
        it can carry the owner_celiac declaration, which never goes to a public column)."""
        res = (
            self._db.table("suggestions")
            .select("*")
            .eq("promoted_place_id", place_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def fetch_recent_negative_reports(self, place_id: str, days: int = 30) -> list[dict]:
        """Negative report texts about a place (admin only — never public)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        res = (
            self._db.table("place_reports")
            .select("id, description, reporter_token, created_at")
            .eq("place_id", place_id)
            .eq("report_type", "negative")
            .gte("created_at", cutoff)
            .order("created_at")
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

    def delete_chatbot_logs(self, cutoff_days: int = 30) -> int:
        """Delete agent_log rows for agent='chatbot' older than cutoff_days.

        Marked chatbot turns can carry raw user/bot text (ADR-006 decision 10),
        so this is the only mechanism that removes it -- the filter is
        hardcoded to 'chatbot' and must never widen to "everything in
        agent_log", a table shared by every other agent. See
        scripts/purge_chat_logs.py and .github/workflows/chat-log-purge.yml.

        Returns the number of rows deleted.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=cutoff_days)
        ).isoformat()
        res = (
            self._db.table("agent_log")
            .delete()
            .eq("agent", "chatbot")
            .lt("created_at", cutoff)
            .execute()
        )
        return len(res.data or [])
