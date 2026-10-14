#!/usr/bin/env python
"""Read-only audit of ``places`` against the map scope rules (2026-10-13): which rows are a general retail chain (1a) or a place
that teaches or informs without selling to the public (1b)?

READ-ONLY by construction: one paged SELECT on ``places`` (every status), no ``--apply``, no write method, no Google or model call.
It prints a Markdown report; a status is only ever changed by the admin, afterwards.

Two levels of certainty:
* "seguro": the deterministic layer the agents use (``agents/map_scope.out_of_scope_reason``: brand list, the chain's own site,
  a name that starts with "escuela / cursos de cocina / blog / recetas").
* "dudoso": loose words in the name, the site or the Validator's own note, a ``social_url`` that is a platform's topic page (the
  lead came from nobody's page; the row is usually a real business all the same) and the municipal layer of Montevideo (IM, PR #20)
  when its licence registers production or distribution with no sale to the public. These are the possible false positives.

    python db/checks/map_scope_audit.py > db/checks/2026-10-13-map-scope-audit.md
"""
from __future__ import annotations

import csv
import io
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agents.clients.supabase_client import SupabaseClient  # noqa: E402
from agents.evidence_finder import social_page_kind  # noqa: E402
from agents.manual_overrides import manual_override_marker  # noqa: E402
from agents.map_scope import _AMBIGUOUS_BRANDS, _DISTINCTIVE_BRANDS, _has_phrase, _norm, out_of_scope_reason  # noqa: E402
from config.settings import get_settings  # noqa: E402

COLUMNS = ("id,name,country,city,status,category,safety_level,source,website,social_url,address,lat,lng,"
           "validation_notes,validation_confidence,flags")
PAGE = 1000
IMM_CSV = "data/imm-locales-gluten-free:db/checks/2026-10-13-imm/imm_locales_libres_de_gluten.csv"

RETAIL_WORDS = ("supermercado supermercados hipermercado hiper autoservicio autoservicios minimercado minimarket super farmacia "
                "farmacias mayorista").split()
# "Mercado" / "market" name many health-food shops: they count only without a specialised word next to them.
MARKET_WORDS = ("mercado", "market")
SPECIALISED = frozenset("natural naturales saludable saludables sano sana healthy organico dietetica gluten tacc celiaco celiacos keto "
                        "verde almacen gastronomico".split())
TEACH_WORDS = ("escuela academia instituto curso cursos taller talleres clases blog recetas asociacion fundacion nutricionista "
               "consultorio distribuidora distribuidor").split()
NOTE_RE = re.compile(
    r"supermercad|supermarket|hipermercad|hypermarket|autoservicio|farmacia|pharmacy|retail chain|grocery chain"
    r"|escuela|school|cursos?\b|courses?\b|taller(?:es)?\b|workshop|no vende|does not sell|no es un (?:local|comercio)"
    r"|not a (?:business|restaurant|shop)|distribuidor|mayorista|wholesal"
)
BLOG_HOSTS = ("blogspot.", "wordpress.com", "medium.com", "substack.com", "youtube.com", "tiktok.com", "linktr.ee")
IMM_NO_SALE = re.compile(r"distribu|importador|deposito|planta|fraccionam|elaborador")
IMM_SALE = re.compile(r"venta|expendio|restaurante|cafeteria|bar\b|comidas al paso|rotiseria|panaderia|heladeria|confiteria|sucursal")


def fetch_all(db) -> list[dict]:
    rows, start = [], 0
    while True:
        page = db._db.table("places").select(COLUMNS).order("created_at").range(start, start + PAGE - 1).execute().data or []
        rows += page
        if len(page) < PAGE:
            return rows
        start += PAGE


def imm_rows() -> list[dict]:
    out = subprocess.run(["git", "show", IMM_CSV], cwd=ROOT, capture_output=True, encoding="utf-8")
    return list(csv.DictReader(io.StringIO(out.stdout))) if out.returncode == 0 else []


def metres(a_lat, a_lng, b_lat, b_lng) -> float:
    k = 111_320.0
    return math.hypot((a_lat - b_lat) * k, (a_lng - b_lng) * k * math.cos(math.radians(a_lat)))


def imm_signal(place: dict, imm: list[dict]) -> str | None:
    if place.get("city") != "Montevideo" or place.get("lat") is None:
        return None
    for row in imm:
        try:
            near = metres(place["lat"], place["lng"], float(row["lat"]), float(row["lon"])) <= 40
        except (TypeError, ValueError):
            continue
        giros = _norm(row["giros"])
        if near and IMM_NO_SALE.search(giros) and not IMM_SALE.search(giros) and "exp" not in row["rubro"].lower():
            return f"IM (a ≤ 40 m, «{row['nombre']}», rubro {row['rubro']}): {row['giros']}"
    return None


def loose_signals(place: dict, imm: list[dict]) -> list[str]:
    tokens = _norm(place.get("name")).split()
    found = []
    brands = [label for brand, label in {**_DISTINCTIVE_BRANDS, **_AMBIGUOUS_BRANDS}.items() if _has_phrase(tokens, brand)]
    if brands:
        found.append("el nombre contiene la marca " + " / ".join(sorted(set(brands))))
    words = [w for w in RETAIL_WORDS + TEACH_WORDS if w in tokens]
    words += [w for w in MARKET_WORDS if w in tokens and not SPECIALISED & set(tokens)]
    if words:
        found.append("palabra en el nombre: " + ", ".join(words))
    site = (place.get("website") or "").lower()
    if any(h in site for h in BLOG_HOSTS):
        found.append(f"sitio en una plataforma de contenidos ({place['website']})")
    if social_page_kind(place.get("social_url")) == "topic":
        found.append(f"su social_url es una página de tema, no una cuenta ({place['social_url']}): el lead salió de ahí")
    note = _norm(place.get("validation_notes"))
    m = None if "lugar de ejemplo del seed" in note else NOTE_RE.search(note)
    if m:
        found.append(f"la nota del Validator dice «…{note[max(0, m.start() - 50): m.end() + 60]}…»")
    signal = imm_signal(place, imm)
    if signal:
        found.append(signal)
    return found


def row(place: dict, motivo: str, certeza: str) -> str:
    manual = manual_override_marker(place.get("validation_notes"))
    conf = place.get("validation_confidence")
    estado = place["status"] + (f" · {place['safety_level']}" if place["status"] == "approved" else "")
    cells = [f"{place['name']} (`{place['id'][:8]}`)", f"{place.get('city') or '—'}, {place['country']}", estado,
             "" if conf is None else f"{conf:g}", motivo.replace("|", "/").replace("\n", " "), certeza,
             f"sí ({manual})" if manual else "no"]
    return "| " + " | ".join(cells) + " |"


HEAD = ("| Lugar | Ciudad, país | Estado actual | Conf. | Motivo del match | Certeza | Decisión manual |\n"
        "|---|---|---|---|---|---|---|")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")
    places = fetch_all(SupabaseClient(settings.supabase_url, settings.supabase_service_role_key))
    imm = imm_rows()

    sure, doubtful = [], []
    for p in places:
        reason = out_of_scope_reason(p.get("name"), website=p.get("website"))
        if reason:
            sure.append((p, ("1a · " if reason.kind == "chain" else "1b · ") + reason.detail))
            continue
        signals = loose_signals(p, imm)
        if signals:
            doubtful.append((p, "; ".join(signals)))

    def block(title, items, certeza, statuses):
        chosen = sorted((it for it in items if it[0]["status"] in statuses), key=lambda it: (it[0]["country"], it[0]["name"].lower()))
        print(f"\n### {title} — {len(chosen)}\n")
        if chosen:
            print(HEAD)
            for p, motivo in chosen:
                print(row(p, motivo, certeza))
        else:
            print("Ninguno.")

    by_status = {}
    for p in places:
        by_status[p["status"]] = by_status.get(p["status"], 0) + 1
    print("# Auditoría de alcance del mapa (solo lectura)\n")
    print(f"`python db/checks/map_scope_audit.py` · {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")
    print("**No se cambió ningún estado.** Un `SELECT` paginado sobre `places` (todos los estados), sin llamadas a Google ni al modelo.")
    print(f"Filas leídas: {len(places)} ({', '.join(f'{k} {v}' for k, v in sorted(by_status.items()))}). "
          f"Capa de la IM: {len(imm)} filas" + ("" if imm else " (no disponible: la rama del #20 no está en este clon)") + ".\n")
    print(f"- **Seguros** (la misma regla determinista que usan los agentes): {len(sure)}, de los cuales "
          f"{sum(1 for p, _ in sure if p['status'] == 'approved')} están aprobados en el mapa.")
    print(f"- **Dudosos** (palabras sueltas, nota del Validator, giros de la IM — posibles falsos positivos): {len(doubtful)}, de los "
          f"cuales {sum(1 for p, _ in doubtful if p['status'] == 'approved')} están aprobados en el mapa.")

    print("\n## 1. APROBADOS EN EL MAPA")
    block("1.1 Seguros", sure, "alta", {"approved"})
    block("1.2 Dudosos (revisar uno por uno: pueden ser falsos positivos)", doubtful, "baja", {"approved"})
    print("\n## 2. Fuera del mapa (otros estados)")
    block("2.1 Seguros — en cola o pendientes (`needs_review`, `pending`)", sure, "alta", {"needs_review", "pending"})
    block("2.2 Dudosos — en cola o pendientes", doubtful, "baja", {"needs_review", "pending"})
    block("2.3 Seguros — ya descartados", sure, "alta", {"discarded"})
    block("2.4 Dudosos — ya descartados", doubtful, "baja", {"discarded"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
