"""Unit tests for SupabaseClient — the geographic scope guard on insert.

`insert_place_candidate` is a source-agnostic chokepoint: every discovery
agent (Search / Social / Web / Suggestion) funnels new places through it, so
an approximate Uruguay+Argentina bounding-box check here is a last-resort net
against a place landing far outside the project's scope — a location-biased
Google search, or a mis-matched Find Place result, that slipped past
`to_candidate()` / `resolve_location()`. See CLAUDE.md "Brazil out-of-scope
places — Curitiba cluster".
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agents.clients.supabase_client import SupabaseClient, coordinates_in_scope


def _client_with_mock_db() -> SupabaseClient:
    # Bypass __init__ (which would build a real supabase Client) and inject a
    # mock for the underlying connection.
    client = SupabaseClient.__new__(SupabaseClient)
    client._db = MagicMock()
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
