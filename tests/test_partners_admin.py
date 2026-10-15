"""scripts/partners_admin.py, offline: Mercado Pago and Supabase are fakes. Every refusal of --link is covered."""
from __future__ import annotations

import copy
import re
from datetime import date
from pathlib import Path

import pytest

from scripts import partners_admin as pa
from scripts.partners_admin import AdminError, Context, Plan

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "scripts" / "partners_admin.py").read_text(encoding="utf-8")
PLAN_ID = "plan0000000000000000000000000001"
SUB_ID = "sub00000000000000000000000000001"
SELLER = 3691494674
PAYER = 3690859920
TODAY = date(2026, 10, 15)


def payment(**over):
    p = {
        "id": 184244837074, "status": "approved", "collector_id": SELLER, "transaction_amount": 790,
        "currency_id": "UYU", "payer": {"id": PAYER, "email": "Comprador@Ejemplo.com"}, "date_created": "2026-10-15",
        "point_of_interaction": {"type": "SUBSCRIPTIONS", "transaction_data": {
            "subscription_id": SUB_ID, "plan_id": PLAN_ID, "subscription_sequence": {"number": 1, "total": None}}},
    }
    p.update(over)
    return p


def preapproval(**over):
    s = {
        "id": SUB_ID, "status": "authorized", "preapproval_plan_id": PLAN_ID, "payer_id": PAYER,
        "next_payment_date": "2026-11-15T00:42:34.000-04:00",
        "auto_recurring": {"transaction_amount": 790.0, "currency_id": "UYU"},
    }
    s.update(over)
    return s


def app(**over):
    a = {
        "ref_code": "CM-TEST10", "publication_status": "eligible", "payment_status": "pending",
        "mp_preapproval_id": None, "mp_first_payment_id": None, "paid_through": None,
        "business_name": "Comercio de Prueba", "city": "Fray Bentos", "country": "Uruguay",
        "contact_email": "comprador@ejemplo.com", "created_at": "2026-10-15T00:00:00Z",
    }
    a.update(over)
    return a


class FakeMP:
    def __init__(self, pay=None, sub=None, plan_amount=790.0, plan_currency="UYU"):
        self.pay, self.sub = pay or payment(), sub or preapproval()
        self.plan_amount, self.plan_currency = plan_amount, plan_currency
        self.calls = []

    def me(self):
        return {"id": SELLER, "tags": ["test_user"], "site_id": "MLU"}

    def plan(self, plan_id):
        self.calls.append(("plan", plan_id))
        return Plan(plan_id, self.plan_amount, self.plan_currency)

    def payment(self, payment_id):
        self.calls.append(("payment", payment_id))
        return self.pay

    def preapproval(self, preapproval_id):
        self.calls.append(("preapproval", preapproval_id))
        return self.sub

    def subscriptions(self, plan_id):
        return [self.sub]

    def authorized_payments(self, preapproval_id):
        return [{"payment": {"id": self.pay["id"]}}]


def _matches(row, filters):
    for key, cond in filters.items():
        if key in ("select", "order"):
            continue
        if key == "or":
            options = re.findall(r"([a-z_]+)\.eq\.([^,)]+)", cond)
            if not any(str(row.get(k)) == v for k, v in options):
                return False
            continue
        value = row.get(key)
        if cond == "is.null" and value is not None:
            return False
        if cond == "not.is.null" and value is None:
            return False
        if cond.startswith("eq.") and str(value) != cond[3:]:
            return False
    return True


class FakeDb:
    def __init__(self, rows):
        self.rows = [copy.deepcopy(r) for r in rows]
        self.updates = []

    def select(self, **filters):
        return [copy.deepcopy(r) for r in self.rows if _matches(r, filters)]

    def by_ref(self, ref):
        rows = self.select(ref_code=f"eq.{ref}")
        if not rows:
            raise AdminError(f"no hay ninguna solicitud {ref}")
        return rows[0]

    def update(self, ref, expected, values):
        self.updates.append((ref, expected, values))
        hits = [r for r in self.rows if r["ref_code"] == ref and _matches(r, expected)]
        if len(hits) != 1:
            raise AdminError("cambió mientras tanto")
        hits[0].update(values)
        return copy.deepcopy(hits[0])


def ctx(rows=None, mp=None, apply=False):
    return Context(FakeDb(rows if rows is not None else [app()]), mp or FakeMP(), PLAN_ID, apply, TODAY)


def run(context, *args):
    return pa.main(["--env", "staging", *args], context=context)


# --- --link: success ----------------------------------------------------------------------------------------------

def test_link_dry_run_writes_nothing(capsys):
    c = ctx()
    assert run(c, "--link", "CM-TEST10", "--mp-payment", "184244837074") == 0
    assert c.db.updates == [] and "dry run" in capsys.readouterr().out


def test_link_apply_stores_only_the_four_payment_fields():
    c = ctx(apply=True)
    assert run(c, "--link", "CM-TEST10", "--mp-payment", "184244837074", "--apply") == 0
    (ref, expected, values), = c.db.updates
    assert values == {"mp_preapproval_id": SUB_ID, "mp_first_payment_id": "184244837074",
                      "paid_through": "2026-11-15", "payment_status": "active"}
    assert expected == {"publication_status": "eq.eligible", "payment_status": "eq.pending",
                        "mp_preapproval_id": "is.null", "mp_first_payment_id": "is.null"}
    row = c.db.by_ref("CM-TEST10")
    assert row["publication_status"] == "eligible", "linking never publishes"
    assert "payer_email" not in row and "comprador" not in str(values).lower()


def test_link_reads_amount_and_currency_from_the_configured_plan():
    """A plan of 990 UYU refuses a 790 payment even though 790 is a valid amount elsewhere: nothing is hardcoded."""
    c = ctx(mp=FakeMP(plan_amount=990.0))
    assert run(c, "--link", "CM-TEST10", "--mp-payment", "184244837074", "--apply") == 2
    assert c.db.updates == []
    assert ("plan", PLAN_ID) in c.mp.calls
    assert "790" not in SOURCE


# --- --link: every refusal ----------------------------------------------------------------------------------------

REFUSALS = [
    ("not eligible", dict(app=app(publication_status="requested")), "no está en estado elegible"),
    ("already approved", dict(app=app(publication_status="approved")), "no está en estado elegible"),
    ("already paid", dict(app=app(payment_status="active")), "ya tiene un pago vinculado"),
    ("subscription already linked", dict(app=app(mp_preapproval_id="other")), "ya tiene un pago vinculado"),
    ("payment already linked", dict(app=app(mp_first_payment_id="1")), "ya tiene un pago vinculado"),
    ("payment rejected", dict(pay=payment(status="rejected")), "no está aprobado"),
    ("payment refunded", dict(pay=payment(status="refunded")), "no está aprobado"),
    ("another collector", dict(pay=payment(collector_id=1)), "no lo cobró esta cuenta"),
    ("another plan in the payment", dict(pay=payment(point_of_interaction={"transaction_data": {
        "subscription_id": SUB_ID, "plan_id": "other", "subscription_sequence": {"number": 1}}})), "plan configurado"),
    ("not the first charge", dict(pay=payment(point_of_interaction={"transaction_data": {
        "subscription_id": SUB_ID, "plan_id": PLAN_ID, "subscription_sequence": {"number": 2}}})), "primer cobro"),
    ("amount differs", dict(pay=payment(transaction_amount=500)), "el plan es de 790 UYU"),
    ("currency differs", dict(pay=payment(currency_id="USD")), "el plan es de 790 UYU"),
    ("subscription cancelled", dict(sub=preapproval(status="cancelled")), "no está autorizada"),
    ("subscription paused", dict(sub=preapproval(status="paused")), "no está autorizada"),
    ("subscription of another plan", dict(sub=preapproval(preapproval_plan_id="other")), "no es del plan configurado"),
    ("subscription amount differs", dict(sub=preapproval(auto_recurring={"transaction_amount": 100.0,
                                                                         "currency_id": "UYU"})), "monto o la moneda"),
    ("another payer", dict(sub=preapproval(payer_id=1)), "pagador"),
    ("payment of another subscription", dict(sub=preapproval(id="sub-other")), "no corresponde a esa suscripción"),
    ("no next charge date", dict(sub=preapproval(next_payment_date=None)), "próximo cobro"),
]


@pytest.mark.parametrize("label, case, message", REFUSALS, ids=[r[0] for r in REFUSALS])
def test_link_refuses(label, case, message, capsys):
    c = ctx(rows=[case.get("app", app())], mp=FakeMP(case.get("pay"), case.get("sub")), apply=True)
    assert run(c, "--link", "CM-TEST10", "--mp-payment", "184244837074", "--apply") == 2
    assert c.db.updates == []
    assert message in capsys.readouterr().err


def test_link_refuses_a_payment_or_subscription_linked_to_another_request(capsys):
    other = app(ref_code="CM-OTHER1", publication_status="approved", payment_status="active",
                mp_preapproval_id=SUB_ID, mp_first_payment_id="184244837074")
    c = ctx(rows=[app(), other], apply=True)
    assert run(c, "--link", "CM-TEST10", "--mp-payment", "184244837074", "--apply") == 2
    assert c.db.updates == [] and "ya está vinculado a CM-OTHER1" in capsys.readouterr().err


def test_link_refuses_a_payment_that_is_not_a_subscription(capsys):
    c = ctx(mp=FakeMP(pay=payment(point_of_interaction={"type": "CHECKOUT", "transaction_data": {}})), apply=True)
    assert run(c, "--link", "CM-TEST10", "--mp-payment", "184244837074", "--apply") == 2
    assert c.db.updates == [] and "no es de una suscripción" in capsys.readouterr().err


@pytest.mark.parametrize("args", [
    ["--link", "CM-TEST10"],
    ["--link", "CM-TEST10", "--mp-payment", "abc"],
    ["--link", "cm-test10", "--mp-payment", "1"],
    ["--link", "CM-NOPE00", "--mp-payment", "1"],
])
def test_link_refuses_bad_arguments(args):
    c = ctx(apply=True)
    assert run(c, *args, "--apply") == 2 and c.db.updates == []


def test_link_is_compare_and_set():
    """If the row changes between the read and the write, the guarded PATCH matches nothing and nothing is written."""
    c = ctx(apply=True)
    original = c.db.update

    def racing_update(ref, expected, values):
        c.db.rows[0]["payment_status"] = "active"
        return original(ref, expected, values)

    c.db.update = racing_update
    assert run(c, "--link", "CM-TEST10", "--mp-payment", "184244837074", "--apply") == 2
    assert c.db.rows[0]["mp_preapproval_id"] is None


# --- --suggest ----------------------------------------------------------------------------------------------------

def test_suggest_matches_email_in_memory_masked_and_writes_nothing(capsys):
    c = ctx(apply=True)
    assert run(c, "--suggest", "CM-TEST10") == 0
    out = capsys.readouterr().out
    assert "sugerencia: pago 184244837074" in out and "co***@e***.com" in out
    assert "comprador@ejemplo.com" not in out.lower()
    assert c.db.updates == []


def test_suggest_without_match_asks_for_the_operation_number(capsys):
    c = ctx(rows=[app(contact_email="otra@persona.com")])
    assert run(c, "--suggest", "CM-TEST10") == 0
    assert "número de operación" in capsys.readouterr().out and c.db.updates == []


def test_suggest_skips_subscriptions_already_linked(capsys):
    other = app(ref_code="CM-OTHER1", mp_preapproval_id=SUB_ID, payment_status="active")
    c = ctx(rows=[app(), other])
    run(c, "--suggest", "CM-TEST10")
    assert "sugerencia" not in capsys.readouterr().out


# --- eligible / reject / approve ----------------------------------------------------------------------------------

def test_eligible_only_from_requested():
    c = ctx(rows=[app(publication_status="requested")], apply=True)
    assert run(c, "--eligible", "CM-TEST10", "--note", "revisado", "--apply") == 0
    assert c.db.updates[0][2] == {"publication_status": "eligible", "admin_notes": "revisado"}
    c = ctx(rows=[app(publication_status="rejected")], apply=True)
    assert run(c, "--eligible", "CM-TEST10", "--apply") == 2 and c.db.updates == []


def test_reject_needs_a_note_and_an_unpaid_request():
    assert run(ctx(rows=[app(publication_status="requested")], apply=True), "--reject", "CM-TEST10", "--apply") == 2
    c = ctx(rows=[app(payment_status="active")], apply=True)
    assert run(c, "--reject", "CM-TEST10", "--note", "x", "--apply") == 2 and c.db.updates == []


def test_approve_needs_an_active_payment_and_eligible_request():
    args = ["--approve", "CM-TEST10", "--public-name", "Comercio", "--text-es", "Hola", "--text-en", "Hi",
            "--public-link", "Instagram=https://instagram.com/x", "--apply"]
    c = ctx(rows=[app()], apply=True)
    assert run(c, *args) == 2 and c.db.updates == []
    c = ctx(rows=[app(payment_status="active")], apply=True)
    assert run(c, *args) == 0
    values = c.db.updates[0][2]
    assert values["publication_status"] == "approved"
    assert values["public_links"] == [{"label": "Instagram", "url": "https://instagram.com/x"}]


def test_approve_refuses_a_non_https_link():
    c = ctx(rows=[app(payment_status="active")], apply=True)
    assert run(c, "--approve", "CM-TEST10", "--public-name", "Comercio", "--text-es", "a", "--text-en", "b",
               "--public-link", "Web=http://x.com", "--apply") == 2
    assert c.db.updates == []


# --- --sync -------------------------------------------------------------------------------------------------------

LINKED = dict(publication_status="approved", payment_status="active", mp_preapproval_id=SUB_ID,
              mp_first_payment_id="1", paid_through="2026-11-15")


@pytest.mark.parametrize("sub, linked, today, expected", [
    (preapproval(), {}, TODAY, {}),
    (preapproval(next_payment_date="2026-12-15T00:00:00.000-04:00"), {}, date(2026, 11, 16),
     {"paid_through": "2026-12-15"}),
    (preapproval(status="cancelled"), {}, TODAY, {"payment_status": "cancelled"}),
    (preapproval(status="paused"), {}, TODAY, {"payment_status": "past_due"}),
    (preapproval(next_payment_date="2026-11-15T00:00:00.000-04:00"), {}, date(2026, 11, 20),
     {"payment_status": "past_due"}),
    (preapproval(next_payment_date="2026-11-15T00:00:00.000-04:00"), {"payment_status": "past_due"},
     date(2026, 12, 16), {"publication_status": "ended"}),
    (preapproval(next_payment_date="2026-11-15T00:00:00.000-04:00"), {"payment_status": "past_due"},
     date(2026, 12, 15), {}),
    (preapproval(next_payment_date="2026-12-15T00:00:00.000-04:00"), {"payment_status": "past_due"},
     date(2026, 11, 20), {"payment_status": "active", "paid_through": "2026-12-15"}),
])
def test_sync_values(sub, linked, today, expected):
    assert pa.sync_values({**app(), **LINKED, **linked}, sub, today) == expected


def test_sync_never_unpublishes_by_itself_except_after_30_days_past_due():
    values = pa.sync_values({**app(), **LINKED}, preapproval(status="cancelled"), TODAY)
    assert "publication_status" not in values


# --- Static guards --------------------------------------------------------------------------------------------------

def test_mercado_pago_client_only_reads():
    client = SOURCE[SOURCE.index("class MercadoPago"): SOURCE.index("class Db")]
    assert ".get(" in client
    for verb in (".post(", ".put(", ".patch(", ".delete("):
        assert verb not in client


def test_script_never_touches_the_evaluation_tables_nor_stores_the_payer_email():
    for table in ("places", "place_votes", "reviews", "place_evidence", "suggestions", "place_reports"):
        assert f"/rest/v1/{table}" not in SOURCE and f'"{table}"' not in SOURCE
    assert "payer_email" not in SOURCE.split('"""', 2)[2]
    assert SOURCE.count("/rest/v1/partner_applications") == 1


def test_production_is_not_enabled_yet(capsys):
    assert pa.main(["--env", "production"]) == 2
    assert "Fase 3" in capsys.readouterr().err
