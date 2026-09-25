"""Step 2b: already-approved 100% places without explicit evidence go to "options" + admin flag."""
from agents.validator_agent import PENDING_ADMIN_FLAG
from scripts.cap_unsupported_100 import run


class FakeDB:
    def __init__(self, places, reviews=None, evidence=None):
        self.places, self.reviews, self.evidence, self.updates = places, reviews or {}, evidence or {}, []

    def fetch_places_for_admin(self, status=None, **kw):
        assert status == "approved" and kw["safety_level"] == "gluten_free_100"
        return self.places

    def fetch_reviews_for_place(self, pid):
        return self.reviews.get(pid, [])

    def fetch_place_evidence(self, pid):
        return self.evidence.get(pid, [])

    def update_place(self, pid, patch):
        self.updates.append((pid, patch))


PLACES = [
    {"id": "a", "name": "Sin Gluten Palermo", "validation_notes": "Nombre sugiere sin gluten.", "flags": []},
    {"id": "b", "name": "Los Leños", "validation_notes": "CORRECCIÓN MANUAL 2026-09-24: ...", "flags": []},
    {"id": "c", "name": "Pan Justo", "validation_notes": None, "flags": None},
    {"id": "d", "name": "Blog place", "validation_notes": "x", "flags": ["otra"]},
]


def make():
    return FakeDB(
        PLACES,
        reviews={"c": [{"text": "Todo es sin gluten, genial"}]},
        evidence={"d": [{"text": "el blog dice que tiene opciones sin TACC"}]},
    )


def test_dry_run_lists_without_writing():
    db, lines = make(), []
    run(db, apply=False, out=lines.append)
    assert db.updates == []
    text = "\n".join(lines)
    assert "1 con decisión manual" in text and "1 con evidencia explícita" in text and "2 pasarían" in text


def test_apply_caps_only_the_unsupported_and_never_the_manual_ones():
    db = make()
    run(db, apply=True, out=lambda *_: None)
    changed = {pid: patch for pid, patch in db.updates}
    assert set(changed) == {"a", "d"}
    for patch in changed.values():
        assert patch["safety_level"] == "celiac_friendly"
        assert PENDING_ADMIN_FLAG in patch["flags"]
        assert patch["validation_notes"].startswith("CORRECCIÓN RETROACTIVA DE NIVEL")
        assert "status" not in patch and "validation_confidence" not in patch
    assert "otra" in changed["d"]["flags"]
