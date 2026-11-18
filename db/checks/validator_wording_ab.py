#!/usr/bin/env python
"""A/B of the «sin TACC» → «sin gluten» wording change in the Validator RUBRIC (2026-11-18) against the real model.

Resolución Conjunta 32/2023 (Argentina) replaces the «sin TACC» label with «libre de gluten» / «SIN GLUTEN». The previous RUBRIC
lowered confidence when a place said «sin gluten» but not «sin TACC». The new one treats the three wordings as equivalent in both
countries and keeps a wording-neutral flag («bajo en gluten», «reducido en gluten»).

Every scenario is run with the SAME evidence in two or three wordings; only the wording changes. Both arms receive the SAME user
prompt; only the system RUBRIC differs (OLD = a git rev, NEW = the working tree).

  python db/checks/validator_wording_ab.py --old-rev main --n 4 --max-calls 160 --dry-run   # plan and cost, no call
  python db/checks/validator_wording_ab.py --old-rev main --n 4 --max-calls 160

Paid calls are never made without the admin asking: --max-calls is mandatory, the plan is printed first and the run aborts
before the call that would exceed the cap. A failed call stops the run; nothing is retried with another model.

Acceptance (after _normalize; counts out of n samples):
  parity     NEW: «sin gluten» / «libre de gluten» get the same verdicts as «sin TACC» in the same scenario
             (approved and gluten_free_100 counts within 1 sample of each other)
  no_rise    NEW «sin TACC» is not approved, nor labelled 100, more often than OLD «sin TACC» (+1 sample of noise)
  ceiling    NEW «sin gluten» is not approved, nor labelled 100, more often than OLD «sin TACC» (+1 sample of noise):
             the change makes «sin gluten» as strong as «sin TACC» was, never stronger
  never      NEVER_APPROVED scenarios are never approved; NEVER_100 scenarios are never gluten_free_100 (any wording)

No production reads or writes: synthetic places, no DB. Uses ANTHROPIC_API_KEY from .env (never printed).
Cost: ~US$0.011 per call (claude-sonnet-4-6: ~2,300 input + ~250 output tokens); 20 cases x 2 arms x n=4 = 160 calls.
"""
from __future__ import annotations

import argparse
import ast
import collections
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.clients.llm import LLMClient, _parse_json  # noqa: E402
from agents.validator_agent import RUBRIC as NEW_RUBRIC, VERDICT_SCHEMA, ValidatorAgent  # noqa: E402
from config.settings import get_settings  # noqa: E402
from validator_kitchen_ab import MODEL, rubric_at  # noqa: E402

COST_PER_CALL_USD = 0.011
UY = {"address": "Av. Italia 3456, Montevideo", "city": "Montevideo", "country": "Uruguay", "geocode_method": "find_place",
      "source": "google_places"}
AR = {"address": "Av. Corrientes 1234, CABA", "city": "Buenos Aires", "country": "Argentina", "geocode_method": "find_place",
      "source": "google_places"}
WORDINGS = {"tacc": "sin TACC", "gluten": "sin gluten", "libre": "libre de gluten"}


def review(text):
    return [{"text": text}]


def web(text, url):
    return [{"source": "web", "text": text, "url": url}]


# scenario -> (wordings to run, builder(w) -> (place, reviews, evidence))
SCENARIOS = {
    "menu_con_aviso": (("tacc", "gluten", "libre"), lambda w: (
        {**AR, "name": "Café Plaza", "category": "cafe"},
        review(f"Tienen carta {w}, avisás que sos celíaco y lo preparan aparte"), [])),
    "exclusivo_redes": (("tacc", "gluten", "libre"), lambda w: (
        {**UY, "name": "Panadería La Espiga", "category": "cafe", "source": "social"}, [],
        [{"source": "social", "text": f"Panadería 100% {w}. Todo lo que elaboramos y vendemos es apto para celíacos.",
          "url": "https://www.instagram.com/laespiga.uy"}])),
    "web_con_protocolo": (("tacc", "gluten"), lambda w: (
        {**AR, "name": "Resto Lo de Ana", "category": "restaurant"}, [],
        web(f"Menú {w} con protocolo para evitar la contaminación cruzada: utensilios y horno separados.", "https://lodeana.example"))),
    "mencion_suelta": (("tacc", "gluten"), lambda w: (
        {**UY, "name": "Bar El Puerto", "category": "restaurant"}, review(f"Rico todo, hay alguna cosa {w}"), [])),
    "dietetica": (("tacc", "gluten"), lambda w: (
        {**UY, "name": "Dietética Vida Sana", "category": "shop"}, review(f"Mucha variedad de productos {w}, la dueña asesora muy bien"), [])),
    "cocina_compartida": (("tacc", "gluten"), lambda w: (
        {**AR, "name": "Pizzería Don Carlos", "category": "restaurant"},
        review(f"Tienen pizzas {w} pero usan el mismo horno que las comunes"), [])),
    "solo_geocode": (("tacc", "gluten"), lambda w: (
        {**AR, "name": "Pastelería Dulce Vida", "category": "cafe", "source": "web", "geocode_method": "address_only",
         "address": "Calle 7 1450, La Plata", "city": "La Plata"}, [],
        web(f"Pastelería con opciones {w} en La Plata.", "https://guia.example/la-plata"))),
    "contradictorio": (("tacc", "gluten"), lambda w: (
        {**UY, "name": "Heladería Polo", "category": "cafe"},
        review(f"Dicen que tienen helados {w}, pero me contaminé y el empleado no sabía nada"), [])),
}
# Controls run in one wording only.
CONTROLS = {
    "bajo_en_gluten": lambda: ({**AR, "name": "Panadería Integral Sol", "category": "cafe"}, [],
                               web("Panes bajos en gluten y reducidos en gluten, ideales para una dieta liviana.", "https://sol.example")),
    "dietas_especiales": lambda: ({**UY, "name": "Restaurante Sabores", "category": "restaurant"},
                                  review("Apto para dietas especiales, muy buena atención"), []),
    # Iteration 4 (admin, 2026-11-18): "bajo / reducido en gluten" does not exist, it has gluten. A place that also sells a real
    # gluten-free line is not discarded for it, but it cooks with gluten: never 100.
    "mixto_bajo_y_sin": lambda: ({**UY, "name": "Panadería Trigal", "category": "cafe"}, [],
                                 web("Línea sin gluten certificada, elaborada en un sector aparte. También vendemos panes reducidos "
                                     "en gluten.", "https://trigal.example")),
}
ALWAYS_DISCARDED = {"bajo_en_gluten"}  # iteration 4: the admin's rule, discarded in every sample
NEVER_APPROVED = {"mencion_suelta", "cocina_compartida", "solo_geocode", "contradictorio", "bajo_en_gluten", "dietas_especiales"}
NEVER_100 = set(SCENARIOS) - {"exclusivo_redes"} | set(CONTROLS)

# Iteration 3 (--set strong): evidence the OLD RUBRIC approves. Iterations 1-2 had no such case, so they could not show whether a
# stricter text stops approving what is approved today. Acceptance adds "keep": a candidate arm approves each case at least as
# often as OLD minus one sample. None of them is an exclusive kitchen, so none may be labelled 100.
STRONG = {
    "certificado": (("tacc", "gluten"), lambda w: (
        {**AR, "name": "Resto Buen Comer", "category": "restaurant"},
        [{"text": f"Soy celíaca y vengo seguido: carta {w} y nunca me pasó nada"},
         {"text": "Te explican cómo cocinan lo apto, muy atentos con los celíacos"}],
        web(f"Restaurante con certificación {w} de la asociación celíaca local. Platos aptos para celíacos elaborados con "
            "protocolo anti-contaminación cruzada.", "https://buencomer.example"))),
    "resenas_celiacos": (("tacc", "gluten"), lambda w: (
        {**UY, "name": "Café Rambla", "category": "cafe"},
        [{"text": f"Celíaca hace 10 años: tienen tortas y sándwiches {w} y los preparan aparte, con utensilios separados"},
         {"text": f"Mi hijo es celíaco y comemos acá cada semana, todo lo {w} viene envuelto y rotulado"},
         {"text": "Muy cuidadosos con la contaminación cruzada, el personal sabe del tema"}], [])),
    "preparacion_dedicada": (("tacc", "gluten"), lambda w: (
        {**AR, "name": "Pizzería La Esquina", "category": "restaurant"},
        [{"text": f"Las pizzas {w} se hacen en un horno aparte y con otra mesada, ideal para celíacos"}],
        web(f"Pizzas {w} elaboradas en un sector exclusivo de la cocina, con horno, mesada y utensilios propios para evitar "
            "la contaminación cruzada.", "https://laesquina.example"))),
}
SETS = {"base": (SCENARIOS, CONTROLS), "strong": (STRONG, {})}

# Iteration 2 (2026-11-18): two candidate texts built from the OLD RUBRIC. Iteration 1 (the working tree's text, arm "NEW")
# made «sin TACC» stronger instead of making «sin gluten» its equal (db/checks/2026-11-18-validator-wording-ab-iter1.md).
OLD_APPROVED = ('Evidencia explícita y clara de que el lugar ofrece opciones sin TACC, con mención directa de "sin TACC", '
                '"sin gluten" certificado, o descripción de protocolo anti-contaminación cruzada.')
APPROVED_TEXT = {
    "B": ('Evidencia explícita y clara de que el lugar ofrece opciones sin gluten, con mención directa de "sin TACC", '
          '"sin gluten" o "libre de gluten", certificación, o descripción de protocolo anti-contaminación cruzada.'),
    "A": ('Evidencia explícita y clara de que el lugar ofrece opciones sin gluten: mención directa de "sin gluten", '
          '"libre de gluten" o "sin TACC" acompañada de certificación, preparación dedicada o protocolo '
          'anti-contaminación cruzada.'),
    # Iteration 4: A kept "sin TACC" stronger in preparacion_dedicada (iteration 3). A2 says outright that no term is stronger.
    "A2": ('Evidencia explícita y clara de que el lugar ofrece opciones sin gluten: mención directa de "sin gluten", '
           '"libre de gluten" o "sin TACC" acompañada de certificación, preparación dedicada o protocolo '
           'anti-contaminación cruzada. Los tres términos pesan igual: ninguno es más fuerte que otro.'),
    # Iteration 5: no wording neutralised the model's own preference for «sin TACC» (iterations 1-4), so the code now shows the
    # model «sin gluten» wherever a text says «sin TACC» (canonical_wording). A3 = A's criterion + the admin's flag.
    "A3": ('Evidencia explícita y clara de que el lugar ofrece opciones sin gluten: mención directa de "sin gluten", '
           '"libre de gluten" o "sin TACC" acompañada de certificación, preparación dedicada o protocolo '
           'anti-contaminación cruzada.'),
}
COMMON_EDITS = (
    ('- Menciona "sin gluten" pero no "sin TACC" (puede ser marketing, no médico)',
     '- Dice "bajo en gluten", "reducido en gluten" o algo similar: no equivale a "sin gluten"'),
    ("vegetarianas/veganas sin mención explícita sin TACC", "vegetarianas/veganas sin mención explícita sin gluten"),
    ('(mención explícita de "sin TACC", reseñas', '(mención explícita de "sin gluten" o "sin TACC", reseñas'),
)


_REDUCED_FLAG = (
    '- Dice "bajo en gluten", "reducido en gluten" o algo similar: eso NO es sin gluten, el producto tiene gluten. '
    'Si es la única oferta para celíacos, el veredicto es "rejected"')
FLAG_TEXT = {
    "A3": _REDUCED_FLAG,
    # Iteration 4 (admin, 2026-11-18): "reducido en gluten" does not exist as a category; it has gluten, end of story.
    "A2": ('- Dice "bajo en gluten", "reducido en gluten" o algo similar: eso NO es sin gluten, el producto tiene gluten. '
           'Si es la única oferta para celíacos, el veredicto es "rejected"'),
}


def variant(old: str, name: str) -> str:
    text = old
    edits = list(COMMON_EDITS)
    if name in FLAG_TEXT:
        edits[0] = (edits[0][0], FLAG_TEXT[name])
    for before, after in [(OLD_APPROVED, APPROVED_TEXT[name])] + edits:
        if text.count(before) != 1:
            raise SystemExit(f"variant {name}: expected one {before[:50]!r} in the OLD RUBRIC")
        text = text.replace(before, after)
    return text


OLD_LINE_RE = re.compile(r"^\s+OLD: status (\{.*?\}) \| level (\{.*?\})")


def old_counts_from_log(path: Path) -> dict:
    """OLD-arm counts of a previous run's log, keyed by (scenario, wording)."""
    found, current = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        head = re.match(r"^(\w+) \[([\w-]+)\] — ", line)
        if head:
            current = (head[1], head[2])
            continue
        m = OLD_LINE_RE.match(line)
        if m and current:
            status, level = ast.literal_eval(m[1]), ast.literal_eval(m[2])
            found[current] = {"approved": status.get("approved", 0), "100": level.get("gluten_free_100", 0), "malformed": 0}
    return found


def build_cases(scenarios=SCENARIOS, controls=CONTROLS):
    cases = []
    for scenario, (wordings, build) in scenarios.items():
        for key in wordings:
            cases.append((scenario, key, build(WORDINGS[key])))
    for scenario, build in controls.items():
        cases.append((scenario, "-", build()))
    return cases


class CallCap:
    """Hard stop on paid calls: the run aborts before the call that would exceed ``limit``."""

    def __init__(self, limit: int):
        self.limit, self.used, self._lock = limit, 0, threading.Lock()

    def spend(self) -> None:
        with self._lock:
            if self.used >= self.limit:
                raise SystemExit(f"HARD CAP: {self.limit} paid call(s) reached; run stopped.")
            self.used += 1


def counts(outs):
    ok = [o for o in outs if o is not None]
    return {"approved": sum(o["status"] == "approved" for o in ok),
            "100": sum(o["safety_level"] == "gluten_free_100" for o in ok),
            "discarded": sum(o["status"] == "discarded" for o in ok),
            "malformed": len(outs) - len(ok)}


def check(results, n, arms, scenarios=SCENARIOS, strong=False):
    """results[(scenario, wording, arm)] = counts; ``arms`` are the candidate arms. Returns failures per arm."""
    fails = {arm: [] for arm in arms}
    never_100 = set(scenarios) if strong else NEVER_100
    for arm in arms:
        for scenario, (wordings, _) in scenarios.items():
            new_t, old_t = results[(scenario, "tacc", arm)], results.get((scenario, "tacc", "OLD"))
            for key in wordings:
                new_w = results[(scenario, key, arm)]
                old_w = results.get((scenario, key, "OLD"))
                if strong and old_w is not None and new_w["approved"] < old_w["approved"] - 1:
                    fails[arm].append(f"keep {scenario}: {key} approved={new_w['approved']} vs OLD {key} {old_w['approved']}")
                for metric in ("approved", "100"):
                    if key != "tacc" and abs(new_w[metric] - new_t[metric]) > 1:
                        fails[arm].append(f"parity {scenario}: {key} {metric}={new_w[metric]} vs tacc {new_t[metric]}")
                    if old_t is not None and new_w[metric] > old_t[metric] + 1:
                        rule = "no_rise" if key == "tacc" else "ceiling"
                        fails[arm].append(f"{rule} {scenario}: {key} {metric}={new_w[metric]} vs OLD tacc {old_t[metric]}")
        for (scenario, key, a), c in results.items():
            if a != arm:
                continue
            if c["malformed"]:
                fails[arm].append(f"malformed {scenario} ({key}): {c['malformed']}/{n} replies were not valid JSON")
            if scenario in NEVER_APPROVED and c["approved"]:
                fails[arm].append(f"never {scenario} ({key}): approved in {c['approved']}/{n}")
            if not strong and scenario in ALWAYS_DISCARDED and c.get("discarded", n) < n:
                fails[arm].append(f"discard {scenario} ({key}): discarded in {c.get('discarded')}/{n}, not in every sample")
            if scenario in never_100 and c["100"]:
                fails[arm].append(f"never {scenario} ({key}): gluten_free_100 in {c['100']}/{n}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old-rev", default="main", help="git rev with the previous RUBRIC (default: main)")
    ap.add_argument("--n", type=int, default=4, help="samples per case and arm")
    ap.add_argument("--arms", default="NEW", help="candidate arms: NEW (working tree) and/or the variants B, A (comma-separated)")
    ap.add_argument("--set", choices=sorted(SETS), default="base", help="base (iterations 1-2) or strong (iteration 3)")
    ap.add_argument("--schema", action="store_true", help="candidate arms ask for VERDICT_SCHEMA (structured outputs); OLD never does")
    ap.add_argument("--old-log", type=Path, action="append", default=[], help="reuse the OLD arm of a previous run's log; OLD runs only for the cases missing there")
    ap.add_argument("--max-calls", type=int, required=True, help="hard cap on paid calls; the run aborts when reached")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and the estimated cost; make no call")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    old_rubric = rubric_at(args.old_rev)
    rubrics = {}
    for arm in args.arms.split(","):
        rubrics[arm] = NEW_RUBRIC if arm == "NEW" else variant(old_rubric, arm)
        if rubrics[arm] == old_rubric:
            raise SystemExit(f"arm {arm} is identical to the OLD RUBRIC: nothing to compare")
    scenarios, controls = SETS[args.set]
    cases = build_cases(scenarios, controls)
    old_known = {}
    for log in args.old_log:
        old_known.update(old_counts_from_log(log))
    old_todo = [c for c in cases if (c[0], c[1]) not in old_known]
    if old_todo:
        raise SystemExit("OLD must come from the logs: the prompts are now built with canonical_wording, which production does not use")
    # canonical_wording makes the «sin TACC» and «sin gluten» prompts of a scenario identical: each prompt is sampled once per arm.
    same_as, seen = {}, {}
    for scenario, key, (place, reviews, evidence) in cases:
        prompt = ValidatorAgent._build_user_prompt(place, reviews, None, evidence)
        same_as[(scenario, key)] = seen.setdefault((scenario, prompt), key)
    unique = sum(1 for (s_, k_), first in same_as.items() if first == k_)
    planned = (unique * len(rubrics) + len(old_todo)) * args.n
    print(f"PLAN: {len(cases)} case(s), {unique} distinct prompt(s), x {len(rubrics)} candidate arm(s) {list(rubrics)} + OLD for {len(old_todo)} case(s) "
          f"(reused from the log: {len(old_known)}), n={args.n} = {planned} call(s) to {MODEL}, ~US${planned * COST_PER_CALL_USD:.2f}; "
          f"hard cap {args.max_calls} call(s) (~US${args.max_calls * COST_PER_CALL_USD:.2f})")
    if planned > args.max_calls:
        raise SystemExit(f"the plan ({planned}) exceeds --max-calls ({args.max_calls}): nothing was called")
    if args.dry_run:
        for scenario, key, (place, _, _) in cases:
            print(f"  {scenario:<20} {key:<7} {place['name']} ({place['country']})"
                  + ("" if (scenario, key) in old_known else "  + OLD"))
        print("dry run: no call made")
        return 0

    settings = get_settings()
    llm = LLMClient(settings.anthropic_api_key, default_model=MODEL)
    agent = ValidatorAgent(None, llm)
    cap = CallCap(args.max_calls)
    results = {(s, k, "OLD"): c for (s, k), c in old_known.items()}
    malformed = []
    for scenario, key, (place, reviews, evidence) in cases:
        prompt = ValidatorAgent._build_user_prompt(place, reviews, None, evidence)
        print(f"\n{scenario} [{key}] — {place['name']}")
        arms = [("OLD", old_rubric)] if (scenario, key) not in old_known else []
        if (scenario, key) in old_known:
            print(f"  OLD (from the log): {old_known[(scenario, key)]}")
        first = same_as[(scenario, key)]
        if first != key:
            for arm in rubrics:
                results[(scenario, key, arm)] = results[(scenario, first, arm)]
            print(f"  same prompt as [{first}]: results reused, no call")
            continue
        for arm, rubric in arms + list(rubrics.items()):
            def sample(_):
                cap.spend()
                schema = VERDICT_SCHEMA if args.schema and arm != "OLD" else None
                text = llm.complete_text(rubric, prompt, model=MODEL, schema=schema)
                try:
                    raw = _parse_json(text)
                except ValueError:  # malformed JSON: counted as a failure, never retried; the raw reply is kept
                    malformed.append((scenario, key, arm, text))
                    return None
                return agent._normalize(raw, place, None, reviews=reviews, evidence=evidence)
            with ThreadPoolExecutor(max_workers=3) as ex:
                outs = list(ex.map(sample, range(args.n)))
            results[(scenario, key, arm)] = counts(outs)
            ok = [o for o in outs if o is not None]
            statuses = collections.Counter(o["status"] for o in ok)
            levels = collections.Counter(o["safety_level"] for o in ok)
            bad = len(outs) - len(ok)
            print(f"  {arm}: status {dict(statuses)} | level {dict(levels)} | confidence {[o['confidence'] for o in ok]}"
                  + (f" | MALFORMED {bad}" if bad else ""))
    for scenario, key, arm, text in malformed:
        print(f"\nMALFORMED REPLY {scenario} [{key}] {arm}:\n{text}")
    fails = check(results, args.n, list(rubrics), scenarios, strong=args.set == "strong")
    for arm, items in fails.items():
        print(f"\n{arm}: {'FAIL' if items else 'PASS'} ({len(items)} failing check(s))")
        for f in items:
            print("  !! FAIL:", f)
    print(f"\ncalls made: {cap.used} of a cap of {cap.limit}")
    print("RESULT:", " · ".join(f"{arm} {'FAIL' if items else 'PASS'}" for arm, items in fails.items()))
    return 1 if all(fails.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
