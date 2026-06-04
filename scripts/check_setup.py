"""Connectivity / configuration check for the CeliacMap agent foundation.

Run from the repo root:

    python scripts/check_setup.py

- Verifies the geographic config loads (config/targets.yaml).
- Pings Supabase with the service_role key (free — counts rows in places).
- Confirms the Google and Anthropic keys are present. It does NOT call those
  paid APIs, to avoid surprise charges; the individual agents exercise them.

Exits non-zero if a required piece is missing, so CI can gate on it.
"""

from __future__ import annotations

import sys

from config.settings import get_settings, load_targets


def main() -> int:
    ok = True
    settings = get_settings()

    # 1. Geographic config
    try:
        targets = load_targets()
        n_cities = sum(len(c.get("cities", [])) for c in targets.get("countries", []))
        print(f"[ok]   targets.yaml loaded — {n_cities} city/cities, "
              f"{len(targets.get('search_terms', []))} search terms")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] could not load config/targets.yaml: {exc}")
        ok = False

    # 2. Supabase (free ping)
    try:
        settings.require("supabase_url", "supabase_service_role_key")
        from agents.clients.supabase_client import SupabaseClient

        db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
        total = db.health_check()
        print(f"[ok]   Supabase reachable — {total} place(s) in the database")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Supabase: {exc}")
        ok = False

    # 3. Paid API keys — presence only (no calls)
    if settings.google_maps_api_key:
        print("[ok]   GOOGLE_MAPS_API_KEY present (not called)")
    else:
        print("[FAIL] GOOGLE_MAPS_API_KEY missing")
        ok = False

    if settings.anthropic_api_key:
        print(f"[ok]   ANTHROPIC_API_KEY present (validator model: {settings.validator_model})")
    else:
        print("[FAIL] ANTHROPIC_API_KEY missing")
        ok = False

    # Tavily powers the optional Social agent — note its absence but don't fail.
    if settings.tavily_api_key:
        print("[ok]   TAVILY_API_KEY present (not called)")
    else:
        print("[note] TAVILY_API_KEY missing — Social agent will be skipped")

    print("\nSetup OK." if ok else "\nSetup incomplete — see [FAIL] lines above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
