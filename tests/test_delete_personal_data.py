"""scripts/delete_personal_data.py: answer a deletion request (privacy phase 1, 2026-09-29).

Finds rows by text (and an optional date range) in suggestions, place_reports, place_evidence and the
chatbot rows of agent_log; dry run by default; --apply deletes; the agent_log record never carries the
deleted content nor the searched text (both can be personal data).
"""
from __future__ import annotations

import json

import pytest

from scripts.delete_personal_data import SEARCH_COLUMNS, run

ROWS = {
    "suggestions": [
        {"id": "s1", "created_at": "2026-09-20T10:00:00+00:00", "notes": "Soy Ana Pérez, la cocina es aparte", "name": "Pan Justo"},
    ],
    "place_reports": [
        {"id": "r1", "created_at": "2026-09-21T10:00:00+00:00", "description": "Fui con Ana Pérez, muy bien", "author_name": None},
        {"id": "r2", "created_at": "2026-08-01T10:00:00+00:00", "description": "Ana Pérez otra vez", "author_name": "Ana"},
    ],
    "place_evidence": [],
    "agent_log": [
        {"id": "l1", "created_at": "2026-09-22T10:00:00+00:00", "result": {"raw_user_message": "me llamo Ana Pérez y tengo síntomas"}},
    ],
}


class FakeStore:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else ROWS
        self.finds = []
        self.deleted = []
        self.logged = []

    def find(self, table, column, text, since, until):
        self.finds.append((table, column, since, until))
        out = []
        for r in self.rows.get(table, []):
            value = r
            for part in column.replace("->>", "->").split("->"):
                value = (value or {}).get(part) if isinstance(value, dict) else None
            if not (isinstance(value, str) and text.lower() in value.lower()):
                continue
            if since and r["created_at"][:10] < since:
                continue
            if until and r["created_at"][:10] > until:
                continue
            out.append(r)
        return out

    def delete(self, table, ids):
        self.deleted.append((table, sorted(ids)))
        return len(ids)

    def log(self, result):
        self.logged.append(result)


def capture():
    lines = []
    return lines, lambda text="": lines.append(str(text))


def test_search_covers_the_four_tables_and_only_chatbot_text_in_agent_log():
    assert set(SEARCH_COLUMNS) == {"suggestions", "place_reports", "place_evidence", "agent_log"}
    assert all(c.startswith("result->") for c in SEARCH_COLUMNS["agent_log"])
    assert "author_name" in SEARCH_COLUMNS["place_reports"] and "notes" in SEARCH_COLUMNS["suggestions"]


def test_dry_run_lists_every_match_and_deletes_nothing():
    store = FakeStore()
    lines, out = capture()
    assert run(store, text="ana pérez", since=None, until=None, apply=False, request=None, ids=None, out=out) == 0
    text = "\n".join(lines)
    for rid in ("s1", "r1", "r2", "l1"):
        assert rid in text
    assert "DRY RUN" in text
    assert store.deleted == [] and store.logged == []


def test_date_range_limits_the_matches():
    store = FakeStore()
    lines, out = capture()
    run(store, text="ana pérez", since="2026-09-01", until="2026-09-30", apply=False, request=None, ids=None, out=out)
    text = "\n".join(lines)
    assert "r1" in text and "r2" not in text


def test_apply_deletes_the_matches_and_logs_counts_and_ids_but_no_content_nor_searched_text():
    store = FakeStore()
    lines, out = capture()
    assert run(store, text="ana pérez", since=None, until=None, apply=True, request="hola-2026-10-01", ids=None, out=out) == 0
    assert store.deleted == [("suggestions", ["s1"]), ("place_reports", ["r1", "r2"]), ("agent_log", ["l1"])]
    assert len(store.logged) == 1
    record = store.logged[0]
    assert record["request"] == "hola-2026-10-01"
    assert record["deleted"] == {"suggestions": 1, "place_reports": 2, "place_evidence": 0, "agent_log": 1}
    assert record["ids"]["place_reports"] == ["r1", "r2"]
    blob = json.dumps(record, ensure_ascii=False).lower()
    for secret in ("ana", "pérez", "síntomas", "cocina"):
        assert secret not in blob


def test_the_record_is_written_before_deleting_and_a_failed_record_deletes_nothing():
    class NoLog(FakeStore):
        def log(self, result):
            raise RuntimeError("agent_log_agent_check")

    store = NoLog()
    lines, out = capture()
    with pytest.raises(RuntimeError):
        run(store, text="ana pérez", since=None, until=None, apply=True, request=None, ids=None, out=out)
    assert store.deleted == []


def test_ids_restricts_the_deletion_to_what_the_admin_confirmed():
    store = FakeStore()
    lines, out = capture()
    run(store, text="ana pérez", since=None, until=None, apply=True, request=None, ids=["r1"], out=out)
    assert store.deleted == [("place_reports", ["r1"])]
    assert store.logged[0]["deleted"]["place_reports"] == 1


def test_no_match_writes_nothing():
    store = FakeStore(rows={t: [] for t in ROWS})
    lines, out = capture()
    assert run(store, text="nadie", since=None, until=None, apply=True, request=None, ids=None, out=out) == 0
    assert store.deleted == [] and store.logged == []
    assert "No hay coincidencias" in "\n".join(lines)


@pytest.mark.parametrize("bad", ["", "ab", "  a ", "%", "***", "a%b", "x*y", "a,b"])
def test_too_short_or_wildcard_text_is_refused(bad):
    store = FakeStore()
    lines, out = capture()
    assert run(store, text=bad, since=None, until=None, apply=True, request=None, ids=None, out=out) == 2
    assert store.finds == [] and store.deleted == []


def test_bad_dates_are_refused():
    store = FakeStore()
    lines, out = capture()
    assert run(store, text="ana pérez", since="01/09/2026", until=None, apply=False, request=None, ids=None, out=out) == 2
    assert store.finds == []
