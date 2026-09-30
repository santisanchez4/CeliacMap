"""Weekly retention purge (ADR-006 decision 10; privacy phase 1, 2026-09-29).

Deletes, and nothing else:
- agent_log rows with agent='chatbot' older than 30 days (marked turns can carry raw user/bot text,
  health-adjacent PII; every other agent's rows are untouched -- the filter is hardcoded);
- chat_usage rate-limit counters (session token / IP hash buckets) older than 7 days;
- Google review snippets (reviews.source='google') older than 30 days (Google Places ToS). The place
  ids whose snippets were deleted are logged (agent='search', action='google_reviews_purged') so the
  monthly Search run re-fetches them (SupabaseClient.fetch_purged_review_place_ids).

Run from the repo root:

    python scripts/purge_chat_logs.py

Invoked weekly by .github/workflows/chat-log-purge.yml (schedule + workflow_dispatch).
"""

from __future__ import annotations

import logging
import sys

from agents.clients.supabase_client import SupabaseClient
from config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("celiacmap.retention_purge")

CHATBOT_LOG_DAYS = 30
CHAT_USAGE_DAYS = 7
GOOGLE_REVIEW_DAYS = 30


def run(db) -> dict:
    chatbot_logs = db.delete_chatbot_logs(cutoff_days=CHATBOT_LOG_DAYS)
    chat_usage = db.delete_old_chat_usage(cutoff_days=CHAT_USAGE_DAYS)
    review_places = db.delete_expired_google_reviews(cutoff_days=GOOGLE_REVIEW_DAYS)
    if review_places:
        db.insert_agent_log("search", "google_reviews_purged", {"place_ids": review_places}, "success")
    summary = {"chatbot_logs": chatbot_logs, "chat_usage": chat_usage, "google_reviews_places": len(review_places)}
    logger.info(
        "Purged %d chatbot log row(s) > %d days, %d chat_usage row(s) > %d days, "
        "Google reviews > %d days for %d place(s)",
        chatbot_logs, CHATBOT_LOG_DAYS, chat_usage, CHAT_USAGE_DAYS, GOOGLE_REVIEW_DAYS, len(review_places),
    )
    return summary


def main() -> int:
    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")
    run(SupabaseClient(settings.supabase_url, settings.supabase_service_role_key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
