"""Email the admin about what people do on the site (audit plan step 9).

Two channels:
- ``AdminNotifier.urgent()`` — one email per event, only for what cannot wait (a negative report,
  a place taken off the map, a business replying). Capped per hour: past the cap the event is only
  logged and shows up in the daily digest, so a bot filling a form cannot flood the inbox.
- ``scripts/admin_digest.py`` — one email a day with everything else.

Sent with Resend from ``avisos@celiacmap.org`` to ``ADMIN_EMAIL``. Subjects carry a fixed
``[CeliacMap]`` prefix so the inbox can filter them. Best-effort: a failed email never breaks the
agent that triggered it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("celiacmap.agent")

SUBJECT_PREFIX = "[CeliacMap]"
DEFAULT_SENDER = "CeliacMap <avisos@celiacmap.org>"
URGENT_HOURLY_CAP = 10
ALERT_ACTION = "admin_alert_sent"


class AdminNotifier:
    def __init__(self, resend, db, to: str, from_address: str = DEFAULT_SENDER,
                 hourly_cap: int = URGENT_HOURLY_CAP):
        self.resend = resend
        self.db = db
        self.to = (to or "").strip()
        self.from_address = from_address
        self.hourly_cap = hourly_cap

    @property
    def enabled(self) -> bool:
        return bool(self.resend and self.to)

    def urgent(self, subject: str, text: str, *, agent: str, place_id: str | None = None) -> bool:
        """Send one urgent email now. Returns True when it was sent."""
        if not self.enabled:
            return False
        since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        try:
            sent_last_hour = int(self.db.fetch_agent_log_count(ALERT_ACTION, since))
        except Exception:  # noqa: BLE001 - if we can't count, still alert (it's urgent)
            logger.exception("counting admin alerts failed")
            sent_last_hour = 0
        if sent_last_hour >= self.hourly_cap:
            logger.warning("admin alert cap reached (%s/h); leaving %r for the digest", self.hourly_cap, subject)
            return False
        try:
            self.resend.send(
                to=self.to,
                subject=f"{SUBJECT_PREFIX} {subject}",
                text=text,
                from_address=self.from_address,
            )
        except Exception:  # noqa: BLE001 - an email must never break the caller
            logger.exception("admin alert failed: %r", subject)
            return False
        try:
            self.db.insert_agent_log(agent, ALERT_ACTION, {"subject": subject}, "success", place_id)
        except Exception:  # noqa: BLE001
            logger.exception("logging the admin alert failed")
        return True


def build_notifier(settings, db) -> AdminNotifier | None:
    """An AdminNotifier when RESEND_API_KEY and ADMIN_EMAIL are set, else None (alerts off)."""
    if not (getattr(settings, "resend_api_key", "") and getattr(settings, "admin_email", "")):
        return None
    from agents.clients.resend_client import ResendClient

    return AdminNotifier(ResendClient(settings.resend_api_key), db, settings.admin_email,
                         settings.admin_sender_email or DEFAULT_SENDER)
