"""review_queue --proposals / --accept-proposals: the admin confirms evidence proposals in bulk, never silently.

Dry run unless --apply. Only the admin's command writes (place_evidence rows with source 'web', the APROBACIÓN MANUAL header,
the queue flag removed); it refuses whatever changed, was already decided, or has nothing to cite.
"""
from __future__ import annotations

import json

from agents.validator_agent import PENDING_ADMIN_FLAG
from scripts.review_queue import build_parser, run

P1 = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10"
P2 = "9a1c5d7e-2b44-4f60-8c31-5e0d7a9b1c22"
P3 = "5d4e3c2b-1a09-4f8e-9d7c-6b5a4f3e2d1c"
TS = "2026-09-20T10:00:00+00:00"

CITE_OWN = {"text": "Somos 100% sin gluten desde 2015.", "url": "https://tiempolibre.com.ar", "source_kind": "propia",
            "matched_by": "own_url", "has_signal": True, "alcance": "establecimiento", "contradice": False,
            "verificacion": "verificada"}
CITE_BLOG = {"text": "Todo es sin gluten, cocina exclusiva.", "url": "https://blog.example/guia", "source_kind": "tercero",
             "matched_by": "name_and_city", "has_signal": True, "alcance": "establecimiento", "contradice": False,
             "verificacion": "solo_snippet"}
CITE_OPT = {"text": "Tienen opciones sin TACC para celíacos.", "url": "https://blog.example/opciones", "source_kind": "tercero",
            "matched_by": "name_and_city", "has_signal": False, "alcance": "opciones", "contradice": False,
            "verificacion": "verificada"}
CITE_INSTA = {"text": "100% libre de gluten, 100% libre de gluten de San Nicolás.", "url": "https://www.instagram.com/apto.libredegluten",
              "source_kind": "tercero", "matched_by": "name_and_city", "has_signal": True, "alcance": "establecimiento",
              "contradice": False, "verificacion": "no_verificable"}


def result(pid, name, proposal, citations, link="website", updated_at=TS):
    return {"place_id": pid, "name": name, "city": "Rosario", "country": "Argentina", "category": "cafe", "website": None,
            "social_url": None, "updated_at": updated_at, "safety_level": "gluten_free_100", "link_kind": link,
            "proposal": proposal, "reasons": ["r"], "citations": citations, "stats": {"searches": 2}}


def write_report(tmp_path, rows):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"meta": {"created_at": TS}, "places": rows}, ensure_ascii=False), encoding="utf-8")
    return str(path)


class DB:
    def __init__(self, places=None, evidence_error=False):
        self.places = places if places is not None else {
            P1: self._place(P1, "Tiempo Libre"), P2: self._place(P2, "Otro Local"), P3: self._place(P3, "Tercer Local"),
        }
        self.evidence_error = evidence_error
        self.updates, self.evidence, self.logs = [], [], []

    @staticmethod
    def _place(pid, name, **kw):
        base = {"id": pid, "name": name, "status": "approved", "safety_level": "gluten_free_100", "updated_at": TS,
                "flags": [PENDING_ADMIN_FLAG, "sin ficha"], "validation_confidence": 0.9, "validation_notes": "Solo Places.",
                "city": "Rosario", "country": "Argentina", "lat": -32.9, "lng": -60.6}
        base.update(kw)
        return base

    def fetch_place_by_id(self, pid):
        return self.places.get(pid)

    def update_place(self, pid, patch):
        self.updates.append((pid, patch))

    def add_place_evidence(self, pid, source, text=None, url=None):
        if self.evidence_error:
            raise RuntimeError("insert failed")
        self.evidence.append((pid, source, text, url))

    def insert_agent_log(self, agent, action, result=None, status="success", place_id=None):
        self.logs.append((agent, action, result, status))

    def fetch_place_evidence(self, pid):
        return []


def go(db, *argv):
    lines = []
    code = run(db, build_parser().parse_args(list(argv)), out=lambda t="": lines.append(str(t)))
    return code, "\n".join(lines)


ROWS = [
    result(P1, "Tiempo Libre", "100", [CITE_BLOG, CITE_OWN]),
    result(P2, "Otro Local", "options", [CITE_OPT]),
    result(P3, "Tercer Local", "insuficiente", [], link="nada"),
]


# --- listing ---------------------------------------------------------------------------------------------------------------

def test_proposals_lists_the_counts_the_citations_with_their_urls_and_the_ids_to_copy(tmp_path):
    code, text = go(DB(), "--proposals", write_report(tmp_path, ROWS))
    assert code == 0
    assert "100: 1" in text and "options: 1" in text and "insuficiente: 1" in text
    assert "«Somos 100% sin gluten desde 2015.»" in text and "https://tiempolibre.com.ar" in text
    assert "propia" in text and "señal de exclusividad" in text
    assert f"IDs 100: {P1}" in text and f"IDs options: {P2}" in text


def test_proposals_only_filters_one_kind_and_writes_nothing(tmp_path):
    db = DB()
    code, text = go(db, "--proposals", write_report(tmp_path, ROWS), "--only", "options")
    assert code == 0 and "Otro Local" in text and "Tiempo Libre" not in text and "Tercer Local" not in text
    assert db.updates == [] and db.evidence == [] and db.logs == []


def test_a_missing_or_malformed_report_is_a_clear_error(tmp_path):
    assert go(DB(), "--proposals", str(tmp_path / "nope.json"))[0] == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    code, text = go(DB(), "--accept-proposals", P1, "--report", str(bad))
    assert code == 2 and "reporte" in text.lower()


# --- accepting: dry run first ----------------------------------------------------------------------------------------------

def test_accept_is_a_dry_run_by_default_and_shows_the_note_the_level_and_the_evidence(tmp_path):
    db = DB()
    code, text = go(db, "--accept-proposals", P1, P2, "--report", write_report(tmp_path, ROWS))
    assert code == 0 and "DRY RUN" in text
    assert db.updates == [] and db.evidence == [] and db.logs == []
    assert "Tiempo Libre" in text and "https://tiempolibre.com.ar" in text
    # An options acceptance changes what people see, and the dry run says so.
    assert "Espacio 100% sin gluten" in text and "Tiene opciones sin TACC" in text
    assert "evidencia a guardar: 2 fila(s)" in text and "evidencia a guardar: 1 fila(s)" in text


def test_accept_100_with_apply_writes_web_evidence_the_manual_header_and_removes_only_the_queue_flag(tmp_path):
    db = DB()
    code, text = go(db, "--accept-proposals", P1, "--report", write_report(tmp_path, ROWS), "--apply")
    assert code == 0
    assert [(e[1], e[3]) for e in db.evidence] == [("web", "https://tiempolibre.com.ar"), ("web", "https://blog.example/guia")]
    (pid, patch), = db.updates
    assert pid == P1 and patch["status"] == "approved" and patch["safety_level"] == "gluten_free_100"
    assert patch["flags"] == ["sin ficha"]
    assert patch["validation_notes"].startswith("APROBACIÓN MANUAL (")
    assert "«Somos 100% sin gluten desde 2015.»" in patch["validation_notes"] and "https://tiempolibre.com.ar" in patch["validation_notes"]
    assert "Solo Places." in patch["validation_notes"]  # what the Validator had said stays below the header
    assert "verified" not in patch and "validation_confidence" not in patch
    (agent, action, log, status), = db.logs
    assert (agent, action, status) == ("validator", "accept_evidence_proposals", "success") and log["accepted"] == [P1]


def test_accept_options_with_apply_lowers_the_public_level(tmp_path):
    db = DB()
    code, _ = go(db, "--accept-proposals", P2, "--report", write_report(tmp_path, ROWS), "--apply")
    assert code == 0
    (_, patch), = db.updates
    assert patch["safety_level"] == "options_available" and PENDING_ADMIN_FLAG not in patch["flags"]
    assert "opciones sin TACC" in patch["validation_notes"]


def test_the_quote_in_the_public_note_is_at_most_160_characters(tmp_path):
    long_cite = dict(CITE_OWN, text="Nuestra cocina es " + "exclusiva y dedicada " * 20 + "sin gluten.")
    db = DB()
    go(db, "--accept-proposals", P1, "--report", write_report(tmp_path, [result(P1, "Tiempo Libre", "100", [long_cite])]), "--apply")
    quoted = db.updates[0][1]["validation_notes"].split("«", 1)[1].split("»", 1)[0]
    assert len(quoted) <= 160


# --- accepting: what it refuses ---------------------------------------------------------------------------------------------

def refused(db, tmp_path, rows, ids, reason):
    code, text = go(db, "--accept-proposals", *ids, "--report", write_report(tmp_path, rows), "--apply")
    assert code == 1, text
    assert reason in text, text
    assert db.updates == [] and db.evidence == [] and db.logs == []


def test_it_refuses_an_insuficiente_proposal(tmp_path):
    refused(DB(), tmp_path, ROWS, [P3], "insuficiente")


def test_it_refuses_an_id_that_is_not_in_the_report(tmp_path):
    refused(DB(), tmp_path, ROWS[:1], [P2], "no está en el reporte")


def test_it_refuses_a_place_that_already_has_a_manual_decision(tmp_path):
    db = DB()
    db.places[P1]["validation_notes"] = "OVERRIDE MANUAL (2026-09-01): conozco el local."
    refused(db, tmp_path, ROWS, [P1], "decisión manual")


def test_it_refuses_a_place_that_left_the_queue_or_is_no_longer_approved(tmp_path):
    db = DB()
    db.places[P1]["flags"] = ["sin ficha"]
    refused(db, tmp_path, ROWS, [P1], "ya no está en la cola")
    db = DB()
    db.places[P1]["status"] = "discarded"
    refused(db, tmp_path, ROWS, [P1], "ya no está aprobado")


def test_it_refuses_a_place_that_changed_after_the_report_was_made(tmp_path):
    db = DB()
    db.places[P1]["updated_at"] = "2026-09-25T09:00:00+00:00"
    refused(db, tmp_path, ROWS, [P1], "cambió después del reporte")


def test_it_refuses_a_place_that_does_not_exist_and_an_invalid_id(tmp_path):
    refused(DB(places={}), tmp_path, ROWS, [P1], "No existe")
    code, text = go(DB(), "--accept-proposals", "no-es-uuid", "--report", write_report(tmp_path, ROWS))
    assert code == 2 and "uuid" in text.lower()


def test_it_refuses_a_note_that_would_carry_health_data(tmp_path):
    sick = dict(CITE_OWN, text="La dueña es celíaca y todo es sin gluten.")
    refused(DB(), tmp_path, [result(P1, "Tiempo Libre", "100", [sick])], [P1], "datos de salud")


def test_it_needs_the_report(tmp_path):
    code, text = go(DB(), "--accept-proposals", P1)
    assert code == 2 and "--report" in text


def test_when_the_evidence_cannot_be_saved_the_place_is_not_approved(tmp_path):
    db = DB(evidence_error=True)
    code, text = go(db, "--accept-proposals", P1, "--report", write_report(tmp_path, ROWS), "--apply")
    assert code == 1 and db.updates == [] and "evidencia" in text.lower()


# --- "100 · verificar en la fuente" -------------------------------------------------------------------------------------------------

P4 = "7c6b5a49-3827-4165-9e0d-1f2a3b4c5d6e"
UNVERIFIED = [result(P1, "Tiempo Libre", "100", [CITE_INSTA]), result(P4, "Apto Libre", "100", [CITE_BLOG])]


def test_a_100_that_needs_the_source_check_is_refused_in_bulk_and_says_to_open_the_link(tmp_path):
    db = DB()
    code, text = go(db, "--accept-proposals", P1, "--report", write_report(tmp_path, UNVERIFIED), "--apply")
    assert code == 1 and "verificar en la fuente" in text and "--verified-source" in text
    assert db.updates == [] and db.evidence == [] and db.logs == []


def test_it_is_accepted_alone_with_verified_source_and_the_public_note_does_not_quote_the_snippet(tmp_path):
    db = DB()
    code, _ = go(db, "--accept-proposals", P1, "--report", write_report(tmp_path, UNVERIFIED), "--verified-source", "--apply")
    assert code == 0
    (pid, patch), = db.updates
    notes = patch["validation_notes"]
    assert pid == P1 and patch["safety_level"] == "gluten_free_100"
    assert "evidencia en redes del local para 100% sin gluten (https://www.instagram.com/apto.libredegluten)" in notes
    assert "libre de gluten de San Nicolás" not in notes and "«" not in notes
    (_, source, text, url), = db.evidence
    assert source == "web" and text.startswith("(sin verificar en la página) ") and url == "https://www.instagram.com/apto.libredegluten"


def test_the_dry_run_of_a_source_check_place_tells_the_admin_to_open_the_link(tmp_path):
    db = DB()
    code, text = go(db, "--accept-proposals", P1, "--report", write_report(tmp_path, UNVERIFIED), "--verified-source")
    assert code == 0 and "DRY RUN" in text and "abriste" in text
    assert db.updates == [] and db.evidence == []


def test_verified_source_is_for_one_place_at_a_time(tmp_path):
    db = DB()
    code, text = go(db, "--accept-proposals", P1, P4, "--report", write_report(tmp_path, UNVERIFIED), "--verified-source", "--apply")
    assert code == 2 and "de a uno" in text
    assert db.updates == [] and db.evidence == []


def test_a_bulk_command_accepts_the_verified_places_and_refuses_only_the_ones_that_need_the_link(tmp_path):
    db = DB()
    db.places[P4] = DB._place(P4, "Apto Libre")
    rows = [ROWS[0], ROWS[1], UNVERIFIED[1]]
    code, text = go(db, "--accept-proposals", P1, P2, P4, "--report", write_report(tmp_path, rows), "--apply")
    assert code == 1
    assert [u[0] for u in db.updates] == [P1, P2]
    assert db.logs[0][2]["accepted"] == [P1, P2] and db.logs[0][2]["refused"] == [P4]


def test_the_flag_changes_nothing_for_a_place_that_needs_no_source_check(tmp_path):
    db = DB()
    code, _ = go(db, "--accept-proposals", P1, "--report", write_report(tmp_path, ROWS), "--verified-source", "--apply")
    assert code == 0 and "«Somos 100% sin gluten desde 2015.»" in db.updates[0][1]["validation_notes"]


def test_the_listing_shows_the_labels_the_models_veto_the_possible_100_and_the_ids_split_by_how_they_are_accepted(tmp_path):
    veto = {"tipo": "alcance", "cita": 1, "texto": "Nuestras tortas son 100% sin gluten.", "url": "https://a.example/1",
            "motivo_modelo": "Habla solo de las tortas."}
    possible = dict(result(P3, "Tercer Local", "options", [CITE_OPT]), possible_100=True,
                    possible_100_quote={"text": "Exclusivamente para celíacos.", "url": "https://f.example/2"})
    vetoed = dict(result(P2, "Otro Local", "options", [CITE_OPT]), vetoes=[veto])
    rows = [ROWS[0], UNVERIFIED[1], vetoed, possible]
    code, text = go(DB(), "--proposals", write_report(tmp_path, rows))
    assert code == 0
    assert "verificada en la página" in text and "solo snippet" in text
    assert "veto del modelo" in text and "Habla solo de las tortas." in text and "cita 1" in text
    assert "posible 100" in text and "Exclusivamente para celíacos." in text
    assert f"IDs 100: {P1}" in text and f"IDs 100 · verificar en la fuente" in text and P4 in text.split("IDs 100 · verificar en la fuente", 1)[1]
    assert "100 · verificar en la fuente: 1" in text


def test_one_refusal_does_not_block_the_others_but_the_exit_code_says_so(tmp_path):
    db = DB()
    code, text = go(db, "--accept-proposals", P3, P1, "--report", write_report(tmp_path, ROWS), "--apply")
    assert code == 1
    assert [u[0] for u in db.updates] == [P1]
    assert db.logs[0][2]["accepted"] == [P1] and db.logs[0][2]["refused"] == [P3]
