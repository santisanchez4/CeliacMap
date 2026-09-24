#!/usr/bin/env python
"""Live verification of the public community opinions against PRODUCTION (spec 2026-09-24).

Follows the protocol of the earlier live checks: it WRITES test rows, tags every one with an exact marker in
`description`, and reverts NOTHING itself -- the operator deletes them with SQL shown first and verifies against
the baseline. Public values only for the anonymous part (js/config.js); the moderation part uses the service
role from .env through the same code path `scripts/moderate_opinions.py` uses.

  python db/checks/opinions_live.py                 # DRY RUN: prints the plan
  python db/checks/opinions_live.py --send --out run.json

Steps (each is a PASS/FAIL line):
  a  anon POST with `published_at` already set            -> rejected (401/403); nothing inserted
  b  anon POST of a normal recommendation with a name     -> 201
  c  the public view                                      -> does NOT show it (not approved yet)
  d  the moderation listing (service role)                -> shows it with its place (embedded select works)
  e  `moderate_opinions --approve ... --apply`            -> the public view now shows it, with the name
  f  `moderate_opinions --hide ... --apply`               -> the public view no longer shows it
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PREFERRED_PLACE = "Cucina Paradiso Senza Glutine"


def load_public_config() -> tuple[str, str]:
    cfg = (ROOT / "js" / "config.js").read_text(encoding="utf-8")
    return (re.search(r'SUPABASE_URL\s*:\s*"([^"]+)"', cfg).group(1).rstrip("/"),
            re.search(r'SUPABASE_ANON_KEY\s*:\s*"([^"]+)"', cfg).group(1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    print("SENDING to production" if args.send else "DRY RUN (nothing is sent)")
    print("Steps" + __doc__.split("Steps")[1].rstrip("\n"))
    if not args.send:
        return 0

    import requests

    from agents.clients.supabase_client import SupabaseClient
    from config.settings import get_settings
    from scripts.moderate_opinions import run

    url, key = load_public_config()
    rest = f"{url}/rest/v1"
    anon = {"apikey": key, "Authorization": f"Bearer {key}"}
    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")
    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)

    def public_view(marker: str) -> list[dict]:
        r = requests.get(f"{rest}/community_opinions", headers=anon, timeout=30, params={
            "select": "id,description,author_name,place_name,city", "description": f"eq.{marker}"})
        r.raise_for_status()
        return r.json()

    def rows_with(marker: str) -> list[dict]:
        return db._db.table("place_reports").select("id,report_type,published_at,author_name,description") \
            .eq("description", marker).execute().data or []

    r = requests.get(f"{rest}/places", headers=anon, timeout=30, params={
        "select": "id,name,city", "status": "eq.approved", "name": f"eq.{PREFERRED_PLACE}", "limit": 1})
    r.raise_for_status()
    places = r.json() or requests.get(f"{rest}/places", headers=anon, timeout=30,
                                      params={"select": "id,name,city", "status": "eq.approved", "limit": 1}).json()
    place = places[0]
    print(f"\nplace under test: {place['name']} ({place['city']}) {place['id']}")

    tag = uuid.uuid4().hex[:12]
    marker_a, marker_b = f"PRUEBA-OPINIONES-A-{tag}", f"PRUEBA-OPINIONES-B-{tag}"
    results: list[tuple[str, bool, str]] = []

    def check(step: str, ok: bool, detail: str) -> None:
        results.append((step, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {step}: {detail}")

    post_headers = {**anon, "Content-Type": "application/json", "Prefer": "return=minimal"}

    # a) an anonymous client tries to publish itself
    ra = requests.post(f"{rest}/place_reports", headers=post_headers, timeout=30, json={
        "place_id": place["id"], "report_type": "positive", "description": marker_a,
        "author_name": "Prueba", "published_at": "2026-09-24T12:00:00+00:00"})
    check("a) anon insert with published_at is rejected", ra.status_code in (401, 403) and not rows_with(marker_a),
          f"HTTP {ra.status_code}, rows inserted: {len(rows_with(marker_a))}")

    # b) a normal recommendation with a name
    rb = requests.post(f"{rest}/place_reports", headers=post_headers, timeout=30, json={
        "place_id": place["id"], "report_type": "positive", "description": marker_b, "author_name": "Prueba"})
    mine = rows_with(marker_b)
    check("b) anon insert of a recommendation with a name", rb.status_code == 201 and len(mine) == 1,
          f"HTTP {rb.status_code}, rows: {len(mine)}, published_at: {mine[0]['published_at'] if mine else None}")
    if not mine:
        print("\nstopping: the test row was not created")
        return 1
    rid = mine[0]["id"]

    # c) not visible before approval
    check("c) the public view does not show it before approval", public_view(marker_b) == [], f"{public_view(marker_b)}")

    # d) the moderation listing sees it, with its place embedded
    pending = {p["id"]: p for p in db.fetch_unpublished_opinions(limit=500)}
    check("d) the moderation listing shows it with its place", rid in pending and bool((pending.get(rid) or {}).get("places")),
          f"in list: {rid in pending}; place: {(pending.get(rid) or {}).get('places')}")

    # e) approve -> visible with the name
    print("\n--- moderate_opinions --approve --apply ---")
    code = run(db, approve=[rid], hide=[], apply=True)
    seen = public_view(marker_b)
    check("e) after approval the public view shows it with the name",
          code == 0 and len(seen) == 1 and seen[0]["author_name"] == "Prueba", f"exit {code}, view: {seen}")

    # f) hide -> gone
    print("\n--- moderate_opinions --hide --apply ---")
    code = run(db, approve=[], hide=[rid], apply=True)
    check("f) after hiding the public view no longer shows it", code == 0 and public_view(marker_b) == [], f"exit {code}")

    ok = all(o for _, o, _ in results)
    print(f"\n{'ALL PASSED' if ok else 'FAILURES'}: {sum(o for _, o, _ in results)}/{len(results)}")
    print("\nTest rows to delete (SQL is shown and approved before running it):")
    print(f"  delete from public.place_reports where description in ('{marker_a}', '{marker_b}');")
    if args.out:
        Path(args.out).write_text(json.dumps({"markers": [marker_a, marker_b], "report_id": rid, "place": place,
                                              "steps": [{"step": s, "ok": o, "detail": d} for s, o, d in results]},
                                             ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
