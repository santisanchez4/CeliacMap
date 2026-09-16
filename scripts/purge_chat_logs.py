"""Purge expired chatbot turn logs from agent_log (ADR-006 decision 10).

Marked chatbot turns (refusals, rate-limit hits, out-of-scope attempts) can
carry raw user/bot text -- health-adjacent PII that must not accumulate
indefinitely in the shared agent_log audit table. This deletes only
agent_log rows with agent='chatbot' older than 30 days; every other agent's
rows are untouched (SupabaseClient.delete_chatbot_logs hardcodes the filter).

Run from the repo root:

    python scripts/purge_chat_logs.py

Invoked weekly by .github/workflows/chat-log-purge.yml (schedule +
workflow_dispatch). No dependencies beyond what the project already has.
"""

from __future__ import annotations

import logging
import sys

from agents.clients.supabase_client import SupabaseClient
from config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("celiacmap.chat_log_purge")


def main() -> int:
    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")

    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    deleted = db.delete_chatbot_logs(cutoff_days=30)
    logger.info("Purged %d agent_log row(s) with agent='chatbot' older than 30 days", deleted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
