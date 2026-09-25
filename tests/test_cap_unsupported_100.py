"""Step 2b: already-approved 100% places without explicit evidence go to "options" + admin flag."""
from agents.validator_agent import PENDING_ADMIN_FLAG
from scripts.cap_unsupported_100 import build_parser, run


class FakeDB:
    def __init__(self, places, reviews=None, evidence=None):
        self.places, self.reviews, self.evidence, self.updates = places, reviews or {}, evidence or {}, []
        self.logs = []

    def insert_agent_log(self, agent, action, result=None, status="success", place_id=None):
        self.logs.append((agent, action, result, status, place_id))

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


# --- --flag-only: mark the places for the admin queue WITHOUT changing what the map shows ------------


def test_flag_only_changes_nothing_but_the_flags_of_the_unsupported_places():
    db = make()
    run(db, apply=True, flag_only=True, out=lambda *_: None)
    changed = {pid: patch for pid, patch in db.updates}
    assert set(changed) == {"a", "d"}
    for patch in changed.values():
        assert set(patch) == {"flags"}  # no safety_level, status, confidence, verified or validation_notes
        assert PENDING_ADMIN_FLAG in patch["flags"]


def test_flag_only_keeps_the_flags_the_place_already_had():
    db = make()
    run(db, apply=True, flag_only=True, out=lambda *_: None)
    changed = {pid: patch for pid, patch in db.updates}
    assert changed["d"]["flags"] == ["otra", PENDING_ADMIN_FLAG]
    assert changed["a"]["flags"] == [PENDING_ADMIN_FLAG]


def test_flag_only_does_not_duplicate_the_flag_nor_rewrite_a_place_that_already_has_it():
    places = [
        {"id": "a", "name": "ya marcado", "validation_notes": "x", "flags": [PENDING_ADMIN_FLAG]},
        {"id": "b", "name": "ya marcado y otra", "validation_notes": "x", "flags": ["otra", PENDING_ADMIN_FLAG]},
        {"id": "c", "name": "sin marcar", "validation_notes": "x", "flags": []},
    ]
    db, lines = FakeDB(places), []
    run(db, apply=True, flag_only=True, out=lines.append)
    assert [pid for pid, _ in db.updates] == ["c"]
    assert db.updates[0][1]["flags"].count(PENDING_ADMIN_FLAG) == 1
    assert "2 ya estaban marcados" in "\n".join(lines)


def test_flag_only_never_touches_a_place_with_a_manual_marker():
    db = make()
    run(db, apply=True, flag_only=True, out=lambda *_: None)
    assert "b" not in {pid for pid, _ in db.updates}  # "CORRECCIÓN MANUAL": a human call, not ours to flag


def test_flag_only_dry_run_writes_nothing_and_says_the_level_stays():
    db, lines = make(), []
    run(db, apply=False, flag_only=True, out=lines.append)
    assert db.updates == [] and db.logs == []
    text = "\n".join(lines)
    assert "DRY RUN" in text and "el nivel no cambia" in text and "2 se marcarían" in text


def test_flag_only_apply_leaves_one_agent_log_row_with_the_counts():
    db = make()
    run(db, apply=True, flag_only=True, out=lambda *_: None)
    (agent, action, result, status, place_id), = db.logs
    assert (agent, action, status, place_id) == ("validator", "flag_unsupported_100", "success", None)
    assert result == {"approved_100": 4, "manual": 1, "explicit_evidence": 1, "candidates": 2, "flagged": 2, "already_flagged": 0}


def test_the_default_mode_still_lowers_the_level_and_the_flag_is_opt_in():
    assert build_parser().parse_args([]).flag_only is False
    args = build_parser().parse_args(["--flag-only", "--apply"])
    assert args.flag_only is True and args.apply is True
    db = make()
    run(db, apply=True, out=lambda *_: None)  # no flag_only: the original behaviour
    assert {patch["safety_level"] for _, patch in db.updates} == {"celiac_friendly"}
