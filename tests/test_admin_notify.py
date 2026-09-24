"""Admin notifications (audit plan step 9): urgent alerts with an hourly cap, and the daily digest."""
from __future__ import annotations

from unittest.mock import MagicMock

from agents.admin_notify import ALERT_ACTION, AdminNotifier, build_notifier
from agents.review_handler import ReviewHandler
from agents.validator_agent import PENDING_ADMIN_FLAG
from scripts.admin_digest import build_digest


def notifier(sent_last_hour=0):
    resend, db = MagicMock(), MagicMock()
    db.fetch_agent_log_count.return_value = sent_last_hour
    return AdminNotifier(resend, db, "santiagosanchez@celiacmap.org"), resend, db


def test_urgent_sends_with_prefix_and_logs_it():
    n, resend, db = notifier()
    assert n.urgent("Reporte negativo — X", "texto", agent="review_handler", place_id="p1")
    kwargs = resend.send.call_args.kwargs
    assert kwargs["to"] == "santiagosanchez@celiacmap.org"
    assert kwargs["subject"] == "[CeliacMap] Reporte negativo — X"
    assert kwargs["from_address"] == "CeliacMap <avisos@celiacmap.org>"
    db.insert_agent_log.assert_called_once_with("review_handler", ALERT_ACTION, {"subject": "Reporte negativo — X"}, "success", "p1")


def test_urgent_respects_the_hourly_cap():
    n, resend, _ = notifier(sent_last_hour=10)
    assert not n.urgent("x", "y", agent="review_handler")
    resend.send.assert_not_called()


def test_a_failed_email_never_raises():
    n, resend, _ = notifier()
    resend.send.side_effect = RuntimeError("resend down")
    assert n.urgent("x", "y", agent="review_handler") is False


def test_notifications_are_off_without_admin_email():
    settings = MagicMock(resend_api_key="re_x", admin_email="")
    assert build_notifier(settings, MagicMock()) is None


def test_review_handler_alerts_the_admin_with_the_report_text():
    db, llm, n = MagicMock(), MagicMock(), MagicMock()
    db.claim_place_report.return_value = True
    db.fetch_place_by_id.return_value = {"id": "p1", "name": "Cafe X", "city": "Salto", "country": "Uruguay",
                                         "status": "approved", "safety_level": "celiac_friendly"}
    db.fetch_place_report_by_id.return_value = {"id": "r1", "place_id": "p1", "report_type": "negative",
                                                "description": "me contaminé con una torta"}
    db.fetch_reviews_for_place.return_value = []
    db.fetch_place_evidence.return_value = []
    db.fetch_recent_negative_report_count.return_value = 1
    llm.complete_json.return_value = {"verdict": "needs_review", "confidence_score": 0.5,
                                      "reporte_contaminacion_creible": True}

    ReviewHandler(db, llm, notifier=n).handle("p1", "r1")

    subject, text = n.urgent.call_args.args
    assert subject.startswith("URGENTE: retirado del mapa")
    assert "me contaminé con una torta" in text


class DigestDB:
    def __init__(self, **kw):
        self.kw = kw

    def fetch_suggestions_since(self, since):
        return self.kw.get("suggestions", [])

    def fetch_suggestions_by_status(self, status, limit=50):
        return self.kw.get("needs_location", [])

    def fetch_place_reports_since(self, since):
        return self.kw.get("reports", [])

    def fetch_unpublished_opinions(self):
        return self.kw.get("opinions", [])

    def fetch_places_for_admin(self, status=None, **kw):
        return self.kw.get("pending_100", []) if kw.get("flag") == PENDING_ADMIN_FLAG else self.kw.get("warned", [])

    def fetch_agent_log_since(self, since):
        return self.kw.get("log", [])


def test_nothing_new_means_no_email():
    assert build_digest(DigestDB()) is None


def test_digest_groups_everything_and_never_includes_chat_text():
    db = DigestDB(
        suggestions=[{"name": "Pastas Lo de Flor", "address": "JC 23", "city": "Fray Bentos", "country": "Uruguay",
                      "status": "new", "notes": "pastas caseras", "kitchen_exclusive": True, "owner_celiac": True}],
        reports=[{"report_type": "negative", "description": "cerraron", "places": {"name": "Cafe X", "city": "Salto", "country": "Uruguay"}}],
        opinions=[{"id": "o1", "description": "riquísimo", "author_name": None, "places": {"name": "San Felipa", "city": "Gualeguaychú", "country": "Argentina"}}],
        log=[
            {"agent": "validator", "action": "validate", "status": "success", "result": {"status": "needs_review"}},
            {"agent": "chatbot", "action": "turn", "status": "success", "result": {"marked": True, "raw_user_text": "SECRETO"}},
            {"agent": "social", "action": "social_query_failed", "status": "error", "result": {}},
        ],
    )
    subject, text = build_digest(db)
    assert subject.startswith("[CeliacMap] Resumen del día")
    assert "Pastas Lo de Flor" in text and "dueño/a celíaco/a sí" in text
    assert "cerraron" in text and "riquísimo" in text and "moderate_opinions --approve o1" in text
    assert "a revisión humana 1" in text
    assert "social/social_query_failed: 1" in text
    assert "1 turnos · 1 marcados" in text
    assert "SECRETO" not in text
