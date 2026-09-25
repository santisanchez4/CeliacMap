"""The admin review queue: lists by default, writes only with --apply, never a silent decision."""
from __future__ import annotations

from agents.validator_agent import PENDING_ADMIN_FLAG
from scripts.review_queue import build_parser, run

PID = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10"
SID = "9a1c5d7e-2b44-4f60-8c31-5e0d7a9b1c22"


class FakeDB:
    def __init__(self, place=None, suggestion=None):
        self.place = place or {
            "id": PID, "name": "Bienestar Gluten Free", "status": "needs_review", "safety_level": "celiac_friendly",
            "validation_confidence": 0.52, "validation_notes": "Solo geocodificado.", "flags": [PENDING_ADMIN_FLAG, "sin ficha"],
            "lat": -33.12, "lng": -58.30, "city": "Fray Bentos", "country": "Uruguay",
        }
        self.suggestion = suggestion
        self.updates, self.warnings, self.inserted, self.statuses, self.queries = [], [], [], [], []

    def fetch_place_by_id(self, pid):
        return self.place if pid == PID else None

    def update_place(self, pid, patch):
        self.updates.append((pid, patch))

    def set_community_warning(self, pid, at):
        self.warnings.append((pid, at))

    def fetch_places_for_admin(self, status=None, **kw):
        self.queries.append((status, kw))
        return [self.place]

    def fetch_suggestions_by_status(self, status, limit=50):
        return [self.suggestion] if self.suggestion else []

    def fetch_suggestion_by_id(self, sid):
        return self.suggestion if sid == SID else None

    def fetch_suggestion_for_place(self, pid):
        return {"notes": "todo sin gluten", "kitchen_exclusive": True, "owner_celiac": True, "created_at": "2026-09-01"}

    def fetch_place_evidence(self, pid):
        return [{"source": "social", "text": "100% sin TACC", "url": "https://instagram.com/x"}]

    def fetch_recent_negative_reports(self, pid, days=30):
        return [{"created_at": "2026-09-20", "description": "me contaminé"}]

    def insert_place_candidate(self, c):
        self.inserted.append(c)
        return {"id": "new-place"}

    def update_suggestion_status(self, sid, status, pid=None):
        self.statuses.append((sid, status, pid))

    def add_place_evidence(self, *a):
        pass


def go(db, *argv):
    lines = []
    code = run(db, build_parser().parse_args(list(argv)), out=lambda t="": lines.append(str(t)))
    return code, "\n".join(lines)


def test_default_lists_every_queue_with_the_evidence_and_the_admin_only_kitchen_data():
    code, text = go(FakeDB())
    assert code == 0
    for heading in ("100% pendientes", "needs_review", "Sugerencias sin ubicar", "reportados por la comunidad"):
        assert heading in text
    assert "[social] 100% sin TACC https://instagram.com/x" in text
    assert "dueño/a celíaco/a sí (solo para vos)" in text
    assert "me contaminé" in text  # the report text: admin only
    assert "https://www.google.com/maps?q=-33.12,-58.3" in text


def test_approve_is_a_dry_run_by_default():
    db = FakeDB()
    code, text = go(db, "--approve", PID, "--level", "100", "--note", "Conozco el local")
    assert code == 0 and "DRY RUN" in text
    assert db.updates == []


def test_approve_writes_a_visible_override_and_never_touches_confidence():
    db = FakeDB()
    go(db, "--approve", PID, "--level", "100", "--note", "Conozco el local", "--apply")
    (pid, patch), = db.updates
    assert patch["status"] == "approved" and patch["safety_level"] == "gluten_free_100"
    assert patch["validation_notes"].startswith("APROBACIÓN MANUAL")
    assert patch["validation_notes"].endswith("Solo geocodificado.")
    assert "0.52" in patch["validation_notes"]
    assert PENDING_ADMIN_FLAG not in patch["flags"] and "sin ficha" in patch["flags"]
    assert "validation_confidence" not in patch and "verified" not in patch


def test_approve_options_keeps_the_finer_level():
    db = FakeDB()
    go(db, "--approve", PID, "--level", "options", "--note", "tiene menú aparte", "--apply")
    assert db.updates[0][1]["safety_level"] == "celiac_friendly"


def test_a_decision_needs_a_note_and_a_level():
    assert go(FakeDB(), "--approve", PID, "--level", "100")[0] == 2
    assert go(FakeDB(), "--approve", PID, "--note", "x")[0] == 2
    assert go(FakeDB(), "--discard", PID)[0] == 2


def test_the_note_refuses_an_owner_health_detail():
    code, text = go(FakeDB(), "--approve", PID, "--level", "100", "--note", "la dueña es celíaca", "--apply")
    assert code == 2 and "datos de salud" in text


def test_clear_warning_and_discard():
    db = FakeDB()
    go(db, "--clear-warning", PID, "--apply")
    assert db.warnings == [(PID, None)]
    go(db, "--discard", PID, "--note", "cerró", "--apply")
    assert db.updates[-1][1]["status"] == "discarded"


def test_discard_takes_the_place_out_of_the_pending_100_queue():
    """A discarded place must not stay in --pending-100 (that list has no status filter): the flag goes."""
    db = FakeDB()
    go(db, "--discard", PID, "--note", "cerró", "--apply")
    patch = db.updates[-1][1]
    assert PENDING_ADMIN_FLAG not in patch["flags"] and "sin ficha" in patch["flags"]
    assert patch["validation_notes"].startswith("DESCARTE MANUAL")
    assert "validation_confidence" not in patch


def test_approving_at_either_level_clears_the_pending_100_flag():
    for level in ("100", "options"):
        db = FakeDB()
        go(db, "--approve", PID, "--level", level, "--note", "lo conozco", "--apply")
        flags = db.updates[0][1]["flags"]
        assert PENDING_ADMIN_FLAG not in flags and "sin ficha" in flags, level


def test_offset_pages_through_the_queue_and_defaults_to_the_first_page():
    db = FakeDB()
    go(db, "--pending-100", "--limit", "5")
    assert db.queries[-1][1]["limit"] == 5 and db.queries[-1][1]["offset"] == 0
    go(db, "--pending-100", "--limit", "5", "--offset", "10", "--city", "Rosario")
    kw = db.queries[-1][1]
    assert (kw["limit"], kw["offset"], kw["city"]) == (5, 10, "Rosario")
    assert kw["flag"] == PENDING_ADMIN_FLAG


def test_locate_places_a_needs_location_suggestion_as_pending():
    sug = {"id": SID, "status": "needs_location", "name": "Pastas Lo de Flor", "address": "JC 23", "city": "Fray Bentos",
           "country": "Uruguay", "category": "shop", "notes": "pastas", "evidence_url": None}
    db = FakeDB(suggestion=sug)
    code, _ = go(db, "--locate", SID, "--lat", "-33.13", "--lng", "-58.29", "--address", "Eugenio Guevara 128", "--apply")
    assert code == 0
    c, = db.inserted
    assert c["geocode_method"] == "address_only" and c["address"] == "Eugenio Guevara 128" and c["source"] == "user"
    assert db.statuses == [(SID, "promoted", "new-place")]


def test_invalid_id_is_refused():
    assert go(FakeDB(), "--clear-warning", "nope")[0] == 2
