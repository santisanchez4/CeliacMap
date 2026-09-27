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


# --- the dedup of insert_place_candidate (One Google place, one row) --------------------------------------------------
# A dry run must report what production would (not) insert: the real client skips a candidate whose place_id belongs to any row.

CANDIDATE = {"name": "Rikuras", "source": "google_places", "external_id": "ChIJexisting", "lat": -34.9, "lng": -56.16}


def test_dry_run_reports_a_candidate_whose_place_id_already_exists_as_skipped_not_as_an_insert(caplog):
    inner = MagicMock()
    inner.place_exists_by_external_id.return_value = True

    with caplog.at_level("INFO"):
        out = DryRunSupabase(inner).insert_place_candidate(dict(CANDIDATE))

    assert out is None
    inner.place_exists_by_external_id.assert_called_once_with("ChIJexisting")
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "would SKIP" in messages and "Rikuras" in messages and "ChIJexisting" in messages
    assert "would insert" not in messages
    inner.insert_place_candidate.assert_not_called()


def test_dry_run_still_reports_a_new_place_id_as_would_insert_and_writes_nothing(caplog):
    inner = MagicMock()
    inner.place_exists_by_external_id.return_value = False

    with caplog.at_level("INFO"):
        out = DryRunSupabase(inner).insert_place_candidate(dict(CANDIDATE))

    assert out is None
    assert "would insert candidate 'Rikuras'" in " ".join(r.getMessage() for r in caplog.records)
    inner.insert_place_candidate.assert_not_called()


def test_dry_run_never_looks_up_a_candidate_without_an_external_id(caplog):
    inner = MagicMock()

    with caplog.at_level("INFO"):
        DryRunSupabase(inner).insert_place_candidate({**CANDIDATE, "external_id": None})

    inner.place_exists_by_external_id.assert_not_called()
    assert "would insert" in " ".join(r.getMessage() for r in caplog.records)


def test_dry_run_treats_a_failed_lookup_like_the_real_client_and_reports_would_insert(caplog):
    inner = MagicMock()
    inner.place_exists_by_external_id.side_effect = RuntimeError("network")

    with caplog.at_level("INFO"):
        DryRunSupabase(inner).insert_place_candidate(dict(CANDIDATE))

    assert "would insert" in " ".join(r.getMessage() for r in caplog.records)


def test_dry_run_checks_the_scope_before_the_lookup_like_the_real_client():
    inner = MagicMock()

    DryRunSupabase(inner).insert_place_candidate({**CANDIDATE, "lat": 48.85, "lng": 2.35})

    inner.place_exists_by_external_id.assert_not_called()
