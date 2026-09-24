"""DryRunSupabase must mirror every READ the agents make.

`--dry-run` (and the workflow's dry_run input) wraps the database client so writes are suppressed but reads pass
straight through. A read that is missing from the wrapper raises AttributeError inside an agent's best-effort
try/except: it is swallowed, a traceback is logged for every place, and the agent silently runs WITHOUT that
context — so the rehearsal diverges from production (found in the kitchen-info branch review: the Validator's
community claims, and with them Tope B, were silently off in a dry run).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from agents.clients.supabase_client import SupabaseClient
from scripts.run_agents import DryRunSupabase


def test_dry_run_wrapper_delegates_community_claims():
    inner = MagicMock()
    inner.fetch_community_claims.return_value = [{"kitchen_exclusive": True}]

    out = DryRunSupabase(inner).fetch_community_claims("place-1", limit=3)

    inner.fetch_community_claims.assert_called_once_with("place-1", limit=3)
    assert out == [{"kitchen_exclusive": True}]


def test_dry_run_wrapper_mirrors_every_read_method_of_the_client():
    reads = [
        name for name in dir(SupabaseClient)
        if not name.startswith("_") and (name.startswith("fetch_") or name in ("health_check", "place_exists_by_external_id"))
    ]
    missing = [name for name in reads if not hasattr(DryRunSupabase, name)]
    assert missing == [], f"DryRunSupabase lacks these reads: {missing}"


def test_dry_run_wrapper_reads_unpublished_opinions_but_never_publishes():
    inner = MagicMock()
    inner.fetch_unpublished_opinions.return_value = [{"id": "r1"}]
    wrapper = DryRunSupabase(inner)

    assert wrapper.fetch_unpublished_opinions(limit=5) == [{"id": "r1"}]
    inner.fetch_unpublished_opinions.assert_called_once_with(limit=5)

    assert wrapper.set_opinions_published(["r1"], True) == []
    inner.set_opinions_published.assert_not_called()
