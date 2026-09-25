"""The admin's review queue: everything that waits for a human decision, and the commands to decide.

Audit plan step 6 (docs/plans/PLAN-auditoria-2026-09-24.md). Lists are read-only; every write is a
dry run unless ``--apply`` is given. Same shape as ``scripts/moderate_opinions.py``.

    python -m scripts.review_queue                          # summary of every queue
    python -m scripts.review_queue --pending-100            # places the Validator left "100% pendiente"
    python -m scripts.review_queue --needs-review --city "Fray Bentos" --limit 15
    python -m scripts.review_queue --pending-100 --limit 20 --offset 20   # second page of 20 (places lists only)
    python -m scripts.review_queue --suggestions            # suggestions whose address could not be placed
    python -m scripts.review_queue --warnings               # places with a recent community report

    python -m scripts.review_queue --approve ID --level 100 --note "conozco el local" --apply
    python -m scripts.review_queue --approve ID --level options --note "..." --apply
    python -m scripts.review_queue --discard ID --note "cerró" --apply
    python -m scripts.review_queue --clear-warning ID --apply
    python -m scripts.review_queue --locate SUGGESTION_ID --lat -33.12 --lng -58.30 --apply

Rules it applies (CLAUDE.md "Manual Validator overrides — allowed, but never silent"): an approval
prepends an ``APROBACIÓN MANUAL`` header to ``validation_notes`` (the Validator's text is kept below),
never changes ``validation_confidence`` and never sets ``verified``. The note you pass goes to a public
column: do not write anyone's health data in it (e.g. that the owner is celiac).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta, timezone

from agents.validator_agent import _OWNER_HEALTH_RE, PENDING_ADMIN_FLAG

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
WARNING_DAYS = 30
LEVEL_LABELS = {
    "gluten_free_100": "Espacio 100% sin gluten",
    "celiac_friendly": "Tiene opciones sin TACC",
    "options_available": "Tiene opciones sin TACC",
}
_TRI = {True: "sí", False: "no", None: "sin dato"}


def _warned_since() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=WARNING_DAYS)).isoformat()


def _maps_link(p: dict) -> str:
    if p.get("lat") is None or p.get("lng") is None:
        return "(sin coordenadas)"
    return f"https://www.google.com/maps?q={p['lat']},{p['lng']}"


def _print_place(db, p: dict, out, *, reports: bool = False) -> None:
    out("")
    out(f"  id:        {p.get('id')}")
    out(f"  lugar:     {p.get('name')} — {p.get('address') or '(sin dirección)'} · {p.get('city')}, {p.get('country')}")
    out(f"  estado:    {p.get('status')} · nivel: {LEVEL_LABELS.get(p.get('safety_level'), p.get('safety_level'))}"
        f" · fuente: {p.get('source')} · ubicación: {p.get('geocode_method') or 'Google Places'}")
    out(f"  mapa:      {_maps_link(p)}")
    if p.get("social_url") or p.get("website"):
        out(f"  links:     {' · '.join(x for x in (p.get('social_url'), p.get('website')) if x)}")
    conf = p.get("validation_confidence")
    out(f"  validator: {conf if conf is not None else '-'} · flags: {', '.join(p.get('flags') or []) or '-'}")
    if p.get("validation_notes"):
        out(f"  notas:     {p['validation_notes']}")
    if p.get("recommendation"):
        out(f"  sugiere:   {p['recommendation']}")
    for e in _safe(lambda: db.fetch_place_evidence(p["id"])):
        out(f"  evidencia: [{e.get('source')}] {e.get('text') or ''} {e.get('url') or ''}".rstrip())
    suggestion = _safe(lambda: db.fetch_suggestion_for_place(p["id"]), default=None)
    if suggestion:
        out(f"  sugerido:  {suggestion.get('created_at')} · nota: {suggestion.get('notes') or '-'}")
        out(f"  cocina:    exclusiva {_TRI.get(suggestion.get('kitchen_exclusive'), 'sin dato')}"
            f" · preparación {suggestion.get('celiac_prep') or 'sin dato'}"
            f" · dueño/a celíaco/a {_TRI.get(suggestion.get('owner_celiac'), 'sin dato')} (solo para vos)")
    if reports:
        for r in _safe(lambda: db.fetch_recent_negative_reports(p["id"], days=WARNING_DAYS)):
            out(f"  reporte:   {r.get('created_at')} · {r.get('description')}")


def _safe(fn, default=()):
    try:
        return fn() or default
    except Exception:  # noqa: BLE001 - one missing context must not hide the rest of the queue
        return default


def _print_suggestions(rows: list[dict], out) -> None:
    for s in rows:
        out("")
        out(f"  id:        {s.get('id')}")
        out(f"  lugar:     {s.get('name')} — {s.get('address')} · {s.get('city')}, {s.get('country')}")
        out(f"  enviado:   {s.get('created_at')} · categoría {s.get('category') or '-'} · link {s.get('evidence_url') or '-'}")
        out(f"  nota:      {s.get('notes') or '-'}")
        out(f"  cocina:    exclusiva {_TRI.get(s.get('kitchen_exclusive'), 'sin dato')}"
            f" · preparación {s.get('celiac_prep') or 'sin dato'}"
            f" · dueño/a celíaco/a {_TRI.get(s.get('owner_celiac'), 'sin dato')} (solo para vos)")
        out("  → corregí la ubicación con: --locate ID --lat <lat> --lng <lng> [--address '...'] --apply")


def list_queues(db, args, out) -> int:
    only = [k for k in ("pending_100", "needs_review", "suggestions", "warnings") if getattr(args, k)]
    show_all = not only
    if show_all or args.pending_100:
        rows = db.fetch_places_for_admin(
            None, flag=PENDING_ADMIN_FLAG, city=args.city, limit=args.limit, offset=args.offset
        )
        out(f"== 100% pendientes de tu confirmación: {len(rows)} ==")
        for p in rows:
            _print_place(db, p, out)
    if show_all or args.needs_review:
        rows = db.fetch_places_for_admin("needs_review", city=args.city, limit=args.limit, offset=args.offset)
        out(f"== En revisión humana (needs_review), los {len(rows)} más viejos ==")
        for p in rows:
            _print_place(db, p, out)
    if show_all or args.suggestions:
        rows = db.fetch_suggestions_by_status("needs_location", limit=args.limit)
        out(f"== Sugerencias sin ubicar: {len(rows)} ==")
        _print_suggestions(rows, out)
    if show_all or args.warnings:
        rows = db.fetch_places_for_admin(
            None, warned_since=_warned_since(), city=args.city, limit=args.limit, offset=args.offset
        )
        out(f"== Lugares reportados por la comunidad (últimos {WARNING_DAYS} días): {len(rows)} ==")
        for p in rows:
            _print_place(db, p, out, reports=True)
    return 0


def _header(kind: str, note: str, place: dict) -> str:
    conf = place.get("validation_confidence")
    return (
        f"{kind} ({date.today().isoformat()}, review_queue): {note.strip()}. "
        f"El Validator había dejado: {place.get('status')}"
        f"{f' @ {conf}' if conf is not None else ''}."
    )


def approve(db, place_id: str, level: str, note: str, apply: bool, out) -> int:
    place = db.fetch_place_by_id(place_id)
    if not place:
        out(f"No existe el lugar {place_id}.")
        return 1
    current = place.get("safety_level")
    if level == "100":
        safety = "gluten_free_100"
    else:  # "options": keep the finer internal level when it already is one of the two option levels
        safety = current if current in ("celiac_friendly", "options_available") else "options_available"
    flags = [f for f in (place.get("flags") or []) if f != PENDING_ADMIN_FLAG]
    old_notes = (place.get("validation_notes") or "").strip()
    header = _header("APROBACIÓN MANUAL", note, place)
    patch = {
        "status": "approved",
        "safety_level": safety,
        "flags": flags,
        "validation_notes": f"{header}\n\n{old_notes}" if old_notes else header,
    }
    out(f"{place.get('name')}: {place.get('status')} → approved · {LEVEL_LABELS.get(safety)}")
    out(f"  nota: {header}")
    if not apply:
        out("DRY RUN — agregá --apply para escribir.")
        return 0
    db.update_place(place_id, patch)
    out("Listo.")
    return 0


def discard(db, place_id: str, note: str, apply: bool, out) -> int:
    place = db.fetch_place_by_id(place_id)
    if not place:
        out(f"No existe el lugar {place_id}.")
        return 1
    old_notes = (place.get("validation_notes") or "").strip()
    header = _header("DESCARTE MANUAL", note, place)
    # --pending-100 has no status filter, so a discarded place would stay in that queue for good.
    flags = [f for f in (place.get("flags") or []) if f != PENDING_ADMIN_FLAG]
    out(f"{place.get('name')}: {place.get('status')} → discarded")
    if not apply:
        out("DRY RUN — agregá --apply para escribir.")
        return 0
    db.update_place(
        place_id,
        {
            "status": "discarded",
            "flags": flags,
            "validation_notes": f"{header}\n\n{old_notes}" if old_notes else header,
        },
    )
    out("Listo.")
    return 0


def clear_warning(db, place_id: str, apply: bool, out) -> int:
    out(f"Se quitaría el aviso 'reportado por la comunidad' de {place_id}.")
    if not apply:
        out("DRY RUN — agregá --apply para escribir.")
        return 0
    db.set_community_warning(place_id, None)
    out("Listo.")
    return 0


def locate(db, suggestion_id: str, lat: float, lng: float, address: str | None, apply: bool, out) -> int:
    """Place a suggestion the promoter could not geocode, with coordinates the admin checked.

    The place goes in as 'pending' (address_only), like any other suggestion: the next Validator
    run judges it, or the admin approves it with --approve.
    """
    s = db.fetch_suggestion_by_id(suggestion_id)
    if not s:
        out(f"No existe la sugerencia {suggestion_id}.")
        return 1
    if s.get("status") != "needs_location":
        out(f"La sugerencia está en '{s.get('status')}', no en 'needs_location'.")
        return 1
    candidate = {
        "name": s["name"],
        "lat": lat,
        "lng": lng,
        "address": address or s.get("address"),
        "city": s["city"],
        "country": s["country"],
        "category": s.get("category") or "restaurant",
        "safety_level": "options_available",
        "source": "user",
        "external_id": None,
        "social_url": s.get("evidence_url"),
        "geocode_method": "address_only",
    }
    out(f"Se cargaría '{s['name']}' en ({lat}, {lng}) como pendiente · {_maps_link(candidate)}")
    if not apply:
        out("DRY RUN — agregá --apply para escribir.")
        return 0
    row = db.insert_place_candidate(candidate)
    if not row:
        out("No se insertó (¿coordenadas fuera de Uruguay/Argentina?).")
        return 1
    db.update_suggestion_status(suggestion_id, "promoted", row.get("id"))
    try:
        db.add_place_evidence(row.get("id"), "user", s.get("notes"), s.get("evidence_url"))
    except Exception:  # noqa: BLE001 - evidence is best-effort
        out("Aviso: no se pudo guardar la nota como evidencia.")
    out(f"Listo: lugar {row.get('id')} (pending). Aprobalo con --approve si lo conocés.")
    return 0


def run(db, args, out=print) -> int:
    target = args.approve or args.discard or args.clear_warning
    if target and not _UUID.match(target):
        out(f"Id inválido (se espera un uuid): {target}")
        return 2
    if args.locate and not _UUID.match(args.locate):
        out(f"Id inválido (se espera un uuid): {args.locate}")
        return 2
    if (args.approve or args.discard) and not (args.note or "").strip():
        out("Falta --note: toda decisión manual queda explicada (nunca en silencio).")
        return 2
    if args.note and _OWNER_HEALTH_RE.search(args.note):
        out("La nota va a una columna pública: no escribas datos de salud de personas (p. ej. que el dueño es celíaco).")
        return 2
    if args.approve:
        if args.level not in ("100", "options"):
            out("Falta --level 100 u --level options.")
            return 2
        return approve(db, args.approve, args.level, args.note, args.apply, out)
    if args.discard:
        return discard(db, args.discard, args.note, args.apply, out)
    if args.clear_warning:
        return clear_warning(db, args.clear_warning, args.apply, out)
    if args.locate:
        if args.lat is None or args.lng is None:
            out("Falta --lat y --lng.")
            return 2
        return locate(db, args.locate, args.lat, args.lng, args.address, args.apply, out)
    return list_queues(db, args, out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pending-100", action="store_true", help="places awaiting your 100%% confirmation")
    parser.add_argument("--needs-review", action="store_true", help="the needs_review queue, oldest first")
    parser.add_argument("--suggestions", action="store_true", help="suggestions whose address could not be placed")
    parser.add_argument("--warnings", action="store_true", help="places with a recent community report")
    parser.add_argument("--city", help="filter the lists by city")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--offset", type=int, default=0, help="skip this many places (next page of a long list)")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--approve", metavar="PLACE_ID")
    actions.add_argument("--discard", metavar="PLACE_ID")
    actions.add_argument("--clear-warning", metavar="PLACE_ID")
    actions.add_argument("--locate", metavar="SUGGESTION_ID")
    parser.add_argument("--level", choices=["100", "options"])
    parser.add_argument("--note", help="why (goes to the public validation_notes; no health data)")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lng", type=float)
    parser.add_argument("--address")
    parser.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    from agents.clients.supabase_client import SupabaseClient
    from config.settings import get_settings

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")
    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    return run(db, args)


if __name__ == "__main__":
    raise SystemExit(main())
