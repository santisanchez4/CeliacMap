"""The admin's tool for the partner program «CeliacMap Aliado» (ADR-011, docs/plans/PLAN-partner-program.md, phase 1).

Contracting and publishing are separate steps: Mercado Pago charges, this script checks the charge against Mercado Pago
(read-only GETs) and the admin approves the card. Lists are read-only; every write is a dry run unless ``--apply``.
Only ``--env staging`` exists until phase 3. It never touches places, votes, reviews or the Validator.

    python -m scripts.partners_admin --env staging --project-ref REF                       # list the requests
    python -m scripts.partners_admin ... --eligible CM-XXXXXX [--note "..."] [--apply]      # requested -> eligible
    python -m scripts.partners_admin ... --reject CM-XXXXXX --note "..." [--apply]          # requested/eligible -> rejected
    python -m scripts.partners_admin ... --suggest CM-XXXXXX                                # payments whose payer email matches (read-only)
    python -m scripts.partners_admin ... --link CM-XXXXXX --mp-payment PAYMENT_ID [--apply] # link the subscription
    python -m scripts.partners_admin ... --approve CM-XXXXXX --public-name "..." --text-es "..." --text-en "..." \\
                                         --public-link "Instagram=https://..." [--apply]     # publish the card
    python -m scripts.partners_admin ... --sync [--apply]                                   # payment state from Mercado Pago

``--link`` writes only after every check passes: the request is ``eligible``, still unpaid and has no payment linked; the
payment is ``approved``, is the FIRST charge of a subscription of the configured plan, was collected by this account, and
its amount and currency are the plan's (read from Mercado Pago, never written in code); the subscription is
``authorized``, belongs to the plan and to the same payer; neither the payment nor the subscription is linked to another
request. It stores only ``mp_preapproval_id``, ``mp_first_payment_id``, ``paid_through`` (the subscription's next charge
date) and ``payment_status = 'active'``. It never sets ``publication_status``: publishing is ``--approve``.

The payer's email is only compared in memory by ``--suggest`` (case-insensitive, exact) and printed masked; it is never
stored and never links by itself.

Config (``.env.staging``, see docs/runbooks/staging.md): the staging Supabase keys, ``MP_TEST_ACCESS_TOKEN`` (must be a
Mercado Pago test user of Uruguay) and ``MP_TEST_PLAN_ID``. Production keys are separate and are not wired until phase 3.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from scripts.staging_guard import ENV_FILE, StagingGuardError, load_env, staging_target

MP_API = "https://api.mercadopago.com"
TIMEOUT = 30
PAST_DUE_GRACE_DAYS = 30
REF_RE = re.compile(r"CM-[A-Z0-9]{6}")
LINKED_PAYMENT_STATUSES = ("active", "past_due", "cancelled")


class AdminError(RuntimeError):
    """A refusal. The message is safe to print (no token, no full email)."""


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "(sin email)"
    user, domain = email.split("@", 1)
    host, _, tld = domain.rpartition(".")
    return f"{user[:2]}***@{host[:1]}***.{tld or '?'}"


def mp_date(value: str | None) -> date | None:
    """Mercado Pago dates carry their own offset (-04:00); the calendar date is the one Mercado Pago shows."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


# --- Mercado Pago (GET only) -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Plan:
    id: str
    amount: float
    currency: str


class MercadoPago:
    def __init__(self, token: str, session: requests.Session | None = None):
        self._token = token
        self._session = session or requests.Session()

    def get(self, path: str, **params) -> dict:
        resp = self._session.get(f"{MP_API}{path}", headers={"Authorization": f"Bearer {self._token}"},
                                 params=params or None, timeout=TIMEOUT)
        if resp.status_code == 404:
            raise AdminError(f"Mercado Pago: {path} no existe (404)")
        if resp.status_code >= 300:
            raise AdminError(f"Mercado Pago: GET {path} respondió HTTP {resp.status_code}")
        return resp.json()

    def me(self) -> dict:
        return self.get("/users/me")

    def plan(self, plan_id: str) -> Plan:
        data = self.get(f"/preapproval_plan/{plan_id}")
        rec = data.get("auto_recurring") or {}
        if data.get("status") != "active":
            raise AdminError(f"el plan {plan_id} no está activo en Mercado Pago ({data.get('status')})")
        if rec.get("transaction_amount") is None or not rec.get("currency_id"):
            raise AdminError(f"el plan {plan_id} no tiene monto o moneda")
        return Plan(plan_id, float(rec["transaction_amount"]), rec["currency_id"])

    def payment(self, payment_id: str) -> dict:
        return self.get(f"/v1/payments/{payment_id}")

    def preapproval(self, preapproval_id: str) -> dict:
        return self.get(f"/preapproval/{preapproval_id}")

    def subscriptions(self, plan_id: str) -> list[dict]:
        return self.get("/preapproval/search", preapproval_plan_id=plan_id).get("results", [])

    def authorized_payments(self, preapproval_id: str) -> list[dict]:
        return self.get("/authorized_payments/search", preapproval_id=preapproval_id).get("results", [])


# --- Supabase (PostgREST, service_role) ---------------------------------------------------------------------------

class Db:
    def __init__(self, url: str, service_key: str, session: requests.Session | None = None):
        self._base = url.rstrip("/") + "/rest/v1/partner_applications"
        self._headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
        self._session = session or requests.Session()

    def select(self, **filters: str) -> list[dict]:
        resp = self._session.get(self._base, headers=self._headers,
                                 params={"select": "*", "order": "created_at.asc", **filters}, timeout=TIMEOUT)
        if resp.status_code >= 300:
            raise AdminError(f"Supabase: lectura de partner_applications HTTP {resp.status_code}")
        return resp.json()

    def by_ref(self, ref: str) -> dict:
        rows = self.select(ref_code=f"eq.{ref}")
        if not rows:
            raise AdminError(f"no hay ninguna solicitud {ref}")
        return rows[0]

    def update(self, ref: str, expected: dict[str, str], values: dict) -> dict:
        """Compare-and-set: the PATCH only matches if the row is still in the expected state. Exactly one row or error."""
        params = {"ref_code": f"eq.{ref}", **expected}
        resp = self._session.patch(self._base, params=params, json=values, timeout=TIMEOUT,
                                   headers={**self._headers, "Content-Type": "application/json",
                                            "Prefer": "return=representation"})
        if resp.status_code >= 300:
            raise AdminError(f"Supabase rechazó la escritura: HTTP {resp.status_code} {resp.text[:200]}")
        rows = resp.json()
        if len(rows) != 1:
            raise AdminError(f"la solicitud {ref} cambió mientras tanto ({len(rows)} filas): no se escribió nada")
        return rows[0]


# --- Decisions (pure, tested offline) ------------------------------------------------------------------------------

def _transaction_data(payment: dict) -> dict:
    return ((payment.get("point_of_interaction") or {}).get("transaction_data")) or {}


def link_problems(app: dict, payment: dict, preapproval: dict, plan: Plan, seller_id: int | str,
                  linked_rows: list[dict]) -> list[str]:
    """Every reason --link must refuse. Empty list = the link is safe."""
    problems: list[str] = []
    ref = app.get("ref_code")
    if app.get("publication_status") != "eligible":
        problems.append(f"{ref} no está en estado elegible (está en {app.get('publication_status')})")
    if app.get("payment_status") != "pending" or app.get("mp_preapproval_id") or app.get("mp_first_payment_id"):
        problems.append(f"{ref} ya tiene un pago vinculado ({app.get('payment_status')})")

    td = _transaction_data(payment)
    if payment.get("status") != "approved":
        problems.append(f"el pago {payment.get('id')} no está aprobado ({payment.get('status')})")
    if str(payment.get("collector_id")) != str(seller_id):
        problems.append("el pago no lo cobró esta cuenta de Mercado Pago")
    if td.get("plan_id") != plan.id:
        problems.append("el pago no es de una suscripción del plan configurado")
    if not td.get("subscription_id") or td.get("subscription_id") != preapproval.get("id"):
        problems.append("el pago no corresponde a esa suscripción")
    if ((td.get("subscription_sequence") or {}).get("number")) != 1:
        problems.append("el pago no es el primer cobro de la suscripción")
    if float(payment.get("transaction_amount") or 0) != plan.amount or payment.get("currency_id") != plan.currency:
        problems.append(f"el pago es de {payment.get('transaction_amount')} {payment.get('currency_id')},"
                        f" el plan es de {plan.amount:g} {plan.currency}")

    rec = preapproval.get("auto_recurring") or {}
    if preapproval.get("status") != "authorized":
        problems.append(f"la suscripción no está autorizada ({preapproval.get('status')})")
    if preapproval.get("preapproval_plan_id") != plan.id:
        problems.append("la suscripción no es del plan configurado")
    if float(rec.get("transaction_amount") or 0) != plan.amount or rec.get("currency_id") != plan.currency:
        problems.append("el monto o la moneda de la suscripción no son los del plan")
    if str(preapproval.get("payer_id")) != str((payment.get("payer") or {}).get("id")):
        problems.append("el pagador del pago no es el de la suscripción")
    if not mp_date(preapproval.get("next_payment_date")):
        problems.append("la suscripción no tiene fecha del próximo cobro")

    for row in linked_rows:
        if row.get("ref_code") != ref:
            problems.append(f"ese pago o esa suscripción ya está vinculado a {row.get('ref_code')}")
    return problems


def link_values(payment: dict, preapproval: dict) -> dict:
    return {
        "mp_preapproval_id": preapproval["id"],
        "mp_first_payment_id": str(payment["id"]),
        "paid_through": mp_date(preapproval["next_payment_date"]).isoformat(),
        "payment_status": "active",
    }


def sync_values(app: dict, preapproval: dict, today: date) -> dict:
    """The payment state Mercado Pago implies for a linked request. {} = nothing to change.

    authorized + next charge not in the past -> active, paid_through = next charge date;
    authorized with a next charge already past (a charge failed) or paused -> past_due (paid_through unchanged);
    cancelled -> cancelled (paid_through unchanged: the card stays until then);
    past_due for more than 30 days after paid_through -> publication_status ended (owner decision 2026-10-14).
    """
    status = preapproval.get("status")
    nxt = mp_date(preapproval.get("next_payment_date"))
    paid = date.fromisoformat(app["paid_through"]) if app.get("paid_through") else None
    values: dict = {}
    if status == "cancelled":
        values["payment_status"] = "cancelled"
    elif status == "authorized" and nxt and nxt >= today:
        values["payment_status"] = "active"
        values["paid_through"] = nxt.isoformat()
    elif status in ("authorized", "paused"):
        values["payment_status"] = "past_due"
    new_status = values.get("payment_status", app.get("payment_status"))
    if (new_status == "past_due" and paid and today > paid + timedelta(days=PAST_DUE_GRACE_DAYS)
            and app.get("publication_status") not in ("ended", "rejected")):
        values["publication_status"] = "ended"
    return {k: v for k, v in values.items() if app.get(k) != v}


def public_links(pairs: list[str]) -> list[dict]:
    links = []
    for pair in pairs:
        label, sep, url = pair.partition("=")
        if not sep or not url.startswith("https://") or not label.strip() or len(label) > 40 or len(url) > 300:
            raise AdminError(f"--public-link debe ser 'Etiqueta=https://...': {pair!r}")
        links.append({"label": label.strip(), "url": url.strip()})
    return links


def approve_problems(app: dict, name: str, text_es: str, text_en: str) -> list[str]:
    problems = []
    if app.get("publication_status") != "eligible":
        problems.append(f"{app.get('ref_code')} no está en estado elegible (está en {app.get('publication_status')})")
    if app.get("payment_status") != "active":
        problems.append(f"el pago de {app.get('ref_code')} no está activo ({app.get('payment_status')})")
    if not 2 <= len(name.strip()) <= 80:
        problems.append("--public-name: entre 2 y 80 caracteres")
    for flag, text in (("--text-es", text_es), ("--text-en", text_en)):
        if not text.strip() or len(text) > 400:
            problems.append(f"{flag}: entre 1 y 400 caracteres")
    return problems


# --- Commands ------------------------------------------------------------------------------------------------------

@dataclass
class Context:
    db: Db
    mp: MercadoPago
    plan_id: str
    apply: bool
    today: date


def show(rows: list[dict]) -> None:
    if not rows:
        print("no hay solicitudes")
    for r in rows:
        print(f"{r['ref_code']}  {r['publication_status']:<9} pago={r['payment_status']:<9} hasta={r.get('paid_through') or '-':<10}"
              f"  {r['business_name']} ({r['city']}, {r['country']})  contacto {mask_email(r.get('contact_email'))}"
              f"  creada {str(r.get('created_at'))[:10]}")


def write(ctx: Context, ref: str, expected: dict[str, str], values: dict) -> None:
    print(f"{ref}: {json.dumps(values, ensure_ascii=False)}")
    if not ctx.apply:
        print("dry run: no se escribió nada. Agregá --apply.")
        return
    row = ctx.db.update(ref, expected, values)
    print(f"escrito: {row['ref_code']} {row['publication_status']} pago={row['payment_status']}")


def cmd_eligible(ctx: Context, ref: str, note: str | None) -> None:
    app = ctx.db.by_ref(ref)
    if app["publication_status"] != "requested":
        raise AdminError(f"{ref} no está en 'requested' (está en {app['publication_status']})")
    values = {"publication_status": "eligible"}
    if note:
        values["admin_notes"] = note
    write(ctx, ref, {"publication_status": "eq.requested"}, values)


def cmd_reject(ctx: Context, ref: str, note: str) -> None:
    app = ctx.db.by_ref(ref)
    if app["publication_status"] not in ("requested", "eligible") or app["payment_status"] != "pending":
        raise AdminError(f"{ref} solo se rechaza antes de pagar y de publicar (está en {app['publication_status']},"
                         f" pago {app['payment_status']})")
    write(ctx, ref, {"publication_status": f"eq.{app['publication_status']}", "payment_status": "eq.pending"},
          {"publication_status": "rejected", "admin_notes": note})


def cmd_suggest(ctx: Context, ref: str) -> None:
    app = ctx.db.by_ref(ref)
    wanted = (app.get("contact_email") or "").strip().lower()
    linked = {r.get("mp_preapproval_id") for r in ctx.db.select(mp_preapproval_id="not.is.null")}
    found = 0
    for sub in ctx.mp.subscriptions(ctx.plan_id):
        if sub.get("id") in linked or sub.get("status") != "authorized":
            continue
        for ap in ctx.mp.authorized_payments(sub["id"]):
            pay_id = (ap.get("payment") or {}).get("id")
            if not pay_id:
                continue
            payment = ctx.mp.payment(str(pay_id))
            email = ((payment.get("payer") or {}).get("email") or "").strip().lower()
            if email and email == wanted:
                found += 1
                print(f"sugerencia: pago {pay_id} (suscripción {sub['id']}, {str(payment.get('date_created'))[:10]},"
                      f" {payment.get('transaction_amount')} {payment.get('currency_id')}) · pagador {mask_email(email)}")
    if not found:
        print(f"ningún pago sin vincular del plan tiene el email de {ref} ({mask_email(wanted)}):"
              " pedile al comercio el número de operación.")
    else:
        print(f"una sugerencia no vincula nada: confirmala con el comercio y usá --link {ref} --mp-payment ID")


def cmd_link(ctx: Context, ref: str, payment_id: str) -> None:
    app = ctx.db.by_ref(ref)
    payment = ctx.mp.payment(payment_id)
    sub_id = _transaction_data(payment).get("subscription_id")
    if not sub_id:
        raise AdminError(f"el pago {payment_id} no es de una suscripción")
    preapproval = ctx.mp.preapproval(sub_id)
    plan = ctx.mp.plan(ctx.plan_id)
    seller = ctx.mp.me().get("id")
    linked = ctx.db.select(**{"or": f"(mp_preapproval_id.eq.{sub_id},mp_first_payment_id.eq.{payment_id})"})
    problems = link_problems(app, payment, preapproval, plan, seller, linked)
    if problems:
        raise AdminError("no se vincula:\n  - " + "\n  - ".join(problems))
    print(f"plan {plan.id}: {plan.amount:g} {plan.currency} · pago {payment_id} aprobado · suscripción {sub_id} autorizada")
    write(ctx, ref, {"publication_status": "eq.eligible", "payment_status": "eq.pending",
                     "mp_preapproval_id": "is.null", "mp_first_payment_id": "is.null"},
          link_values(payment, preapproval))


def cmd_approve(ctx: Context, ref: str, name: str, text_es: str, text_en: str, links: list[str]) -> None:
    app = ctx.db.by_ref(ref)
    problems = approve_problems(app, name, text_es, text_en)
    if problems:
        raise AdminError("no se aprueba:\n  - " + "\n  - ".join(problems))
    write(ctx, ref, {"publication_status": "eq.eligible", "payment_status": "eq.active"}, {
        "publication_status": "approved",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "public_name": name.strip(),
        "public_text_es": text_es.strip(),
        "public_text_en": text_en.strip(),
        "public_links": public_links(links),
    })


def cmd_sync(ctx: Context) -> None:
    rows = ctx.db.select(mp_preapproval_id="not.is.null")
    changed = 0
    for app in rows:
        values = sync_values(app, ctx.mp.preapproval(app["mp_preapproval_id"]), ctx.today)
        if values:
            changed += 1
            write(ctx, app["ref_code"], {"payment_status": f"eq.{app['payment_status']}",
                                         "publication_status": f"eq.{app['publication_status']}"}, values)
    print(f"{len(rows)} solicitudes vinculadas revisadas, {changed} con cambios")


# --- Wiring --------------------------------------------------------------------------------------------------------

def staging_context(project_ref: str, env_file: Path, apply: bool) -> Context:
    env = load_env(env_file)
    staging_target(project_ref, env)
    token = (env.get("MP_TEST_ACCESS_TOKEN") or "").strip()
    plan_id = (env.get("MP_TEST_PLAN_ID") or "").strip()
    if not token or not plan_id:
        raise AdminError(f"{env_file.name} necesita MP_TEST_ACCESS_TOKEN y MP_TEST_PLAN_ID")
    mp = MercadoPago(token)
    me = mp.me()
    if "test_user" not in (me.get("tags") or []) or me.get("site_id") != "MLU":
        raise AdminError("MP_TEST_ACCESS_TOKEN no es de un usuario de prueba de Mercado Pago Uruguay")
    db = Db(env["STAGING_SUPABASE_URL"], env["STAGING_SUPABASE_SERVICE_ROLE_KEY"])
    return Context(db, mp, plan_id, apply, datetime.now(timezone.utc).date())


def main(argv: list[str] | None = None, context: Context | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", choices=["staging", "production"], required=True)
    parser.add_argument("--project-ref", help="staging project ref (required with --env staging)")
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--eligible", metavar="REF")
    action.add_argument("--reject", metavar="REF")
    action.add_argument("--suggest", metavar="REF")
    action.add_argument("--link", metavar="REF")
    action.add_argument("--approve", metavar="REF")
    action.add_argument("--sync", action="store_true")
    parser.add_argument("--mp-payment", help="Mercado Pago payment id (the 'número de operación') for --link")
    parser.add_argument("--note")
    parser.add_argument("--public-name")
    parser.add_argument("--text-es")
    parser.add_argument("--text-en")
    parser.add_argument("--public-link", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    try:
        for ref in (args.eligible, args.reject, args.suggest, args.link, args.approve):
            if ref and not REF_RE.fullmatch(ref):
                raise AdminError(f"código de solicitud inválido: {ref!r}")
        if context is None:
            if args.env == "production":
                raise AdminError("producción no está habilitada hasta la Fase 3 (ADR-011)")
            if not args.project_ref:
                raise AdminError("--env staging necesita --project-ref")
            context = staging_context(args.project_ref, args.env_file, args.apply)
        if args.eligible:
            cmd_eligible(context, args.eligible, args.note)
        elif args.reject:
            if not args.note:
                raise AdminError("--reject necesita --note")
            cmd_reject(context, args.reject, args.note)
        elif args.suggest:
            cmd_suggest(context, args.suggest)
        elif args.link:
            if not args.mp_payment or not args.mp_payment.isdigit():
                raise AdminError("--link necesita --mp-payment con el número de operación (solo dígitos)")
            cmd_link(context, args.link, args.mp_payment)
        elif args.approve:
            if not (args.public_name and args.text_es and args.text_en):
                raise AdminError("--approve necesita --public-name, --text-es y --text-en")
            cmd_approve(context, args.approve, args.public_name, args.text_es, args.text_en, args.public_link)
        elif args.sync:
            cmd_sync(context)
        else:
            show(context.db.select())
    except (AdminError, StagingGuardError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except requests.RequestException as exc:
        print(f"refused: error de red ({type(exc).__name__})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
