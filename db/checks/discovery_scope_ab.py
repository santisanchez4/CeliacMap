#!/usr/bin/env python
"""A/B of the map scope edits to the two discovery prompts (2026-10-13) against the real model.

  social   PARSE_RUBRIC (agents/social_agent.py, Haiku). Synthetic search results (title + snippet), no Tavily, no geocoding.
           What only the model shows: whether "sells_to_public" is false for a page that teaches or informs, and never false for
           a business (only an explicit false drops a lead). Name and category are compared with the OLD arm.
  web      RESEARCH_RUBRIC (agents/web_agent.py, WEB_SEARCH_MODEL with Anthropic web search). One live research turn per city and
           arm; nothing is geocoded or inserted. The searches differ from run to run, so this arm is read, not scored: the leads
           are listed, and the ones the deterministic layer (agents/map_scope.py) would drop are counted.

Both arms receive the SAME user prompt; only the system prompt differs (OLD = a git rev, NEW = the working tree).

  python db/checks/discovery_scope_ab.py social --old-rev fix/social-agent-post-is-not-a-profile --n 3
  python db/checks/discovery_scope_ab.py web    --old-rev fix/social-agent-post-is-not-a-profile --n 2

Paid calls are never made without the admin asking: --max-calls is mandatory and the run aborts before the call that would exceed
it (for web, one research turn counts as one call but costs far more than a plain call). A failed call stops the run; nothing is
retried with another model.

No production reads or writes. Uses ANTHROPIC_API_KEY from .env (never printed).
Cost: social ~US$0.001 per call (19 cases x 2 arms x n); web ~US$0.10-0.50 per research turn (cities x 2 arms x n).
"""
from __future__ import annotations

import argparse
import ast
import collections
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agents.clients.llm import LLMClient  # noqa: E402
from agents.map_scope import out_of_scope_reason  # noqa: E402
from agents.social_agent import PARSE_RUBRIC  # noqa: E402
from agents.web_agent import RESEARCH_RUBRIC, WebAgent  # noqa: E402
from config.settings import get_settings  # noqa: E402


class CallCap:
    """Hard stop on paid calls: the run aborts before the call that would exceed ``limit``."""

    def __init__(self, limit: int):
        self.limit, self.used, self._lock = limit, 0, threading.Lock()

    def spend(self) -> None:
        with self._lock:
            if self.used >= self.limit:
                raise SystemExit(f"HARD CAP: {self.limit} paid call(s) reached; run stopped.")
            self.used += 1


def constant_at(rev: str, path: str, name: str) -> str:
    """The string constant ``name`` of ``path`` as it was at git ``rev``."""
    source = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True, encoding="utf-8", check=True).stdout
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit(f"{name} not found in {path} at {rev}")


SOCIAL_CASES = [
    # (kind, label, title, snippet)
    ("out", "blog", "Celíacos en Montevideo (@celiacosenmvd) • Instagram",
     "Blog con recetas sin gluten, guías de lugares y novedades para la comunidad celíaca de Montevideo. Link al blog en la bio."),
    ("out", "cuenta_de_recetas", "Cocina Sin TACC con Lau (@cocinasintaccconlau) • Instagram photos and videos",
     "Recetas sin TACC fáciles todos los días 🍞 Guardá el reel y seguime para más recetas. 85 mil seguidores."),
    ("out", "escuela_de_cocina", "By Gessi | Educación Gastronómica Sin Gluten (@bygessi) • Instagram",
     "Chef y formadora en cocina sin gluten. Cursos presenciales y online de panificados y pastelería. Inscripciones abiertas."),
    ("out", "taller", "Taller de Panadería Sin Gluten - Facebook",
     "Talleres mensuales para aprender a hacer pan sin TACC en casa. Cupos limitados, consultá fechas. Montevideo."),
    ("out", "asociacion", "ACELU - Asociación Celíaca del Uruguay | Facebook",
     "Asociación civil sin fines de lucro. Información, charlas y apoyo para personas celíacas y sus familias."),
    ("out", "pagina_informativa", "Vivir sin gluten Argentina (@vivirsingluten.ar) • Instagram",
     "Información y consejos para la dieta sin TACC. Novedades del listado de ANMAT, tips para el diagnóstico reciente."),
    ("in", "panaderia", "Panadería La Espiga Sin Gluten (@laespiga.singluten) • Instagram",
     "Panadería 100% sin TACC en Pocitos. Panes, facturas y tortas. Abierto de lunes a sábado. Bulevar España 2345."),
    ("in", "dietetica", "Dietética Vida Sana - Facebook",
     "Dietética en Córdoba. Productos sin TACC, sin azúcar, veganos. Av. Colón 1200. Envíos a domicilio."),
    ("in", "restaurante", "La Parrilla de Juan (@laparrilladejuan) • Instagram",
     "Parrilla en Palermo. Menú sin TACC disponible. Reservas por WhatsApp."),
    ("in", "heladeria_cadena", "Zero Helados (@zerohelados) • Instagram",
     "Helados sin gluten y sin azúcar. 6 locales en Montevideo y Punta del Este."),
    ("in", "panaderia_cadena", "Ramona | Panadería y pastelería 100% sin gluten (@ramona.singluten) • Instagram",
     "4 locales en Buenos Aires. Pedidos por la web."),
    ("in", "panaderia_que_tambien_da_talleres", "Sin Trigo Panadería (@sintrigo.panaderia) • Instagram",
     "Panadería sin TACC. Vendemos panes y facturas en el local. También dictamos talleres de panificación sin gluten."),
    ("in", "fabrica_con_venta_directa", "Pastas Don Luis - Fábrica de pastas sin TACC | Facebook",
     "Fábrica de pastas sin TACC. Venta al público en nuestro local de fábrica, de lunes a sábado. Rosario."),
    ("in", "emprendimiento_por_pedido", "Dulce Miga – Pastelería libre de gluten (@dulcemiga.sg) • Instagram",
     "Tortas y budines sin TACC por pedido. Retiro en Nueva Córdoba. Pedidos por DM."),
    # Admin decision 2026-10-13: these three real places stay on the map.
    ("in", "entresano", "Entresano Supermercado Saludable (@entresano.supersaludable) • Instagram",
     "Supermercado saludable en Córdoba. Productos sin TACC, sin azúcar, keto y veganos. 3 sucursales."),
    ("in", "minimarket_la_isla", "La Isla 24/7 (@laisla24_7) • Instagram",
     "Minimarket abierto las 24 horas en Maldonado. Más de 1.500 productos sin gluten, vinos y cocina propia."),
    ("in", "la_molienda", "La Molienda (@lamoliendauy) • Instagram",
     "Tienda natural. Frutos secos, productos sin gluten, sin azúcar, veganos. 9 tiendas en Montevideo y Ciudad de la Costa."),
    # No pass/fail: the text does not say what the page is. Expected null (the lead goes on to the Validator).
    ("report", "texto_ambiguo", "Sin Gluten Uruguay (@singlutenuy) • Instagram", "Todo sin gluten 🌾🚫 Montevideo."),
    ("report", "influencer_con_tienda", "Celi Viajera (@celiviajera) • Instagram",
     "Viajo y como sin gluten. Reseñas de restaurantes aptos. Mi tienda de premezclas en el link."),
]

WEB_CITIES = [("Uruguay", "Montevideo"), ("Argentina", "Buenos Aires")]


def run_social(llm: LLMClient, model: str, old: str, n: int, cap: CallCap) -> int:
    failures = 0
    for kind, label, title, snippet in SOCIAL_CASES:
        user = f"title: {title}\nsnippet: {snippet}"
        print(f"\n[{kind}] {label} — {title}")
        seen = {}
        for tag, rubric in (("OLD", old), ("NEW", PARSE_RUBRIC)):
            with ThreadPoolExecutor(max_workers=3) as ex:
                outs = list(ex.map(lambda _: (cap.spend(), llm.complete_json(rubric, user, model=model, max_tokens=200))[1], range(n)))
            seen[tag] = outs
            sells = collections.Counter(repr(o.get("sells_to_public", "—")) for o in outs)
            names = collections.Counter(str(o.get("name")) for o in outs)
            cats = collections.Counter(str(o.get("category")) for o in outs)
            print(f"  {tag}: sells_to_public {dict(sells)} | name {dict(names)} | category {dict(cats)}")
        false_n = sum(1 for o in seen["NEW"] if o.get("sells_to_public") is False)
        if kind == "out" and false_n < n:
            failures += 1
            print(f"  !! FAIL: a page that does not sell was kept in {n - false_n}/{n}")
        elif kind == "in" and false_n:
            failures += 1
            print(f"  !! FAIL: a business was dropped in {false_n}/{n}")
        lost = sum(1 for o in seen["NEW"] if not o.get("name")) - sum(1 for o in seen["OLD"] if not o.get("name"))
        if kind == "in" and lost > 0:
            failures += 1
            print(f"  !! FAIL: the NEW arm lost the name in {lost} more sample(s) than OLD")
    print("\nRESULT:", "FAIL" if failures else "PASS", f"({failures} failing case(s))")
    return 1 if failures else 0


def run_web(llm: LLMClient, model: str, old: str, n: int, max_searches: int, cap: CallCap) -> int:
    jobs = [(country, city, tag, rubric, i) for country, city in WEB_CITIES for tag, rubric in (("OLD", old), ("NEW", RESEARCH_RUBRIC))
            for i in range(n)]

    def research(job):
        country, city, tag, rubric, i = job
        cap.spend()
        try:
            result = llm.research_with_web_search(rubric, WebAgent._user_prompt(country, city), model=model, max_searches=max_searches)
            return job, (result or {}).get("places") or [], None
        except Exception as exc:  # noqa: BLE001 - one failed turn is reported, not fatal
            return job, [], f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(research, jobs))

    totals = collections.defaultdict(lambda: [0, 0, 0])  # tag -> [turns, leads, out of scope by the deterministic layer]
    for (country, city, tag, _, i), leads, error in results:
        print(f"\n[{tag}] {city}, {country} — run {i + 1}: " + (f"ERROR {error}" if error else f"{len(leads)} lead(s)"))
        totals[tag][0] += 1
        for lead in leads:
            reason = out_of_scope_reason(lead.get("name"), website=lead.get("source_url"))
            totals[tag][1] += 1
            totals[tag][2] += bool(reason)
            mark = f"  ⛔ {reason.kind}" if reason else ""
            print(f"  - {lead.get('name')} [{lead.get('category')}]{mark} — {(lead.get('evidence') or '')[:150]} ({lead.get('source_url')})")
    print()
    for tag, (turns, leads, out) in totals.items():
        print(f"{tag}: {turns} turn(s), {leads} lead(s), {out} that the deterministic layer drops")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt", choices=("social", "web"))
    ap.add_argument("--old-rev", default="main", help="git rev with the previous prompt (default: main)")
    ap.add_argument("--n", type=int, default=3, help="samples per case (social) or research turns per city (web), per arm")
    ap.add_argument("--max-calls", type=int, required=True, help="hard cap on paid calls; the run aborts when reached")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and the estimated cost; make no call")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    planned = (len(SOCIAL_CASES) if args.prompt == "social" else len(WEB_CITIES)) * 2 * args.n
    each = "~US$0.001 each" if args.prompt == "social" else "~US$0.10-0.50 each with Haiku, several times that with a larger model"
    print(f"PLAN: {planned} call(s), {each}; hard cap {args.max_calls} call(s)")
    if planned > args.max_calls:
        raise SystemExit(f"the plan ({planned}) exceeds --max-calls ({args.max_calls}): nothing was called")
    if args.dry_run:
        print("dry run: no call made")
        return 0
    cap = CallCap(args.max_calls)
    llm = LLMClient(settings.anthropic_api_key, default_model=settings.haiku_model)
    if args.prompt == "social":
        print(f"model: {settings.haiku_model} · n={args.n} · OLD = {args.old_rev}")
        return run_social(llm, settings.haiku_model, constant_at(args.old_rev, "agents/social_agent.py", "PARSE_RUBRIC"), args.n, cap)
    print(f"model: {settings.web_search_model} · n={args.n} · OLD = {args.old_rev} · max searches {settings.max_web_searches_per_city}")
    return run_web(llm, settings.web_search_model, constant_at(args.old_rev, "agents/web_agent.py", "RESEARCH_RUBRIC"), args.n,
                   settings.max_web_searches_per_city, cap)


if __name__ == "__main__":
    raise SystemExit(main())
