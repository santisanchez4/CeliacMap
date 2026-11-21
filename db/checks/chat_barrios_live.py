"""Live check of the barrio search (chat v29) against the DEPLOYED `chat` function (production), 2026-11-21.

Five single-message search turns with ONE fixed session token, so the cleanup can target it. It writes only what normal
chat usage writes: one `agent_log` row per turn and the `chat_usage` counters (session, ip, global). No report or
suggestion is ever submitted. ~10 Haiku calls (router + redactor per turn). The cleanup SQL is shown and approved apart.

Run: python db/checks/chat_barrios_live.py --out db/checks/2026-11-21-chat-barrios-live-run.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = (ROOT / "js" / "config.js").read_text(encoding="utf-8")
BASE = re.search(r'SUPABASE_URL\s*:\s*"([^"]+)"', CFG).group(1).rstrip("/")
KEY = re.search(r'SUPABASE_ANON_KEY\s*:\s*"([^"]+)"', CFG).group(1)
SESSION = "celiac-test-barrios-v29-20261121"
TURNS = [
    "dime un lugar para cenar en Ciudad Vieja Montevideo",
    "lugares sin gluten en Pocitos",
    "dónde comer en Palermo, Buenos Aires",
    "un restaurante en Belgrano",
    "algo sin gluten en Malvín Alto",
]


def chat(message: str) -> dict:
    body = {"messages": [{"role": "user", "content": message}], "session_token": SESSION, "pending_submission": None}
    req = urllib.request.Request(BASE + "/functions/v1/chat", data=json.dumps(body).encode(), headers={
        "apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "application/json", "Origin": "https://celiacmap.org"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    started = datetime.now(timezone.utc).isoformat()
    results = []
    for message in TURNS:
        try:
            response = chat(message)
        except Exception as exc:  # noqa: BLE001 — report, never retry
            response = {"error": str(exc)}
        results.append({"message": message, "response": response})
        print(f"\n=== {message}\n{response.get('reply') or response}")
        print("places:", [p.get("name") for p in response.get("places") or []])
    finished = datetime.now(timezone.utc).isoformat()
    print(f"\nwindow: {started} .. {finished}")
    if args.out:
        Path(args.out).write_text(json.dumps({"session": SESSION, "started": started, "finished": finished,
                                              "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
