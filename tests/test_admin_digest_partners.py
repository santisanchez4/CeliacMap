"""The partner part of the admin digest (scripts/admin_digest.py, PLAN-partner-program.md phase 1).

New requests, past_due partners and partners waiting for --sync send the email; eligible requests waiting for
payment and the partners by payment state are only listed when it goes out anyway. Never an email or a phone.
partner_applications does not exist in production until phase 3: the digest skips the part without failing.
"""
from __future__ import annotations

from datetime import date

import pytest
from postgrest.exceptions import APIError

from agents.clients.supabase_client import SupabaseClient
from scripts.admin_digest import build_digest, partners_to_close

TODAY = date(2026, 10, 18)
SINCE = "2026-10-17T03:00:00+00:00"


class DB:
    def __init__(self, partners=None, suggestions=()):
        self.partners = partners
        self.suggestions = list(suggestions)

    def fetch_suggestions_since(self, since):
        return self.suggestions

    def fetch_suggestions_by_status(self, status, limit=50):
        return []

    def fetch_place_reports_since(self, since):
        return []

    def fetch_unpublished_opinions(self):
        return []

    def fetch_places_for_admin(self, status=None, **kw):
        return []

    def fetch_agent_log_since(self, since):
        return []

    def fetch_partner_applications_for_digest(self):
        return self.partners


def row(ref, pub="requested", pay="pending", paid=None, created="2026-10-01T12:00:00Z", **extra):
    return {"ref_code": ref, "business_name": f"Comercio {ref}", "publication_status": pub, "payment_status": pay,
            "paid_through": paid, "created_at": created, **extra}


SUGGESTION = {"name": "Lugar", "address": "Calle 1", "city": "Salto", "country": "Uruguay", "status": "pending"}


def digest(partners, **kw):
    return build_digest(DB(partners, **kw), since=SINCE, today=TODAY)


def test_a_missing_table_skips_the_partner_part_without_failing():
    assert digest(None) is None
    subject, text = digest(None, suggestions=[SUGGESTION])
    assert "ALIADO" not in text and "aliado" not in subject


def test_a_new_request_sends_the_email_with_code_name_and_state():
    subject, text = digest([row("CM-NEW001", created="2026-10-17T20:00:00Z")])
    assert "1 solicitudes de aliado" in subject
    assert "SOLICITUDES DE ALIADO NUEVAS (1)" in text
    assert "- CM-NEW001 · Comercio CM-NEW001 · requested" in text


def test_an_old_request_is_not_new():
    assert digest([row("CM-OLD001", created="2026-10-16T20:00:00Z")]) is None


def test_eligible_requests_waiting_for_payment_do_not_send_the_email():
    waiting = [row("CM-ELI001", pub="eligible")]
    assert digest(waiting) is None
    subject, text = digest(waiting, suggestions=[SUGGESTION])
    assert "ELEGIBLES ESPERANDO PAGO (1)" in text and "- CM-ELI001 · Comercio CM-ELI001" in text
    assert "aliado" not in subject


def test_active_and_cancelled_partners_are_listed_only_when_the_email_goes_out():
    rows = [row("CM-ACT001", pub="approved", pay="active", paid="2026-11-17"),
            row("CM-CAN001", pub="approved", pay="cancelled", paid="2026-10-30")]
    assert digest(rows) is None
    _, text = digest(rows, suggestions=[SUGGESTION])
    assert "ALIADOS POR ESTADO DE PAGO" in text
    assert "active (1)" in text and "CM-ACT001 · Comercio CM-ACT001 · approved · pagado hasta 2026-11-17" in text
    assert "cancelled (1)" in text and "CM-CAN001" in text


def test_a_past_due_partner_sends_the_email():
    subject, text = digest([row("CM-DUE001", pub="approved", pay="past_due", paid="2026-10-10")])
    assert "1 aliados con pago atrasado" in subject
    assert "past_due (1)" in text and "pagado hasta 2026-10-10" in text
    assert "PARA CERRAR" not in text  # 8 days late: still inside the 30 days


def test_partners_waiting_for_sync_are_listed_to_close_and_send_the_email():
    rows = [
        row("CM-CAN002", pub="approved", pay="cancelled", paid="2026-10-17"),   # paid period over
        row("CM-CAN003", pub="approved", pay="cancelled", paid="2026-10-18"),   # last paid day: stays
        row("CM-DUE002", pub="approved", pay="past_due", paid="2026-09-17"),    # 31 days late
        row("CM-DUE003", pub="approved", pay="past_due", paid="2026-09-18"),    # 30 days late: stays
        row("CM-END001", pub="ended", pay="cancelled", paid="2026-01-01"),      # already ended
    ]
    assert [r["ref_code"] for r in partners_to_close(rows, TODAY)] == ["CM-CAN002", "CM-DUE002"]
    subject, text = digest(rows)
    assert "2 aliados para cerrar" in subject
    assert "PARA CERRAR (correr --sync) (2)" in text
    assert "--sync --apply" in text
    closing = text.split("PARA CERRAR")[1].split("\n\n")[0]
    assert "CM-CAN002" in closing and "CM-DUE002" in closing
    assert "CM-CAN003" not in closing and "CM-DUE003" not in closing and "CM-END001" not in closing


def test_ended_and_rejected_requests_are_not_listed():
    rows = [row("CM-END002", pub="ended", pay="cancelled", paid="2026-01-01"),
            row("CM-REJ001", pub="rejected")]
    _, text = digest(rows, suggestions=[SUGGESTION])
    assert "CM-END002" not in text and "CM-REJ001" not in text


def test_the_digest_never_carries_the_contact_data():
    contact = {"contact_name": "Ana Pérez", "contact_email": "ana@comercio.example", "contact_phone": "+598 99 123 456"}
    rows = [row("CM-NEW002", created="2026-10-18T01:00:00Z", **contact),
            row("CM-DUE004", pub="approved", pay="past_due", paid="2026-09-01", **contact)]
    subject, text = digest(rows)
    for value in contact.values():
        assert value not in text and value not in subject
    assert "@" not in text.replace("hola@celiacmap.org", "")


def test_the_client_selects_no_contact_column():
    columns = {c.strip() for c in SupabaseClient.PARTNER_DIGEST_COLUMNS.split(",")}
    assert columns == {"ref_code", "business_name", "publication_status", "payment_status", "paid_through", "created_at"}


class Query:
    """The supabase-py chain, failing on execute() with the error production gives."""

    def __init__(self, error):
        self.error = error

    def __getattr__(self, name):
        return lambda *a, **k: self

    @property
    def not_(self):
        return self

    def execute(self):
        raise self.error


class FakeSupabase:
    def __init__(self, error):
        self.error = error
        self.tables = []

    def table(self, name):
        self.tables.append(name)
        return Query(self.error)


def client(error):
    db = SupabaseClient.__new__(SupabaseClient)
    db._db = FakeSupabase(error)
    return db


PGRST205 = {"code": "PGRST205", "details": None, "hint": None,
            "message": "Could not find the table 'public.partner_applications' in the schema cache"}


def test_the_client_reads_a_missing_table_as_none():
    db = client(APIError(PGRST205))
    assert db.fetch_partner_applications_for_digest() is None
    assert db.purge_partner_applications("2026-04-18", "2024-11-18") is None
    assert db.purge_partner_applications("2026-04-18", "2024-11-18", dry_run=True) is None
    assert set(db._db.tables) == {"partner_applications"}


class ProductionQuery(Query):
    """What production answered on 2026-10-18: a GET carries PGRST205, a HEAD count has no body (bare 404)."""

    def __init__(self):
        super().__init__(None)
        self.head = False

    def select(self, *args, head=False, **kwargs):
        self.head = head
        return self

    def execute(self):
        raise APIError({"message": "JSON could not be generated", "code": 404} if self.head else PGRST205)


def test_a_dry_run_count_is_skipped_too_although_head_loses_the_code():
    db = SupabaseClient.__new__(SupabaseClient)
    db._db = type("DB", (), {"table": lambda self, name: ProductionQuery()})()
    assert db.purge_partner_applications("2026-04-18", "2024-11-18", dry_run=True) is None
    assert db.purge_partner_applications("2026-04-18", "2024-11-18") is None


def test_any_other_error_still_fails():
    for error in (APIError({"code": "42501", "message": "permission denied"}), RuntimeError("network down")):
        db = client(error)
        with pytest.raises(type(error)):
            db.fetch_partner_applications_for_digest()
        with pytest.raises(type(error)):
            db.purge_partner_applications("2026-04-18", "2024-11-18")
