"""Guards the community-opinions block in db/schema.sql
(docs/superpowers/specs/2026-09-24-community-opinions-design.md).

The public read path is a VIEW with an explicit column list, and the anonymous INSERT policy must refuse
a row that arrives already published. pglast only checks syntax, so these tests read the statements.
"""
import re
from pathlib import Path

from pglast import parse_sql
from pglast.ast import ViewStmt

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
PUBLIC_COLUMNS = {
    "id", "description", "author_name", "published_at",
    "place_id", "place_name", "city", "country",
}


def _text() -> str:
    return SCHEMA.read_text(encoding="utf-8").replace("\r\n", "\n")


def _block() -> str:
    text = _text()
    return text[text.index("-- COMMUNITY-OPINIONS-BEGIN"): text.index("-- COMMUNITY-OPINIONS-END")]


def _expression(block: str, constraint: str) -> str:
    m = re.search(rf"{constraint}\s+check \((.*?)\);", block, re.DOTALL)
    assert m, f"{constraint} not found"
    return " ".join(m.group(1).split())


def _view() -> ViewStmt:
    for raw in parse_sql(_block()):
        stmt = raw.stmt
        if isinstance(stmt, ViewStmt) and stmt.view.relname == "community_opinions":
            return stmt
    raise AssertionError("view community_opinions not found")


def test_whole_schema_still_parses():
    assert parse_sql(_text())


def test_author_name_is_optional_and_bounded():
    expr = _expression(_block(), "place_reports_author_name_check")
    assert "author_name is null" in expr, expr
    assert "between 1 and 40" in expr, expr
    assert "btrim(author_name)" in expr, "a name of only spaces must be rejected"


def test_only_a_positive_report_can_be_published():
    expr = _expression(_block(), "place_reports_publish_positive_only_check")
    assert "published_at is null" in expr, expr
    assert "report_type = 'positive'" in expr, expr


def test_anonymous_insert_policy_refuses_an_already_published_row():
    text = _text()
    m = re.search(
        r'create policy "public can submit place reports"(.*?);\n', text, re.DOTALL
    )
    assert m, "policy not found"
    body = " ".join(m.group(1).split())
    assert "published_at is null" in body, body
    assert "status = 'new'" in body, body


def test_view_exposes_exactly_the_public_columns():
    names = []
    for target in _view().query.targetList:
        names.append(target.name or target.val.fields[-1].sval)
    assert set(names) == PUBLIC_COLUMNS, names
    assert len(names) == len(PUBLIC_COLUMNS), f"duplicate column in {names}"


def test_view_only_shows_published_positive_reports_of_approved_places():
    block = " ".join(_block().split())
    where = block[block.index("where r.report_type"): block.index("grant select on public.community_opinions")]
    assert "r.report_type = 'positive'" in where
    assert "r.published_at is not null" in where
    assert "p.status = 'approved'" in where


def test_view_is_public_but_the_table_stays_closed():
    assert "grant select on public.community_opinions to anon, authenticated" in " ".join(_block().split())
    assert not re.search(r"grant\s+select[^;]*on\s+public\.place_reports", _text(), re.IGNORECASE)


def test_view_privileges_are_reset_to_select_only():
    """Supabase grants every privilege on new objects to anon/authenticated by default, and the view runs with
    its owner's rights (bypassing RLS): if it ever became auto-updatable, anon could write through it. So the
    block must REVOKE first and only then grant SELECT (the same revoke-then-grant shape used for the tables)."""
    block = " ".join(_block().split())
    revoke = "revoke all on public.community_opinions from anon, authenticated"
    grant = "grant select on public.community_opinions to anon, authenticated"
    assert revoke in block, "the default privileges on the view are never removed"
    assert grant in block
    assert block.index(revoke) < block.index(grant), "the revoke must come first or it would remove the grant"
