"""Answer a personal-data deletion request (privacy phase 1, 2026-09-29).

Finds rows by text, optionally within a date range, in the tables that hold what people write:
suggestions, place_reports, place_evidence and the chatbot rows of agent_log (the raw text of marked
turns). Dry run by default: it lists every match with an excerpt so the admin can check they belong to
the person asking. --apply deletes them (or only --ids, the ones the admin confirmed) and writes one
agent_log record (agent='privacy') with the request reference, the counts and the deleted ids -- never
the deleted content nor the searched text, which can be personal data themselves.

    python -m scripts.delete_personal_data --text "Ana Pérez"                        # dry run
    python -m scripts.delete_personal_data --text "Ana Pérez" --since 2026-09-01 --until 2026-09-30
    python -m scripts.delete_personal_data --text "Ana Pérez" --apply --request hola-2026-10-01
    python -m scripts.delete_personal_data --text "Ana Pérez" --apply --ids <uuid> <uuid>

It does not touch places (business data), the admin's mailbox or the providers' own logs: see
docs/legal/runbook-pedidos-de-datos.md for the whole procedure.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta

SEARCH_COLUMNS: dict[str, list[str]] = {
    "suggestions": ["name", "address", "city", "notes", "evidence_url"],
    "place_reports": ["description", "author_name", "place_name_text"],
    "place_evidence": ["text", "url"],
    # Only the chatbot's marked-turn text; every other agent's rows are audit data about places.
    "agent_log": ["result->>raw_user_message", "result->>raw_bot_reply", "result->guard->>discarded_bot_reply"],
}
MIN_TEXT = 4
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _excerpt(row: dict, columns: list[str], text: str) -> str:
    for column in columns:
        value = row
        for part in column.replace("->>", "->").split("->"):
            value = value.get(part) if isinstance(value, dict) else None
        if isinstance(value, str) and text.lower() in value.lower():
            one_line = " ".join(value.split())
            return f"{column}: {one_line[:140]}{'…' if len(one_line) > 140 else ''}"
    return ""


def run(store, text: str, since: str | None, until: str | None, apply: bool,
        request: str | None, ids: list[str] | None, out=print) -> int:
    text = (text or "").strip()
    if len(text) < MIN_TEXT or re.search(r"[%*,()]", text):
        out(f"Texto inválido: al menos {MIN_TEXT} caracteres y sin comodines ni % * , ( ).")
        return 2
    for label, value in (("--since", since), ("--until", until)):
        if value and not _DATE.match(value):
            out(f"{label} inválido: usá AAAA-MM-DD.")
            return 2

    matches: dict[str, dict[str, dict]] = {table: {} for table in SEARCH_COLUMNS}
    for table, columns in SEARCH_COLUMNS.items():
        for column in columns:
            for row in store.find(table, column, text, since, until):
                matches[table][row["id"]] = row
    if ids:
        wanted = set(ids)
        matches = {t: {i: r for i, r in rows.items() if i in wanted} for t, rows in matches.items()}

    total = sum(len(rows) for rows in matches.values())
    if not total:
        out("No hay coincidencias.")
        return 0
    out(f"{total} fila(s) coinciden:")
    for table, rows in matches.items():
        for rid, row in sorted(rows.items(), key=lambda kv: kv[1].get("created_at") or ""):
            out(f"  [{table}] {rid} · {row.get('created_at')} · {_excerpt(row, SEARCH_COLUMNS[table], text)}")

    if not apply:
        out("DRY RUN — no se borró nada. Revisá que todo sea de la persona que lo pide; "
            "agregá --apply (y --ids para borrar solo algunas).")
        return 0

    # The record goes first: if it cannot be written, nothing is deleted (no deletion without a trace).
    store.log({
        "request": request,
        "since": since,
        "until": until,
        "deleted": {table: len(rows) for table, rows in matches.items()},
        "ids": {table: sorted(rows) for table, rows in matches.items() if rows},
    })
    deleted = {table: 0 for table in SEARCH_COLUMNS}
    for table, rows in matches.items():
        if rows:
            deleted[table] = store.delete(table, list(rows))
    out(f"Borradas: {sum(deleted.values())} fila(s) ({', '.join(f'{t} {n}' for t, n in deleted.items() if n)}).")
    if sum(deleted.values()) != total:
        out(f"⚠ Se esperaban {total}: revisá las que faltan (el registro lista los ids).")
    return 0


class SupabaseStore:
    """The four operations run() needs, over the service-role client."""

    def __init__(self, client):
        self._db = client._db
        self._client = client

    def find(self, table, column, text, since, until):
        query = self._db.table(table).select("*").ilike(column, f"%{text}%")
        if table == "agent_log":
            query = query.eq("agent", "chatbot")
        if since:
            query = query.gte("created_at", since)
        if until:
            query = query.lt("created_at", (date.fromisoformat(until) + timedelta(days=1)).isoformat())
        return query.limit(500).execute().data or []

    def delete(self, table, ids):
        res = self._db.table(table).delete().in_("id", list(ids)).execute()
        return len(res.data or [])

    def log(self, result):
        self._client.insert_agent_log("privacy", "personal_data_deleted", result, "success")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--text", required=True, help="text to look for (a name, a phrase the person wrote)")
    parser.add_argument("--since", help="AAAA-MM-DD, inclusive")
    parser.add_argument("--until", help="AAAA-MM-DD, inclusive")
    parser.add_argument("--ids", nargs="+", metavar="ID", help="delete only these of the matches")
    parser.add_argument("--request", help="reference of the request (e.g. hola-2026-10-01), stored in the record")
    parser.add_argument("--apply", action="store_true", help="delete (default: dry run)")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    from agents.clients.supabase_client import SupabaseClient
    from config.settings import get_settings

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")
    store = SupabaseStore(SupabaseClient(settings.supabase_url, settings.supabase_service_role_key))
    return run(store, args.text, args.since, args.until, args.apply, args.request, args.ids)


if __name__ == "__main__":
    raise SystemExit(main())
