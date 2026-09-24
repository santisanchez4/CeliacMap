"""The moderation script: list by default, write only with --apply, approve only what is pending."""
import pytest

from scripts.moderate_opinions import run

ID_A = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10"
ID_B = "9a1c5d7e-2b44-4f60-8c31-5e0d7a9b1c22"
ID_C = "c0ffee00-1234-4abc-8def-0123456789ab"


def row(rid, name=None, text="Muy rico todo"):
    return {
        "id": rid, "description": text, "author_name": name, "created_at": "2026-09-23T10:00:00+00:00",
        "place_id": "p1", "places": {"name": "San Felipa", "city": "Gualeguaychú", "country": "Argentina", "status": "approved"},
    }


class FakeDB:
    def __init__(self, pending):
        self.pending = pending
        self.writes = []

    def fetch_unpublished_opinions(self, limit=100):
        return self.pending

    def set_opinions_published(self, ids, published):
        self.writes.append((list(ids), published))
        return [{"id": i} for i in ids]


def capture():
    lines = []
    return lines, lambda text="": lines.append(str(text))


def test_no_ids_lists_pending_with_the_full_text_and_anonymous_label():
    long_text = "palabra " * 250  # ~2000 chars: the admin must see all of it
    db = FakeDB([row(ID_A, name=None, text=long_text), row(ID_B, name="Ana")])
    lines, out = capture()

    assert run(db, approve=[], hide=[], apply=False, out=out) == 0

    text = "\n".join(lines)
    assert ID_A in text and ID_B in text
    assert "San Felipa" in text and "Gualeguaychú" in text
    assert "Anónimo" in text and "Ana" in text
    assert long_text.strip() in text
    assert db.writes == []


def test_approve_is_a_dry_run_without_apply():
    db = FakeDB([row(ID_A)])
    lines, out = capture()
    assert run(db, approve=[ID_A], hide=[], apply=False, out=out) == 0
    assert db.writes == []
    assert "DRY RUN" in "\n".join(lines)


def test_approve_with_apply_publishes_only_the_pending_ids():
    db = FakeDB([row(ID_A), row(ID_B)])
    lines, out = capture()
    code = run(db, approve=[ID_A, ID_C], hide=[], apply=True, out=out)
    assert db.writes == [([ID_A], True)]
    assert ID_C in "\n".join(lines)  # reported as skipped, not silently dropped
    assert code == 1  # an id was skipped: the operator must notice


def test_approve_never_publishes_an_id_that_is_not_pending():
    db = FakeDB([row(ID_A)])
    _, out = capture()
    assert run(db, approve=[ID_C], hide=[], apply=True, out=out) == 1
    assert db.writes == []


def test_hide_with_apply_unpublishes():
    db = FakeDB([])
    _, out = capture()
    assert run(db, approve=[], hide=[ID_B], apply=True, out=out) == 0
    assert db.writes == [([ID_B], False)]


def test_hide_is_a_dry_run_without_apply():
    db = FakeDB([])
    _, out = capture()
    run(db, approve=[], hide=[ID_B], apply=False, out=out)
    assert db.writes == []


def test_an_invalid_id_is_rejected_before_touching_anything():
    db = FakeDB([row(ID_A)])
    _, out = capture()
    assert run(db, approve=["no-es-un-uuid"], hide=[], apply=True, out=out) == 2
    assert db.writes == []


def test_approve_and_hide_together_are_refused():
    with pytest.raises(ValueError):
        run(FakeDB([]), approve=[ID_A], hide=[ID_B], apply=True, out=lambda *_: None)
