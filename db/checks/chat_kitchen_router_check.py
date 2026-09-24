#!/usr/bin/env python
"""Router check for the kitchen declarations, against the real model (no production writes).

Replays the exact production router call (same model, same system prompt from prompts.ts, same
user-message format as buildRouterUserMessage) over ES/EN messages and reports, per case, how
many of N samples matched the expected fields. The point is the two failure modes a structural
test cannot see:
  over-extraction   "tienen opciones sin gluten" must NOT become cocina_exclusiva
  lost draft        "no sé" as the answer to the kitchen question must be cocina_respuesta=true and
                    must NOT be classified fuera_de_alcance (that would drop the person's draft)

  python db/checks/chat_kitchen_router_check.py --n 8

Acceptance: every "must-not-infer" case 100% (n/n); every other case >= 90%.
Cost: ~US$0.001 per call (claude-haiku-4-5). Uses ANTHROPIC_API_KEY from .env (never printed).
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from chat_prompt_ab import MODEL, load_prompts  # noqa: E402

KITCHEN_Q = (
    'Perfecto: Pan Justo, Corrientes 100, Rosario, Argentina, con tu comentario "muy buena atención". '
    "Antes de enviarlo, si sabés: ¿la cocina es exclusivamente sin gluten? Si no lo es, ¿cómo preparan lo "
    "apto para celíacos (cocina separada, preparación aparte o misma cocina)? ¿El dueño o la dueña es "
    'celíaco/a? Podés decir "no sé" o "dale" para enviarlo así.'
)
DRAFT = [
    {"role": "user", "content": "quiero recomendar Pan Justo en Rosario, muy buena atención"},
    {"role": "assistant", "content": KITCHEN_Q},
]

# (label, history-before-the-last-user-message, last user message, expected subset, must_not_infer)
CASES = [
    ("answers both", DRAFT, "sí, es todo sin gluten y la dueña es celíaca",
     {"cocina_exclusiva": "si", "dueno_celiaco": "si", "cocina_respuesta": True}, False),
    ("'no sé' is an answer, not out of scope", DRAFT, "no sé",
     {"cocina_respuesta": True, "cocina_exclusiva": None, "preparacion_celiaca": None, "dueno_celiaco": None}, True),
    ("'no sé, dale' confirms", DRAFT, "no sé, dale",
     {"cocina_respuesta": True, "confirma_envio": True, "cocina_exclusiva": None}, True),
    ("separate kitchen", DRAFT, "cocinan de todo pero tienen cocina separada para celíacos",
     {"cocina_exclusiva": "no", "preparacion_celiaca": "cocina_separada", "cocina_respuesta": True}, False),
    ("same kitchen, no separation", DRAFT, "usan la misma cocina para todo, sin separar nada",
     {"cocina_exclusiva": "no", "preparacion_celiaca": "misma_cocina", "cocina_respuesta": True}, False),
    ("separate prep, same kitchen", DRAFT, "cocinan también con gluten, pero preparan aparte con utensilios propios",
     {"cocina_exclusiva": "no", "preparacion_celiaca": "preparacion_aparte"}, False),
    ("owner is not celiac", DRAFT, "el dueño no es celíaco",
     {"dueno_celiaco": "no", "cocina_respuesta": True}, False),
    ("no context: 'opciones sin gluten' is NOT exclusive", [], "quiero recomendar Café Sol en Salta, tienen opciones sin gluten muy ricas",
     {"cocina_exclusiva": None, "preparacion_celiaca": None, "dueno_celiaco": None, "cocina_respuesta": False}, True),
    ("no context: 'pastas sin TACC' is NOT exclusive", [], "quiero recomendar Lo de Flor en Fray Bentos, hacen pastas sin TACC",
     {"cocina_exclusiva": None, "dueno_celiaco": None, "cocina_respuesta": False}, True),
    ("no context: praise only", [], "quiero recomendar Café Sol en Salta, excelente atención y muy ricos los postres",
     {"cocina_exclusiva": None, "dueno_celiaco": None, "cocina_respuesta": False}, True),
    ("no context: volunteered separate kitchen", [], "quiero recomendar Pan Justo en Rosario: cocinan de todo pero tienen una cocina separada para celíacos",
     {"cocina_exclusiva": "no", "preparacion_celiaca": "cocina_separada", "cocina_respuesta": False}, False),
    ("no context: 100% and owner", [], "quiero recomendar La Espiga en La Plata, es 100% sin gluten y la dueña es celíaca",
     {"cocina_exclusiva": "si", "dueno_celiaco": "si", "cocina_respuesta": False}, False),
    ("english", [], "I'd like to recommend Green Bakery in Mendoza, everything there is gluten-free",
     {"cocina_exclusiva": "si", "idioma": "en"}, False),
]


def router_message(history: list[dict], last: str) -> str:
    full = history + [{"role": "user", "content": last}]
    dumps = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))  # noqa: E731 — like JSON.stringify
    return "\n".join(["Historial reciente (más nuevo al final):", dumps(full), "", f"Último mensaje del usuario: {dumps(last)}"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--rev", default="WORKTREE", help="prompts.ts source: a git rev or WORKTREE (default)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    import anthropic
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    system = load_prompts(args.rev)["ROUTER_PROMPT"]

    def call(history, last):
        msg = client.messages.create(model=MODEL, max_tokens=400, system=system,
                                     messages=[{"role": "user", "content": router_message(history, last)}])
        text = msg.content[0].text
        try:
            return json.loads(text[text.index("{"): text.rindex("}") + 1])
        except ValueError:
            return {}

    failures = 0
    for label, history, last, expected, strict in CASES:
        with ThreadPoolExecutor(max_workers=4) as ex:
            outs = list(ex.map(lambda _: call(history, last), range(args.n)))
        ok = [all(o.get(k) == v for k, v in expected.items()) for o in outs]
        lost = sum(1 for o in outs if o.get("modulo") == "fuera_de_alcance" and history)
        need = args.n if strict else max(1, int(args.n * 0.9 + 0.999))
        verdict = "PASS" if sum(ok) >= need and lost == 0 else "FAIL"
        failures += verdict == "FAIL"
        print(f"[{verdict}] {sum(ok)}/{args.n} {'(must not infer) ' if strict else ''}{label}"
              + (f"  !! {lost} classified fuera_de_alcance" if lost else ""))
        if verdict == "FAIL":
            for o, good in zip(outs, ok):
                if not good:
                    print("      got:", {k: o.get(k) for k in ["modulo", *expected]})
                    break
    print("\nRESULT:", "FAIL" if failures else "PASS", f"({failures} failing case(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
