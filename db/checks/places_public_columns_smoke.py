"""Read-only smoke test of the public (anon) read of places — privacy phase 1, 2026-09-29.

Run: python db/checks/places_public_columns_smoke.py [--chat]
Uses the frontend's public anon key. Only GETs, plus (with --chat) one ordinary chat search turn.

Expected after db/migrations/2026-09-29-places-public-columns.sql:
  map / ranking / report autocomplete / chat search queries -> 200 with rows
  community_opinions -> 200
  select=contact_email, validation_notes, outreach_opt_out, * -> refused (401/403)
Before the migration the "refused" checks fail: that is the exposure being closed.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[2]
config = (root / "js/config.js").read_text(encoding="utf-8")
base = re.search(r'SUPABASE_URL: "([^"]+)', config)[1]
key = re.search(r'SUPABASE_ANON_KEY:\s*"([^"]+)', config)[1]
headers = {"apikey": key, "Authorization": "Bearer " + key}


def get(path: str) -> tuple[int, object]:
    request = urllib.request.Request(base + "/rest/v1/" + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")
        try:
            return err.code, json.loads(body)
        except ValueError:
            return err.code, body


# The same queries the public readers send (js/map.js, js/ranking.js, js/report.js, chat).
ALLOWED = {
    "map": "places?select=id,name,lat,lng,category,city,safety_level,address,source,phone,website,opening_hours,"
           "social_url,rating,user_ratings_total,community_warning_at&status=eq.approved&order=name.asc,id.asc&limit=5",
    "ranking": "places?select=id,name,city,country,category,safety_level,vote_count,rating,community_warning_at"
               "&status=eq.approved&country=eq.Uruguay&vote_count=gt.0"
               "&order=vote_count.desc,rating.desc.nullslast,name.asc&limit=3",
    "report_autocomplete": "places?select=id,name,city&status=eq.approved&name=ilike.*cafe*&limit=3",
    "chat_search": "places?select=id,community_warning_at,name,address,city,country,category,safety_level,rating,"
                   "user_ratings_total,opening_hours,website,phone,lat,lng,vote_count&status=eq.approved"
                   "&city=ilike.*Montevideo*&order=vote_count.desc,rating.desc.nullslast,name.asc&limit=3",
    "chat_region": "places?select=city&status=eq.approved&region=eq.Canelones&country=eq.Uruguay&limit=3",
    "community_opinions": "community_opinions?select=id,description,author_name,place_id,place_name,city,country&limit=3",
}
REFUSED = {
    "contact_email": "places?select=id,contact_email&limit=1",
    "validation_notes": "places?select=validation_notes&limit=1",
    "outreach_opt_out": "places?select=outreach_opt_out&limit=1",
    "flags": "places?select=flags&limit=1",
    "wildcard": "places?select=*&limit=1",
    "filter_on_contact_email": "places?select=id&contact_email=not.is.null&limit=1",
}

results = []
for name, path in ALLOWED.items():
    status, body = get(path)
    ok = status == 200 and isinstance(body, list) and (len(body) > 0 or name == "community_opinions")
    results.append({"check": name, "expect": "200", "status": status, "rows": len(body) if isinstance(body, list) else None, "passed": ok})
for name, path in REFUSED.items():
    status, body = get(path)
    code = body.get("code") if isinstance(body, dict) else None
    results.append({"check": name, "expect": "refused", "status": status, "code": code, "passed": status in (401, 403)})

if "--chat" in sys.argv:
    body = {"messages": [{"role": "user", "content": "lugares sin tacc en montevideo"}],
            "session_token": "celiac-test-privacy-" + uuid4().hex, "pending_submission": None}
    request = urllib.request.Request(base + "/functions/v1/chat", data=json.dumps(body).encode(), headers={
        **headers, "Content-Type": "application/json", "Origin": "https://celiacmap.org"})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.load(response)
    places = [p.get("name") for p in data.get("places", [])]
    results.append({"check": "chat_turn", "expect": "places", "places": places[:3], "passed": bool(places)})

for r in results:
    print(json.dumps(r, ensure_ascii=True))
failed = [r["check"] for r in results if not r["passed"]]
print("FAILED: " + ", ".join(failed) if failed else "ALL PASSED")
sys.exit(1 if failed else 0)
