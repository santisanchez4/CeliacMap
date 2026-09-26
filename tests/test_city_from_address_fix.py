"""Guards db/fixes/2026-09-27-city-from-address.sql (13 rows whose `city` contradicts their own address).

Two things this file exists to protect:
  * the CORRECCIÓN MANUAL header it prepends is a DATA correction (agents/manual_overrides.py): it must never make
    a place "protected" from the Validator's cap/flag pass or from a community report, so its wording has to keep
    containing one of DATA_CORRECTION_PHRASES ("ciudad corregida");
  * the fix touches `city` and `validation_notes` and nothing else (the SQL asserts it with a snapshot hash; here the
    UPDATE's assignments are read).
pglast only checks that the SQL parses.
"""
import re
from pathlib import Path

from pglast import parse_sql

from agents.manual_overrides import DATA_CORRECTION_PHRASES, manual_override_marker

FIX = Path(__file__).resolve().parent.parent / "db" / "fixes" / "2026-09-27-city-from-address.sql"
HEADER_PREFIX = "CORRECCIÓN MANUAL 2026-09-27: ciudad corregida según la dirección (era "
NL2 = chr(92) + "n" + chr(92) + "n"  # the two characters backslash-n, twice, as written inside E'...' in SQL


def _text() -> str:
    return FIX.read_text(encoding="utf-8").replace("\r\n", "\n")


def _without_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


def _update_blocks(text: str) -> list[str]:
    return re.findall(r"update public\.places p\b.*?get diagnostics n = row_count;", _without_comments(text), re.S)


def test_the_header_is_a_data_correction_and_protects_nothing():
    header = HEADER_PREFIX + "Fray Bentos)"
    assert "ciudad corregida" in DATA_CORRECTION_PHRASES
    assert manual_override_marker(header) is None
    # Still true on top of the previous text of a place that carries no safety decision.
    assert manual_override_marker(header + "\n\nValidator: sin evidencia clara de protocolo anti-contaminación cruzada.") is None


def test_the_check_is_sensitive_a_header_without_a_data_phrase_would_protect():
    assert manual_override_marker("CORRECCIÓN MANUAL 2026-09-27: ciudad arreglada (era Fray Bentos)") == "correccion manual"
    # ...and a safety header written apart keeps protecting even under our data header.
    assert manual_override_marker(HEADER_PREFIX + "X)\n\nOVERRIDE MANUAL: aprobado por el admin.") == "override"


def test_the_fix_prepends_exactly_that_header_keeping_the_original_text_below():
    blocks = _update_blocks(_text())
    assert len(blocks) == 2, "one UPDATE per group (approved, needs_review)"
    for block in blocks:
        assert f"'{HEADER_PREFIX}' || f.old_city || ')'" in block
        assert f"concat_ws(E'{NL2}'" in block and "nullif(p.validation_notes, '')" in block


def test_the_fix_rows_are_unique_ids_split_into_11_approved_and_2_needs_review():
    rows = re.findall(r"\('([0-9a-f-]{36})', '([^']+)', '([^']+)', '(approved|needs_review)'\)", _text())
    assert len(rows) == 13
    assert len({r[0] for r in rows}) == 13
    assert sum(1 for r in rows if r[3] == "approved") == 11 and sum(1 for r in rows if r[3] == "needs_review") == 2
    assert all(old != new for _, old, new, _ in rows)
    # CABA stays "Buenos Aires": no row is corrected TO it.
    assert not any(new == "Buenos Aires" for _, _, new, _ in rows)


def test_each_block_asserts_its_exact_row_count():
    text = _text()
    assert re.search(r"if n <> 11 then raise exception 'approved: expected 11", text)
    assert re.search(r"if n <> 2 then raise exception 'needs_review: expected 2", text)


def test_the_updates_assign_only_city_and_validation_notes_and_are_guarded_by_the_old_city():
    blocks = _update_blocks(_text())
    assert len(blocks) == 2
    for block in blocks:
        set_clause = re.search(r"\bset\b(.*?)\bfrom _fix f\b", block, re.S).group(1)
        assert re.findall(r"(?m)^\s*(\w+)\s*=", "\n" + set_clause.strip() + "\n") == ["city", "validation_notes"]
        assert "p.city = f.old_city" in block, "guarded by the old city: a second run matches 0 rows and aborts"


def test_one_balanced_transaction_that_keeps_updated_at_and_parses():
    text = _text()
    body = _without_comments(text)
    assert body.count("begin;") == 1 and body.rstrip().endswith("commit;")
    assert body.index("disable trigger places_set_updated_at") < body.index("enable trigger places_set_updated_at")
    for guard in ("changed something other than city and validation_notes", "original notes are not kept", "places_set_updated_at was left disabled"):
        assert guard in body, guard
    parse_sql(text)
