"""Live replay of the department / province searches against the DEPLOYED `chat` function (production).

It WRITES only what normal chat usage writes: one `agent_log` row per turn and `chat_usage` counters. It never
submits a report or a suggestion (every message is a search). Session tokens all start with `celiac-test-region-`,
so `chat_usage` cleanup can target them; the run window is printed for the `agent_log` cleanup (see CLAUDE.md,
"show the exact command before prod writes"; the cleanup SQL is shown and approved separately).

Run: python db/checks/chat_region_live.py --out db/checks/2026-09-26-chat-region-live-run.json
Uses the public anon key from js/config.js (the browser's). Each reply is checked against the database itself
(approved places of the region, read with the same anon key), not only against what the model said.

Scenarios: the real conversation (Fraile Muerto -> y en cerro largo? -> Melo), "provincia de Buenos Aires",
"Córdoba", and "Maldonado" (its city has 1 place and its department 16, so it shows the city-first ordering that
Córdoba cannot: every approved Córdoba place is in the capital today).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
CFG = (ROOT / "js" / "config.js").read_text(encoding="utf-8")
BASE = re.search(r'SUPABASE_URL\s*:\s*"([^"]+)"', CFG).group(1).rstrip("/")
KEY = re.search(r'SUPABASE_ANON_KEY\s*:\s*"([^"]+)"', CFG).group(1)
PREFIX = "celiac-test-region-"
MELO = {"EMPATIA GLUTEN FREE", "Gluten Free | Sandra | Productos"}
NEGATION = re.compile(r"\b(no|ningun[oa]?|sin|nada)\b", re.I)
EXISTENCE = re.compile(r"\b(hay|tengo|tenemos|encontr\w+|confirmad\w+|\d+\s+(lugares|locales|espacios))\b", re.I)
LIST_ITEM = re.compile(r"^\s*(?:[•\-*]|\d+[.)])\s+(.+)$", re.M)


def rest_get(path: str):
    req = urllib.request.Request(f"{BASE}/rest/v1/{path}", headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def truth(region: str, country: str) -> set[str]:
    rows = rest_get(f"places?select=id&status=eq.approved&region=eq.{urllib.parse.quote(region)}&country=eq.{country}&limit=500")
    return {r["id"] for r in rows}


def chat(history: list[dict], session: str) -> dict:
    body = {"messages": history, "session_token": session, "pending_submission": None}
    req = urllib.request.Request(BASE + "/functions/v1/chat", data=json.dumps(body).encode(), headers={
        "apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "application/json", "Origin": "https://celiacmap.org"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def origin_claims(reply: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", reply)
    return [s for s in sentences if re.search(r"fraile muerto", s, re.I) and EXISTENCE.search(s) and not NEGATION.search(s)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    cerro_largo = truth("Cerro Largo", "Uruguay")
    buenos_aires = truth("Buenos Aires", "Argentina")
    caba = truth("Ciudad Autónoma de Buenos Aires", "Argentina")
    cordoba = truth("Córdoba", "Argentina")
    maldonado = truth("Maldonado", "Uruguay")
    print(f"truth: Cerro Largo {len(cerro_largo)}, Buenos Aires {len(buenos_aires)}, CABA {len(caba)}, "
          f"Córdoba {len(cordoba)}, Maldonado {len(maldonado)}")

    started = datetime.now(timezone.utc)
    results: list[dict] = []

    def turn(label: str, history: list[dict], message: str, session: str, checks) -> dict:
        history.append({"role": "user", "content": message})
        data = chat(history, session)
        places = data.get("places", [])
        verdicts = {name: bool(fn(data.get("reply", ""), places)) for name, fn in checks.items()}
        record = {"label": label, "session": session, "message": message, "reply": data.get("reply"),
                  "places": [{"name": p["name"], "city": p.get("city")} for p in places],
                  "ids": [p["id"] for p in places], "action": data.get("action"), "checks": verdicts,
                  "passed": all(verdicts.values()) and not data.get("action")}
        results.append(record)
        print(f"\n[{'PASS' if record['passed'] else 'FAIL'}] {label}: {message!r}")
        print("  reply :", (data.get("reply") or "").replace("\n", " / ")[:420])
        print("  places:", [(p["name"][:28], p.get("city")) for p in places])
        print("  checks:", verdicts)
        history.append({"role": "assistant", "content": data["reply"]})
        return record

    # --- the real conversation (one session, the history grows like the widget's) -----------------
    s = PREFIX + uuid4().hex[:10] + "-conversation"
    h: list[dict] = []
    turn("1 widened (Fraile Muerto)", h,
         "que locales puedo visitar para conseguir productos libre de gluten cerca de Fraile Muerto Cerro Largo?", s, {
             "no places listed as datos": lambda r, p: p == [],
             "names Cerro Largo and Melo": lambda r, p: "cerro largo" in r.lower() and "melo" in r.lower(),
             "no place claimed in Fraile Muerto": lambda r, p: not origin_claims(r),
             "no list, no place names": lambda r, p: not LIST_ITEM.search(r) and "empatia" not in r.lower() and "sandra" not in r.lower(),
         })
    turn("2 region asked outright", h, "y en cerro largo?", s, {
        "the two places of Melo": lambda r, p: {x["name"] for x in p} == MELO,
        "all in Melo": lambda r, p: all(x.get("city") == "Melo" for x in p),
        "reply names both": lambda r, p: "empatia" in r.lower() and "sandra" in r.lower(),
        "does not mention Fraile Muerto": lambda r, p: "fraile muerto" not in r.lower(),
    })
    turn("3 Melo", h, "veo en el mapa 2 lugares en Melo", s, {
        "the two places of Melo": lambda r, p: {x["name"] for x in p} == MELO,
        "reply names both": lambda r, p: "empatia" in r.lower() and "sandra" in r.lower(),
    })

    # --- a province with its marker ---------------------------------------------------------------
    turn("4 provincia de Buenos Aires", [], "lugares sin tacc en la provincia de Buenos Aires", PREFIX + uuid4().hex[:10] + "-bsas", {
        "8 places": lambda r, p: len(p) == 8,
        "all in the province (region Buenos Aires)": lambda r, p: {x["id"] for x in p} <= buenos_aires,
        "none is a CABA place": lambda r, p: not ({x["id"] for x in p} & caba),
    })

    # --- a province typed as the city --------------------------------------------------------------
    turn("5 Córdoba", [], "algo sin tacc en Córdoba", PREFIX + uuid4().hex[:10] + "-cordoba", {
        "8 places": lambda r, p: len(p) == 8,
        "all in the province (region Córdoba)": lambda r, p: {x["id"] for x in p} <= cordoba,
        "the capital's places (city Córdoba) come first": lambda r, p: [x.get("city") for x in p][:min(len(p), 3)] == ["Córdoba"] * min(len(p), 3),
    })

    # --- the ordering Córdoba cannot show ----------------------------------------------------------
    turn("6 Maldonado (city-first ordering)", [], "algo sin tacc en Maldonado?", PREFIX + uuid4().hex[:10] + "-maldonado", {
        "8 places": lambda r, p: len(p) == 8,
        "all in the department (region Maldonado)": lambda r, p: {x["id"] for x in p} <= maldonado,
        "the place of the city of Maldonado comes first": lambda r, p: bool(p) and (p[0].get("city") or "").lower() == "maldonado",
    })

    finished = datetime.now(timezone.utc)
    failing = [r["label"] for r in results if not r["passed"]]
    print(f"\nrun window (UTC): {started.isoformat()} .. {finished.isoformat()}  ({len(results)} turns)")
    print("sessions:", sorted({r["session"] for r in results}))
    print("RESULT:", "PASS" if not failing else f"FAIL {failing}")
    if args.out:
        Path(args.out).write_text(json.dumps({"started": started.isoformat(), "finished": finished.isoformat(), "results": results},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
