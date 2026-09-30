"""The public (anon / authenticated) read of `places` is a column allowlist, not the whole row.

`places` carries business contact data and internal review columns (contact_email, outreach_*,
validation_notes, flags, recommendation). The anon key is public, so db/schema.sql revokes every
privilege on the table and grants SELECT only on the columns the public readers actually use:
js/map.js, js/ranking.js, js/report.js and the chat Edge Function (which reads with the anon key).
This test fails when a public reader starts using a column that is not granted (the page would
break with a permission error) or when a sensitive column enters the grant.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
CHAT = (ROOT / "supabase" / "functions" / "chat" / "index.ts").read_text(encoding="utf-8")

SENSITIVE = {
    "contact_email", "contact_email_checked_at", "outreach_status", "outreach_channel", "outreach_opt_out",
    "validation_notes", "validation_confidence", "flags", "recommendation", "external_id",
}


def granted_columns() -> set[str]:
    block = re.search(r"-- PLACES-PUBLIC-COLUMNS-BEGIN(.*?)-- PLACES-PUBLIC-COLUMNS-END", SCHEMA, re.S)
    assert block, "db/schema.sql needs the PLACES-PUBLIC-COLUMNS block"
    grant = re.search(r"grant select\s*\((.*?)\)\s*on public\.places to anon, authenticated;", block.group(1), re.S)
    assert grant, "the block must grant SELECT (column list) on public.places to anon, authenticated"
    return {c.strip() for c in grant.group(1).split(",") if c.strip()}


def frontend_selects() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for name in ("map.js", "ranking.js", "report.js"):
        src = (ROOT / "js" / name).read_text(encoding="utf-8")
        # Join the string concatenations so a select split across lines reads as one.
        joined = re.sub(r'"\s*\+\s*"', "", src)
        for m in re.finditer(r"/places\?select=([a-z_,]+)", joined):
            out.setdefault(name, set()).update(m.group(1).split(","))
        for m in re.finditer(r"[?&]([a-z_]+)=(?:eq|gt|ilike|in)\.", joined):
            out.setdefault(name, set()).add(m.group(1))
        for m in re.finditer(r"order=([a-z_.,]+)", joined):
            out.setdefault(name, set()).update(p.split(".")[0] for p in m.group(1).split(","))
    return out


def chat_columns() -> set[str]:
    fields = re.search(r"export const PLACES_SELECT_FIELDS = \[(.*?)\] as const;", CHAT, re.S)
    assert fields
    cols = set(re.findall(r'"([a-z_]+)"', fields.group(1)))
    # Extra selects, filters and orderings the chat builds on places with the anon key.
    for m in re.finditer(r"select=([a-z_,$]+)", CHAT):
        cols.update(c for c in m.group(1).split(",") if re.fullmatch(r"[a-z_]+", c))
    for m in re.finditer(r'searchParams\.set\("select", "([a-z_,]+)"\)', CHAT):
        cols.update(m.group(1).split(","))
    for m in re.finditer(r'params\.set\("select", "([a-z_,]+)"\)', CHAT):
        cols.update(m.group(1).split(","))
    for m in re.finditer(r"[`\"&(]([a-z_]+)=(?:eq|ilike|in)\.", CHAT):
        cols.add(m.group(1))
    for m in re.finditer(r'params\.set\("([a-z_]+)", `(?:eq|ilike)\.', CHAT):
        cols.add(m.group(1))
    for m in re.finditer(r"order=([a-z_.,]+)", CHAT):
        cols.update(p.split(".")[0] for p in m.group(1).split(","))
    return cols


def test_grant_excludes_sensitive_columns():
    assert granted_columns() & SENSITIVE == set()


def test_every_public_reader_column_is_granted():
    granted = granted_columns()
    for name, cols in frontend_selects().items():
        assert cols, name
        assert cols <= granted, (name, sorted(cols - granted))
    chat = chat_columns()
    assert {"name", "status", "region", "city", "id", "community_warning_at"} <= chat, sorted(chat)
    assert chat <= granted, sorted(chat - granted)


def test_place_votes_policy_columns_are_granted():
    # The place_votes WITH CHECK subquery runs as anon and reads places.id and places.status.
    assert {"id", "status"} <= granted_columns()


def test_no_public_wildcard_select_on_places():
    for name in ("map.js", "ranking.js", "report.js", "opinions.js"):
        src = (ROOT / "js" / name).read_text(encoding="utf-8")
        assert "places?select=*" not in src, name
    assert "places?select=*" not in CHAT


def test_revoke_all_precedes_the_column_grant():
    block = re.search(r"-- PLACES-PUBLIC-COLUMNS-BEGIN(.*?)-- PLACES-PUBLIC-COLUMNS-END", SCHEMA, re.S).group(1)
    revoke = block.find("revoke all on public.places from anon, authenticated;")
    grant = block.find("grant select (")
    assert 0 <= revoke < grant
    assert not re.search(r"grant select on public\.places\s+to", SCHEMA), "no table-wide SELECT grant on places"


def test_migration_matches_schema_block():
    migration = (ROOT / "db" / "migrations" / "2026-09-29-places-public-columns.sql").read_text(encoding="utf-8")
    block = re.search(r"-- PLACES-PUBLIC-COLUMNS-BEGIN.*?-- PLACES-PUBLIC-COLUMNS-END", SCHEMA, re.S).group(0)
    assert block in migration
