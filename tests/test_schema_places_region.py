"""Guards the `places.region` column: schema.sql, its migration and the one-off backfill.

The backfill is a data file (one (id, region) pair per existing row, computed offline by
GooglePlacesClient.region_from_address), so these tests read it: every id is a unique uuid, every value is
a canonical region, the number of pairs matches the row count the file asserts, and the transaction is
balanced (trigger off -> on, begin -> commit). pglast only checks that the SQL parses.
"""
import re
from pathlib import Path

from pglast import parse_sql

from agents.clients.google_places import AR_REGION_NAMES, CABA_REGION, UY_REGION_NAMES

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "db" / "schema.sql"
MIGRATION = ROOT / "db" / "migrations" / "2026-09-26-places-region.sql"
BACKFILL = ROOT / "db" / "fixes" / "2026-09-26-places-region-backfill.sql"

ADD_COLUMN = "alter table public.places add column if not exists region text;"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _schema_block() -> str:
    text = _text(SCHEMA)
    return text[text.index("-- PLACES-REGION-BEGIN"): text.index("-- PLACES-REGION-END")]


def test_schema_declares_only_the_column_no_check_no_index():
    # 1.3k rows, and the canonical list lives in code (Python + the chat), not in SQL.
    statements = [ln.strip() for ln in _schema_block().splitlines() if ln.strip() and not ln.strip().startswith("--")]
    assert statements == [ADD_COLUMN]


def test_migration_is_the_schema_statement_in_one_transaction():
    text = _text(MIGRATION)
    assert ADD_COLUMN in text
    assert text.count("begin;") == 1 and text.rstrip().endswith("commit;")
    parse_sql(text)


def _pairs(text: str) -> list[tuple[str, str]]:
    return re.findall(r"\('([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', '([^']+)'\)", text)


def test_backfill_pairs_are_unique_uuids_with_canonical_regions():
    pairs = _pairs(_text(BACKFILL))
    assert pairs, "no (id, region) pairs found"
    ids = [i for i, _ in pairs]
    assert len(ids) == len(set(ids)), "an id appears twice"
    canonical = set(AR_REGION_NAMES.values()) | set(UY_REGION_NAMES.values()) | {CABA_REGION}
    unknown = {r for _, r in pairs} - canonical
    assert not unknown, f"non-canonical regions: {unknown}"


def test_backfill_asserts_exactly_the_number_of_pairs_it_carries():
    text = _text(BACKFILL)
    m = re.search(r"if n <> (\d+) then raise exception 'expected \d+ rows updated", text)
    assert m, "the row-count assertion is missing"
    assert int(m.group(1)) == len(_pairs(text))


def test_backfill_is_one_balanced_transaction_that_keeps_updated_at_and_refuses_a_second_run():
    text = _text(BACKFILL)
    body = re.sub(r"--[^\n]*", "", text)
    assert body.count("begin;") == 1 and body.rstrip().endswith("commit;")
    assert body.index("disable trigger places_set_updated_at") < body.index("enable trigger places_set_updated_at")
    assert "and p.region is null" in body, "the UPDATE must be guarded so a second run matches 0 rows and aborts"
    for guard in ("approved places without region", "not in the list of its country", "changed something other than region"):
        assert guard in body, guard
    parse_sql(text)
