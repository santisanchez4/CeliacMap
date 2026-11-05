"""The needs_review queue gets the evidence tools: batches by department, how each quote says it, and the admin's four exits
(approve as options, 100 one by one with its evidence, discard with a reason, "revisado sin evidencia")."""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from agents.clients.supabase_client import SupabaseClient
from agents.evidence_finder import quote_terms, source_date
from agents.validator_agent import PENDING_ADMIN_FLAG, REVIEWED_NO_EVIDENCE_FLAG
from scripts import find_evidence
from scripts.review_queue import build_parser, run

PID = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10"
OTHER = "9a1c5d7e-2b44-4f60-8c31-5e0d7a9b1c22"
UPDATED = "2026-11-01T10:00:00+00:00"


# --- reading: region and the excluded flag, on the server -----------------------------------------------------------


def _chain():
    calls: list[tuple[str, tuple]] = []
    q = MagicMock()

    def record(name):
        def fn(*a, **k):
            calls.append((name, a))
            return q

        return fn

    for name in ("select", "eq", "ilike", "contains", "gte", "or_", "order", "limit", "range"):
        setattr(q, name, record(name))
    q.execute.return_value = MagicMock(data=[])
    return q, calls


def _client():
    client = SupabaseClient.__new__(SupabaseClient)
    client._db = MagicMock()
    q, calls = _chain()
    client._db.table.return_value = q
    return client, calls


def test_region_is_an_exact_match_on_the_canonical_department_name():
    client, calls = _client()
    client.fetch_places_for_admin("needs_review", region="Montevideo")
    assert ("eq", ("region", "Montevideo")) in calls


def test_the_excluded_flag_keeps_rows_whose_flags_are_null():
    # Measured live (2026-11-05): a bare `not.cs` drops the 292 rows with flags NULL; the `or` keeps them.
    client, calls = _client()
    client.fetch_places_for_admin("needs_review", exclude_flag=REVIEWED_NO_EVIDENCE_FLAG)
    expected = "flags.is.null,flags.not.cs." + json.dumps([REVIEWED_NO_EVIDENCE_FLAG], ensure_ascii=False)
    assert ("or_", (expected,)) in calls


def test_no_region_and_no_excluded_flag_change_nothing():
    client, calls = _client()
    client.fetch_places_for_admin("needs_review")
    assert not [c for c in calls if c[0] == "or_" or (c[0] == "eq" and c[1][0] == "region")]


def test_an_excluded_flag_that_would_break_the_or_syntax_is_refused():
    client, _ = _client()
    with pytest.raises(ValueError):
        client.fetch_places_for_admin("needs_review", exclude_flag="a, b")


def test_the_reviewed_flag_has_no_date_so_the_filter_is_exact():
    assert REVIEWED_NO_EVIDENCE_FLAG == "revisado sin evidencia"


# --- how each quote says it ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text, label", [
    ("Todo nuestro menú es sin TACC", "sin TACC"),
    ("Productos libres de T.A.C.C. y sin lactosa", "sin TACC"),
    ("#sintacc #celiacos", "sin TACC"),
    ("Productos 100% aptos para celíacos", "apto celíacos"),
    ("Apto celiacos, sin gluten", "apto celíacos"),
    ("Cafetería Gluten Free", "solo sin gluten"),
    ("Elaboración de comida sin gluten", "solo sin gluten"),
])
def test_quote_terms_names_the_strongest_wording(text, label):
    assert quote_terms(text) == label


def test_source_date_is_the_date_closest_to_the_quote():
    text = ("Photo by Pagana on March 04, 2026. ☕ Cafetería Gluten Free. Lo más rico. "
            + "x" * 400 + " Photo by Pagana on June 01, 2021.")
    assert source_date(text, "☕ Cafetería Gluten Free") == "2026-03-04"


@pytest.mark.parametrize("text", ["Publicado el 27 de marzo de 2026: todo sin TACC.", "2026-03-27 · todo sin TACC."])
def test_source_date_reads_spanish_and_iso_dates(text):
    assert source_date(text, "todo sin TACC") == "2026-03-27"


def test_source_date_is_none_when_no_date_is_near():
    assert source_date("Todo sin TACC, pedidos por WhatsApp.", "Todo sin TACC") is None
    assert source_date("Todo sin TACC." + " y" * 300 + " March 04, 2026", "Todo sin TACC.") is None


# --- find_evidence in needs_review mode ------------------------------------------------------------------------------


class ReadDB:
    def __init__(self):
        self.reads = []

    def fetch_places_for_admin(self, status=None, **kw):
        self.reads.append((status, kw))
        return [{"id": PID, "name": "Lugar", "city": "Montevideo", "country": "Uruguay", "status": "needs_review",
                 "flags": [], "updated_at": UPDATED, "safety_level": "options_available"}]

    def fetch_place_by_id(self, pid):
        return None


def _select(*argv):
    db = ReadDB()
    args = find_evidence.build_parser().parse_args(list(argv))
    places = find_evidence._select(db, args, lambda *_: None)
    return db, places


def test_find_evidence_reads_needs_review_by_region_without_the_reviewed():
    db, places = _select("--status", "needs_review", "--region", "Montevideo", "--limit", "5")
    status, kw = db.reads[0]
    assert status == "needs_review"
    assert kw["region"] == "Montevideo" and kw["exclude_flag"] == REVIEWED_NO_EVIDENCE_FLAG
    assert kw.get("flag") is None
    assert len(places) == 1


def test_include_reviewed_brings_them_back():
    db, _ = _select("--status", "needs_review", "--include-reviewed")
    assert db.reads[0][1]["exclude_flag"] is None


def test_the_default_queue_is_still_the_pending_100_one():
    db, _ = _select("--region", "Maldonado")
    status, kw = db.reads[0]
    assert status is None and kw["flag"] == PENDING_ADMIN_FLAG and kw["region"] == "Maldonado"


def test_the_report_says_which_queue_it_read(tmp_path):
    class NoSearch:
        def search(self, *a, **k):
            return []

    out = []
    args = find_evidence.build_parser().parse_args(["--status", "needs_review", "--no-llm", "--no-freeze", "--out-dir", str(tmp_path)])
    assert find_evidence.run(ReadDB(), NoSearch(), None, args, out=out.append, fetch_text=lambda u: "") == 0
    data = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert data["meta"]["queue"] == "needs_review"


# --- review_queue: the four exits ------------------------------------------------------------------------------------


class DB:
    def __init__(self, **place):
        self.place = {"id": PID, "name": "Lugar", "status": "needs_review", "safety_level": "options_available",
                      "validation_confidence": 0.6, "validation_notes": "Texto del Validator.", "flags": ["otro"],
                      "updated_at": UPDATED, "city": "Montevideo", "country": "Uruguay", **place}
        self.other = {"id": OTHER, "name": "Lugar (original)", "status": "approved"}
        self.updates, self.evidence, self.queries, self.logs = [], [], [], []

    def fetch_place_by_id(self, pid):
        return {PID: self.place, OTHER: self.other}.get(pid)

    def update_place(self, pid, patch):
        self.updates.append((pid, patch))

    def add_place_evidence(self, pid, source, text, url):
        self.evidence.append((pid, source, text, url))

    def fetch_places_for_admin(self, status=None, **kw):
        self.queries.append((status, kw))
        return []

    def fetch_suggestions_by_status(self, status, limit=50):
        return []

    def insert_agent_log(self, *a, **k):
        self.logs.append(a)


def go(db, *argv):
    lines = []
    code = run(db, build_parser().parse_args(list(argv)), out=lambda t="": lines.append(str(t)))
    return code, "\n".join(lines)


def _report(tmp_path, proposal, queue="needs_review", **entry):
    row = {"place_id": PID, "name": "Lugar", "city": "Montevideo", "country": "Uruguay", "proposal": proposal,
           "updated_at": UPDATED, "reasons": [], "verify_in_source": False,
           "citations": [{"text": "Tenemos opciones sin TACC", "url": "https://lugar.uy", "source_kind": "propia",
                          "verificacion": "verificada", "has_signal": False, "alcance": "opciones", "contradice": False,
                          "multi_negocio": False}], **entry}
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"meta": {"queue": queue}, "places": [row]}), encoding="utf-8")
    return str(path)


def test_the_needs_review_list_filters_by_region_and_skips_the_reviewed():
    db = DB()
    go(db, "--needs-review", "--region", "Montevideo")
    status, kw = db.queries[0]
    assert status == "needs_review" and kw["region"] == "Montevideo" and kw["exclude_flag"] == REVIEWED_NO_EVIDENCE_FLAG


def test_include_reviewed_shows_them_in_the_list():
    db = DB()
    go(db, "--needs-review", "--include-reviewed")
    assert db.queries[0][1]["exclude_flag"] is None


def test_a_needs_review_report_approves_its_options_with_the_quotes(tmp_path):
    db = DB()
    code, text = go(db, "--accept-proposals", PID, "--report", _report(tmp_path, "options"), "--apply")
    assert code == 0
    patch = db.updates[-1][1]
    assert patch["status"] == "approved" and patch["safety_level"] == "options_available"
    assert patch["validation_notes"].startswith("APROBACIÓN MANUAL (")
    assert [e[1] for e in db.evidence] == ["web"]
    assert "validation_confidence" not in patch and "verified" not in patch


def test_a_needs_review_report_never_approves_a_100_in_bulk(tmp_path):
    db = DB()
    path = _report(tmp_path, "100", citations=[{"text": "Todo es sin TACC", "url": "https://lugar.uy", "source_kind": "propia",
                                                "verificacion": "verificada", "has_signal": True, "alcance": "establecimiento",
                                                "contradice": False, "multi_negocio": False}])
    code, text = go(db, "--accept-proposals", PID, "--report", path, "--apply")
    assert code == 1 and not db.updates and not db.evidence
    assert "--approve" in text and "--evidence-from" in text


def test_a_pending_100_report_still_refuses_a_needs_review_place(tmp_path):
    db = DB()
    code, text = go(db, "--accept-proposals", PID, "--report", _report(tmp_path, "options", queue="pending_100"), "--apply")
    assert code == 1 and not db.updates
    assert "ya no está aprobado" in text


def test_a_needs_review_report_refuses_a_place_that_left_needs_review(tmp_path):
    db = DB(status="approved")
    code, text = go(db, "--accept-proposals", PID, "--report", _report(tmp_path, "options"), "--apply")
    assert code == 1 and not db.updates
    assert "ya no está en needs_review" in text


def test_approve_100_with_evidence_from_a_report_saves_the_quotes_and_an_admin_row(tmp_path):
    db = DB()
    path = _report(tmp_path, "100", citations=[{"text": "Todo es sin TACC", "url": "https://lugar.uy", "source_kind": "propia",
                                                "verificacion": "verificada", "has_signal": True, "alcance": "establecimiento",
                                                "contradice": False, "multi_negocio": False}])
    code, _ = go(db, "--approve", PID, "--level", "100", "--note", "cocina exclusiva confirmada", "--evidence-from", path, "--apply")
    assert code == 0
    assert db.updates[-1][1]["safety_level"] == "gluten_free_100"
    sources = [e[1] for e in db.evidence]
    assert sources == ["web", "admin"]
    admin = db.evidence[-1][2]
    assert "cocina exclusiva confirmada" in admin and "«Todo es sin TACC»" in admin


def test_approve_with_an_admin_quote_saves_one_admin_row():
    db = DB()
    code, _ = go(db, "--approve", PID, "--level", "100", "--note", "lo conozco", "--evidence", "Todo es sin gluten",
                 "--evidence-url", "https://instagram.com/lugar", "--apply")
    assert code == 0
    today = date.today().isoformat()
    assert db.evidence == [(PID, "admin", f"Revisión manual ({today}, review_queue): lo conozco. Cita: «Todo es sin gluten»",
                            "https://instagram.com/lugar")]


def test_the_admin_evidence_is_written_before_the_decision_and_a_failure_stops_it():
    db = DB()

    def boom(*a):
        raise RuntimeError("down")

    db.add_place_evidence = boom
    code, text = go(db, "--approve", PID, "--level", "options", "--note", "x", "--evidence", "cita", "--apply")
    assert code == 1 and not db.updates
    assert "No se pudo guardar la evidencia" in text


def test_approve_without_evidence_still_works_but_reminds_the_rule():
    db = DB()
    code, text = go(db, "--approve", PID, "--level", "options", "--note", "x", "--apply")
    assert code == 0 and db.updates and not db.evidence
    assert "place_evidence" in text


def test_admin_evidence_with_health_data_is_refused():
    db = DB()
    code, text = go(db, "--approve", PID, "--level", "100", "--note", "x", "--evidence", "la dueña es celíaca", "--apply")
    assert code == 2 and not db.updates and not db.evidence


def test_approve_and_discard_drop_the_reviewed_flag():
    db = DB(flags=[REVIEWED_NO_EVIDENCE_FLAG, "otro"])
    go(db, "--approve", PID, "--level", "options", "--note", "x", "--apply")
    assert db.updates[-1][1]["flags"] == ["otro"]
    db = DB(flags=[REVIEWED_NO_EVIDENCE_FLAG, PENDING_ADMIN_FLAG])
    go(db, "--discard", PID, "--reason", "cerrado", "--note", "x", "--apply")
    assert db.updates[-1][1]["flags"] == []


@pytest.mark.parametrize("reason, words", [
    ("cerrado", "Cerrado"), ("no_es_comercio", "No es un comercio"), ("evidencia_contraria", "Evidencia contraria"),
])
def test_discard_needs_a_concrete_reason_and_says_it(reason, words):
    db = DB()
    code, _ = go(db, "--discard", PID, "--reason", reason, "--note", "según su Facebook", "--apply")
    assert code == 0
    notes = db.updates[-1][1]["validation_notes"]
    assert notes.startswith("DESCARTE MANUAL (") and f"review_queue): {words}: según su Facebook." in notes


def test_discard_without_a_reason_is_refused():
    db = DB()
    code, text = go(db, "--discard", PID, "--note", "cerró", "--apply")
    assert code == 2 and not db.updates
    assert "--reason" in text


def test_a_duplicate_names_the_place_that_stays():
    db = DB()
    code, _ = go(db, "--discard", PID, "--reason", "duplicado", "--duplicate-of", OTHER, "--note", "misma ficha", "--apply")
    assert code == 0
    assert f"Duplicado de {OTHER}: misma ficha." in db.updates[-1][1]["validation_notes"]


@pytest.mark.parametrize("extra", [[], ["--duplicate-of", "00000000-0000-4000-8000-000000000000"], ["--duplicate-of", PID]])
def test_a_duplicate_needs_another_place_that_exists(extra):
    db = DB()
    code, _ = go(db, "--discard", PID, "--reason", "duplicado", "--note", "x", *extra, "--apply")
    assert code != 0 and not db.updates


def test_duplicate_of_only_goes_with_the_duplicate_reason():
    db = DB()
    code, _ = go(db, "--discard", PID, "--reason", "cerrado", "--duplicate-of", OTHER, "--note", "x", "--apply")
    assert code == 2 and not db.updates


def test_mark_reviewed_keeps_the_place_in_needs_review_with_the_flag_and_the_date():
    db = DB()
    code, text = go(db, "--mark-reviewed", PID, "--apply")
    assert code == 0
    pid, patch = db.updates[-1]
    assert set(patch) == {"flags", "validation_notes"}
    assert patch["flags"] == ["otro", REVIEWED_NO_EVIDENCE_FLAG]
    assert patch["validation_notes"].startswith("REVISIÓN SIN EVIDENCIA (")
    assert patch["validation_notes"].endswith("Texto del Validator.")


def test_mark_reviewed_is_a_dry_run_by_default_and_skips_what_it_must_not_touch():
    db = DB()
    code, text = go(db, "--mark-reviewed", PID)
    assert code == 0 and not db.updates and "DRY RUN" in text
    for place in (DB(status="approved"), DB(flags=[REVIEWED_NO_EVIDENCE_FLAG])):
        code, _ = go(place, "--mark-reviewed", PID, "--apply")
        assert code == 1 and not place.updates


def test_the_review_line_does_not_count_as_a_manual_decision():
    from agents.manual_overrides import manual_override_marker
    assert manual_override_marker("REVISIÓN SIN EVIDENCIA (2026-11-05, review_queue): sin evidencia pública.") is None
