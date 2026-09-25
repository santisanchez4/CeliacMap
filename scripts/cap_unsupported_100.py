"""One-off pass over the places already published as "Espacio 100% sin gluten" (audit plan step 2b).

Tope C now keeps a Validator ``gluten_free_100`` only when the reviews / evidence it saw state that
the place is exclusively gluten free. This script applies the same rule to the places approved
before it existed: for each approved ``gluten_free_100`` place WITHOUT a manual-override marker, if
neither its reviews nor its ``place_evidence`` contain an explicit exclusivity phrase, its level goes
down to ``celiac_friendly`` (public label "Tiene opciones sin TACC") with the
``100% pendiente de confirmación del administrador`` flag, so the admin can confirm it with
``scripts/review_queue.py --pending-100``. Status, confidence and ``verified`` are not touched.

It CHANGES WHAT PEOPLE SEE ON THE MAP: read the dry-run list before ``--apply``.

``--flag-only`` is the gentle variant: for the same places it ONLY adds the
``100% pendiente de confirmación del administrador`` flag (no duplicates, existing flags kept). The
level, status, confidence, ``verified`` and ``validation_notes`` are not touched, so the map does not
change; the places just show up in ``scripts/review_queue.py --pending-100`` for the admin to confirm one
by one. Use it when "no stored evidence" is not proof of "no backing": ``place_evidence`` starts empty for
old places and Google review snippets are deleted after 30 days. One ``agent_log`` row per applied run.

    python -m scripts.cap_unsupported_100                        # dry run: what would be lowered
    python -m scripts.cap_unsupported_100 --apply
    python -m scripts.cap_unsupported_100 --flag-only            # dry run: what would be flagged
    python -m scripts.cap_unsupported_100 --flag-only --apply
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from agents.manual_overrides import manual_override_marker
from agents.validator_agent import PENDING_ADMIN_FLAG, ValidatorAgent

HEADER = "CORRECCIÓN RETROACTIVA DE NIVEL ({day}): el 100% no tenía evidencia explícita de cocina exclusiva " \
         "(reseñas ni evidencia guardada); pasa a 'Tiene opciones sin TACC' hasta que el admin lo confirme."


def _flag_only(db, places: list[dict], keep_manual: int, keep_signal: int, to_cap: list[dict], apply: bool, out) -> int:
    already = [p for p in to_cap if PENDING_ADMIN_FLAG in (p.get("flags") or [])]
    to_flag = [p for p in to_cap if PENDING_ADMIN_FLAG not in (p.get("flags") or [])]
    out(f"{len(places)} lugares 100% aprobados: {keep_manual} con decisión manual (no se tocan), "
        f"{keep_signal} con evidencia explícita (se quedan), {len(to_cap)} sin evidencia explícita guardada: "
        f"{len(to_flag)} se marcarían como '100% pendiente de confirmación' y {len(already)} ya estaban marcados "
        f"(el nivel no cambia):")
    for p in to_flag:
        out(f"  {p['id']}  {p.get('name')} — {p.get('city')}, {p.get('country')} (fuente {p.get('source')})")
    if not apply:
        out("DRY RUN — revisá la lista y agregá --apply para escribir (solo se agrega la marca; el nivel no cambia).")
        return 0

    for p in to_flag:
        db.update_place(p["id"], {"flags": [*(p.get("flags") or []), PENDING_ADMIN_FLAG]})
    db.insert_agent_log(
        "validator",
        "flag_unsupported_100",
        {
            "approved_100": len(places),
            "manual": keep_manual,
            "explicit_evidence": keep_signal,
            "candidates": len(to_cap),
            "flagged": len(to_flag),
            "already_flagged": len(already),
        },
        status="success",
    )
    out(f"Listo: {len(to_flag)} lugares marcados ({len(already)} ya lo estaban). Revisalos con "
        f"python -m scripts.review_queue --pending-100")
    return 0


def run(db, apply: bool, limit: int = 2000, out=print, flag_only: bool = False) -> int:
    places = db.fetch_places_for_admin("approved", safety_level="gluten_free_100", limit=limit)
    keep_manual = keep_signal = 0
    to_cap = []
    for p in places:
        if manual_override_marker(p.get("validation_notes")):
            keep_manual += 1
            continue
        texts = [r.get("text") for r in (db.fetch_reviews_for_place(p["id"]) or [])]
        texts += [e.get("text") for e in (db.fetch_place_evidence(p["id"]) or [])]
        if ValidatorAgent.has_exclusive_signal(texts):
            keep_signal += 1
            continue
        to_cap.append(p)

    if flag_only:
        return _flag_only(db, places, keep_manual, keep_signal, to_cap, apply, out)

    out(f"{len(places)} lugares 100% aprobados: {keep_manual} con decisión manual (no se tocan), "
        f"{keep_signal} con evidencia explícita (se quedan), {len(to_cap)} pasarían a 'Tiene opciones sin TACC':")
    for p in to_cap:
        out(f"  {p['id']}  {p.get('name')} — {p.get('city')}, {p.get('country')} (fuente {p.get('source')})")
    if not to_cap:
        return 0
    if not apply:
        out("DRY RUN — revisá la lista y agregá --apply para escribir.")
        return 0

    header = HEADER.format(day=date.today().isoformat())
    for p in to_cap:
        flags = list(p.get("flags") or [])
        if PENDING_ADMIN_FLAG not in flags:
            flags.append(PENDING_ADMIN_FLAG)
        old = (p.get("validation_notes") or "").strip()
        db.update_place(p["id"], {
            "safety_level": "celiac_friendly",
            "flags": flags,
            "validation_notes": f"{header}\n\n{old}" if old else header,
        })
    out(f"Listo: {len(to_cap)} lugares actualizados.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    parser.add_argument(
        "--flag-only",
        action="store_true",
        help="only add the admin-queue flag; do NOT lower the level or touch anything else",
    )
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
    return run(
        SupabaseClient(settings.supabase_url, settings.supabase_service_role_key),
        args.apply,
        flag_only=args.flag_only,
    )


if __name__ == "__main__":
    raise SystemExit(main())
