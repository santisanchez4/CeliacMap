"""Bring the IM Montevideo "Locales_Gluten_Free" layer into CeliacMap through the Validator (docs/DECISIONS.md, 2026-10-13).

The layer (Servicio de Regulación Alimentaria, Intendencia de Montevideo) lists the premises licensed as "libre de gluten". A licence
is evidence, not an approval: every place still goes through the same ``RUBRIC`` and the same 0.85 / 0.7 / 0.5 gates, and a 100% label
still needs an explicit exclusivity phrase in the evidence (Tope C). Two steps, driven by a plan file the admin reads and edits:

    python -m scripts.import_imm_source gather --only 34 35 5 --search   # READ-ONLY for the database: Google + Tavily -> local dossier
    python -m scripts.import_imm_source apply                            # DRY RUN: real Sonnet verdicts, no writes
    python -m scripts.import_imm_source apply --apply                    # writes to the database

Plan entries (``db/checks/2026-10-13-imm/plan.json``): ``{"n": <CSV row>, "mode": "new" | "reevaluate" | "report_only", ...}``.
``apply`` only touches the entries whose ``action`` is ``insert`` (a new row, inserted ``pending`` by ``insert_place_candidate`` and
validated right away) or ``reevaluate`` (an existing ``needs_review`` / ``discarded`` row, re-evaluated in place: it never goes back
through ``pending``). Everything else (``no_aplica``, ``no_verificable``, ``rechazado``, ``solo_reporte``) is report-only.
The source of each place is kept in ``place_evidence`` (an ``admin`` row with the licence dates, read by the Validator) and in ``agent_log``.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

from agents.clients.google_places import GooglePlacesClient
from agents.clients.website_scraper import fetch_page_text, is_social_url
from agents.evidence_finder import quote_is_literal
from agents.manual_overrides import manual_override_marker
from agents.validator_agent import MAX_EVIDENCE, ValidatorAgent

SOURCE_LABEL = "IM Montevideo - Locales_Gluten_Free"
CITY, COUNTRY, REGION = "Montevideo", "Uruguay", "Montevideo"
DEFAULT_DIR = "db/checks/2026-10-13-imm"
DEFAULT_CSV = f"{DEFAULT_DIR}/imm_locales_libres_de_gluten.csv"
DEFAULT_PLAN = f"{DEFAULT_DIR}/plan.json"
DEFAULT_OUT_DIR = "db/checks/evidence-proposals"  # git-ignored: third-party text
DEFAULT_DOSSIER = f"{DEFAULT_OUT_DIR}/imm-dossier.json"
MAX_CITATIONS = MAX_EVIDENCE - 1  # the Validator reads 5 evidence rows: the licence + 4 quotes
REEVALUABLE = ("needs_review", "discarded")
WRITE_ACTIONS = ("insert", "reevaluate")


# --- the CSV -----------------------------------------------------------------------------------------------------------------

def load_rows(path: str) -> dict[int, dict]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return {n: row for n, row in enumerate(csv.DictReader(handle), start=1)}


def business_name(row: dict) -> str:
    """The layer's name, or the company for a row published as "(sin nombre - empresa: X)"."""
    match = re.search(r"empresa:\s*([^)]+)\)", row["nombre"])
    return (match.group(1) if match else row["nombre"]).strip()


def street_address(row: dict) -> str:
    """"AV DR. LUIS ALBERTO DE HERRERA Nº: 1387" -> "Av Dr. Luis Alberto De Herrera 1387" (no flat number)."""
    text = re.sub(r"\s*Apto:.*$", "", row["direccion"], flags=re.IGNORECASE)
    text = re.sub(r"\s*N[º°o]\s*:\s*", " ", text)
    return " ".join(text.split()).title()


def licence_is_current(row: dict) -> bool:
    return (row.get("vigente_hoy") or "").strip().lower() == "si"


def im_evidence_text(row: dict, captured: str, other_address: bool = False) -> str:
    """The licence as the layer states it. Only literal data from the CSV: the wording must never look like an exclusivity claim of
    ours (the dates go before the "giros" so the Validator's 400-character cut can only shorten the list)."""
    state = "vigente" if licence_is_current(row) else "figura vencida en la fuente"
    where = " (otra dirección que la de esta ficha)" if other_address else ""
    text = (
        f"Fuente: {SOURCE_LABEL} (Servicio de Regulación Alimentaria, capturada {captured}). "
        f"Registro: {row['nombre']}, {row['direccion']}{where}. "
        f"Habilitación {row['habilitado_desde']} a {row['habilitado_hasta']} ({state}). "
        f"Rubro {row['rubro']}. Giros: {row['giros']}"
    )
    if ValidatorAgent.has_exclusive_signal([text]):
        raise ValueError(f"the licence text of {row['nombre']!r} reads as an exclusivity claim; reword im_evidence_text")
    return text


def evidence_rows(row: dict, captured: str, finder_result: dict | None, entry: dict | None = None) -> list[dict]:
    """What goes to ``place_evidence``, oldest first: up to four public quotes, then the licence (so it is the newest row).

    The plan can drop quotes the admin found to be about another business (``exclude``: fragments of the URL or of the text) and add sentences
    read on the business's own page (``extra_quotes``; ``verify_extra_quotes`` checks they are literal there). Extra quotes go first.
    """
    entry = entry or {}
    excluded = [x.lower() for x in entry.get("exclude") or []]
    rows, seen = [], set()
    for cite in list(entry.get("extra_quotes") or []) + list((finder_result or {}).get("citations") or []):
        text, url = (cite.get("text") or "").strip(), (cite.get("url") or "").strip()
        if not text or text in seen or any(x in url.lower() or x in text.lower() for x in excluded):
            continue
        seen.add(text)
        rows.append({"source": "social" if is_social_url(url) else "web", "text": text, "url": url or None})
        if len(rows) == MAX_CITATIONS:
            break
    rows.append({"source": "admin", "text": im_evidence_text(row, captured, bool(entry.get("other_address"))), "url": None})
    return rows


def verify_extra_quotes(plan: list[dict], fetch_text) -> list[str]:
    """Every ``extra_quotes`` sentence must be literal on the page it cites; returns the problems (empty = all good)."""
    problems, pages = [], {}
    for entry in plan:
        for quote in entry.get("extra_quotes") or []:
            url = quote.get("url") or ""
            if url not in pages:
                pages[url] = fetch_text(url) or ""
            if not quote_is_literal(quote.get("text") or "", pages[url]):
                problems.append(f"#{entry['n']}: la cita no está literal en {url}: «{(quote.get('text') or '')[:80]}»")
    return problems


def distance_m(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> int:
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b_lng - a_lng) / 2) ** 2
    return round(2 * 6371000 * math.asin(math.sqrt(h)))


# --- files -------------------------------------------------------------------------------------------------------------------

def _read_json(path: str, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _write_json(path: str, data) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _selected(plan: list[dict], only: list[int] | None) -> list[dict]:
    return [e for e in plan if not only or e["n"] in only]


# --- gather: Google + public web, never the database -------------------------------------------------------------------------

def gather(db, places, finder, rows: dict[int, dict], plan: list[dict], args, out=print) -> int:
    dossier = _read_json(args.dossier, {})
    for entry in _selected(plan, args.only):
        row, key = rows[entry["n"]], str(entry["n"])
        item = dossier.setdefault(key, {})
        if entry["mode"] == "new" and ("resolved" not in item or args.refresh):
            lat, lon = float(row["lat"]), float(row["lon"])
            resolved = places.resolve_location(entry.get("search_name") or business_name(row), street_address(row), CITY, COUNTRY,
                                               location=(lat, lon))
            item["resolved"] = None
            item.pop("details", None)
            if resolved:
                item["resolved"] = {**asdict(resolved), "dist_m": distance_m(lat, lon, resolved.lat, resolved.lng)}
                if resolved.geocode_method == "find_place":
                    result = places.place_details(resolved.place_id).get("result") or {}
                    item["details"] = {
                        "name": result.get("name"), "types": result.get("types"), "business_status": result.get("business_status"),
                        "has_opening_hours": bool((result.get("opening_hours") or {}).get("weekday_text")),
                        **GooglePlacesClient.extract_rich_fields(result),
                    }
        if entry["mode"] == "reevaluate" and "listing_website" not in item:
            place = db.fetch_place_by_id(entry["place_id"]) or {}
            item["listing_website"] = None
            if place.get("external_id") and place.get("geocode_method") != "address_only":
                result = places.place_details(place["external_id"]).get("result") or {}
                item["listing_website"] = GooglePlacesClient.extract_rich_fields(result).get("website")
        if args.search and finder is not None:
            place = _finder_place(db, entry, row, item)
            if place:
                item["evidence"] = finder.find(place)
        r, d, e = item.get("resolved"), item.get("details") or {}, item.get("evidence") or {}
        out(f"#{entry['n']} {row['nombre']} [{entry['mode']}] · "
            + (f"{r['geocode_method']} «{r.get('name')}» {r.get('formatted_address')} ({r['dist_m']} m) {r.get('business_status')}"
               if r else "sin resolver" if entry["mode"] == "new" else "fila existente")
            + (f" · tipos {d.get('types')} · horario {'sí' if d.get('has_opening_hours') else 'no'} · "
               f"{d.get('website') or d.get('social_url') or 'sin web'}" if d else "")
            + (f" · evidencia: {e.get('proposal')} ({len(e.get('citations') or [])} citas)" if e else ""))
        _write_json(args.dossier, dossier)
    if finder is not None:
        out(f"Búsquedas de Tavily usadas: {finder.searches_used} · sin escrituras en la base. Dossier: {args.dossier}")
    return 0


def _finder_place(db, entry: dict, row: dict, item: dict) -> dict | None:
    if entry["mode"] == "reevaluate":
        place = db.fetch_place_by_id(entry["place_id"])
        if place and not place.get("website") and item.get("listing_website"):
            place = {**place, "website": item["listing_website"]}
        return place
    details = item.get("details") or {}
    return {
        "id": f"imm-{entry['n']}",
        "name": entry.get("search_name") or entry.get("name") or details.get("name") or business_name(row).title(),
        "city": CITY, "country": COUNTRY, "region": REGION, "category": entry.get("category") or "shop",
        "website": entry.get("website") or details.get("website"), "social_url": details.get("social_url"),
    }


# --- apply: the Validator decides ----------------------------------------------------------------------------------------------

def _source_meta(row: dict, captured: str) -> dict:
    return {"import_source": SOURCE_LABEL, "source_captured": captured, "im_registro": row["nombre"],
            "im_habilitado_desde": row["habilitado_desde"], "im_habilitado_hasta": row["habilitado_hasta"],
            "im_vigente": licence_is_current(row)}


def _verdict_log(place: dict, v: dict, extra: dict) -> dict:
    return {"name": place.get("name"), "verdict": v["verdict"], "status": v["status"], "category": v["category"],
            "safety_level": v["safety_level"], "confidence": v["confidence"], "reasoning": v["reason"], "flags": v["flags"],
            "recommendation": v["recommendation"], **extra}


def build_candidate(entry: dict, row: dict, item: dict, rich: dict) -> dict:
    resolved = item["resolved"]
    candidate = {
        "lat": resolved["lat"], "lng": resolved["lng"],
        "address": resolved.get("formatted_address") or f"{street_address(row)}, {CITY}, {COUNTRY}",
        "external_id": resolved["place_id"], "source": "manual",
        "country": resolved.get("country") or COUNTRY, "city": resolved.get("city") or CITY, "region": REGION,
        "category": entry.get("category") or "shop",
        "safety_level": "options_available",  # provisional floor; the Validator assigns the level
        "geocode_method": resolved["geocode_method"],
        **rich,
    }
    candidate["name"] = entry.get("name") or resolved.get("name") or business_name(row).title()
    if entry.get("website") and not candidate.get("website"):
        candidate["website"] = entry["website"]
    return candidate


def insert_new(db, places, validator, entry: dict, row: dict, item: dict, captured: str, apply: bool) -> dict:
    resolved = item.get("resolved")
    if not resolved:
        return {"outcome": "sin_ubicacion"}
    rich, snippets = {}, []
    if resolved["geocode_method"] == "find_place":
        result = places.place_details_with_reviews(resolved["place_id"]).get("result") or {}
        rich = GooglePlacesClient.extract_rich_fields(result)
        snippets = GooglePlacesClient.extract_gf_snippets(result.get("reviews"))
    candidate = build_candidate(entry, row, item, rich)
    new_evidence = evidence_rows(row, captured, item.get("evidence"), entry)
    if db.place_exists_by_external_id(candidate["external_id"]):
        return {"outcome": "duplicado", "candidate": candidate}

    if not apply:
        place = {**candidate, "status": "pending"}
        reviews, evidence = snippets[:5], list(reversed(new_evidence))[:MAX_EVIDENCE]
    else:
        place = db.insert_place_candidate(candidate)
        if not place:
            return {"outcome": "no_insertado", "candidate": candidate}
        for e in new_evidence:
            db.add_place_evidence(place["id"], e["source"], e["text"], e["url"])
        for snippet in snippets:
            db.insert_review(place["id"], snippet["text"], rating=snippet.get("rating"), source="google")
        reviews, evidence = db.fetch_reviews_for_place(place["id"]), db.fetch_place_evidence(place["id"])

    v = validator.evaluate(place, reviews, [], evidence)
    if apply:
        db.update_place_validation(place["id"], status=v["status"], confidence=v["confidence"], notes=v["reason"],
                                   category=v["category"], safety_level=v["safety_level"], flags=v["flags"],
                                   recommendation=v["recommendation"])
        validator.log("validate", _verdict_log(place, v, _source_meta(row, captured)), place_id=place["id"])
    return {"outcome": "validado", "place_id": place.get("id"), "candidate": candidate, "evidence": new_evidence,
            "reviews": len(reviews), "verdict": v}


def reevaluation_notes(place: dict, v: dict, today: str) -> str:
    """Traceable ``validation_notes`` for a row re-evaluated in place (same shape as the retroactive re-validation)."""
    parts = [
        f"RE-EVALUACIÓN CON EVIDENCIA NUEVA ({today}): fila re-evaluada en su lugar con el RUBRIC vigente y la evidencia de "
        f"place_evidence ({SOURCE_LABEL} + web/redes). Antes: status '{place.get('status')}' con validation_confidence "
        f"{place.get('validation_confidence')}. Resultado: status '{v['status']}' (veredicto del modelo '{v['verdict']}', "
        f"confidence {v['confidence']}). La fila no volvió a status='pending'."
    ]
    if v.get("reason"):
        parts.append(f"--- Razonamiento nuevo del Validator: {v['reason']}")
    old = (place.get("validation_notes") or "").strip()
    if old:
        parts.append(f"--- Nota anterior: {old}")
    return "\n".join(parts)


def reevaluate(db, validator, entry: dict, row: dict, item: dict, captured: str, apply: bool) -> dict:
    place = db.fetch_place_by_id(entry["place_id"])
    if not place:
        return {"outcome": "no_existe"}
    before = {"status": place.get("status"), "confidence": place.get("validation_confidence"),
              "safety_level": place.get("safety_level")}
    if place.get("status") not in REEVALUABLE:
        return {"outcome": "estado_inesperado", "before": before}
    marker = manual_override_marker(place.get("validation_notes"))
    if marker:
        return {"outcome": "decision_manual", "before": before, "marker": marker}

    new_evidence = evidence_rows(row, captured, item.get("evidence"), entry)
    if apply:
        for e in new_evidence:
            db.add_place_evidence(place["id"], e["source"], e["text"], e["url"])
        evidence = db.fetch_place_evidence(place["id"])
    else:
        evidence = (list(reversed(new_evidence)) + list(db.fetch_place_evidence(place["id"]) or []))[:MAX_EVIDENCE]
    reviews = db.fetch_reviews_for_place(place["id"])
    claims = list(db.fetch_community_claims(place["id"]) or [])

    v = validator.evaluate(place, reviews, claims, evidence)
    if apply:
        db.update_place_validation(place["id"], status=v["status"], confidence=v["confidence"],
                                   notes=reevaluation_notes(place, v, date.today().isoformat()), category=v["category"],
                                   safety_level=v["safety_level"], flags=v["flags"], recommendation=v["recommendation"])
        validator.log("revalidate_with_evidence",
                      _verdict_log(place, v, {**_source_meta(row, captured), "old_status": before["status"],
                                              "old_confidence": before["confidence"]}), place_id=place["id"])
    return {"outcome": "validado", "place_id": place["id"], "name": place.get("name"), "before": before,
            "evidence": new_evidence, "reviews": len(reviews), "verdict": v}


def apply_plan(db, places, validator, rows: dict[int, dict], plan: list[dict], args, out=print, fetch_text=fetch_page_text) -> int:
    dossier = _read_json(args.dossier, {})
    problems = verify_extra_quotes([e for e in _selected(plan, args.only) if e.get("action") in WRITE_ACTIONS], fetch_text)
    if problems:
        for problem in problems:
            out(problem)
        return 2
    results = []
    for entry in _selected(plan, args.only):
        if entry.get("action") not in WRITE_ACTIONS:
            continue
        row, item = rows[entry["n"]], dossier.get(str(entry["n"]), {})
        if entry["action"] == "insert":
            result = insert_new(db, places, validator, entry, row, item, args.captured, args.apply)
        else:
            result = reevaluate(db, validator, entry, row, item, args.captured, args.apply)
        result.update({"n": entry["n"], "action": entry["action"], "im_nombre": row["nombre"], "im_direccion": row["direccion"]})
        results.append(result)
        name = (result.get("candidate") or {}).get("name") or result.get("name") or row["nombre"]
        v = result.get("verdict")
        line = f"#{entry['n']} {name} [{entry['action']}] {result['outcome']}"
        if v:
            before = result.get("before")
            line += ((f" · antes {before['status']} @ {before['confidence']}" if before else "")
                     + f" · {v['status']} @ {v['confidence']} · {v['safety_level']} · {v['category']} · "
                       f"evidencia {len(result['evidence'])} filas, reseñas {result['reviews']}")
            out(line)
            out(f"     {v['reason']}")
            if v["flags"]:
                out("     flags: " + "; ".join(v["flags"]))
        else:
            out(line)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = f"{args.out_dir}/imm-{'apply' if args.apply else 'dryrun'}-{stamp}.json"
    _write_json(path, {"applied": bool(args.apply), "captured": args.captured, "results": results})
    out(("ESCRITO en la base." if args.apply else "DRY RUN: sin escrituras en la base.") + f" Resultado: {path}")
    return 0


# --- CLI -----------------------------------------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("gather", "apply"))
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--plan", default=DEFAULT_PLAN)
    parser.add_argument("--dossier", default=DEFAULT_DOSSIER)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--only", nargs="+", type=int, metavar="N", help="CSV row numbers")
    parser.add_argument("--captured", default="2026-10-13", help="date the layer was captured")
    parser.add_argument("--search", action="store_true", help="gather: also look for public evidence (2 Tavily searches per place)")
    parser.add_argument("--refresh", action="store_true", help="gather: resolve the location again")
    parser.add_argument("--apply", action="store_true", help="apply: write to the database (default: dry run)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    from agents.clients.llm import LLMClient
    from agents.clients.supabase_client import SupabaseClient
    from agents.clients.tavily_client import TavilySearchClient
    from agents.evidence_finder import EvidenceFinder
    from config.settings import get_settings

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key", "google_maps_api_key", "anthropic_api_key")
    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    places = GooglePlacesClient(settings.google_maps_api_key)
    rows, plan = load_rows(args.csv), _read_json(args.plan, [])
    if args.command == "gather":
        finder = None
        if args.search:
            settings.require("tavily_api_key")
            finder = EvidenceFinder(TavilySearchClient(settings.tavily_api_key),
                                    llm=LLMClient(settings.anthropic_api_key, settings.haiku_model))
        return gather(db, places, finder, rows, plan, args)
    validator = ValidatorAgent(db, LLMClient(settings.anthropic_api_key, settings.validator_model), model=settings.validator_model)
    return apply_plan(db, places, validator, rows, plan, args)


if __name__ == "__main__":
    raise SystemExit(main())
