#!/usr/bin/env python
"""A/B of the map scope paragraph of the Validator RUBRIC (2026-10-13) against the real model.

What only the real model shows: whether it answers "not_applicable" for a general retail chain or a place that does not sell to the
public, and whether it leaves food and specialised businesses alone (the over-exclusion risk). The deterministic layer
(agents/map_scope.py) is deliberately bypassed here: every case goes to the model, so this measures the criterion, not the name list.

Both arms receive the SAME user prompt; only the system RUBRIC differs (OLD = a git rev, NEW = the working tree).

  python db/checks/validator_scope_ab.py --old-rev main --n 3 --max-calls 162 --dry-run   # plan and cost, no call
  python db/checks/validator_scope_ab.py --old-rev main --n 3 --max-calls 162

Paid calls are never made without the admin asking: --max-calls is mandatory, the plan is printed first and the run aborts
before the call that would exceed the cap. A failed call stops the run; nothing is retried with another model.

Acceptance (NEW arm, after _normalize):
  out        every sample is "not_applicable" (status discarded): never approved, never needs_review
  same       a case of EXPECT_STATUS has that status in EVERY sample (scope must not move the safety verdict)
  ceiling    a case of MAX_APPROVED is not approved more often than with the previous RUBRIC
  in         no sample is "not_applicable"

No production reads or writes: synthetic places, no DB. Uses ANTHROPIC_API_KEY from .env (never printed).
Cost: ~US$0.011 per call (claude-sonnet-4-6: ~2,300 input + ~250 output tokens); 27 cases x 2 arms x n=3 = 162 calls.
"""
from __future__ import annotations

import argparse
import collections
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.clients.llm import LLMClient  # noqa: E402
from agents.validator_agent import NOT_APPLICABLE, RUBRIC as NEW_RUBRIC, ValidatorAgent  # noqa: E402
from config.settings import get_settings  # noqa: E402
from validator_kitchen_ab import MODEL, rubric_at  # noqa: E402

UY = {"address": "Av. Italia 3456, Montevideo", "city": "Montevideo", "country": "Uruguay", "geocode_method": "find_place",
      "source": "google_places"}
AR = {"address": "Av. Corrientes 1234, CABA", "city": "Buenos Aires", "country": "Argentina", "geocode_method": "find_place",
      "source": "google_places"}
COST_PER_CALL_USD = 0.011
# Acceptance criteria set by the admin on 2026-10-14. These cases are decided by safety, not by scope: the scope section must
# leave them where the previous RUBRIC had them.
EXPECT_STATUS = {
    "restaurante_con_opciones": "needs_review",          # shared grill: review, never rejected
    "zero_helados_cadena": "needs_review",
    "minimarket_la_isla": "needs_review",
    "la_molienda_tienda_natural": "needs_review",
    "entresano_supermercado_saludable": "approved",
    "panaderia_que_tambien_da_talleres": "approved",
}
# Approved samples allowed per run: the previous RUBRIC approved Ramona in 1 of 6 samples and Mi Cocina Sin Gluten in 0 of 6.
MAX_APPROVED = {"ramona_cadena": 1, "mi_cocina_sin_gluten": 0}
SHELF = [{"text": "Tienen una góndola de productos sin TACC muy completa, encuentro todo para celíacos"}]


def shop(base, name, reviews=(), evidence=()):
    return ({**base, "name": name, "category": "shop"}, list(reviews), list(evidence))


CASES = [
    # (kind, label, (place, reviews, evidence))
    ("out", "geant", shop(UY, "Géant Fresh Market")),
    ("out", "tata", shop(UY, "Ta-Ta")),
    ("out", "devoto_con_gondola", shop(UY, "Devoto Express", SHELF)),
    ("out", "disco", shop(UY, "Disco N° 5")),
    ("out", "tienda_inglesa_con_gondola", shop(UY, "Tienda Inglesa", SHELF)),
    ("out", "carrefour", shop(AR, "Carrefour Market")),
    ("out", "coto_con_gondola", shop(AR, "Coto", SHELF)),
    ("out", "jumbo", shop(AR, "Jumbo")),
    ("out", "dia", shop(AR, "Supermercado DIA")),
    ("out", "cadena_no_listada", shop({**AR, "city": "Mar del Plata", "address": "Av. Colón 2100, Mar del Plata"}, "Supermercados Toledo")),
    ("out", "farmacia_de_cadena", shop(AR, "Farmacity")),
    ("out", "by_gessi_escuela", ({**UY, "name": "By Gessi Cocina Inclusiva", "category": "restaurant"},
                                 [{"text": "Excelente el curso online de panificados sin gluten, la profe explica todo"},
                                  {"text": "Hice dos clases en la escuela byGessi, muy recomendable para aprender a cocinar sin gluten"}],
                                 [{"source": "web", "text": "Chef y formadora en cocina sin gluten. Educación Gastronómica Sin Gluten. Cursos presenciales y online.",
                                   "url": "https://bygessi.com"}])),
    ("out", "blog", ({**UY, "name": "Celíacos en Montevideo", "category": "shop", "source": "web", "geocode_method": "address_only"}, [],
                     [{"source": "web", "text": "Blog con recetas sin gluten, guías de lugares y novedades para la comunidad celíaca de Montevideo.",
                       "url": "https://celiacosenmontevideo.example/blog"}])),
    ("out", "cuenta_de_recetas", ({**AR, "name": "Cocina Sin TACC con Lau", "category": "cafe", "source": "social"}, [],
                                  [{"source": "social", "text": "Recetas sin TACC fáciles todos los días. Guardá el reel y seguime para más recetas.",
                                    "url": "https://www.instagram.com/cocinasintaccconlau"}])),
    ("in", "zero_helados_cadena", ({**UY, "name": "Zero Helados", "category": "cafe"}, [], [])),
    ("in", "ramona_cadena", ({**AR, "name": "Ramona", "category": "cafe"}, [],
                             [{"source": "social", "text": "Ramona | Panadería y pastelería 100% sin gluten. 4 locales en Buenos Aires.",
                               "url": "https://www.instagram.com/ramona.singluten"}])),
    ("in", "mi_cocina_sin_gluten", ({**UY, "name": "Mi Cocina Sin Gluten", "category": "shop"}, [],
                                    [{"source": "web", "text": "Elaboración propia de productos sin gluten. Venta en nuestros locales de Pocitos y Centro.",
                                      "url": "https://micocinasingluten.example"}])),
    ("in", "dietetica", shop(UY, "Dietética Vida Sana", [{"text": "Mucha variedad de productos sin TACC, la dueña asesora muy bien"}])),
    ("in", "panaderia_exclusiva", ({**UY, "name": "Panadería La Espiga", "category": "cafe"},
                                   [{"text": "Todo el local es 100% sin gluten, cocinan solo para celíacos"}], [])),
    ("in", "fabrica_con_venta_directa", ({**AR, "name": "Pastas Don Luis", "category": "shop"}, [],
                                         [{"source": "web", "text": "Fábrica de pastas sin TACC. Venta al público en nuestro local de fábrica, de lunes a sábado.",
                                           "url": "https://pastasdonluis.example"}])),
    ("in", "restaurante_con_opciones", ({**AR, "name": "La Parrilla de Juan", "category": "restaurant"},
                                        [{"text": "Tienen menú sin TACC y avisan en la cocina, pero comparten parrilla"}], [])),
    ("in", "panaderia_que_tambien_da_talleres", ({**UY, "name": "Sin Trigo Panadería", "category": "cafe"}, [],
                                                 [{"source": "social", "text": "Panadería sin TACC. Vendemos panes y facturas en el local. También dictamos talleres de panificación sin gluten.",
                                                   "url": "https://www.instagram.com/sintrigo.panaderia"}])),
    ("in", "almacen_natural", shop(UY, "Almacén Natural Don Pepe", [{"text": "Buen surtido de harinas y galletitas sin gluten"}])),
    # Admin decision 2026-10-13: these three real places stay on the map. A name with "supermarket" / "minimarket" or a brand with
    # several branches does not make a specialised shop general retail.
    ("in", "entresano_supermercado_saludable", shop(
        {**AR, "city": "Córdoba", "address": "Blvd. San Juan 85, Córdoba"}, "EntreSano Healthy Supermarket",
        [{"text": "Mucha variedad de productos sin TACC, ideal para celíacas"}],
        [{"source": "web", "text": "Entresano - Supermercado Saludable. Categorías: Sin Tacc (671), Sin Harina y sin Azúcar (75), Semillas (70).",
          "url": "https://entresano.com/"}])),
    ("in", "minimarket_la_isla", shop(
        {**UY, "city": "Maldonado", "address": "Av. José Batlle y Ordoñez, Maldonado"}, "Minimarket La Isla 24 hours.",
        [{"text": "Tienen de todo sin TACC: empanadas, pizzas, panificados y dulces. Muy recomendable para celíacos"}],
        [{"source": "web", "text": "La Isla es un minimarket abierto las 24 horas en Maldonado: almacén, bebidas, cientos de vinos, más de 1.500 "
                                   "productos sin gluten y cocina propia.", "url": "https://www.laisla247.com/"}])),
    ("in", "la_molienda_tienda_natural", shop(
        {**UY, "source": "manual", "address": "Av. Alfredo Arocena 2014, Montevideo"}, "La Molienda - Carrasco", [],
        [{"source": "web", "text": "La Molienda - Tienda natural online. Frutos secos, sin gluten, sin azúcar, vegano, keto. Productos Sin Gluten en "
                                   "Uruguay: harinas, pastas, snacks, galletitas. 444 artículos.", "url": "https://www.lamolienda.uy/celiaco"}])),
    # Admin decision 2026-10-13: an independent self-service shop whose only gluten-free offer is a shelf is out too.
    ("out", "autoservicio_independiente", shop(UY, "Autoservicio El Trébol", SHELF)),
]


class CallCap:
    """Hard stop on paid calls: the run aborts before the call that would exceed ``limit``."""

    def __init__(self, limit: int):
        self.limit, self.used, self._lock = limit, 0, threading.Lock()

    def spend(self) -> None:
        with self._lock:
            if self.used >= self.limit:
                raise SystemExit(f"HARD CAP: {self.limit} paid call(s) reached; run stopped.")
            self.used += 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old-rev", default="main", help="git rev with the previous RUBRIC (default: main)")
    ap.add_argument("--n", type=int, default=3, help="samples per case and arm")
    ap.add_argument("--only-new", action="store_true", help="skip the OLD arm (cheaper)")
    ap.add_argument("--cases", help="comma-separated labels: run only these cases")
    ap.add_argument("--max-calls", type=int, required=True, help="hard cap on paid calls; the run aborts when reached")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and the estimated cost; make no call")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    wanted = set(args.cases.split(",")) if args.cases else None
    unknown = (wanted or set()) - {label for _, label, _ in CASES}
    if unknown:
        raise SystemExit(f"unknown case(s): {sorted(unknown)}")
    cases = [c for c in CASES if not wanted or c[1] in wanted]
    n_arms = 1 if args.only_new else 2
    planned = len(cases) * n_arms * args.n
    print(f"PLAN: {len(cases)} case(s) x {n_arms} arm(s) x n={args.n} = {planned} call(s) to {MODEL}, "
          f"~US${planned * COST_PER_CALL_USD:.2f}; hard cap {args.max_calls} call(s) (~US${args.max_calls * COST_PER_CALL_USD:.2f})")
    if planned > args.max_calls:
        raise SystemExit(f"the plan ({planned}) exceeds --max-calls ({args.max_calls}): nothing was called")
    if args.dry_run:
        print("dry run: no call made")
        return 0

    settings = get_settings()
    llm = LLMClient(settings.anthropic_api_key, default_model=MODEL)
    agent = ValidatorAgent(None, llm)
    cap = CallCap(args.max_calls)
    arms = [("NEW", NEW_RUBRIC)]
    if not args.only_new:
        arms.insert(0, ("OLD", rubric_at(args.old_rev)))

    failures = 0
    for kind, label, (place, reviews, evidence) in cases:
        prompt = ValidatorAgent._build_user_prompt(place, reviews, None, evidence)
        print(f"\n[{kind}] {label} — {place['name']}")
        for tag, rubric in arms:
            def sample(_):
                cap.spend()
                raw = llm.complete_json(rubric, prompt, model=MODEL)
                return agent._normalize(raw, place, None, reviews=reviews, evidence=evidence)
            with ThreadPoolExecutor(max_workers=3) as ex:
                outs = list(ex.map(sample, range(args.n)))
            verdicts = collections.Counter(v["verdict"] for v in outs)
            statuses = collections.Counter(v["status"] for v in outs)
            confs = [v["confidence"] for v in outs]
            print(f"  {tag}: verdict {dict(verdicts)} | status {dict(statuses)} | confidence {confs}")
            if tag != "NEW":
                continue
            na = verdicts.get(NOT_APPLICABLE, 0)
            print(f"       {outs[0]['reason']}")
            if kind == "out" and na < args.n:
                failures += 1
                print(f"  !! FAIL: out-of-scope place not excluded in {args.n - na}/{args.n}")
            elif kind == "in" and na:
                failures += 1
                print(f"  !! FAIL: an in-scope place was excluded in {na}/{args.n}")
            expected = EXPECT_STATUS.get(label)
            if expected and statuses.get(expected, 0) < args.n:
                failures += 1
                print(f"  !! FAIL: expected status {expected} in every sample (scope must not move the safety verdict)")
            ceiling = MAX_APPROVED.get(label)
            if ceiling is not None and statuses.get("approved", 0) > ceiling:
                failures += 1
                print(f"  !! FAIL: approved in {statuses['approved']}/{args.n}, more than with the previous RUBRIC (at most {ceiling})")
    print(f"\ncalls made: {cap.used} of a cap of {cap.limit}")
    print("RESULT:", "FAIL" if failures else "PASS", f"({failures} failing case(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
