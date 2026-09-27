"""scripts/find_evidence.py: reads the admin-pending 100% queue and writes a LOCAL report. It never writes to the database."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.clients.supabase_client import SupabaseClient
from agents.validator_agent import PENDING_ADMIN_FLAG
from scripts.find_evidence import build_parser, run

ROOT = Path(__file__).resolve().parent.parent
ESTABLISHMENT = {"citas": [{"n": 1, "alcance": "establecimiento", "contradice_exclusividad": False, "habla_de_este_negocio": True}]}


def make_places(n=30):
    cities = ["Buenos Aires", "Córdoba", "Mar del Plata", "Mendoza", "La Plata", "Montevideo", "Rosario", "Paraná",
              "Gualeguaychú", "Punta del Este", "Mercedes", "San Isidro"]
    rows = []
    for i in range(n):
        rows.append({
            "id": f"00000000-0000-4000-8000-{i:012d}", "name": f"Panadería Local{i}", "city": cities[i % len(cities)],
            "country": "Argentina", "category": ("cafe", "shop", "restaurant")[i % 3], "safety_level": "gluten_free_100",
            "status": "approved", "flags": [PENDING_ADMIN_FLAG], "updated_at": "2026-09-20T10:00:00+00:00",
            "website": ("https://sitio%d.com" % i) if i % 3 == 0 else None,
            "social_url": ("https://instagram.com/l%d" % i) if i % 3 == 1 else None,
        })
    return rows


class ReadOnlyDB:
    """Only reads exist. Any write the script might attempt is an AttributeError, which is the point."""

    def __init__(self, places):
        self.places = places
        self.reads = []

    def fetch_places_for_admin(self, status=None, **kw):
        self.reads.append((status, kw))
        rows = [p for p in self.places if not kw.get("city") or kw["city"].lower() in p["city"].lower()]
        if kw.get("flag"):
            rows = [p for p in rows if kw["flag"] in p["flags"]]
        return rows[kw.get("offset", 0): kw.get("offset", 0) + kw.get("limit", 15)]

    def fetch_place_by_id(self, pid):
        return next((p for p in self.places if p["id"] == pid), None)


class Search:
    def __init__(self):
        self.calls = []

    def search(self, query, num=10, include_domains=None):
        self.calls.append((query, include_domains))
        if include_domains is None and "Local3" in query:
            return [{"title": "", "link": "https://blog.example/g", "snippet": "Panadería Local3 en Mendoza: todo es sin gluten."}]
        return []


class LLM:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system, user, model=None, max_tokens=1024):
        self.calls += 1
        return ESTABLISHMENT


def go(tmp_path, places, *argv, search=None, llm=None):
    lines = []
    db = ReadOnlyDB(places)
    code = run(db, search or Search(), llm if llm is not None else LLM(), build_parser().parse_args([*argv, "--out-dir", str(tmp_path)]),
               out=lambda t="": lines.append(str(t)), fetch_text=lambda url: "")
    return code, "\n".join(lines), db


def reports(tmp_path):
    return sorted(p for p in tmp_path.glob("*.json") if not p.name.endswith(".frozen.json")), sorted(tmp_path.glob("*.md"))


def frozen(tmp_path):
    return sorted(tmp_path.glob("*.frozen.json"))


def test_the_pilot_writes_a_local_report_of_ten_places_in_ten_cities_and_touches_nothing_else(tmp_path):
    search = Search()
    code, text, db = go(tmp_path, make_places(48), "--pilot", search=search)
    assert code == 0
    (jpath,), (mpath,) = reports(tmp_path)
    data = json.loads(jpath.read_text(encoding="utf-8"))
    assert len(data["places"]) == 10 and len({p["city"] for p in data["places"]}) == 10
    assert data["summary"]["total"] == 10 and set(data["summary"]["por_propuesta"]) == {"100", "options", "insuficiente"}
    assert data["meta"]["searches_used"] == len(search.calls) == 20
    assert all(p["updated_at"] == "2026-09-20T10:00:00+00:00" and p["place_id"] for p in data["places"])
    assert "insuficiente" in mpath.read_text(encoding="utf-8")
    assert db.reads and all(kw.get("flag") == PENDING_ADMIN_FLAG for _, kw in db.reads)  # only the queue was read


def test_the_markdown_report_shows_the_counts_the_insuficientes_by_link_and_every_citation_with_its_url(tmp_path):
    places = make_places(48)
    ids = [p["id"] for p in places if p["name"].endswith("Local3")]
    code, _, _ = go(tmp_path, places, "--ids", *ids)
    assert code == 0
    md = reports(tmp_path)[1][0].read_text(encoding="utf-8")
    assert "«Panadería Local3 en Mendoza: todo es sin gluten.»" in md and "https://blog.example/g" in md
    assert "Local3" in md


class VetoLLM:
    last_usage = {"input": 100, "output": 20}

    def complete_json(self, system, user, model=None, max_tokens=1024):
        return {"citas": [{"n": 1, "alcance": "producto_o_linea", "contradice_exclusividad": False,
                           "habla_de_este_negocio": True, "motivo": "Habla solo de las tortas."}]}


class NoiseSearch:
    def search(self, query, num=10, include_domains=None):
        return [{"title": "Guia Mendoza", "link": "https://blog.example/mendoza", "snippet": "Una panaderia de Mendoza con tortas sin gluten."}]


def test_the_markdown_shows_the_verification_label_the_models_veto_with_its_reason_and_the_haiku_tokens(tmp_path):
    places = make_places(48)
    ids = [p["id"] for p in places if p["name"].endswith("Local3")]
    code, text, _ = go(tmp_path, places, "--ids", *ids, llm=VetoLLM())
    assert code == 0
    (jpath,), (mpath,) = reports(tmp_path)
    md, data = mpath.read_text(encoding="utf-8"), json.loads(jpath.read_text(encoding="utf-8"))
    assert "solo snippet" in md and "veto del modelo" in md and "Habla solo de las tortas." in md and "cita 1" in md
    assert data["meta"]["haiku_tokens"] == {"input": 100, "output": 20} and "Haiku" in md and "100" in md
    assert data["meta"]["haiku_est_usd"] > 0
    assert data["places"][0]["citations"][0]["verificacion"] == "solo_snippet"
    assert "verificar en la fuente" in text  # the run summary counts the "100 · verificar en la fuente" too


def test_the_markdown_lists_the_discarded_sources_of_an_insuficiente_with_the_reason(tmp_path):
    code, _, _ = go(tmp_path, make_places(48), "--limit", "3", search=NoiseSearch())
    assert code == 0
    md = reports(tmp_path)[1][0].read_text(encoding="utf-8")
    assert "insuficiente (3)" in md and "Fuentes descartadas" in md
    assert "https://blog.example/mendoza" in md and "no menciona ni el nombre ni la ciudad" in md


class ExplodingSearch:
    def search(self, *a, **k):
        raise AssertionError("a replay must not call Tavily")


def test_every_run_writes_a_freeze_of_what_it_retrieved_next_to_the_report(tmp_path):
    places = make_places(48)
    ids = [p["id"] for p in places if p["name"].endswith("Local3")]
    code, text, _ = go(tmp_path, places, "--ids", *ids)
    assert code == 0
    (path,) = frozen(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["searches"]) == 2 and data["searches"][0]["hits"][0]["link"] == "https://blog.example/g"
    assert set(data) >= {"created_at", "searches", "pages"} and "congelado" in text.lower()


def test_no_freeze_skips_the_file(tmp_path):
    go(tmp_path, make_places(48), "--limit", "3", "--no-freeze")
    assert frozen(tmp_path) == []


def test_a_replay_reproduces_the_proposals_without_touching_tavily_and_costs_no_searches(tmp_path):
    places = make_places(48)
    first = tmp_path / "first"
    second = tmp_path / "second"
    go(first, places, "--pilot")
    (path,) = frozen(first)
    before = json.loads(reports(first)[0][0].read_text(encoding="utf-8"))
    code, text, _ = go(second, places, "--pilot", "--replay", str(path), search=ExplodingSearch())
    assert code == 0
    after = json.loads(reports(second)[0][0].read_text(encoding="utf-8"))
    assert [(p["place_id"], p["proposal"]) for p in after["places"]] == [(p["place_id"], p["proposal"]) for p in before["places"]]
    assert after["meta"]["replay"] is True and after["meta"]["searches_used"] == 0 and after["meta"]["freeze_misses"] == 0
    assert frozen(second) == []  # a replay does not freeze again


def test_a_replay_needs_no_search_cap_however_many_places_it_covers(tmp_path):
    places = make_places(48)
    go(tmp_path / "a", places, "--limit", "20")
    (path,) = frozen(tmp_path / "a")
    code, _, _ = go(tmp_path / "b", places, "--replay", str(path), search=ExplodingSearch())
    assert code == 0


def test_a_replay_reports_the_searches_the_freeze_did_not_have(tmp_path):
    places = make_places(48)
    go(tmp_path / "a", places, "--limit", "2")
    (path,) = frozen(tmp_path / "a")
    code, text, _ = go(tmp_path / "b", places, "--limit", "6", "--replay", str(path), search=ExplodingSearch())
    data = json.loads(reports(tmp_path / "b")[0][0].read_text(encoding="utf-8"))
    assert code == 0 and data["meta"]["freeze_misses"] > 0 and "faltaban" in text


def test_a_replay_of_something_that_is_not_a_freeze_is_refused(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    code, text, _ = go(tmp_path / "x", make_places(48), "--pilot", "--replay", str(bad), search=ExplodingSearch())
    assert code == 2 and "congelado" in text.lower()


def test_the_summary_counts_insuficientes_by_website_red_social_or_nada(tmp_path):
    code, text, _ = go(tmp_path, make_places(48), "--pilot")
    data = json.loads(reports(tmp_path)[0][0].read_text(encoding="utf-8"))
    ins = data["summary"]["insuficientes_por_link"]
    assert set(ins) == {"website", "red social", "nada"}
    assert sum(ins.values()) == data["summary"]["por_propuesta"]["insuficiente"]
    assert "website" in text and "nada" in text  # printed too


def test_a_run_over_more_than_twenty_places_needs_an_explicit_search_cap(tmp_path):
    code, text, _ = go(tmp_path, make_places(48))
    assert code == 2 and "--max-searches" in text and reports(tmp_path) == ([], [])


def test_the_search_cap_is_respected_and_the_skipped_places_are_listed_not_labelled(tmp_path):
    search = Search()
    code, text, _ = go(tmp_path, make_places(48), "--max-searches", "40", search=search)
    data = json.loads(reports(tmp_path)[0][0].read_text(encoding="utf-8"))
    assert len(search.calls) <= 40 and len(data["places"]) == 20
    assert data["meta"]["skipped_by_cap"] == 28 and data["summary"]["total"] == 20
    assert "28" in text


def test_a_small_selection_needs_no_cap(tmp_path):
    assert go(tmp_path, make_places(48), "--limit", "5")[0] == 0
    assert go(tmp_path, make_places(48), "--city", "Mendoza")[0] == 0


def test_no_llm_never_calls_the_model_and_never_proposes_100(tmp_path):
    llm = LLM()
    code, _, _ = go(tmp_path, make_places(48), "--pilot", "--no-llm", llm=llm)
    data = json.loads(reports(tmp_path)[0][0].read_text(encoding="utf-8"))
    assert llm.calls == 0 and data["summary"]["por_propuesta"]["100"] == 0


def test_three_queries_per_place_use_three_searches(tmp_path):
    search = Search()
    go(tmp_path, make_places(48), "--pilot", "--queries", "3", search=search)
    assert len(search.calls) == 30


def test_the_database_client_has_no_write_the_script_could_reach_through_the_read_only_double():
    for name in ("update_place", "add_place_evidence", "insert_agent_log"):
        assert not hasattr(ReadOnlyDB([]), name)


def test_the_admin_place_columns_carry_updated_at_so_a_stale_report_can_be_detected():
    assert "updated_at" in [c.strip() for c in SupabaseClient.ADMIN_PLACE_COLUMNS.split(",")]


def test_the_admin_place_columns_carry_the_region_the_source_filter_uses():
    assert "region" in [c.strip() for c in SupabaseClient.ADMIN_PLACE_COLUMNS.split(",")]


def test_the_proposal_reports_are_git_ignored():
    assert "db/checks/evidence-proposals/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("argv", [["--queries", "5"], ["--pilot", "--ids", "x"]])
def test_bad_arguments_are_rejected_by_the_parser(argv):
    with pytest.raises(SystemExit):
        build_parser().parse_args(argv)
