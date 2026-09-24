#!/usr/bin/env python
"""A/B of the Validator RUBRIC change for community kitchen declarations, against the real model.

Spec: docs/superpowers/specs/2026-09-24-kitchen-info-design.md, section 10. The unit tests prove the
code caps; only the real model shows whether the RUBRIC text keeps a declaration from producing
`approved` / `gluten_free_100` on its own. Both arms receive the SAME user prompt (built with the
new claims block); only the system RUBRIC differs (OLD = a git rev, NEW = the working tree).

  python db/checks/validator_kitchen_ab.py --old-rev main --n 4

Acceptance (NEW arm, raw model output BEFORE the code caps):
  claim-only cases      no sample is "approved" and none is "gluten_free_100"
  claim-only-low cases  no sample is "gluten_free_100"
  regression cases      (no claims) reported side by side; a human compares OLD vs NEW

No production writes: synthetic places, no DB. Uses ANTHROPIC_API_KEY from .env (never printed).
Cost: ~US$0.01 per call (claude-sonnet-4-6); default 8 cases x 2 arms x n=4 = 64 calls.
"""
from __future__ import annotations

import argparse
import ast
import collections
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agents.clients.llm import LLMClient  # noqa: E402
from agents.validator_agent import RUBRIC as NEW_RUBRIC  # noqa: E402
from agents.validator_agent import ValidatorAgent  # noqa: E402
from config.settings import get_settings  # noqa: E402

MODEL = "claude-sonnet-4-6"  # the Validator's documented model

BASE = {
    "name": "Panadería La Espiga",
    "address": "Av. Corrientes 1234, Rosario",
    "city": "Rosario",
    "country": "Argentina",
    "category": "cafe",
    "source": "user",
    "geocode_method": "find_place",
}
# owner_celiac is deliberately not part of any case: it never reaches the model (a named third party's
# health condition would otherwise be able to land in publicly readable places columns).
EXCLUSIVE = {"kitchen_exclusive": True, "celiac_prep": None}
SHARED = {"kitchen_exclusive": False, "celiac_prep": "shared_kitchen"}
SEPARATE = {"kitchen_exclusive": False, "celiac_prep": "separate_kitchen"}
# A place NOT suggested by the community: Tope A (source='user') does not apply, so only the RUBRIC
# text stands between a claim and a 100% level. This is the path the code caps do not cover.
GOOGLE = {**BASE, "source": "google_places"}
WEAK_REVIEWS = [
    {"text": "Muy rico todo, lindo ambiente y buena atención"},
    {"text": "Buena atención, volveremos"},
]

# (label, place, reviews, claims, kind)
CASES = [
    ("exclusive_claim_only", BASE, [], [EXCLUSIVE], "claim-only"),
    ("contradicting_claims", BASE, [], [EXCLUSIVE, SHARED], "claim-only"),
    ("shared_kitchen", BASE, [], [SHARED], "claim-only-low"),
    ("separate_kitchen", BASE, [], [SEPARATE], "claim-only-low"),
    ("google_exclusive_claim_only", GOOGLE, [], [EXCLUSIVE], "claim-only"),
    ("google_exclusive_claim_weak_reviews", GOOGLE, WEAK_REVIEWS, [EXCLUSIVE], "claim-only"),
    ("no_claims_neutral", {**BASE, "name": "Restaurante El Sol"}, [], [], "regression"),
    ("no_claims_named_gluten_free", {**GOOGLE, "name": "Panadería Sin Gluten Rosario"}, [], [], "regression"),
    (
        "no_claims_strong_evidence",
        {**GOOGLE, "name": "Panadería Sin Gluten Rosario"},
        [
            {"text": "Todo el local es 100% sin gluten, certificado por ACELA; cocinan solo para celíacos"},
            {"text": "Mi hija es celíaca y comemos tranquilos, no entra nada con gluten a esa cocina"},
        ],
        [],
        "regression",
    ),
]


def rubric_at(rev: str) -> str:
    src = subprocess.run(
        ["git", "show", f"{rev}:agents/validator_agent.py"],
        cwd=ROOT, capture_output=True, encoding="utf-8", check=True,
    ).stdout
    m = re.search(r'RUBRIC = """\\\n(.*?)"""', src, re.DOTALL)
    return ast.literal_eval('"""\\\n' + m.group(1) + '"""')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old-rev", default="main", help="git rev with the previous RUBRIC (default: main)")
    ap.add_argument("--n", type=int, default=4, help="samples per case and arm")
    ap.add_argument("--only-new", action="store_true", help="skip the OLD arm (cheaper)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    llm = LLMClient(settings.anthropic_api_key, default_model=MODEL)
    arms = [("NEW", NEW_RUBRIC)]
    if not args.only_new:
        arms.insert(0, ("OLD", rubric_at(args.old_rev)))

    def sample(rubric: str, prompt: str) -> tuple[str, str]:
        raw = llm.complete_json(rubric, prompt, model=MODEL)
        return str(raw.get("verdict", "?")), str(raw.get("safety_level", "?"))

    failures = 0
    for label, place, reviews, claims, kind in CASES:
        prompt = ValidatorAgent._build_user_prompt(place, reviews, claims)
        print(f"\n[{kind}] {label}")
        for tag, rubric in arms:
            with ThreadPoolExecutor(max_workers=4) as ex:
                outs = list(ex.map(lambda _: sample(rubric, prompt), range(args.n)))
            verdicts = collections.Counter(v for v, _ in outs)
            levels = collections.Counter(s for _, s in outs)
            approved = verdicts.get("approved", 0)
            hundred = levels.get("gluten_free_100", 0)
            print(f"  {tag}: verdict {dict(verdicts)} | safety {dict(levels)}")
            if tag == "NEW":
                bad = (kind == "claim-only" and (approved or hundred)) or (kind == "claim-only-low" and hundred)
                if bad:
                    failures += 1
                    print(f"  !! FAIL: NEW rubric let a declaration alone produce approved={approved} / 100%={hundred}")
    print("\nRESULT:", "FAIL" if failures else "PASS", f"({failures} failing case(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
