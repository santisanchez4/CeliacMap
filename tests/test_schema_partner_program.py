"""Guards the PARTNER-PROGRAM block of db/schema.sql (ADR-011, docs/plans/PLAN-partner-program.md §4).

The public may only INSERT a request (no read back, no state, no payment, no public field), the only public read is
the view partners_public, whose WHERE is the visibility rule (approved by the admin and paid up), and the block never
touches the evaluation tables. pglast only checks syntax, so these tests read the statements.
"""
import re
from pathlib import Path

from pglast import parse_sql
from pglast.ast import ViewStmt

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "db" / "schema.sql"
MIGRATION = ROOT / "db" / "migrations" / "2026-10-14-partner-program.PENDING.sql"
PUBLIC_COLUMNS = ["public_name", "public_text_es", "public_text_en", "logo_path", "public_links"]
REQUEST_COLUMNS = {
    "ref_code", "business_name", "city", "country", "contact_name", "contact_email", "contact_phone", "links",
    "description", "on_map_claim", "consent_version",
}
SERVER_ONLY = {
    "id", "place_id", "payment_status", "publication_status", "mp_preapproval_id", "mp_first_payment_id", "paid_through",
    "approved_at", "admin_notes", "public_name", "public_text_es", "public_text_en", "logo_path", "public_links",
    "created_at", "updated_at",
}


def _block(text: str) -> str:
    text = text.replace("\r\n", "\n")
    return text[text.index("-- PARTNER-PROGRAM-BEGIN"): text.index("-- PARTNER-PROGRAM-END")]


def _flat(text: str) -> str:
    return " ".join(text.split())


BLOCK = _block(SCHEMA.read_text(encoding="utf-8"))
FLAT = _flat(BLOCK)


def test_migration_carries_the_schema_block_verbatim():
    assert _block(MIGRATION.read_text(encoding="utf-8")) == BLOCK


def test_migration_and_schema_block_are_marked_pending_for_production():
    """partner_applications / partners_public must not exist in production before phase 3 (owner decision 2026-10-15)."""
    assert not (ROOT / "db" / "migrations" / "2026-10-14-partner-program.sql").exists()
    header = MIGRATION.read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("-- PENDING: aplicada solo en staging; producción en la Fase 3")
    schema = SCHEMA.read_text(encoding="utf-8")
    marker = schema.index("-- PENDING: aplicado solo en staging; producción en la Fase 3")
    assert marker < schema.index("-- PARTNER-PROGRAM-BEGIN")


def test_block_and_whole_schema_parse():
    assert parse_sql(BLOCK)
    assert parse_sql(SCHEMA.read_text(encoding="utf-8"))


def test_table_columns_are_the_request_plus_the_server_columns():
    table = re.search(r"create table if not exists public\.partner_applications \((.*?)\n\);", BLOCK, re.S)
    assert table
    columns = {m.group(1) for m in re.finditer(r"^\s{2}([a-z_]+)\s", table.group(1), re.M)} - {"constraint"}
    assert columns == REQUEST_COLUMNS | SERVER_ONLY


def test_rls_is_on_and_privileges_are_reset_before_the_grant():
    assert "alter table public.partner_applications enable row level security" in FLAT
    revoke = "revoke all on public.partner_applications from anon, authenticated"
    assert revoke in FLAT
    assert FLAT.index(revoke) < FLAT.index("grant insert (")


def test_public_may_insert_only_the_request_columns():
    grant = re.search(r"grant insert \((.*?)\) on public\.partner_applications to anon, authenticated;", BLOCK, re.S)
    assert grant, "the public grant must be a column list"
    granted = {c.strip() for c in grant.group(1).split(",")}
    assert granted == REQUEST_COLUMNS
    assert not granted & SERVER_ONLY


def test_public_never_reads_updates_or_deletes_the_table():
    for verb in ("select", "update", "delete", "all"):
        assert not re.search(rf"grant\s+{verb}\b[^;]*on\s+public\.partner_applications", FLAT, re.I), verb


def test_insert_policy_forces_an_unpaid_unreviewed_unpublished_row():
    m = re.search(r'create policy "public can request a partnership"(.*?);', FLAT)
    assert m
    body = m.group(1)
    assert "for insert" in body and "to anon, authenticated" in body
    assert "payment_status = 'pending'" in body
    assert "publication_status = 'requested'" in body
    for column in SERVER_ONLY - {"id", "payment_status", "publication_status", "created_at", "updated_at"}:
        assert f"{column} is null" in body, column


def test_ref_code_is_unique_and_shaped():
    assert "constraint partner_applications_ref_code_key unique (ref_code)" in FLAT
    assert "ref_code ~ '^CM-[A-Z0-9]{6}$'" in FLAT


def test_one_open_request_per_email_and_business():
    assert (
        "create unique index if not exists partner_applications_open_request_idx on public.partner_applications "
        "(lower(contact_email), lower(business_name)) where publication_status in ('requested', 'eligible', 'approved')"
    ) in FLAT


def _view() -> ViewStmt:
    for raw in parse_sql(BLOCK):
        if isinstance(raw.stmt, ViewStmt) and raw.stmt.view.relname == "partners_public":
            return raw.stmt
    raise AssertionError("view partners_public not found")


def test_view_exposes_exactly_the_card_columns():
    names = [t.name or t.val.fields[-1].sval for t in _view().query.targetList]
    assert names == PUBLIC_COLUMNS


def test_view_shows_only_approved_and_paid_up_partners():
    where = FLAT[FLAT.index("from public.partner_applications where"): FLAT.index("revoke all on public.partners_public")]
    assert "publication_status = 'approved'" in where
    assert "public_name is not null" in where
    assert "payment_status = 'active' or (payment_status = 'cancelled' and paid_through >= current_date)" in where
    assert "past_due" not in where and "pending" not in where


def test_view_privileges_are_reset_to_select_only():
    revoke = "revoke all on public.partners_public from anon, authenticated"
    grant = "grant select on public.partners_public to anon, authenticated"
    assert revoke in FLAT and grant in FLAT
    assert FLAT.index(revoke) < FLAT.index(grant)


def test_partner_sql_never_touches_the_evaluation_tables():
    """ADR-011 point 3 (= ADR-009 point 5): a partnership never changes places, votes, reviews or the Validator."""
    sources = [BLOCK, MIGRATION.read_text(encoding="utf-8"),
               (ROOT / "db" / "migrations" / "2026-10-14-partner-program-revert.sql").read_text(encoding="utf-8")]
    for text in sources:
        flat = _flat(text).lower()
        for table in ("places", "place_votes", "reviews", "place_evidence", "place_reports", "suggestions"):
            assert not re.search(rf"(alter table|update|insert into|delete from|drop table)( if exists)? public\.{table}\b", flat), table
        assert "references public.places(id) on delete set null" in flat or "drop" in flat


def test_staging_delta_matches_the_current_block():
    """db/staging/2026-10-15-partner-payment-columns.sql brings staging (created from the first version) to this shape."""
    delta = (ROOT / "db" / "staging" / "2026-10-15-partner-payment-columns.sql").read_text(encoding="utf-8")
    policy = re.search(r'create policy "public can request a partnership".*?\n  \);', BLOCK, re.S).group(0)
    assert policy in delta
    assert "drop column if exists payer_email" in delta
    assert "partner_applications_mp_first_payment_id_key unique (mp_first_payment_id)" in delta
    assert "payer_email" not in BLOCK, "the payer's email is never stored"
    assert "STAGING ONLY" in delta.splitlines()[0]
