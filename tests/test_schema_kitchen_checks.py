"""Guards the kitchen-declaration CHECK constraints in db/schema.sql.

A CHECK constraint PASSES when its expression evaluates to NULL. So

    check (celiac_prep is null or kitchen_exclusive = false)

lets a `celiac_prep` through when `kitchen_exclusive` IS NULL (`null::boolean = false` is NULL — verified
against Postgres). The rule is "celiac_prep only exists when the kitchen is explicitly NOT exclusive", so the
comparison must be `is false`, which is never NULL. pglast only checks syntax, so this cannot be caught there.
"""
import re
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def _kitchen_block() -> str:
    text = SCHEMA.read_text(encoding="utf-8").replace("\r\n", "\n")
    return text[text.index("-- KITCHEN-DECLARATIONS-BEGIN"): text.index("-- KITCHEN-DECLARATIONS-END")]


def _expression(block: str, constraint: str) -> str:
    m = re.search(rf"{constraint}\s+check \((.*?)\);", block, re.DOTALL)
    assert m, f"{constraint} not found"
    return " ".join(m.group(1).split())


def test_celiac_prep_requires_an_explicit_not_exclusive_kitchen_on_both_tables():
    block = _kitchen_block()
    for table in ("suggestions", "place_reports"):
        expr = _expression(block, f"{table}_celiac_prep_requires_mixed_check")
        assert "kitchen_exclusive is false" in expr, expr
        assert "kitchen_exclusive = false" not in expr, f"{table}: '= false' lets NULL through a CHECK"


def test_negative_reports_carry_no_kitchen_data_and_nulls_are_explicit():
    expr = _expression(_kitchen_block(), "place_reports_kitchen_positive_only_check")
    for col in ("kitchen_exclusive", "celiac_prep", "owner_celiac"):
        assert f"{col} is null" in expr, expr
