"""Moderate the community's positive recommendations before they show on the public site.

A positive report becomes public only when the admin sets ``published_at``. This script is the way to
do it: it lists what is waiting (the FULL text -- read it before approving), publishes chosen ids, or
hides a published one. Dry-run by default; nothing is written without ``--apply``.

    python -m scripts.moderate_opinions                              # list pending
    python -m scripts.moderate_opinions --approve ID [ID ...]        # dry run
    python -m scripts.moderate_opinions --approve ID --apply         # publish
    python -m scripts.moderate_opinions --hide ID --apply            # take one down

Only positive reports of currently approved places can be approved (the database also forbids
publishing a negative one). See docs/superpowers/specs/2026-09-24-community-opinions-design.md.

Only recommendations sent with form B are offered (privacy phase 1, 2026-09-29). The chat does not
tell the person that a comment may be published as "Anónimo" (that notice waits for the next prompt
batch), so a row without ``reporter_token`` -- the chat never sends one, form B always does -- is
listed apart and refused. A form row older than the token (before 2026-09-24) looks the same and is
refused too: when in doubt, it is not published.
"""
from __future__ import annotations

import argparse
import re
import sys

from agents.clients.supabase_client import SupabaseClient
from agents.validator_agent import ValidatorAgent
from config.settings import get_settings

def from_the_form(r: dict) -> bool:
    """A recommendation sent with form B (the only kind offered for publishing)."""
    return bool(r.get("reporter_token"))


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _print_pending(rows: list[dict], out) -> None:
    pending = [r for r in rows if from_the_form(r)]
    from_chat = len(rows) - len(pending)
    if from_chat:
        out(f"({from_chat} más llegó por el chat o no tiene origen claro: no se ofrece para publicar,"
            " porque el chat no avisa que puede publicarse.)")
    if not pending:
        out("No hay recomendaciones pendientes de aprobar.")
        return
    out(f"{len(pending)} recomendación(es) pendiente(s):")
    for r in pending:
        place = r.get("places") or {}
        name = (r.get("author_name") or "").strip() or "(sin nombre → se publicaría como Anónimo)"
        out("")
        out(f"  id:     {r['id']}")
        out(f"  lugar:  {place.get('name')} — {place.get('city')}, {place.get('country')}")
        out(f"  autor:  {name}")
        out(f"  fecha:  {r.get('created_at')}")
        out(f"  texto:  {r.get('description')}")
        if place.get("safety_level") != "gluten_free_100" and ValidatorAgent.has_exclusive_signal([r.get("description")]):
            # Audit plan step 5: a public card must not contradict the map's label.
            out("  ⚠ AVISO: el texto dice que el lugar es 100% / exclusivo sin gluten, pero en el mapa figura como")
            out("    'Tiene opciones sin TACC'. Si lo publicás, la tarjeta contradice la etiqueta. Revisá el nivel")
            out("    (scripts/review_queue.py --approve ID --level 100) o no la publiques así.")


def run(db, approve: list[str], hide: list[str], apply: bool, out=print) -> int:
    if approve and hide:
        raise ValueError("use --approve or --hide, not both")
    invalid = [i for i in (approve + hide) if not _UUID.match(i)]
    if invalid:
        out(f"Id inválido (se espera un uuid): {', '.join(invalid)}")
        return 2

    if not approve and not hide:
        _print_pending(db.fetch_unpublished_opinions(), out)
        return 0

    if hide:
        if not apply:
            out(f"DRY RUN — se retirarían {len(hide)} comentario(s): {', '.join(hide)}. Agregá --apply para escribir.")
            return 0
        changed = db.set_opinions_published(hide, False)
        out(f"Retirados: {len(changed)} de {len(hide)}.")
        return 0

    rows = db.fetch_unpublished_opinions()
    pending_ids = {r["id"] for r in rows if from_the_form(r)}
    chat_ids = {r["id"] for r in rows if not from_the_form(r)}
    allowed = [i for i in approve if i in pending_ids]
    skipped = [i for i in approve if i not in pending_ids]
    from_chat = [i for i in skipped if i in chat_ids]
    other = [i for i in skipped if i not in chat_ids]
    if from_chat:
        out(f"Omitidos (llegaron por el chat o sin origen claro; no se publican): {', '.join(from_chat)}")
    if other:
        out(f"Omitidos (no son una recomendación positiva pendiente de un lugar aprobado): {', '.join(other)}")
    if not allowed:
        return 1
    if not apply:
        out(f"DRY RUN — se publicarían {len(allowed)} comentario(s): {', '.join(allowed)}. Agregá --apply para escribir.")
        return 1 if skipped else 0
    changed = db.set_opinions_published(allowed, True)
    out(f"Publicados: {len(changed)} de {len(allowed)}.")
    return 1 if skipped else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--approve", nargs="+", default=[], metavar="ID", help="publish these report ids")
    group.add_argument("--hide", nargs="+", default=[], metavar="ID", help="take these report ids down")
    parser.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")
    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    return run(db, args.approve, args.hide, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
