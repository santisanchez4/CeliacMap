"""Live check of the `category_zero` telemetry against the DEPLOYED `chat` function (production): ONE turn.

Cerro Largo has approved shops only (2, in Melo), so a search for cafes there finds no row with its category and 2
without it: the case the telemetry exists for. The turn must return exactly what it returned before the change (no
places, nothing listed); what changed is only `agent_log.result.query`, which is read back separately with the CLI.

It WRITES only what normal chat usage writes: one `agent_log` row and three `chat_usage` counters (the session bucket,
the `ip:` bucket and `global`). The session token starts with `celiac-test-catzero-`. The cleanup SQL is shown and
approved separately (CLAUDE.md, "show the exact command before prod writes").

Run: python db/checks/chat_category_zero_live.py --out db/checks/2026-09-27-chat-category-zero-live-run.json
Uses the public anon key from js/config.js (the browser's). Ground truth (the approved places of the region) is read with
that same key.
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

ROOT = Path(__file__).resolve().parents[2]
CFG = (ROOT / "js" / "config.js").read_text(encoding="utf-8")
BASE = re.search(r'SUPABASE_URL\s*:\s*"([^"]+)"', CFG).group(1).rstrip("/")
KEY = re.search(r'SUPABASE_ANON_KEY\s*:\s*"([^"]+)"', CFG).group(1)
SESSION = "celiac-test-catzero-20260927"
MESSAGE = "hay cafés sin tacc en Cerro Largo?"


def rest_get(path: str):
    req = urllib.request.Request(f"{BASE}/rest/v1/{path}", headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def chat(history: list[dict]) -> dict:
    body = {"messages": history, "session_token": SESSION, "pending_submission": None}
    req = urllib.request.Request(BASE + "/functions/v1/chat", data=json.dumps(body).encode(), headers={
        "apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "application/json", "Origin": "https://celiacmap.org"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    rows = rest_get("places?select=name,category&status=eq.approved&region=eq." + urllib.parse.quote("Cerro Largo") + "&country=eq.Uruguay&limit=500")
    by_category: dict[str, int] = {}
    for row in rows:
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
    print(f"truth: approved places in Cerro Largo = {len(rows)}  by category = {by_category}")
    shop_words = {w.lower() for r in rows for w in re.findall(r"\w{5,}", r["name"])}

    started = datetime.now(timezone.utc)
    data = chat([{"role": "user", "content": MESSAGE}])
    finished = datetime.now(timezone.utc)
    reply = data.get("reply", "")
    places = data.get("places", [])
    checks = {
        "no cafes exist in the region (premise of the case)": by_category.get("cafe", 0) == 0,
        "places is empty, as before the change": places == [],
        "no action, no pending submission": not data.get("action") and not data.get("pending_submission"),
        "the reply lists no place of the region": not any(w in reply.lower() for w in shop_words),
    }
    print(f"\nmessage: {MESSAGE!r}\nreply  : {reply.replace(chr(10), ' / ')[:500]}\nplaces : {places}\nchecks : {checks}")
    print(f"\nrun window (UTC): {started.isoformat()} .. {finished.isoformat()}  (1 turn)")
    passed = all(checks.values())
    print("RESULT:", "PASS" if passed else "FAIL")
    if args.out:
        Path(args.out).write_text(json.dumps({
            "message": MESSAGE, "session": SESSION, "reply": reply, "places": places, "truth_by_category": by_category,
            "checks": checks, "passed": passed, "window": [started.isoformat(), finished.isoformat()],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
