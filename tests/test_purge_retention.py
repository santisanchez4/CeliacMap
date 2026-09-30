"""The weekly retention purge (scripts/purge_chat_logs.py, .github/workflows/chat-log-purge.yml).

Privacy phase 1 (2026-09-29): chatbot logs 30 days, chat_usage 7 days, Google review snippets 30 days (the
emptied place ids are logged so the monthly Search run re-fetches them).
Privacy phase 2 (2026-09-30), windows decided by the owner: agent_log 1 year; suggestions, unpublished
place_reports and the suggestion notes copied to place_evidence (source 'user') 2 years; contact_email and
outreach_messages 2 years after the last contact. place_votes and published opinions are never purged here.
--dry-run only counts.
"""
from __future__ import annotations

from scripts.purge_chat_logs import run


class FakeDB:
    def __init__(self, expired_places=None):
        self.calls = []
        self.logged = []
        self.expired_places = expired_places or []

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
        return {"agent_log": 7, "suggestions": 1, "place_reports": 2, "place_evidence": 0}[table]

    def expire_outreach_contacts(self, older_than_days=730, dry_run=False):
        self.calls.append(("outreach", older_than_days, dry_run))
        return {"contact_emails": 1, "messages": 4}

    def insert_agent_log(self, agent, action, result, status, place_id=None):
        self.logged.append((agent, action, result, status))


EXPECTED_WINDOWS = [
    ("chatbot_logs", 30),
    ("chat_usage", 7),
    ("google_reviews", 30),
    ("agent_log", 365, ()),
    ("suggestions", 730, ()),
    ("place_reports", 730, (("is_", "published_at", "null"),)),
    ("place_evidence", 730, (("eq", "source", "user"),)),
    ("outreach", 730),
]


def _windows(calls):
    return [c[:-1] for c in calls]


def test_run_applies_every_retention_window():
    db = FakeDB()
    summary = run(db)
    assert _windows(db.calls) == EXPECTED_WINDOWS
    assert all(c[-1] is False for c in db.calls)
    assert summary == {
        "chatbot_logs": 3, "chat_usage": 5, "google_reviews_places": 0, "agent_log": 7, "suggestions": 1,
        "place_reports_unpublished": 2, "place_evidence_user": 0, "contact_emails": 1, "outreach_messages": 4,
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
