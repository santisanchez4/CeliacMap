"""Shared base class for CeliacMap agents.

Provides the common dependency (the Supabase client) and a convenience
``log`` helper that records every meaningful action to the ``agent_log`` table,
which doubles as the human review/audit trail.
"""

from __future__ import annotations

import logging

from agents.clients.supabase_client import SupabaseClient

logger = logging.getLogger("celiacmap.agent")


class BaseAgent:
    #: one of 'search' | 'validator' | 'updater' — set by each subclass.
    name: str = "base"

    def __init__(self, db: SupabaseClient):
        self.db = db

    def log(
        self,
        action: str,
        result: dict | None = None,
        status: str = "success",
        place_id: str | None = None,
    ) -> None:
        """Write an entry to agent_log (and mirror to the local logger)."""
        logger.info("[%s] %s (%s)", self.name, action, status)
        try:
            self.db.insert_agent_log(self.name, action, result, status, place_id)
        except Exception:  # logging must never crash an agent run
            logger.exception("failed to write agent_log entry")

    def run(self) -> dict:
        """Execute the agent. Subclasses must implement and return a summary."""
        raise NotImplementedError
