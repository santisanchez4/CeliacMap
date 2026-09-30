"""The weekly retention purge (scripts/purge_chat_logs.py, .github/workflows/chat-log-purge.yml).

Privacy phase 1 (2026-09-29): besides the 30-day chatbot logs it deletes chat_usage counters older
than 7 days and Google review snippets older than 30 days, and logs which places lost their snippets
so the monthly Search run can re-fetch them.
"""
from __future__ import annotations

from scripts.purge_chat_logs import run


class FakeDB:
    def __init__(self, expired_places=None):
        self.calls = []
        self.logged = []
        self.expired_places = expired_places or []

    def delete_chatbot_logs(self, cutoff_days=30):
        self.calls.append(("chatbot_logs", cutoff_days))
        return 3

    def delete_old_chat_usage(self, cutoff_days=7):
        self.calls.append(("chat_usage", cutoff_days))
        return 5

    def delete_expired_google_reviews(self, cutoff_days=30):
        self.calls.append(("google_reviews", cutoff_days))
        return list(self.expired_places)

    def insert_agent_log(self, agent, action, result, status, place_id=None):
        self.logged.append((agent, action, result, status))


def test_run_purges_the_three_retention_windows():
    db = FakeDB()
    summary = run(db)
    assert db.calls == [("chatbot_logs", 30), ("chat_usage", 7), ("google_reviews", 30)]
    assert summary == {"chatbot_logs": 3, "chat_usage": 5, "google_reviews_places": 0}


def test_run_logs_the_places_whose_reviews_were_deleted_so_search_can_refetch_them():
    db = FakeDB(expired_places=["p1", "p2"])
    summary = run(db)
    assert summary["google_reviews_places"] == 2
    assert db.logged == [("search", "google_reviews_purged", {"place_ids": ["p1", "p2"]}, "success")]


def test_run_logs_nothing_when_no_review_expired():
    db = FakeDB()
    run(db)
    assert db.logged == []
