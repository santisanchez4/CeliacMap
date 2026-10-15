"""Every public table and view starts from `revoke all` for anon / authenticated, then gets only its minimal grant.

Supabase grants every privilege on new objects to anon and authenticated. Revoking only SELECT (as db/schema.sql
once did on `reviews`) leaves INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES and TRIGGER behind, and TRUNCATE is not
stopped by RLS. See db/migrations/2026-10-15-public-grants-revoke-all.sql.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = " ".join((ROOT / "db" / "schema.sql").read_text(encoding="utf-8").split())
MIGRATION_TEXT = (ROOT / "db" / "migrations" / "2026-10-15-public-grants-revoke-all.sql").read_text(encoding="utf-8")
MIGRATION = " ".join(MIGRATION_TEXT.split())
CHECKS = (ROOT / "db" / "checks" / "2026-10-15-public-grants-checks.sql").read_text(encoding="utf-8")
REHEARSAL = (ROOT / "db" / "checks" / "2026-10-15-public-grants-rehearsal.sql").read_text(encoding="utf-8")

INSERT_ONLY = {"suggestions", "place_reports", "place_votes"}
SERVER_ONLY = {"reviews", "agent_log", "outreach_messages", "chat_usage", "place_evidence"}


def tables(text: str) -> set[str]:
    return set(re.findall(r"create table if not exists public\.([a-z_]+)", text))


def views(text: str) -> set[str]:
    return set(re.findall(r"create or replace view public\.([a-z_]+)", text))


def test_every_public_table_and_view_is_reset_with_revoke_all():
    for name in tables(SCHEMA) | views(SCHEMA):
        assert f"revoke all on public.{name} from anon, authenticated" in SCHEMA, name


def test_no_partial_revoke_on_a_table():
    assert not re.search(r"revoke (select|insert|update|delete)\b[^;]* on public\.", SCHEMA)


def test_public_grants_are_only_the_minimal_ones():
    grants = re.findall(r"grant ([a-z ,]+?)(?: \([^)]*\))? on public\.([a-z_]+) to anon, authenticated", SCHEMA)
    for privilege, name in grants:
        privilege = privilege.strip()
        if name in INSERT_ONLY or name == "partner_applications":
            assert privilege == "insert", (name, privilege)
        else:
            assert privilege == "select" and (name == "places" or name in views(SCHEMA)), (name, privilege)
    assert not {name for _, name in grants} & SERVER_ONLY


def test_migration_resets_every_table_of_the_production_schema():
    for name in INSERT_ONLY | SERVER_ONLY | {"places", "community_opinions"}:
        assert f"revoke all on public.{name} from anon, authenticated" in MIGRATION, name
    for name in INSERT_ONLY:
        assert f"grant insert on public.{name} to anon, authenticated" in MIGRATION, name
    assert "grant select on public.community_opinions to anon, authenticated" in MIGRATION
    schema_places = re.search(r"(grant select \( id, name.*?\) on public\.places to anon, authenticated;)", SCHEMA)
    assert schema_places and schema_places.group(1) in MIGRATION, "the places column list must match the schema"


def test_rehearsal_is_the_migration_plus_the_checks_and_never_commits():
    body = MIGRATION_TEXT[MIGRATION_TEXT.index("begin;\n") + len("begin;\n"): MIGRATION_TEXT.index("commit;\n")]
    assert body in REHEARSAL
    assert CHECKS in REHEARSAL
    statements = [line.strip() for line in REHEARSAL.splitlines() if line.strip() and not line.strip().startswith("--")]
    assert statements[0] == "begin;" and statements[-1] == "rollback;"
    assert "commit" not in REHEARSAL.lower().replace("never commits", "")
    assert "raise exception 'PUBLIC-GRANTS" in CHECKS
