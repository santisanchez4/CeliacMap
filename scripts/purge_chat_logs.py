"""Weekly retention purge (ADR-006 decision 10; privacy phases 1 and 2, 2026-09-29 / 30).

Deletes, and nothing else:
- agent_log rows with agent='chatbot' older than 30 days (marked turns can carry raw user/bot text);
- chat_usage rate-limit counters (session token / IP HMAC buckets) older than 7 days;
- Google review snippets (reviews.source='google') older than 30 days (Google Places ToS). The place
  ids whose snippets were deleted are logged (agent='search', action='google_reviews_purged') so the
  monthly Search run re-fetches them (SupabaseClient.fetch_purged_review_place_ids);
- every agent_log row older than 1 year, except the deletion-request records (agent='privacy': request
  reference, counts and ids, never the content), which prove a request was answered and are kept 5 years;
- suggestions, place_reports that are not published (a hidden opinion included) and the suggestion notes
  copied to place_evidence (source 'user') older than 2 years;
- a business's contact_email and its outreach_messages 2 years after the last contact;
- partner requests (partner_applications, privacy v1.2 draft section 6): one never charged, 6 months after the
  request; an ended partner, 2 years after its last charge. A partner that is not ``ended`` is never purged, so
  ``partners_admin --sync`` has to close it first (the admin digest lists the ones waiting). Skipped while the
  table does not exist (production until phase 3).
Published opinions and place_votes (they live as long as their place) are never purged here.

Run from the repo root:

    python scripts/purge_chat_logs.py --dry-run   # count what each rule would delete today
    python scripts/purge_chat_logs.py             # delete

Invoked weekly by .github/workflows/chat-log-purge.yml (schedule + workflow_dispatch).
"""

from __future__ import annotations

import argparse
import calendar
import logging
import sys
from datetime import date, datetime, timezone

from agents.clients.supabase_client import SupabaseClient
from config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("celiacmap.retention_purge")

CHATBOT_LOG_DAYS = 30
CHAT_USAGE_DAYS = 7
GOOGLE_REVIEW_DAYS = 30
AGENT_LOG_DAYS = 365
PRIVACY_RECORD_DAYS = 1825  # agent='privacy' deletion-request records: 5 years (owner decision, 2026-09-30)
COMMUNITY_DAYS = 730  # suggestions, unpublished place_reports, suggestion notes in place_evidence
OUTREACH_DAYS = 730   # after the last contact
PARTNER_UNPAID_MONTHS = 6          # a request never charged: 6 months from the request
PARTNER_AFTER_LAST_CHARGE_MONTHS = 24  # an ended partner: 2 years from its last charge


def add_months(day: date, months: int) -> date:
    """``day`` moved by whole calendar months, clamped to the last day of a shorter month."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def partner_cutoffs(today: date) -> tuple[str, str]:
    """(requested_before, paid_through_before) for SupabaseClient.purge_partner_applications.

    The table does not store the date of the last charge. It is derived as paid_through minus one month, which
    ASSUMES A MONTHLY PLAN (the only one, $U 790 per month): partners_admin sets paid_through to the last approved
    charge's date plus one billing period. So "last charge more than 24 months ago" is "paid_through more than 23
    months ago". If a plan with another period is ever added, this has to change.
    """
    requested_before = add_months(today, -PARTNER_UNPAID_MONTHS)
    paid_through_before = add_months(today, -(PARTNER_AFTER_LAST_CHARGE_MONTHS - 1))
    return requested_before.isoformat(), paid_through_before.isoformat()


def run(db, dry_run: bool = False, today: date | None = None) -> dict:
    summary = {
        "chatbot_logs": db.delete_chatbot_logs(cutoff_days=CHATBOT_LOG_DAYS, dry_run=dry_run),
        "chat_usage": db.delete_old_chat_usage(cutoff_days=CHAT_USAGE_DAYS, dry_run=dry_run),
    }
    if dry_run:
        review_places = db.find_expired_google_review_places(cutoff_days=GOOGLE_REVIEW_DAYS)
    else:
        review_places = db.delete_expired_google_reviews(cutoff_days=GOOGLE_REVIEW_DAYS)
        if review_places:
            db.insert_agent_log("search", "google_reviews_purged", {"place_ids": review_places}, "success")
    summary["google_reviews_places"] = len(review_places)
    summary["agent_log"] = db.purge_rows(
        "agent_log", AGENT_LOG_DAYS, filters=[("neq", "agent", "privacy")], dry_run=dry_run)
    summary["privacy_records"] = db.purge_rows(
        "agent_log", PRIVACY_RECORD_DAYS, filters=[("eq", "agent", "privacy")], dry_run=dry_run)
    summary["suggestions"] = db.purge_rows("suggestions", COMMUNITY_DAYS, dry_run=dry_run)
    summary["place_reports_unpublished"] = db.purge_rows(
        "place_reports", COMMUNITY_DAYS, filters=[("is_", "published_at", "null")], dry_run=dry_run)
    summary["place_evidence_user"] = db.purge_rows(
        "place_evidence", COMMUNITY_DAYS, filters=[("eq", "source", "user")], dry_run=dry_run)
    outreach = db.expire_outreach_contacts(OUTREACH_DAYS, dry_run=dry_run)
    summary["contact_emails"] = outreach["contact_emails"]
    summary["outreach_messages"] = outreach["messages"]
    requested_before, paid_through_before = partner_cutoffs(today or datetime.now(timezone.utc).date())
    partners = db.purge_partner_applications(requested_before, paid_through_before, dry_run=dry_run)
    if partners is None:
        logger.info("partner_applications does not exist: partner retention skipped")
        summary["partner_applications"] = "skipped (no table)"
    else:
        summary["partner_requests_unpaid"] = partners["unpaid"]
        summary["partners_ended"] = partners["ended"]
    logger.info("%s %s", "DRY RUN — would delete:" if dry_run else "Deleted:", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="only count what each rule would delete")
    args = parser.parse_args(argv)
    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")
    run(SupabaseClient(settings.supabase_url, settings.supabase_service_role_key), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
