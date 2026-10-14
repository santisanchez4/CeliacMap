"""scripts/import_imm_source.py: the IM Montevideo layer goes through the Validator; the dry run never writes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.validator_agent import ValidatorAgent
from scripts import import_imm_source as imm

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / imm.DEFAULT_CSV
PLAN = ROOT / imm.DEFAULT_PLAN
PLACE_ID = "00000000-0000-4000-8000-000000000001"


def csv_row(**over):
    row = {"nombre": "RAMONA", "direccion": "SAN JOSE Nº: 900", "rubro": "Exp-elab",
           "giros": "Libre de gluten- Confiteria- Panaderia- Restaurante", "habilitado_desde": "18/02/2020",
           "habilitado_hasta": "18/02/2025", "vigente_hoy": "vencida", "lat": "-34.907375", "lon": "-56.197095"}
    return {**row, **over}


class FakeDB:
    def __init__(self, place=None, exists=False):
        self.place, self.exists, self.writes = place, exists, []

    def place_exists_by_external_id(self, external_id):
        return self.exists

    def fetch_place_by_id(self, place_id):
        return dict(self.place) if self.place else None

    def fetch_place_evidence(self, place_id, limit=5):
        return []

    def fetch_reviews_for_place(self, place_id, limit=5):
        return []

    def fetch_community_claims(self, place_id, limit=5):
        return []

    def insert_place_candidate(self, candidate):
        self.writes.append(("insert_place_candidate", candidate))
        return {**candidate, "id": PLACE_ID, "status": "pending"}

    def __getattr__(self, name):  # every other call is a write
        def record(*args, **kwargs):
            self.writes.append((name, args, kwargs))
        return record


class FakePlaces:
    def place_details_with_reviews(self, place_id):
        return {"result": {"website": "https://ejemplo.uy/", "reviews": [{"text": "Todo sin gluten, muy rico", "rating": 5}]}}


class FakeLLM:
    def __init__(self, verdict):
        self.verdict, self.prompts = verdict, []

    def complete_json(self, system, user, model=None, **kwargs):
        self.prompts.append(user)
        return dict(self.verdict)


def validator(db, **verdict):
    base = {"verdict": "approved", "confidence_score": 0.9, "category": "cafe", "safety_level": "gluten_free_100",
            "reasoning": "Evidencia explícita.", "flags": [], "recommendation": "Publicar."}
    llm = FakeLLM({**base, **verdict})
    return ValidatorAgent(db, llm), llm


def item(method="find_place"):
    return {"resolved": {"place_id": "ChIJ-test", "lat": -34.9, "lng": -56.19, "formatted_address": "San José 900, Montevideo",
                         "name": "Café Ramona", "city": "Montevideo", "country": "Uruguay", "geocode_method": method,
                         "business_status": "OPERATIONAL", "dist_m": 5}}


def test_street_address_and_business_name():
    assert imm.street_address(csv_row(direccion="26 DE MARZO Nº: 3265 Apto: 904")) == "26 De Marzo 3265"
    assert imm.street_address(csv_row(direccion="HIPOLITO YRIGOYEN Nº: 1728 BIS")) == "Hipolito Yrigoyen 1728 Bis"
    assert imm.business_name(csv_row(nombre="(sin nombre - empresa: JOVECA S.R.L.)")) == "JOVECA S.R.L."
    assert imm.business_name(csv_row()) == "RAMONA"


def test_licence_text_carries_the_source_and_never_reads_as_exclusivity():
    rows = imm.load_rows(str(CSV))
    assert len(rows) == 35
    for row in rows.values():
        text = imm.im_evidence_text(row, "2026-10-13")  # raises if it looked like an exclusivity claim
        assert imm.SOURCE_LABEL in text and "capturada 2026-10-13" in text and row["habilitado_hasta"] in text
        assert not ValidatorAgent.has_exclusive_signal([text])
    expired = imm.im_evidence_text(csv_row(), "2026-10-13", other_address=True)
    assert "figura vencida en la fuente" in expired and "otra dirección" in expired
    assert "(vigente)" in imm.im_evidence_text(csv_row(vigente_hoy="si"), "2026-10-13")


def test_evidence_rows_cap_exclude_and_put_the_licence_last():
    found = {"citations": [{"text": f"cita {i}", "url": f"https://sitio.uy/{i}"} for i in range(6)]
             + [{"text": "otro negocio", "url": "https://www.instagram.com/reel/x"}]}
    rows = imm.evidence_rows(csv_row(), "2026-10-13", found)
    assert len(rows) == imm.MAX_CITATIONS + 1 and rows[-1]["source"] == "admin" and rows[0]["source"] == "web"

    entry = {"exclude": ["instagram.com", "cita 0"], "extra_quotes": [{"text": "frase propia", "url": "https://sitio.uy/"}]}
    rows = imm.evidence_rows(csv_row(), "2026-10-13", {"citations": found["citations"][:2] + found["citations"][-1:]}, entry)
    assert [r["text"] for r in rows[:-1]] == ["frase propia", "cita 1"]


def test_extra_quotes_must_be_literal_on_their_page():
    plan = [{"n": 34, "extra_quotes": [{"text": "no contiene gluten ni T.A.C.C.", "url": "u"}]}]
    assert imm.verify_extra_quotes(plan, lambda url: "Es sin azúcar y no contiene gluten ni T.A.C.C.!") == []
    assert len(imm.verify_extra_quotes(plan, lambda url: "otra cosa")) == 1


def test_insert_dry_run_validates_without_writing():
    db = FakeDB()
    agent, llm = validator(db)
    result = imm.insert_new(db, FakePlaces(), agent, {"n": 31, "action": "insert"}, csv_row(), item(), "2026-10-13", apply=False)
    assert db.writes == []
    assert result["outcome"] == "validado" and result["candidate"]["source"] == "manual"
    # the licence alone has no exclusivity phrase, but the review does: the level survives Tope C only because of it
    assert "evidencia_descubrimiento" in llm.prompts[0] and imm.SOURCE_LABEL in llm.prompts[0]


def test_licence_alone_never_gives_a_100():
    db = FakeDB()
    agent, _ = validator(db)
    places = FakePlaces()
    places.place_details_with_reviews = lambda place_id: {"result": {}}
    result = imm.insert_new(db, places, agent, {"n": 31, "action": "insert"}, csv_row(), item(), "2026-10-13", apply=False)
    assert result["verdict"]["safety_level"] == "celiac_friendly"
    assert "100% pendiente de confirmación del administrador" in result["verdict"]["flags"]


def test_insert_apply_goes_through_pending_and_logs_the_source():
    db = FakeDB()
    agent, _ = validator(db)
    result = imm.insert_new(db, FakePlaces(), agent, {"n": 31, "action": "insert", "name": "Café Ramona - Centro"}, csv_row(), item(),
                            "2026-10-13", apply=True)
    names = [w[0] for w in db.writes]
    assert names[0] == "insert_place_candidate" and db.writes[0][1]["name"] == "Café Ramona - Centro"
    assert "status" not in db.writes[0][1]  # insert_place_candidate forces 'pending'
    assert names.count("add_place_evidence") == 1 and "update_place_validation" in names
    log = next(w for w in db.writes if w[0] == "insert_agent_log")
    assert log[1][2]["import_source"] == imm.SOURCE_LABEL and log[1][2]["im_habilitado_hasta"] == "18/02/2025"
    assert result["place_id"] == PLACE_ID


def test_insert_skips_a_place_that_already_exists():
    db = FakeDB(exists=True)
    agent, llm = validator(db)
    result = imm.insert_new(db, FakePlaces(), agent, {"n": 31, "action": "insert"}, csv_row(), item(), "2026-10-13", apply=True)
    assert result["outcome"] == "duplicado" and db.writes == [] and llm.prompts == []


def test_reevaluate_keeps_the_row_out_of_pending_and_respects_manual_decisions():
    place = {"id": PLACE_ID, "name": "Me Gusta", "status": "discarded", "validation_confidence": 0.75, "source": "google_places",
             "safety_level": "options_available", "category": "restaurant", "validation_notes": "Sin señales."}
    db = FakeDB(place)
    agent, _ = validator(db, verdict="needs_review", confidence_score=0.7, safety_level="celiac_friendly")
    entry = {"n": 9, "action": "reevaluate", "place_id": PLACE_ID}
    assert imm.reevaluate(db, agent, entry, csv_row(), {}, "2026-10-13", apply=False)["verdict"]["status"] == "needs_review"
    assert db.writes == []

    result = imm.reevaluate(db, agent, entry, csv_row(), {}, "2026-10-13", apply=True)
    update = next(w for w in db.writes if w[0] == "update_place_validation")
    assert update[2]["status"] == "needs_review" and "RE-EVALUACIÓN CON EVIDENCIA NUEVA" in update[2]["notes"]
    assert "Nota anterior: Sin señales." in update[2]["notes"] and "insert_place_candidate" not in [w[0] for w in db.writes]
    assert result["before"]["status"] == "discarded"

    for blocked in ({**place, "validation_notes": "APROBACIÓN MANUAL (2026-09-27, admin): ..."}, {**place, "status": "approved"}):
        db = FakeDB(blocked)
        agent, llm = validator(db)
        assert imm.reevaluate(db, agent, entry, csv_row(), {}, "2026-10-13", apply=True)["outcome"] != "validado"
        assert db.writes == [] and llm.prompts == []


def test_apply_plan_only_touches_write_actions(tmp_path):
    db = FakeDB()
    agent, llm = validator(db)
    plan = [{"n": 21, "mode": "new", "action": "no_aplica"}, {"n": 27, "mode": "report_only", "action": "solo_reporte"}]
    args = argparse.Namespace(dossier=str(tmp_path / "d.json"), only=None, captured="2026-10-13", apply=True, out_dir=str(tmp_path))
    assert imm.apply_plan(db, FakePlaces(), agent, imm.load_rows(str(CSV)), plan, args, out=lambda *_: None) == 0
    assert db.writes == [] and llm.prompts == []


def test_plan_file_covers_its_rows_once_with_a_reason():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    numbers = [e["n"] for e in plan]
    assert len(numbers) == len(set(numbers))
    for entry in plan:
        assert entry["action"] in imm.WRITE_ACTIONS + ("no_aplica", "no_verificable", "rechazado", "solo_reporte", "aprobacion_manual", "ya_esta",
                                                      "sin_cambios")
        if entry["action"] not in imm.WRITE_ACTIONS:
            assert entry.get("motivo")
        if entry["action"] == "reevaluate":
            assert entry["mode"] == "reevaluate" and entry.get("place_id")
