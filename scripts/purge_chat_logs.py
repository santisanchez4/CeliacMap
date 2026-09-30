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
- a business's contact_email and its outreach_messages 2 years after the last contact.
Published opinions and place_votes (they live as long as their place) are never purged here.

Run from the repo root:

    python scripts/purge_chat_logs.py --dry-run   # count what each rule would delete today
    python scripts/purge_chat_logs.py             # delete

Invoked weekly by .github/workflows/chat-log-purge.yml (schedule + workflow_dispatch).
"""

from __future__ import annotations

import argparse
import logging
import sys

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


def run(db, dry_run: bool = False) -> dict:
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
