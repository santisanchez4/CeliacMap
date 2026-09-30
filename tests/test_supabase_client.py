"""Unit tests for SupabaseClient — the geographic scope guard on insert.

`insert_place_candidate` is a source-agnostic chokepoint: every discovery
agent (Search / Social / Web / Suggestion) funnels new places through it, so
an approximate Uruguay+Argentina bounding-box check here is a last-resort net
against a place landing far outside the project's scope — a location-biased
Google search, or a mis-matched Find Place result, that slipped past
`to_candidate()` / `resolve_location()`. See docs/DECISIONS.md "Brazil out-of-scope
places — Curitiba cluster".
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from agents.clients.supabase_client import SupabaseClient, coordinates_in_scope


def _client_with_mock_db() -> SupabaseClient:
    # Bypass __init__ (which would build a real supabase Client) and inject a
    # mock for the underlying connection.
    client = SupabaseClient.__new__(SupabaseClient)
    client._db = MagicMock()
    # By default no row has the candidate's external_id (the normal case); the dedup tests say otherwise.
    client._db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    return client


# --- the pure bounding-box check ----------------------------------------------


def test_coordinates_in_scope_accepts_buenos_aires_and_montevideo():
    assert coordinates_in_scope(-34.6037, -58.3816) is True   # Buenos Aires
    assert coordinates_in_scope(-34.9011, -56.1645) is True   # Montevideo


def test_coordinates_in_scope_accepts_uy_ar_extremes():
    assert coordinates_in_scope(-22.10, -65.60) is True   # La Quiaca, Jujuy (N)
    assert coordinates_in_scope(-54.80, -68.30) is True   # Ushuaia (S)
    assert coordinates_in_scope(-33.69, -53.46) is True   # Chuy, Uruguay (E)
    assert coordinates_in_scope(-49.33, -72.90) is True   # El Chaltén (W)


def test_coordinates_in_scope_rejects_curitiba():
    # The exact coordinates of the "Sem Culpa - Sem Gluten" row.
    assert coordinates_in_scope(-25.4178097, -49.2490747) is False


def test_coordinates_in_scope_rejects_far_flung_geocode_errors():
    assert coordinates_in_scope(34.7475, -92.2636) is False    # Little Rock, USA
    assert coordinates_in_scope(40.4169, -3.6963) is False     # Madrid
    assert coordinates_in_scope(34.9988, 135.7788) is False    # Kyoto
    assert coordinates_in_scope(4.6727, -74.0619) is False     # Bogotá


def test_coordinates_in_scope_rejects_missing_or_non_numeric():
    assert coordinates_in_scope(None, None) is False
    assert coordinates_in_scope("-34.6", "-58.4") is False


# --- wired into insert_place_candidate --------------------------------------


def test_insert_place_candidate_rejects_out_of_scope_without_touching_db():
    client = _client_with_mock_db()

    row = client.insert_place_candidate(
        {
            "name": "LEVAIN GLÚTEN FREE",
            "lat": -25.4011981,
            "lng": -49.2592645,
            "source": "google_places",
            "external_id": "ChIJ_curitiba_levain",
        }
    )

    assert row is None
    client._db.table.assert_not_called()


def test_insert_place_candidate_inserts_in_scope_candidate():
    client = _client_with_mock_db()
    execute = client._db.table.return_value.upsert.return_value.execute
    execute.return_value = MagicMock(data=[{"id": "row-1"}])

    row = client.insert_place_candidate(
        {
            "name": "Café Sano",
            "lat": -34.9011,
            "lng": -56.1645,
            "source": "manual",
            "external_id": None,
        }
    )

    assert row == {"id": "row-1"}
    client._db.table.assert_called_once_with("places")


# --- one place_id, one row: any source, any status ---------------------------------------------------------------
# Found 2026-09-27: 24 place_ids had two rows (google_places + social), 13 of them both approved. The unique index is on
# (source, external_id), so a candidate of another source never conflicted; only Social / Web / Suggestion looked the id up.

EXTERNAL_ID = "ChIJH05jRj-Ln5URB3xgh46-Mck"


def _candidate(**overrides) -> dict:
    return {"name": "Rikuras Sin Gluten El Pinar", "lat": -34.8043848, "lng": -55.9063936, "source": "google_places",
            "external_id": EXTERNAL_ID, "country": "Uruguay", **overrides}


def _lookup(client: SupabaseClient):
    return client._db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute


def test_insert_place_candidate_skips_a_candidate_whose_place_id_belongs_to_a_manual_row():
    client = _client_with_mock_db()
    _lookup(client).return_value = MagicMock(data=[{"id": "manual-row"}])  # a source='manual' row already holds this place_id

    assert client.insert_place_candidate(_candidate()) is None

    client._db.table.return_value.upsert.assert_not_called()


def test_the_lookup_is_by_external_id_alone_so_any_source_and_any_status_counts():
    client = _client_with_mock_db()
    client.insert_place_candidate(_candidate())
    select = client._db.table.return_value.select
    select.assert_called_once_with("id")
    select.return_value.eq.assert_called_once_with("external_id", EXTERNAL_ID)
    # no other filter: not by source (the unique index already covers that) and not by status (a discarded row still holds the id)
    assert select.return_value.eq.return_value.method_calls[0][0] == "limit"
    for name in ("eq", "neq", "in_", "is_", "filter"):
        assert not getattr(select.return_value.eq.return_value, name).called


def test_insert_place_candidate_still_inserts_when_no_row_has_that_place_id():
    client = _client_with_mock_db()
    client._db.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "new-row"}])
    assert client.insert_place_candidate(_candidate()) == {"id": "new-row"}
    client._db.table.return_value.upsert.assert_called_once()


def test_a_candidate_with_no_external_id_never_looks_anything_up():
    client = _client_with_mock_db()
    client._db.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "row-1"}])
    client.insert_place_candidate(_candidate(external_id=None, source="manual"))
    client._db.table.return_value.select.assert_not_called()


def test_the_skip_is_logged_with_the_name_the_place_id_and_the_source(caplog):
    client = _client_with_mock_db()
    _lookup(client).return_value = MagicMock(data=[{"id": "manual-row"}])
    with caplog.at_level("INFO", logger="celiacmap.agent"):
        client.insert_place_candidate(_candidate())
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "Rikuras Sin Gluten El Pinar" in text and EXTERNAL_ID in text and "google_places" in text


def test_a_failed_lookup_does_not_block_the_insert_like_the_other_dedup_checks():
    client = _client_with_mock_db()
    _lookup(client).side_effect = RuntimeError("PostgREST down")
    client._db.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "row-1"}])
    assert client.insert_place_candidate(_candidate()) == {"id": "row-1"}


def test_the_out_of_scope_guard_still_runs_first_and_touches_nothing():
    client = _client_with_mock_db()
    assert client.insert_place_candidate(_candidate(lat=-25.4, lng=-49.3)) is None  # Curitiba
    client._db.table.assert_not_called()


# --- places.region is derived at the same chokepoint ---------------------------


def _upserted_payload(client: SupabaseClient) -> dict:
    return client._db.table.return_value.upsert.call_args.args[0]


def _insert(client: SupabaseClient, **overrides) -> None:
    candidate = {
        "name": "EMPATIA GLUTEN FREE",
        "lat": -32.37,
        "lng": -54.17,
        "source": "social",
        "external_id": "ext-melo",
        "country": "Uruguay",
        "address": "Dr. Luis Alberto de Herrera 859, 37000 Melo, Departamento de Cerro Largo, Uruguay",
        **overrides,
    }
    client._db.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "row-1"}])
    client.insert_place_candidate(candidate)


def test_insert_place_candidate_derives_the_region_from_the_address():
    client = _client_with_mock_db()
    _insert(client)
    assert _upserted_payload(client)["region"] == "Cerro Largo"


def test_insert_place_candidate_keeps_a_region_the_caller_already_set():
    client = _client_with_mock_db()
    _insert(client, region="Rocha")
    assert _upserted_payload(client)["region"] == "Rocha"


def test_insert_place_candidate_leaves_the_region_out_when_the_address_names_none():
    client = _client_with_mock_db()
    _insert(client, address="Rivera 1967, Fray Bentos, Uruguay")
    assert "region" not in _upserted_payload(client)
    client = _client_with_mock_db()
    _insert(client, address=None)
    assert "region" not in _upserted_payload(client)


# --- delete_expired_google_reviews (Google Places ToS: 30-day expiration) -----


def test_delete_expired_google_reviews_returns_distinct_place_ids():
    client = _client_with_mock_db()
    chain = client._db.table.return_value.delete.return_value.eq.return_value.lt
    chain.return_value.execute.return_value = MagicMock(
        data=[
            {"place_id": "p1"},
            {"place_id": "p2"},
            {"place_id": "p1"},  # duplicate row for the same place -> deduped
        ]
    )

    place_ids = client.delete_expired_google_reviews()

    assert place_ids == ["p1", "p2"]
    client._db.table.assert_called_once_with("reviews")
    client._db.table.return_value.delete.return_value.eq.assert_called_once_with(
        "source", "google"
    )


def test_delete_expired_google_reviews_returns_empty_when_nothing_expired():
    client = _client_with_mock_db()
    chain = client._db.table.return_value.delete.return_value.eq.return_value.lt
    chain.return_value.execute.return_value = MagicMock(data=[])

    assert client.delete_expired_google_reviews() == []


# --- delete_chatbot_logs (ADR-006 decision 10: 30-day purge of agent='chatbot') --


def test_delete_chatbot_logs_returns_row_count():
    client = _client_with_mock_db()
    chain = client._db.table.return_value.delete.return_value.eq.return_value.lt
    chain.return_value.execute.return_value = MagicMock(
        data=[{"id": "log-1"}, {"id": "log-2"}]
    )

    deleted = client.delete_chatbot_logs()

    assert deleted == 2
    client._db.table.assert_called_once_with("agent_log")
    client._db.table.return_value.delete.return_value.eq.assert_called_once_with(
        "agent", "chatbot"
    )


def test_delete_chatbot_logs_returns_zero_when_nothing_expired():
    client = _client_with_mock_db()
    chain = client._db.table.return_value.delete.return_value.eq.return_value.lt
    chain.return_value.execute.return_value = MagicMock(data=[])

    assert client.delete_chatbot_logs() == 0


# --- weekly retention purge (privacy phase 1, 2026-09-29) ------------------------


def test_delete_old_chat_usage_deletes_counters_older_than_the_cutoff_day():
    client = _client_with_mock_db()
    chain = client._db.table.return_value.delete.return_value.lt
    chain.return_value.execute.return_value = MagicMock(data=[{"bucket_key": "a"}, {"bucket_key": "b"}])

    assert client.delete_old_chat_usage(cutoff_days=7) == 2
    client._db.table.assert_called_once_with("chat_usage")
    column, value = chain.call_args.args
    assert column == "day"
    cutoff = datetime.fromisoformat(value).date()
    assert (datetime.now(timezone.utc).date() - cutoff).days == 7  # the counters' day is a UTC date


def test_delete_old_chat_usage_dry_run_counts_without_deleting():
    client = _client_with_mock_db()
    counted = client._db.table.return_value.select.return_value.lt.return_value
    counted.execute.return_value = MagicMock(count=4, data=[])
    assert client.delete_old_chat_usage(cutoff_days=7, dry_run=True) == 4
    client._db.table.return_value.delete.assert_not_called()


def test_delete_chatbot_logs_dry_run_counts_without_deleting():
    client = _client_with_mock_db()
    counted = client._db.table.return_value.select.return_value.eq.return_value.lt.return_value
    counted.execute.return_value = MagicMock(count=2, data=[])
    assert client.delete_chatbot_logs(dry_run=True) == 2
    client._db.table.return_value.delete.assert_not_called()


# --- privacy phase 2 (2026-09-30): generic purge + outreach contact expiry ----------------


def test_purge_rows_deletes_older_than_the_window_with_the_filters():
    client = _client_with_mock_db()
    base = client._db.table.return_value.delete.return_value.lt.return_value
    base.is_.return_value.execute.return_value = MagicMock(data=[{"id": "r1"}, {"id": "r2"}])

    n = client.purge_rows("place_reports", 730, filters=[("is_", "published_at", "null")])

    assert n == 2
    client._db.table.assert_called_once_with("place_reports")
    column, cutoff = client._db.table.return_value.delete.return_value.lt.call_args.args
    assert column == "created_at"
    assert (datetime.now(timezone.utc) - datetime.fromisoformat(cutoff)).days == 730
    base.is_.assert_called_once_with("published_at", "null")


def test_purge_rows_dry_run_counts_with_head_and_never_deletes():
    client = _client_with_mock_db()
    select = client._db.table.return_value.select
    select.return_value.lt.return_value.eq.return_value.execute.return_value = MagicMock(count=3, data=[])

    assert client.purge_rows("place_evidence", 730, filters=[("eq", "source", "user")], dry_run=True) == 3
    assert select.call_args.kwargs == {"count": "exact", "head": True}
    client._db.table.return_value.delete.assert_not_called()


def test_purge_rows_refuses_unknown_tables_and_filters():
    client = _client_with_mock_db()
    import pytest
    with pytest.raises(ValueError):
        client.purge_rows("places", 30)
    with pytest.raises(ValueError):
        client.purge_rows("agent_log", 30, filters=[("delete", "x", "y")])


def _outreach_client(places, messages):
    client = _client_with_mock_db()
    tables: dict[str, MagicMock] = {}

    def table(name):
        if name not in tables:
            t = MagicMock()
            if name == "places":
                t.select.return_value.not_.is_.return_value.execute.return_value = MagicMock(data=places)
            if name == "outreach_messages":
                t.select.return_value.execute.return_value = MagicMock(data=messages)
                t.delete.return_value.in_.return_value.execute.return_value = MagicMock(data=[{}] * 3)
            tables[name] = t
        return tables[name]

    client._db.table.side_effect = table
    return client, tables


OLD = "2024-01-01T00:00:00+00:00"
RECENT = datetime.now(timezone.utc).isoformat()


def test_expire_outreach_contacts_uses_the_last_contact_or_the_scrape_date():
    places = [
        {"id": "old-thread", "contact_email_checked_at": OLD},           # last message old too -> expires
        {"id": "recent-thread", "contact_email_checked_at": OLD},        # a recent message keeps it
        {"id": "never-contacted-old", "contact_email_checked_at": OLD},  # no message: the scrape date counts
        {"id": "never-contacted-new", "contact_email_checked_at": RECENT},
    ]
    messages = [
        {"place_id": "old-thread", "created_at": OLD},
        {"place_id": "recent-thread", "created_at": OLD},
        {"place_id": "recent-thread", "created_at": RECENT},
        {"place_id": "no-email-any-more", "created_at": OLD},            # an old thread of a place without email
    ]
    client, tables = _outreach_client(places, messages)

    out = client.expire_outreach_contacts(730, dry_run=True)
    assert out == {"contact_emails": 2, "messages": 2}
    tables["places"].update.assert_not_called()
    tables["outreach_messages"].delete.assert_not_called()


def test_expire_outreach_contacts_applies_the_expiry():
    places = [{"id": "old-thread", "contact_email_checked_at": OLD}]
    messages = [{"place_id": "old-thread", "created_at": OLD}, {"place_id": "old-thread", "created_at": OLD}]
    client, tables = _outreach_client(places, messages)

    out = client.expire_outreach_contacts(730)
    tables["places"].update.assert_called_once_with({"contact_email": None})
    tables["places"].update.return_value.in_.assert_called_once_with("id", ["old-thread"])
    tables["outreach_messages"].delete.return_value.in_.assert_called_once_with("place_id", ["old-thread"])
    assert out["contact_emails"] == 1


def _agent_log_tables(last_run, purge_rows):
    """table('agent_log') is called twice: the last search run, then the purge entries."""
    client = _client_with_mock_db()
    last_q, purge_q = MagicMock(), MagicMock()
    (last_q.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value
     .execute.return_value) = MagicMock(data=last_run)
    purge_base = purge_q.select.return_value.eq.return_value.eq.return_value
    purge_base.execute.return_value = MagicMock(data=purge_rows)
    purge_base.gt.return_value.execute.return_value = MagicMock(data=purge_rows)
    client._db.table.side_effect = [last_q, purge_q]
    return client, purge_base


def test_fetch_purged_review_place_ids_since_the_last_search_run_flattens_and_dedups():
    client, purge_base = _agent_log_tables(
        [{"created_at": "2026-09-01T14:07:40+00:00"}],
        [{"result": {"place_ids": ["p2", "p1"]}}, {"result": {"place_ids": ["p1"]}}, {"result": None}],
    )
    assert client.fetch_purged_review_place_ids() == ["p1", "p2"]
    purge_base.gt.assert_called_once_with("created_at", "2026-09-01T14:07:40+00:00")


def test_fetch_purged_review_place_ids_without_a_previous_search_run_reads_every_entry():
    client, purge_base = _agent_log_tables([], [{"result": {"place_ids": ["p9"]}}])
    assert client.fetch_purged_review_place_ids() == ["p9"]
    purge_base.gt.assert_not_called()


# --- community kitchen claims (server-only intake tables) ----------------------


def _client_with_intake_tables(suggestions=None, reports=None):
    """Return (client, tables) where tables maps table name -> the MagicMock returned
    by `_db.table(name)`, pre-wired for the two query shapes fetch_community_claims uses."""
    client = _client_with_mock_db()
    tables: dict[str, MagicMock] = {}

    def table(name):
        if name not in tables:
            t = MagicMock()
            data = {"suggestions": suggestions, "place_reports": reports}.get(name) or []
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(data=data)
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=data)
            tables[name] = t
        return tables[name]

    client._db.table.side_effect = table
    return client, tables


def test_fetch_community_claims_merges_both_tables_newest_first():
    client, _ = _client_with_intake_tables(
        suggestions=[{"kitchen_exclusive": True, "celiac_prep": None, "owner_celiac": True, "created_at": "2026-09-01T10:00:00"}],
        reports=[{"kitchen_exclusive": False, "celiac_prep": "separate_kitchen", "owner_celiac": None, "created_at": "2026-09-05T10:00:00"}],
    )
    claims = client.fetch_community_claims("place-1")
    assert [c["created_at"] for c in claims] == ["2026-09-05T10:00:00", "2026-09-01T10:00:00"]


def test_fetch_community_claims_drops_rows_with_no_kitchen_datum():
    empty = {"kitchen_exclusive": None, "celiac_prep": None, "owner_celiac": None, "created_at": "2026-09-01T10:00:00"}
    client, _ = _client_with_intake_tables(suggestions=[empty], reports=[empty])
    assert client.fetch_community_claims("place-1") == []


def test_fetch_community_claims_never_selects_the_owner_column():
    """owner_celiac is a third party's health condition: it must not even be read into the process that
    builds the Validator prompt."""
    client, tables = _client_with_intake_tables()
    client.fetch_community_claims("place-1")
    for name in ("suggestions", "place_reports"):
        selected = tables[name].select.call_args.args[0]
        assert "owner_celiac" not in selected, selected


def test_fetch_community_claims_drops_rows_that_only_carry_the_owner_fact():
    only_owner = {"kitchen_exclusive": None, "celiac_prep": None, "owner_celiac": True, "created_at": "2026-09-01T10:00:00"}
    client, _ = _client_with_intake_tables(suggestions=[only_owner], reports=[only_owner])
    assert client.fetch_community_claims("place-1") == []


def test_fetch_community_claims_respects_limit():
    rows = [
        {"kitchen_exclusive": True, "celiac_prep": None, "owner_celiac": None, "created_at": f"2026-09-0{i}T10:00:00"}
        for i in range(1, 8)
    ]
    client, _ = _client_with_intake_tables(reports=rows)
    assert len(client.fetch_community_claims("place-1", limit=3)) == 3


def test_fetch_community_claims_only_reads_positive_reports_and_the_promoted_suggestion():
    client, tables = _client_with_intake_tables()
    client.fetch_community_claims("place-9")
    tables["suggestions"].select.return_value.eq.assert_called_once_with("promoted_place_id", "place-9")
    reports_eq = tables["place_reports"].select.return_value.eq
    reports_eq.assert_called_once_with("place_id", "place-9")
    reports_eq.return_value.eq.assert_called_once_with("report_type", "positive")


def test_fetch_unpublished_opinions_asks_only_for_positive_unpublished_reports_of_approved_places():
    client = _client_with_mock_db()
    table = client._db.table
    chain = (table.return_value.select.return_value.eq.return_value.is_.return_value
             .eq.return_value.order.return_value.limit.return_value)
    chain.execute.return_value = MagicMock(data=[{"id": "r1"}])

    assert client.fetch_unpublished_opinions(limit=7) == [{"id": "r1"}]

    table.assert_called_with("place_reports")
    selected = table.return_value.select.call_args.args[0]
    assert "owner_celiac" not in selected, selected
    assert "places!inner" in selected, selected
    table.return_value.select.return_value.eq.assert_called_once_with("report_type", "positive")
    table.return_value.select.return_value.eq.return_value.is_.assert_called_once_with("published_at", "null")
    (table.return_value.select.return_value.eq.return_value.is_.return_value
     .eq.assert_called_once_with("places.status", "approved"))
    table.return_value.select.return_value.eq.return_value.is_.return_value.eq.return_value.order.return_value.limit.assert_called_once_with(7)
    chain.execute.assert_called_once()


def test_set_opinions_published_stamps_now_or_null_and_only_touches_positive_reports():
    client = _client_with_mock_db()
    update = client._db.table.return_value.update
    update.return_value.in_.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "r1"}])

    assert client.set_opinions_published(["r1"], True) == [{"id": "r1"}]
    payload = update.call_args.args[0]
    assert set(payload) == {"published_at"} and payload["published_at"]
    datetime.fromisoformat(payload["published_at"])  # a real timestamp, not a placeholder
    update.return_value.in_.assert_called_once_with("id", ["r1"])
    update.return_value.in_.return_value.eq.assert_called_once_with("report_type", "positive")

    client.set_opinions_published(["r1"], False)
    assert update.call_args.args[0] == {"published_at": None}


def test_set_opinions_published_with_no_ids_does_not_touch_the_database():
    client = _client_with_mock_db()
    assert client.set_opinions_published([], True) == []
    client._db.table.assert_not_called()


# --- place_evidence ------------------------------------------------------------


def test_add_place_evidence_clamps_to_the_table_bounds():
    from unittest.mock import MagicMock

    from agents.clients.supabase_client import SupabaseClient

    client = SupabaseClient.__new__(SupabaseClient)
    client._db = MagicMock()
    client.add_place_evidence("p1", "web", "x" * 5000, "u" * 900)
    row = client._db.table.return_value.insert.call_args.args[0]
    assert len(row["text"]) == 1000 and len(row["url"]) == 500


def test_add_place_evidence_skips_an_empty_row():
    from unittest.mock import MagicMock

    from agents.clients.supabase_client import SupabaseClient

    client = SupabaseClient.__new__(SupabaseClient)
    client._db = MagicMock()
    client.add_place_evidence("p1", "user", "   ", None)
    client._db.table.assert_not_called()


def test_place_evidence_table_is_server_only():
    from pathlib import Path

    schema = (Path(__file__).resolve().parent.parent / "db" / "schema.sql").read_text(encoding="utf-8")
    assert "alter table public.place_evidence enable row level security;" in schema
    assert "revoke all on public.place_evidence from anon, authenticated;" in schema
    assert "grant select on public.place_evidence" not in schema
    assert "grant insert on public.place_evidence" not in schema


def test_audit_migration_matches_the_schema_blocks():
    """db/migrations/2026-09-24-audit-plan.sql is a copy of blocks of db/schema.sql: they must not drift."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    schema = (root / "db" / "schema.sql").read_text(encoding="utf-8")
    migration = (root / "db" / "migrations" / "2026-09-24-audit-plan.sql").read_text(encoding="utf-8")
    for begin, end in [
        ("-- SUGGESTION-NEEDS-LOCATION-BEGIN", "-- SUGGESTION-NEEDS-LOCATION-END"),
        ("-- COMMUNITY-WARNING-BEGIN", "-- COMMUNITY-WARNING-END"),
        ("-- PLACE-EVIDENCE-BEGIN", "-- PLACE-EVIDENCE-END"),
    ]:
        blk = schema[schema.index(begin): schema.index(end)]
        assert blk in migration, begin
    assert "'admin_notify'" in migration
    assert "revoke all on public.place_evidence from anon, authenticated;" in migration


# --- fetch_places_for_admin: paging for the admin queue ---------------------------------------


def _chain():
    """A query builder where every method returns itself and records the call."""
    calls: list[tuple[str, tuple]] = []
    q = MagicMock()

    def record(name):
        def fn(*a, **k):
            calls.append((name, a))
            return q

        return fn

    for name in ("select", "eq", "ilike", "contains", "gte", "order", "limit", "range"):
        setattr(q, name, record(name))
    q.execute.return_value = MagicMock(data=[{"id": "p1"}])
    return q, calls


def test_fetch_places_for_admin_pages_with_offset():
    client = _client_with_mock_db()
    q, calls = _chain()
    client._db.table.return_value = q
    assert client.fetch_places_for_admin(None, flag="x", limit=5, offset=10) == [{"id": "p1"}]
    assert ("range", (10, 14)) in calls  # rows 10..14 = the third page of 5


def test_fetch_places_for_admin_first_page_is_unchanged_without_an_offset():
    client = _client_with_mock_db()
    q, calls = _chain()
    client._db.table.return_value = q
    client.fetch_places_for_admin("approved", limit=15)
    assert ("range", (0, 14)) in calls


def test_the_flag_filter_reaches_postgrest_as_a_jsonb_array_not_a_postgres_array_literal(monkeypatch):
    """`flags` is jsonb: PostgREST needs `cs.["…"]`. supabase-py turns a Python list into `cs.{…}` (a Postgres array
    literal), which a jsonb column rejects with 22P02 — it broke `review_queue --pending-100` and the daily digest.
    Built on the REAL postgrest builder (no mock of the query) so the wire format is what is asserted."""
    from postgrest import SyncPostgrestClient
    from postgrest._sync.request_builder import SyncSelectRequestBuilder

    from agents.validator_agent import PENDING_ADMIN_FLAG

    captured = {}

    def fake_execute(self):
        captured.update(dict(self.request.params))
        return MagicMock(data=[])

    monkeypatch.setattr(SyncSelectRequestBuilder, "execute", fake_execute)
    client = _client_with_mock_db()
    client._db.table.side_effect = lambda name: SyncPostgrestClient("http://localhost/rest/v1").from_(name)

    client.fetch_places_for_admin(None, flag=PENDING_ADMIN_FLAG, limit=5)

    assert captured["flags"] == 'cs.["' + PENDING_ADMIN_FLAG + '"]'
