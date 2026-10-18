"""Daily email to the admin with everything people and agents left to review (audit plan step 9).

One plain-text email, only when there is something new (last 24 h) or something still waiting.
Urgent events (negative reports, places taken off the map, business replies) are also emailed right
away by ``agents/admin_notify.AdminNotifier``; they appear here again as part of the day's summary.

    python -m scripts.admin_digest --dry-run      # print the email, send nothing
    python -m scripts.admin_digest                # send it (needs RESEND_API_KEY + ADMIN_EMAIL)

Privacy: chatbot turns are only COUNTED (their text is purged after 30 days and must not live on
in an inbox). Suggestion kitchen answers and report texts are for the admin's review and are
included. Whether an owner is celiac (a third party's health data) is never emailed. Partner requests show only
their CM code, the business name, their states and paid_through: never the contact's name, email or phone.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from agents.admin_notify import DEFAULT_SENDER, SUBJECT_PREFIX
from agents.validator_agent import PENDING_ADMIN_FLAG
from scripts.moderate_opinions import from_the_form
from scripts.partners_admin import PAST_DUE_GRACE_DAYS

WINDOW_HOURS = 24
_TRI = {True: "sí", False: "no", None: "sin dato"}


def _since(hours: int = WINDOW_HOURS) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _place_label(r: dict) -> str:
    p = r.get("places") or {}
    if p.get("name"):
        return f"{p['name']} ({p.get('city')}, {p.get('country')})"
    return f"{r.get('place_name_text') or '(sin lugar)'} (no está en el mapa)"


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _partner(r: dict) -> str:
    return f"- {r.get('ref_code')} · {r.get('business_name')}"


def partners_to_close(rows: list[dict], today: date) -> list[dict]:
    """Partners that partners_admin --sync would end (same rule as sync_values) but are not ended yet.

    The purge only deletes ended partners, so one left open keeps its data longer than the privacy policy says."""
    out = []
    for r in rows:
        if r.get("publication_status") in ("ended", "rejected") or not r.get("paid_through"):
            continue
        paid = date.fromisoformat(r["paid_through"])
        if ((r.get("payment_status") == "cancelled" and today > paid)
                or (r.get("payment_status") == "past_due" and today > paid + timedelta(days=PAST_DUE_GRACE_DAYS))):
            out.append(r)
    return out


def partner_sections(rows: list[dict], since: str, today: date) -> tuple[list[list[str]], dict[str, int]]:
    """The partner part of the digest. Only new requests, past_due partners and partners to close send the
    email (they go into the counts); eligible requests waiting for payment and the partners by payment state
    are listed only when the email goes out for another reason."""
    sections: list[list[str]] = []
    counts: dict[str, int] = {}
    cutoff = _parse(since)
    hint = "  python -m scripts.partners_admin --env <entorno> ... (docs/runbooks/partner-program.md)"

    new = [r for r in rows if r.get("created_at") and _parse(r["created_at"]) >= cutoff]
    if new:
        counts["solicitudes de aliado"] = len(new)
        lines = [f"SOLICITUDES DE ALIADO NUEVAS ({len(new)})"]
        lines += [f"{_partner(r)} · {r.get('publication_status')}" for r in new]
        lines.append(hint)
        sections.append(lines)

    to_close = partners_to_close(rows, today)
    if to_close:
        counts["aliados para cerrar"] = len(to_close)
        lines = [f"PARA CERRAR (correr --sync) ({len(to_close)})"]
        lines += [f"{_partner(r)} · pago {r.get('payment_status')} · {r.get('publication_status')}"
                  f" · pagado hasta {r.get('paid_through')}" for r in to_close]
        lines.append("  La purga solo borra los ended: sin --sync, sus datos quedan más de lo que dice la política.")
        lines.append("  python -m scripts.partners_admin --env <entorno> ... --sync --apply")
        sections.append(lines)

    open_rows = [r for r in rows if r.get("publication_status") not in ("ended", "rejected")]
    past_due = [r for r in open_rows if r.get("payment_status") == "past_due"]
    if past_due:
        counts["aliados con pago atrasado"] = len(past_due)

    waiting = [r for r in open_rows if r.get("publication_status") == "eligible" and r.get("payment_status") == "pending"]
    if waiting:
        sections.append([f"ELEGIBLES ESPERANDO PAGO ({len(waiting)})"] + [_partner(r) for r in waiting])

    by_payment = [r for r in open_rows if r.get("payment_status") in ("active", "past_due", "cancelled")]
    if by_payment:
        lines = ["ALIADOS POR ESTADO DE PAGO"]
        for state in ("active", "past_due", "cancelled"):
            group = [r for r in by_payment if r.get("payment_status") == state]
            if group:
                lines.append(f"{state} ({len(group)})")
                lines += [f"  {_partner(r)} · {r.get('publication_status')} · pagado hasta {r.get('paid_through')}"
                          for r in group]
        sections.append(lines)
    return sections, counts


def build_digest(db, since: str | None = None, today: date | None = None) -> tuple[str, str] | None:
    """(subject, text) for the day, or None when there is nothing to tell."""
    since = since or _since()
    today = today or datetime.now(timezone.utc).date()
    sections: list[list[str]] = []
    counts: dict[str, int] = {}

    suggestions = db.fetch_suggestions_since(since)
    if suggestions:
        counts["sugerencias"] = len(suggestions)
        lines = [f"SUGERENCIAS NUEVAS ({len(suggestions)}) — formulario 'Agregalo' y chatbot"]
        for s in suggestions:
            lines.append(f"- {s.get('name')} — {s.get('address')}, {s.get('city')}, {s.get('country')}"
                         f" · estado {s.get('status')}")
            if s.get("notes"):
                lines.append(f"    nota: {s['notes']}")
            if s.get("evidence_url"):
                lines.append(f"    link: {s['evidence_url']}")
            if any(s.get(k) is not None for k in ("kitchen_exclusive", "celiac_prep")):
                lines.append(f"    cocina: exclusiva {_TRI.get(s.get('kitchen_exclusive'))}"
                             f" · preparación {s.get('celiac_prep') or 'sin dato'}")
        lines.append("  (se procesan el lunes; las que no se ubiquen aparecen en review_queue --suggestions)")
        sections.append(lines)

    needs_location = db.fetch_suggestions_by_status("needs_location", limit=50)
    if needs_location:
        counts["sin ubicar"] = len(needs_location)
        lines = [f"SUGERENCIAS SIN UBICAR ({len(needs_location)}) — necesitan tu corrección"]
        lines += [f"- {s.get('name')} — '{s.get('address')}', {s.get('city')} · id {s.get('id')}" for s in needs_location]
        lines.append("  python -m scripts.review_queue --suggestions")
        sections.append(lines)

    reports = db.fetch_place_reports_since(since)
    negative = [r for r in reports if r.get("report_type") == "negative"]
    positive = [r for r in reports if r.get("report_type") == "positive"]
    if negative:
        counts["reportes negativos"] = len(negative)
        lines = [f"REPORTES NEGATIVOS ({len(negative)}) — no se publican"]
        for r in negative:
            lines.append(f"- {_place_label(r)}: {r.get('description')}")
        lines.append("  python -m scripts.review_queue --warnings")
        sections.append(lines)

    unpublished = db.fetch_unpublished_opinions()
    pending_opinions = [r for r in unpublished if from_the_form(r)]
    if positive or pending_opinions:
        counts["opiniones por aprobar"] = len(pending_opinions)
        lines = [f"RECOMENDACIONES: {len(positive)} nuevas hoy · {len(pending_opinions)} esperando tu aprobación"]
        for r in pending_opinions:
            lines.append(f"- {_place_label(r)} · {r.get('author_name') or 'Anónimo'}: {r.get('description')}")
            lines.append(f"    python -m scripts.moderate_opinions --approve {r.get('id')} --apply")
        if len(unpublished) > len(pending_opinions):
            lines.append(f"  ({len(unpublished) - len(pending_opinions)} del chat: no se publican)")
        sections.append(lines)

    warned = db.fetch_places_for_admin(None, warned_since=_since(24 * 30), limit=50)
    if warned:
        counts["avisos en el mapa"] = len(warned)
        lines = [f"LUGARES CON AVISO 'REPORTADO POR LA COMUNIDAD' ({len(warned)})"]
        lines += [f"- {p.get('name')} ({p.get('city')}) · desde {p.get('community_warning_at')}" for p in warned]
        sections.append(lines)

    pending_100 = db.fetch_places_for_admin(None, flag=PENDING_ADMIN_FLAG, limit=50)
    if pending_100:
        counts["100% pendientes"] = len(pending_100)
        lines = [f"100% PENDIENTES DE TU CONFIRMACIÓN ({len(pending_100)}{'+' if len(pending_100) == 50 else ''})"]
        lines += [f"- {p.get('name')} ({p.get('city')}) · {p.get('status')}" for p in pending_100[:10]]
        lines.append("  python -m scripts.review_queue --pending-100")
        sections.append(lines)

    log = db.fetch_agent_log_since(since)
    validated = Counter(
        (r.get("result") or {}).get("status") for r in log if r.get("agent") == "validator" and r.get("action") == "validate"
    )
    if validated:
        counts["validaciones"] = sum(validated.values())
        sections.append([
            "VALIDATOR",
            f"- aprobados {validated.get('approved', 0)} · a revisión humana {validated.get('needs_review', 0)}"
            f" · descartados {validated.get('discarded', 0)}",
            "  python -m scripts.review_queue --needs-review",
        ])
    errors = [r for r in log if r.get("status") == "error" and r.get("agent") != "chatbot"]
    if errors:
        counts["errores"] = len(errors)
        by = Counter(f"{r.get('agent')}/{r.get('action')}" for r in errors)
        sections.append([f"ERRORES DE LOS AGENTES ({len(errors)})"] + [f"- {k}: {n}" for k, n in by.most_common(10)])
    chat = [r for r in log if r.get("agent") == "chatbot"]
    if chat:
        marked = sum(1 for r in chat if (r.get("result") or {}).get("marked"))
        guard = sum(1 for r in chat if (r.get("result") or {}).get("guard"))
        # Counts only: the text of the turns never goes by email.
        sections.append(["CHATBOT", f"- {len(chat)} turnos · {marked} marcados · {guard} respuestas reemplazadas por el guardián"])

    partners = db.fetch_partner_applications_for_digest()
    if partners:  # None: the table does not exist yet (production until phase 3)
        partner_lines, partner_counts = partner_sections(partners, since, today)
        sections += partner_lines
        counts.update(partner_counts)

    if not counts:
        return None
    summary = " · ".join(f"{n} {k}" for k, n in counts.items())
    subject = f"{SUBJECT_PREFIX} Resumen del día — {summary}"
    text = "\n\n".join("\n".join(lines) for lines in sections)
    text += "\n\n—\nCeliacMap · resumen automático (scripts/admin_digest.py)."
    return subject, text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the email, send nothing")
    args = parser.parse_args(argv)
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
    digest = build_digest(db)
    if digest is None:
        print("Nada nuevo: no se envía el resumen.")
        return 0
    subject, text = digest
    if args.dry_run:
        print(subject)
        print()
        print(text)
        return 0

    settings.require("resend_api_key", "admin_email")
    from agents.clients.resend_client import ResendClient

    ResendClient(settings.resend_api_key).send(
        to=settings.admin_email, subject=subject, text=text,
        from_address=settings.admin_sender_email or DEFAULT_SENDER,
    )
    db.insert_agent_log("admin_notify", "admin_digest_sent", {"subject": subject}, "success", None)
    print("Resumen enviado:", subject)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
