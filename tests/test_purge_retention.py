"""The weekly retention purge (scripts/purge_chat_logs.py, .github/workflows/chat-log-purge.yml).

Privacy phase 1 (2026-09-29): chatbot logs 30 days, chat_usage 7 days, Google review snippets 30 days (the
emptied place ids are logged so the monthly Search run re-fetches them).
Privacy phase 2 (2026-09-30), windows decided by the owner: agent_log 1 year; suggestions, unpublished
place_reports and the suggestion notes copied to place_evidence (source 'user') 2 years; contact_email and
outreach_messages 2 years after the last contact. place_votes and published opinions are never purged here.
Partner program (2026-10-18, privacy v1.2 draft section 6): a request never charged 6 months after the request; an
ended partner 2 years after its last charge (paid_through minus one month: monthly plan). Skipped while
partner_applications does not exist (production until phase 3).
--dry-run only counts.
"""
from __future__ import annotations

from datetime import date

import pytest

from scripts.purge_chat_logs import add_months, partner_cutoffs, run


class FakeDB:
    def __init__(self, expired_places=None, partner_table=True):
        self.calls = []
        self.logged = []
        self.expired_places = expired_places or []
        self.partner_table = partner_table
        self.partner_cutoffs = None

    def purge_partner_applications(self, requested_before, paid_through_before, dry_run=False):
        self.calls.append(("partner_applications", dry_run))
        self.partner_cutoffs = (requested_before, paid_through_before)
        return {"unpaid": 2, "ended": 1} if self.partner_table else None

    def delete_chatbot_logs(self, cutoff_days=30, dry_run=False):
        self.calls.append(("chatbot_logs", cutoff_days, dry_run))
        return 3

    def delete_old_chat_usage(self, cutoff_days=7, dry_run=False):
        self.calls.append(("chat_usage", cutoff_days, dry_run))
        return 5

    def delete_expired_google_reviews(self, cutoff_days=30):
        self.calls.append(("google_reviews", cutoff_days, False))
        return list(self.expired_places)

    def find_expired_google_review_places(self, cutoff_days=30):
        self.calls.append(("google_reviews", cutoff_days, True))
        return list(self.expired_places)

    def purge_rows(self, table, older_than_days, filters=(), dry_run=False):
        self.calls.append((table, older_than_days, tuple(filters), dry_run))
        if table == "agent_log":
            return 0 if ("eq", "agent", "privacy") in filters else 7
        return {"suggestions": 1, "place_reports": 2, "place_evidence": 0}[table]

    def expire_outreach_contacts(self, older_than_days=730, dry_run=False):
        self.calls.append(("outreach", older_than_days, dry_run))
        return {"contact_emails": 1, "messages": 4}

    def insert_agent_log(self, agent, action, result, status, place_id=None):
        self.logged.append((agent, action, result, status))


EXPECTED_WINDOWS = [
    ("chatbot_logs", 30),
    ("chat_usage", 7),
    ("google_reviews", 30),
    ("agent_log", 365, (("neq", "agent", "privacy"),)),
    ("agent_log", 1825, (("eq", "agent", "privacy"),)),
    ("suggestions", 730, ()),
    ("place_reports", 730, (("is_", "published_at", "null"),)),
    ("place_evidence", 730, (("eq", "source", "user"),)),
    ("outreach", 730),
    ("partner_applications",),
]


def _windows(calls):
    return [c[:-1] for c in calls]


def test_run_applies_every_retention_window():
    db = FakeDB()
    summary = run(db)
    assert _windows(db.calls) == EXPECTED_WINDOWS
    assert all(c[-1] is False for c in db.calls)
    assert summary == {
        "chatbot_logs": 3, "chat_usage": 5, "google_reviews_places": 0, "agent_log": 7, "privacy_records": 0,
        "suggestions": 1,
        "place_reports_unpublished": 2, "place_evidence_user": 0, "contact_emails": 1, "outreach_messages": 4,
        "partner_requests_unpaid": 2, "partners_ended": 1,
    }


def test_published_opinions_and_votes_are_never_purged():
    db = FakeDB()
    run(db)
    tables = [c[0] for c in db.calls]
    assert "place_votes" not in tables
    reports = next(c for c in db.calls if c[0] == "place_reports")
    assert ("is_", "published_at", "null") in reports[2]


def test_dry_run_counts_every_rule_and_writes_nothing():
    db = FakeDB(expired_places=["p1", "p2"])
    summary = run(db, dry_run=True)
    assert _windows(db.calls) == EXPECTED_WINDOWS
    assert all(c[-1] is True for c in db.calls)
    assert db.logged == []  # no google_reviews_purged record on a dry run
    assert summary["google_reviews_places"] == 2


def test_run_logs_the_places_whose_reviews_were_deleted_so_search_can_refetch_them():
    db = FakeDB(expired_places=["p1", "p2"])
    summary = run(db)
    assert summary["google_reviews_places"] == 2
    assert db.logged == [("search", "google_reviews_purged", {"place_ids": ["p1", "p2"]}, "success")]


def test_run_logs_nothing_when_no_review_expired():
    db = FakeDB()
    run(db)
    assert db.logged == []


def test_deletion_request_records_are_kept_five_years_not_one():
    # The owner's decision (2026-09-30): the agent='privacy' records prove a deletion request was answered
    # (reference, counts, ids; no content), so they are excluded from the 1-year window and kept 5 years.
    db = FakeDB()
    run(db)
    agent_log = [c for c in db.calls if c[0] == "agent_log"]
    assert agent_log == [("agent_log", 365, (("neq", "agent", "privacy"),), False),
                         ("agent_log", 1825, (("eq", "agent", "privacy"),), False)]


def test_partner_windows_come_from_privacy_v12_section_6():
    db = FakeDB()
    run(db, today=date(2026, 10, 18))
    # Never charged: 6 months from the request. Ended: last charge (paid_through - 1 month) over 2 years ago,
    # so paid_through before 2024-11-18 (23 months back).
    assert db.partner_cutoffs == ("2026-04-18", "2024-11-18")


@pytest.mark.parametrize("today, expected", [
    (date(2026, 10, 18), ("2026-04-18", "2024-11-18")),
    (date(2026, 8, 31), ("2026-02-28", "2024-09-30")),   # clamped to the shorter month
    (date(2026, 1, 15), ("2025-07-15", "2024-02-15")),   # across the year
])
def test_partner_cutoffs(today, expected):
    assert partner_cutoffs(today) == expected


def test_last_charge_is_paid_through_minus_one_month():
    # A partner whose last charge was 2024-10-18 has paid_through 2024-11-18 (monthly plan): on 2026-10-18 it is
    # exactly 2 years, not yet over, so it is kept; a day later it goes.
    last_charge = date(2024, 10, 18)
    paid_through = add_months(last_charge, 1)
    assert paid_through.isoformat() >= partner_cutoffs(date(2026, 10, 18))[1]
    assert paid_through.isoformat() < partner_cutoffs(date(2026, 10, 19))[1]


def test_a_missing_partner_table_is_skipped_without_failing():
    db = FakeDB(partner_table=False)
    summary = run(db)
    assert summary["partner_applications"] == "skipped (no table)"
    assert "partners_ended" not in summary
    assert summary["suggestions"] == 1  # the rest of the purge ran
