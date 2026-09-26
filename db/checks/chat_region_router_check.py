#!/usr/bin/env python
"""Router measurement for department / province searches, against the real model (no production writes).

Replays the exact production router call (same model, same system prompt from prompts.ts, same
user-message format as buildRouterUserMessage) over messages that name a Uruguayan department or an
Argentine province, and prints, per message, how the N samples split over the fields the region
search reads: ciudad, zona, pais, category. It is a MEASUREMENT, not a gate: the Edge Function's
region fallback (detectRegion) decides what to do with each shape, so what matters is which shapes
the router actually produces (a department in `ciudad`, in `zona`, or nowhere).

  python db/checks/chat_region_router_check.py --n 8

No production writes. Cost: ~US$0.001 per call (claude-haiku-4-5). Uses ANTHROPIC_API_KEY from .env
(never printed).
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from chat_kitchen_router_check import router_message  # noqa: E402
from chat_prompt_ab import MODEL, load_prompts  # noqa: E402

# The first turn of the real conversation and the reply the bot gave (agent_log 2026-09-25).
FRAILE_HISTORY = [
    {"role": "user", "content": "que locales puedo visitar para conseguir productos libre de gluten cerca de Fraile Muerto Cerro Largo?"},
    {"role": "assistant", "content": "Por ahora no tengo lugares confirmados cerca de Fraile Muerto. Si conocés alguno sin TACC ahí, contame y lo sumamos para revisión."},
]

# (label, history before the last user message, last user message)
CASES = [
    ("Entre Ríos", [], "hay lugares sin tacc en Entre Ríos?"),
    ("Maldonado", [], "algo sin tacc en Maldonado?"),
    ("provincia de Córdoba", [], "lugares sin tacc en la provincia de Córdoba"),
    ("provincia de Buenos Aires", [], "lugares sin tacc en la provincia de Buenos Aires"),
    ("Fraile Muerto Cerro Largo", [],
     "que locales puedo visitar para conseguir productos libre de gluten cerca de Fraile Muerto Cerro Largo?"),
    ("y en cerro largo? (follow-up)", FRAILE_HISTORY, "y en cerro largo?"),
]

FIELDS = ("modulo", "ciudad", "zona", "pais", "category")


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

    print(f"model={MODEL}  prompts={args.rev}  N={args.n}")
    for label, history, last in CASES:
        with ThreadPoolExecutor(max_workers=4) as ex:
            outs = list(ex.map(lambda _: call(history, last), range(args.n)))
        shapes = collections.Counter(tuple(o.get(f) for f in FIELDS) for o in outs)
        print(f"\n[{label}]  {last!r}")
        for shape, count in shapes.most_common():
            print(f"   {count}/{args.n}  " + "  ".join(f"{f}={v!r}" for f, v in zip(FIELDS, shape)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
