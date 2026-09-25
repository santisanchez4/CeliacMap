#!/usr/bin/env python
"""A/B of the audit-plan Validator changes (2026-09-24) against the real model.

Plan: docs/plans/PLAN-auditoria-2026-09-24.md, steps 1-2 (prompts.md §32). What only the real model
shows: whether the new evidence block lets a place WITHOUT a gluten-free name reach 100% from its
evidence (Los Leños / Dalbertt / San Felipa), and whether the new "only the evidence in the message,
never the name" paragraph stops the Serendipia-cea / Enharinate failures.

Both arms receive the SAME user prompt (built with the new evidence block); only the system RUBRIC
differs (OLD = a git rev, NEW = the working tree). For NEW it also reports the level AFTER the code
caps (_normalize: Tope A/B/C), which is what would be written.

  python db/checks/validator_audit_ab.py --old-rev main --n 4

Acceptance (NEW arm):
  name-only / prior-knowledge cases   0 "approved" in the raw verdict, and 0 "gluten_free_100" after caps
  exclusive-evidence cases            after caps, every sample is either "gluten_free_100" or carries the
                                      "100% pendiente de confirmación del administrador" flag (it reaches the
                                      admin's 100% queue). Changed 2026-09-25 after the first run: the model keeps
                                      a single social/web source at "celiac_friendly" (rubric: lowest level when
                                      in doubt), in both the OLD and the NEW rubric.
  options-evidence case               0 "gluten_free_100" after caps
  owner-health case                   0 samples mention the owner's health in reasoning/flags/recommendation
                                      after _normalize (the scrub must hold)

No production writes: synthetic places, no DB. Uses ANTHROPIC_API_KEY from .env (never printed).
Cost: ~US$0.01 per call (claude-sonnet-4-6); default 8 cases x 2 arms x n=4 = 64 calls.
"""
from __future__ import annotations

import argparse
import collections
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.clients.llm import LLMClient  # noqa: E402
from agents.validator_agent import _OWNER_HEALTH_RE, PENDING_ADMIN_FLAG, RUBRIC as NEW_RUBRIC  # noqa: E402
from agents.validator_agent import ValidatorAgent  # noqa: E402
from config.settings import get_settings  # noqa: E402
from validator_kitchen_ab import MODEL, rubric_at  # noqa: E402

PLACE = {"address": "Av. 18 de Julio 1234", "city": "Montevideo", "country": "Uruguay",
         "category": "restaurant", "geocode_method": "find_place"}

CASES = [
    # (label, place, reviews, evidence, kind)
    ("leños_like_social_evidence", {**PLACE, "name": "Los Leños", "source": "social"}, [],
     [{"source": "social", "text": "Los Leños | Instagram — Parrilla y pizzas. Todo es sin gluten: cocina 100% sin TACC.",
       "url": "https://instagram.com/loslenos"}], "exclusive"),
    ("dalbertt_like_web_evidence", {**PLACE, "name": "Dalbertt", "source": "web", "category": "cafe"}, [],
     [{"source": "web", "text": "Blog celíaco: Dalbertt es un espacio libre de gluten, no entra harina de trigo.",
       "url": "https://blog.example/dalbertt"}], "exclusive"),
    ("options_evidence", {**PLACE, "name": "Café Central", "source": "social", "category": "cafe"}, [],
     [{"source": "social", "text": "Café Central — Tenemos opciones sin TACC: tostadas y budines aptos.",
       "url": "https://instagram.com/cafecentral"}], "options"),
    ("name_only_gluten_free", {**PLACE, "name": "Sin Gluten Palermo", "source": "google_places"}, [], [], "name-only"),
    ("name_suffix_serendipia", {**PLACE, "name": "Serendipia-cea", "source": "social"}, [], [], "name-only"),
    ("known_chain_no_evidence", {**PLACE, "name": "Enharinate Mendoza", "city": "Mendoza", "country": "Argentina",
                                 "source": "google_places"}, [], [], "name-only"),
    ("owner_health_in_note", {**PLACE, "name": "Pan Justo", "source": "user", "category": "cafe"}, [],
     [{"source": "user", "text": "La dueña es celíaca, así que cuidan mucho todo. Tienen menú sin TACC.", "url": None}],
     "owner-health"),
    ("strong_reviews_regression", {**PLACE, "name": "Panadería La Espiga", "source": "google_places", "category": "cafe"},
     [{"text": "Todo el local es 100% sin gluten, certificado por ACELU; cocinan solo para celíacos"},
      {"text": "Mi hija es celíaca y comemos tranquilos, no entra nada con gluten a esa cocina"}], [], "exclusive"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old-rev", default="main", help="git rev with the previous RUBRIC (default: main)")
    ap.add_argument("--n", type=int, default=4, help="samples per case and arm")
    ap.add_argument("--only-new", action="store_true", help="skip the OLD arm (cheaper)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    llm = LLMClient(settings.anthropic_api_key, default_model=MODEL)
    agent = ValidatorAgent(None, llm)
    arms = [("NEW", NEW_RUBRIC)]
    if not args.only_new:
        arms.insert(0, ("OLD", rubric_at(args.old_rev)))

    failures = 0
    for label, place, reviews, evidence, kind in CASES:
        prompt = ValidatorAgent._build_user_prompt(place, reviews, None, evidence)
        print(f"\n[{kind}] {label}")
        for tag, rubric in arms:
            def sample(_):
                raw = llm.complete_json(rubric, prompt, model=MODEL)
                return raw, agent._normalize(raw, place, None, reviews=reviews, evidence=evidence)
            with ThreadPoolExecutor(max_workers=4) as ex:
                outs = list(ex.map(sample, range(args.n)))
            raw_verdicts = collections.Counter(str(r.get("verdict")) for r, _ in outs)
            raw_levels = collections.Counter(str(r.get("safety_level")) for r, _ in outs)
            final_levels = collections.Counter(v["safety_level"] for _, v in outs)
            flagged = sum(1 for _, v in outs if PENDING_ADMIN_FLAG in v["flags"])
            print(f"  {tag}: verdict {dict(raw_verdicts)} | raw level {dict(raw_levels)} | after caps {dict(final_levels)}"
                  f" | admin 100% flag {flagged}/{args.n}")
            if tag != "NEW":
                continue
            hundred = final_levels.get("gluten_free_100", 0)
            bad = None
            if kind == "name-only" and (raw_verdicts.get("approved", 0) or hundred):
                bad = "a name alone produced approved / 100%"
            elif kind == "options" and hundred:
                bad = "options evidence produced 100%"
            elif kind == "exclusive":
                reach = sum(1 for _, v in outs
                            if v["safety_level"] == "gluten_free_100" or PENDING_ADMIN_FLAG in v["flags"])
                if reach < args.n:
                    bad = f"exclusivity evidence neither 100% nor in the admin queue in {args.n - reach}/{args.n}"
            elif kind == "owner-health":
                leaks = sum(1 for _, v in outs if any(
                    _OWNER_HEALTH_RE.search(t or "") for t in [v["reason"], v["recommendation"], *v["flags"]]))
                if leaks:
                    bad = f"owner health leaked after the scrub in {leaks}/{args.n}"
            if bad:
                failures += 1
                print(f"  !! FAIL: {bad}")
    print("\nRESULT:", "FAIL" if failures else "PASS", f"({failures} failing case(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
