"""Find public evidence for the places in the admin's "100% pendiente de confirmación" queue (audit plan step 6).

READ-ONLY: it reads the queue, searches the public web and writes a LOCAL report (JSON + markdown) under
``db/checks/evidence-proposals/`` (git-ignored). It never writes to the database and nothing it finds shows on the map: the admin
reads the report and confirms with ``scripts/review_queue.py --proposals`` / ``--accept-proposals``.
Runbook (quota, order of operations, rules): docs/runbooks/evidence-finder.md.

    python -m scripts.find_evidence --pilot                       # 10 places of 10 cities, ~20 Tavily searches
    python -m scripts.find_evidence --ids ID1 ID2                 # specific places
    python -m scripts.find_evidence --city Mendoza --limit 5
    python -m scripts.find_evidence --max-searches 560            # the whole queue, capped (required above 20 places)
    python -m scripts.find_evidence --pilot --replay REPORT.frozen.json   # the same run on frozen sources: no Tavily, no downloads

Tavily's quota is shared with the Social agent: check the account's usage first (runbook) and keep --max-searches below what is left.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from agents.clients.website_scraper import fetch_page_text
from agents.evidence_freeze import (
    RecordingFetch,
    RecordingSearch,
    ReplayFetch,
    ReplaySearch,
    build_freeze,
    load_freeze,
)
from agents.evidence_finder import (
    PROPOSALS,
    EvidenceFinder,
    haiku_cost_usd,
    needs_source_check,
    pick_pilot,
    proposal_label,
    summarize,
    verification_label,
)
from agents.validator_agent import PENDING_ADMIN_FLAG

DEFAULT_OUT_DIR = "db/checks/evidence-proposals"
PILOT_SIZE = 10
CAP_REQUIRED_ABOVE = 20  # places: a bigger selection must say how many searches it may spend
QUEUE_FETCH_LIMIT = 2000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    pick = parser.add_mutually_exclusive_group()
    pick.add_argument("--pilot", action="store_true", help=f"a deterministic sample of {PILOT_SIZE} places in {PILOT_SIZE} cities")
    pick.add_argument("--ids", nargs="+", metavar="PLACE_ID", help="specific places (need not be in the queue)")
    parser.add_argument("--city", help="filter the queue by city")
    parser.add_argument("--limit", type=int, help="how many places of the queue")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--queries", type=int, choices=(2, 3), default=2,
                        help="Tavily searches per place: 2 = open web + Instagram/Facebook; 3 adds ACELU/ACELA/ACA")
    parser.add_argument("--max-searches", type=int, help="hard cap on Tavily searches (required above 20 places)")
    parser.add_argument("--no-llm", action="store_true", help="skip the scope classification (no place is ever proposed as 100)")
    parser.add_argument("--replay", metavar="FROZEN", help="repeat a run on the sources a previous run froze: no Tavily searches, no page downloads")
    parser.add_argument("--no-freeze", action="store_true", help="do not save the retrieved sources next to the report")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--label", help="name for the report files (default: the date)")
    return parser


def _select(db, args, out) -> list[dict]:
    if args.ids:
        found = []
        for pid in args.ids:
            place = db.fetch_place_by_id(pid)
            if place:
                found.append(place)
            else:
                out(f"No existe el lugar {pid}.")
        return found
    queue = db.fetch_places_for_admin(None, flag=PENDING_ADMIN_FLAG, city=args.city, limit=QUEUE_FETCH_LIMIT)
    if args.pilot:
        return pick_pilot(queue, PILOT_SIZE)
    end = args.offset + args.limit if args.limit else None
    return queue[args.offset:end]


def _cite_lines(cite: dict, number: int) -> list[str]:
    flags = (f"[{cite.get('source_kind')}] {verification_label(cite)} · señal de exclusividad: "
             f"{'sí' if cite.get('has_signal') else 'no'} · alcance: {cite.get('alcance')}")
    if cite.get("contradice"):
        flags += " · contradice exclusividad"
    lines = [f"{number}. «{cite.get('text')}»", f"   {cite.get('url')}  ({flags})"]
    if cite.get("motivo"):
        lines.append(f"   motivo del modelo: {cite['motivo']}")
    return lines


def render_markdown(results: list[dict], summary: dict, meta: dict) -> str:
    tokens = meta.get("haiku_tokens") or {"input": 0, "output": 0}
    lines = [
        f"# Propuestas de evidencia — {meta['created_at'][:10]}",
        "",
        "Solo lectura: nada de esto está en el mapa ni en la base. Cada cita es un fragmento literal de un texto recuperado, con su URL, y lleva",
        "su rótulo: verificada en la página, solo snippet (la página no la contiene o no se pudo bajar) o red social: no verificable.",
        "La decisión es del admin (`scripts/review_queue.py --proposals` / `--accept-proposals`).",
        "",
        "## Resumen",
        "",
        "| propuesta | lugares |",
        "|---|---|",
        *[f"| {k} | {summary['por_propuesta'][k]} |" for k in PROPOSALS],
        f"| de las 100: verificar en la fuente | {summary['cien_verificar_en_la_fuente']} |",
        f"| de las options: posible 100 | {summary['posible_100']} |",
        "",
        "Insuficientes por lo que el lugar tiene (website propio > red social > nada): "
        + " · ".join(f"{k} {v}" for k, v in summary["insuficientes_por_link"].items()),
        f"Con al menos una frase explícita de exclusividad: {summary['con_senal_de_exclusividad']} · "
        f"con veto del modelo: {summary['con_veto_del_modelo']}",
        f"Búsquedas de Tavily usadas: {meta['searches_used']} (tope {meta['max_searches']})"
        + (f" · lugares sin procesar por el tope: {meta['skipped_by_cap']}" if meta["skipped_by_cap"] else ""),
        f"Haiku: {tokens['input']} tokens de entrada, {tokens['output']} de salida "
        f"(~US${meta.get('haiku_est_usd', 0):.4f}; estimación a US$1/M entrada y US$5/M salida)",
    ]
    for proposal in PROPOSALS:
        group = [r for r in results if r["proposal"] == proposal]
        lines += ["", f"## {proposal} ({len(group)})"]
        for r in group:
            lines += ["", f"### {r['name']} — {r['city']}, {r['country']}",
                      f"propuesta: **{proposal_label(r)}** · id `{r['place_id']}` · {r.get('category')} · nivel actual "
                      f"{r.get('safety_level')} · links: {r['link_kind']}"]
            if r.get("website") or r.get("social_url"):
                lines.append("links del lugar: " + " · ".join(x for x in (r.get("website"), r.get("social_url")) if x))
            lines.append("motivo: " + "; ".join(r["reasons"]))
            s = r["stats"]
            lines.append(f"(fuentes vistas {s['sources_seen']}, sobre el negocio {s['sources_about_place']}, "
                         f"citas descartadas por el modelo {s['quotes_dropped_by_llm']})")
            for number, cite in enumerate(r["citations"], start=1):
                lines += _cite_lines(cite, number)
            for v in r.get("vetoes") or []:
                lines.append(f"veto del modelo ({v['tipo']}): cita {v['cita']} — {v.get('motivo_modelo') or 'sin motivo'}")
            if r.get("possible_100"):
                q = r.get("possible_100_quote") or {}
                lines.append(f"posible 100: «{q.get('text')}» {q.get('url')} — frase de exclusividad que has_exclusive_signal no "
                             f"reconoce; no es una propuesta de 100, revisala en la fuente")
            if r.get("dropped_by_model"):
                lines.append("citas que el modelo descartó:")
                lines += [f"- «{d['text']}» {d['url']} — {d['razon']}: {d.get('motivo') or 'sin motivo'}" for d in r["dropped_by_model"]]
            if r.get("discarded_sources"):
                lines.append("Fuentes descartadas:")
                lines += [f"- {d['url']} — {d['why']}" + (f" ({d['title']})" if d.get("title") else "") for d in r["discarded_sources"]]
        if group and proposal != "insuficiente":
            block = [r for r in group if not needs_source_check(r)]
            single = [r for r in group if needs_source_check(r)]
            lines.append("")
            if block:
                lines.append(f"IDs {proposal}: " + " ".join(r["place_id"] for r in block))
            if single:
                lines.append(f"IDs {proposal} · verificar en la fuente (de a uno, con --verified-source): "
                             + " ".join(r["place_id"] for r in single))
    return "\n".join(lines) + "\n"


def write_report(results: list[dict], skipped: list[dict], meta: dict, out_dir: str, label: str | None) -> tuple[Path, Path]:
    summary = summarize(results)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"evidence-{label or meta['created_at'][:10]}-{stamp}"
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    data = {"meta": meta, "summary": summary, "places": results,
            "skipped_by_cap": [{"place_id": p.get("id"), "name": p.get("name"), "city": p.get("city")} for p in skipped]}
    json_path, md_path = folder / f"{base}.json", folder / f"{base}.md"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(results, summary, meta), encoding="utf-8")
    return json_path, md_path


def run(db, search, llm, args, out=print, fetch_text=fetch_page_text) -> int:
    places = _select(db, args, out)
    if not places:
        out("No hay lugares para buscar.")
        return 1
    recorder = None
    if args.replay:
        try:
            with open(args.replay, encoding="utf-8") as handle:
                freeze = load_freeze(json.load(handle))
        except (OSError, ValueError) as exc:
            out(f"{args.replay} no es un congelado de scripts/find_evidence: {exc}")
            return 2
        search, fetch_text = ReplaySearch(freeze), ReplayFetch(freeze)
    else:
        if not args.pilot and len(places) > CAP_REQUIRED_ABOVE and args.max_searches is None:
            out(f"{len(places)} lugares × {args.queries} búsquedas: indicá --max-searches N (la cuota de Tavily es compartida con el "
                f"agente Social; ver docs/runbooks/evidence-finder.md).")
            return 2
        if not args.no_freeze:
            search, fetch_text = RecordingSearch(search), RecordingFetch(fetch_text)
            recorder = (search, fetch_text)
    cap = None if args.replay else (args.max_searches if args.max_searches is not None else len(places) * args.queries)
    finder = EvidenceFinder(search, llm=None if args.no_llm else llm, fetch_text=fetch_text, queries=args.queries)
    results, skipped = finder.find_many(places, cap)
    misses = (search.misses + fetch_text.misses) if args.replay else 0
    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(), "mode": "pilot" if args.pilot else ("ids" if args.ids else "queue"),
        "queries": args.queries, "llm": not args.no_llm, "selected": len(places),
        "searches_used": 0 if args.replay else finder.searches_used, "replay": bool(args.replay), "freeze_misses": misses,
        "max_searches": cap, "skipped_by_cap": len(skipped), "writes_to_database": False,
        "haiku_tokens": dict(finder.llm_tokens), "haiku_est_usd": haiku_cost_usd(finder.llm_tokens),
    }
    json_path, md_path = write_report(results, skipped, meta, args.out_dir, args.label)
    freeze_path = None
    if recorder:
        freeze_path = json_path.with_name(json_path.stem + ".frozen.json")
        freeze_path.write_text(json.dumps(build_freeze(*recorder, meta), ensure_ascii=False), encoding="utf-8")
    summary = summarize(results)
    spent = "repetición sobre un congelado: 0 búsquedas de Tavily" if args.replay else f"{finder.searches_used} búsquedas de Tavily"
    out(f"{len(results)} lugares procesados · {spent} · sin escrituras en la base.")
    out("  propuestas: " + " · ".join(f"{k}: {summary['por_propuesta'][k]}" for k in PROPOSALS))
    out(f"  de las 100, verificar en la fuente: {summary['cien_verificar_en_la_fuente']} · de las options, posible 100: "
        f"{summary['posible_100']} · con veto del modelo: {summary['con_veto_del_modelo']}")
    out(f"  Haiku: {finder.llm_tokens['input']} tokens de entrada, {finder.llm_tokens['output']} de salida "
        f"(~US${meta['haiku_est_usd']:.4f})")
    out("  insuficientes por lo que tiene el lugar: " + " · ".join(f"{k} {v}" for k, v in summary["insuficientes_por_link"].items()))
    out(f"  con frase explícita de exclusividad: {summary['con_senal_de_exclusividad']}")
    if skipped:
        out(f"  {len(skipped)} lugares sin procesar por el tope de búsquedas (no se les asignó ninguna propuesta).")
    if misses:
        out(f"  faltaban {misses} búsquedas o páginas en el congelado (se tomaron como vacías).")
    out(f"Reporte: {md_path}\n         {json_path}")
    if freeze_path:
        out(f"Congelado (para repetir sin gastar búsquedas: --replay): {freeze_path}")
    return 0


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
    from config.settings import get_settings

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key", "tavily_api_key")
    if not args.no_llm:
        settings.require("anthropic_api_key")
    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    search = TavilySearchClient(settings.tavily_api_key)
    llm = None if args.no_llm else LLMClient(settings.anthropic_api_key, settings.haiku_model)
    return run(db, search, llm, args)


if __name__ == "__main__":
    raise SystemExit(main())
