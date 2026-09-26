#!/usr/bin/env python
"""Redactor measurement for department searches, against the real model (no production writes).

Option A of the department search changes what the redactor RECEIVES, not its prompt: when a city gave nothing
but the router named its department, <datos> stays empty and <datos_cercanos> carries "Cerro Largo (Melo)" and
a count; when the department is asked for outright, its places are <datos>. This replays the real conversation
(agent_log 2026-09-25) through the real code (chat_region_messages.ts builds the messages with searchPlacesForChat
and buildResponderUserMessage) and the real RESPONDER_PROMPT, N samples per shape, and counts:

  W  widened ("cerca de Fraile Muerto Cerro Largo")
       where     the reply says the places are in Cerro Largo, in Melo
       origin    a sentence that says there ARE places in / near Fraile Muerto (must be 0)
       names     it lists or names a place although <datos> is empty (must be 0)
  R  the department asked outright ("y en cerro largo?"), <datos> = the two places of Melo
       where     both places named, in Melo, in Cerro Largo
       origin    it mentions Fraile Muerto at all (must be 0)
       names     a listed item that is not one of the two places in <datos> (must be 0)
  B0 the control: what production sent for turn 1 before the change (nothing found, no nearby).

Acceptance (fixed before the run): origin = 0 and names = 0 in every shape; where >= 90%.
`cerca` (the reply says the places are "near") is reported, not judged: it comes from RESPONDER_PROMPT's own
example ("Cerca hay 3 en Villa Crespo") and the 2c / examples contradiction is deferred to the next prompt change.

  python db/checks/chat_region_redactor_check.py --n 16

Reads the two public rows of Melo with the anon key from js/config.js (read-only, like the browser). No writes.
Cost: ~US$0.005 per call. Uses ANTHROPIC_API_KEY from .env (never printed).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from chat_prompt_ab import MODEL, load_prompts, sentence_with  # noqa: E402

FIELDS = ("name,address,city,country,category,safety_level,rating,user_ratings_total,opening_hours,website,phone,"
          "lat,lng,vote_count,id,community_warning_at")
NEGATION = re.compile(r"\b(no|ningun[oa]?|sin|nada)\b", re.I)
EXISTENCE = re.compile(r"\b(hay|tengo|tenemos|encontr\w+|confirmad\w+|\d+\s+(lugares|locales|espacios))\b", re.I)
LIST_ITEM = re.compile(r"^\s*(?:[•\-*]|\d+[.)])\s+(.+)$", re.M)


def fixture_rows() -> list[dict]:
    cfg = (ROOT / "js" / "config.js").read_text(encoding="utf-8")
    url = re.search(r'SUPABASE_URL\s*:\s*"([^"]+)"', cfg).group(1).rstrip("/")
    key = re.search(r'SUPABASE_ANON_KEY\s*:\s*"([^"]+)"', cfg).group(1)
    req = urllib.request.Request(
        f"{url}/rest/v1/places?select={FIELDS}&status=eq.approved&city=ilike.*Melo*&country=eq.Uruguay",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def build_messages(rows: list[dict]) -> dict[str, dict]:
    out = subprocess.run(["deno", "run", "--no-lock", "--no-check", "-A", str(ROOT / "db/checks/chat_region_messages.ts")],
                         input=json.dumps(rows), capture_output=True, encoding="utf-8", check=True).stdout
    return {m["label"]: m for m in json.loads(out.strip().splitlines()[-1])}


def origin_claims(reply: str) -> list[str]:
    """Sentences that say there ARE places in / near Fraile Muerto (a negated mention is fine)."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", reply)
    return [s for s in sentences if re.search(r"fraile muerto", s, re.I) and EXISTENCE.search(s) and not NEGATION.search(s)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=16)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    rows = fixture_rows()
    names = [r["name"] for r in rows]
    assert len(rows) == 2, f"expected the 2 places of Melo, got {names}"
    messages = build_messages(rows)
    assert messages["W"]["plan"] == "fallback" and messages["R"]["plan"] == "region", messages
    assert "<datos>[]</datos>" in messages["W"]["message"] and "Cerro Largo (Melo)" in messages["W"]["message"]
    print(f"model={MODEL}  N={args.n}  places in <datos> for R: {names}")
    print("W message:", messages["W"]["message"].replace("\n", " | ")[:330])

    import anthropic
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    system = load_prompts("WORKTREE")["RESPONDER_PROMPT"]

    def call(msg: str) -> str:
        r = client.messages.create(model=MODEL, max_tokens=700, system=system, messages=[{"role": "user", "content": msg}])
        return "".join(b.text for b in r.content if b.type == "text")

    def judge_w(reply: str) -> dict:
        low = reply.lower()
        return {"where": "cerro largo" in low and "melo" in low, "origin": bool(origin_claims(reply)),
                "names": bool(LIST_ITEM.search(reply)) or "**" in reply or any(n.split()[0].lower() in low for n in ("empatia", "sandra")),
                "cerca": "cerca" in low}

    def judge_r(reply: str) -> dict:
        low = reply.lower()
        items = LIST_ITEM.findall(reply)
        stray = [i for i in items if not any(part.lower() in i.lower() for part in ("empatia", "sandra"))]
        return {"where": all(w in low for w in ("empatia", "sandra", "melo", "cerro largo")),
                "origin": "fraile muerto" in low, "names": bool(stray), "cerca": "cerca" in low}

    def judge_b0(reply: str) -> dict:
        low = reply.lower()
        return {"where": "cerro largo" in low and "melo" in low, "origin": bool(origin_claims(reply)),
                "names": False, "cerca": "cerca" in low}

    failures = 0
    for label, judge, title in (("W", judge_w, "widened"), ("R", judge_r, "department asked outright"),
                                ("B0", judge_b0, "control: production before the change")):
        with ThreadPoolExecutor(8) as ex:
            replies = list(ex.map(lambda _: call(messages[label]["message"]), range(args.n)))
        verdicts = [judge(r) for r in replies]
        total = {k: sum(v[k] for v in verdicts) for k in ("where", "origin", "names", "cerca")}
        gate = label != "B0"
        ok = total["origin"] == 0 and total["names"] == 0 and total["where"] >= -(-args.n * 9 // 10)
        failures += gate and not ok
        print(f"\n[{label}] {title}: where {total['where']}/{args.n} | origin {total['origin']}/{args.n} | "
              f"names {total['names']}/{args.n} | 'cerca' {total['cerca']}/{args.n}" + (f"  -> {'PASS' if ok else 'FAIL'}" if gate else ""))
        for reply, v in list(zip(replies, verdicts))[:2]:
            print("   sample:", reply.replace("\n", " / ")[:300])
        for reply, v in zip(replies, verdicts):
            if gate and (v["origin"] or v["names"] or not v["where"]):
                print("   !! ", {k: v[k] for k in ("where", "origin", "names")}, reply.replace("\n", " / ")[:300])
                break
    print("\nRESULT:", "FAIL" if failures else "PASS", f"({failures} failing shape(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
