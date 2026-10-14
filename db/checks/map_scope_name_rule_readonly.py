#!/usr/bin/env python
"""Read-only: which rows of ``places`` would agents/map_scope.out_of_scope_reason exclude today (2026-10-14)?

READ-ONLY by construction: one paged SELECT on ``places`` (every status), no write method, no model or Google call. The scope rule
is not retroactive (it runs before the Validator calls the model, and only on ``pending`` rows), so this only says what the rule
would hit if a row went back through it, and whether any of those is on the map or carries a manual decision.

    python db/checks/map_scope_name_rule_readonly.py > db/checks/2026-10-14-map-scope-name-rule-readonly.md
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agents.clients.supabase_client import SupabaseClient  # noqa: E402
from agents.manual_overrides import manual_override_marker  # noqa: E402
from agents.map_scope import out_of_scope_reason  # noqa: E402
from config.settings import get_settings  # noqa: E402

COLUMNS = "id,name,country,city,status,safety_level,website,validation_notes"
PAGE = 1000
HEADER = re.compile(r"aprobaci[oó]n manual|override manual|correcci[oó]n manual", re.IGNORECASE)


def fetch_all(db) -> list[dict]:
    rows, start = [], 0
    while True:
        page = db._db.table("places").select(COLUMNS).order("created_at").range(start, start + PAGE - 1).execute().data or []
        rows += page
        if len(page) < PAGE:
            return rows
        start += PAGE


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")
    places = fetch_all(SupabaseClient(settings.supabase_url, settings.supabase_service_role_key))

    hits = []
    for p in places:
        reason = out_of_scope_reason(p.get("name"), website=p.get("website"))
        if reason:
            headers = sorted({m.group(0).upper() for m in HEADER.finditer(p.get("validation_notes") or "")})
            hits.append((p, reason, headers))
    with_header = [h for h in hits if h[2]]
    # A CORRECCIÓN MANUAL that only says "no aplica al mapa" is a data correction and protects nothing (DATA_CORRECTION_PHRASES).
    risky = [h for h in hits if h[0]["status"] == "approved" or manual_override_marker(h[0].get("validation_notes"))]

    print("# Regla de alcance en código sobre `places` — solo lectura (2026-10-14)\n")
    print(f"`python db/checks/map_scope_name_rule_readonly.py` · {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")
    print("**No se escribió nada.** Un `SELECT` paginado sobre `places` (todos los estados), sin llamadas a modelos ni a Google. "
          "La regla no es retroactiva: corre antes de que el Validator llame al modelo y solo sobre filas `pending`.\n")
    print(f"- Filas leídas: {len(places)}.")
    print(f"- Filas que `out_of_scope_reason` excluiría: **{len(hits)}**.")
    print(f"- Aprobadas: **{sum(1 for h in hits if h[0]['status'] == 'approved')}**.")
    print(f"- Con encabezado APROBACIÓN MANUAL / OVERRIDE MANUAL / CORRECCIÓN MANUAL: {len(with_header)}.")
    print(f"- Aprobadas o **protegidas** por una decisión manual (`manual_override_marker`): **{len(risky)}**. Una CORRECCIÓN MANUAL "
          "que solo dice «no aplica al mapa» es una corrección de dato y no protege la fila.\n")
    print("| Lugar | Ciudad, país | Estado | Regla | Encabezado manual | Protegida |")
    print("|---|---|---|---|---|---|")
    for p, reason, headers in sorted(hits, key=lambda h: (h[0]["status"], h[0]["name"].lower())):
        rule = "nombre de autoservicio / supermercado independiente" if reason.detail.startswith("comercio general (") else (
            "cadena (nombre o dominio)" if reason.kind == "chain" else "no vende (nombre)")
        print(f"| {p['name']} (`{p['id'][:8]}`) | {p.get('city') or '—'}, {p['country']} | {p['status']} | {rule} | "
              f"{', '.join(headers) or 'no'} | {'sí' if manual_override_marker(p.get('validation_notes')) else 'no'} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
