"""Copy the places production shows on the public map into the STAGING project, and nothing else.

    python -m scripts.seed_staging --project-ref REF            # dry run: reads production, writes nothing
    python -m scripts.seed_staging --project-ref REF --apply    # upserts those places into staging

It reads production with the PUBLIC anon key from js/config.js, so it can only see what the map already shows:
``approved`` places and the columns granted to anon (PLACES-PUBLIC-COLUMNS in db/schema.sql). It never reads
suggestions, reports, opinions, votes, chat logs, evidence, reviews or any email, and refuses a row that is not
``approved``. It writes only ``public.places`` in staging, with the staging service_role key from
``.env.staging``, and refuses if the target is production (scripts/staging_guard.py).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests

from scripts.staging_guard import (
    ENV_FILE,
    PROD_REF,
    ROOT,
    StagingGuardError,
    jwt_claims,
    load_env,
    ref_from_url,
    staging_target,
)

PUBLIC_COLUMNS = (
    "id", "name", "lat", "lng", "category", "country", "city", "region", "address", "safety_level", "status",
    "source", "phone", "website", "opening_hours", "social_url", "rating", "user_ratings_total", "vote_count",
    "community_warning_at",
)
PAGE = 500
BATCH = 200
TIMEOUT = 30


def production_source() -> tuple[str, str]:
    """Production URL and anon key, from the public frontend config. Refuses any key that is not anon."""
    config = (ROOT / "js" / "config.js").read_text(encoding="utf-8")
    url = re.search(r'SUPABASE_URL:\s*"([^"]+)"', config)
    key = re.search(r'SUPABASE_ANON_KEY:\s*"([^"]+)"', config)
    if not (url and key):
        raise StagingGuardError("js/config.js has no SUPABASE_URL / SUPABASE_ANON_KEY")
    if ref_from_url(url.group(1)) != PROD_REF:
        raise StagingGuardError("js/config.js does not point at production")
    claims = jwt_claims(key.group(1))
    if claims.get("role") != "anon" or claims.get("ref") != PROD_REF:
        raise StagingGuardError("the production key in js/config.js is not production's anon key")
    return url.group(1).rstrip("/"), key.group(1)


def fetch_approved(session: requests.Session, url: str, anon_key: str) -> list[dict]:
    headers = {"apikey": anon_key, "Authorization": f"Bearer {anon_key}"}
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "select": ",".join(PUBLIC_COLUMNS),
            "status": "eq.approved",
            "order": "id.asc",
            "limit": str(PAGE),
            "offset": str(offset),
        }
        resp = session.get(f"{url}/rest/v1/places", headers=headers, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        page = resp.json()
        for row in page:
            if row.get("status") != "approved":
                raise StagingGuardError(f"production returned a row that is not approved ({row.get('id')})")
            extra = set(row) - set(PUBLIC_COLUMNS)
            if extra:
                raise StagingGuardError(f"production returned non-public columns: {sorted(extra)}")
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def upsert_places(session: requests.Session, url: str, service_key: str, rows: list[dict]) -> int:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    sent = 0
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        resp = session.post(
            f"{url}/rest/v1/places", headers=headers, params={"on_conflict": "id"}, json=batch, timeout=TIMEOUT
        )
        if resp.status_code >= 300:
            raise StagingGuardError(f"staging refused batch at {start}: HTTP {resp.status_code} {resp.text[:300]}")
        sent += len(batch)
    return sent


def staging_count(session: requests.Session, url: str, anon_key: str) -> str:
    headers = {"apikey": anon_key, "Authorization": f"Bearer {anon_key}", "Prefer": "count=exact"}
    resp = session.head(
        f"{url}/rest/v1/places", headers=headers, params={"select": "id", "status": "eq.approved"}, timeout=TIMEOUT
    )
    return resp.headers.get("Content-Range", "?").split("/")[-1]


def main(argv: list[str] | None = None, session: requests.Session | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-ref", required=True, help="the staging project ref (refused if it is production's)")
    parser.add_argument("--env-file", type=Path, default=ENV_FILE, help="default: .env.staging at the repo root")
    parser.add_argument("--apply", action="store_true", help="really write into staging")
    args = parser.parse_args(argv)
    session = session or requests.Session()

    try:
        env = load_env(args.env_file)
        ref = staging_target(args.project_ref, env)
        source_url, source_key = production_source()
        rows = fetch_approved(session, source_url, source_key)
        countries = sorted({r.get("country") for r in rows if r.get("country")})
        print(f"production (anon key): {len(rows)} approved places · countries: {', '.join(countries)}")
        print(f"target: staging {ref} · table public.places · {len(PUBLIC_COLUMNS)} public columns")
        if not args.apply:
            print("dry run: nothing was written. Add --apply to upsert them into staging.")
            return 0
        target_url = env["STAGING_SUPABASE_URL"].rstrip("/")
        sent = upsert_places(session, target_url, env["STAGING_SUPABASE_SERVICE_ROLE_KEY"], rows)
        print(f"upserted {sent} rows into staging")
        print(f"staging now shows {staging_count(session, target_url, env['STAGING_SUPABASE_ANON_KEY'])} approved places (anon)")
    except (StagingGuardError, requests.RequestException) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
