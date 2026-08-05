"""Unit tests for the Outreach agent (offline, all external calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agents.outreach_agent import OutreachAgent


def make_place(
    id="place-1",
    name="Cafe X",
    category="cafe",
    city="Montevideo",
    phone="099123456",
    website=None,
    contact_email_checked_at=None,
    outreach_opt_out=False,
    contact_email=None,
):
    return {
        "id": id,
        "name": name,
        "category": category,
        "city": city,
        "phone": phone,
        "website": website,
        "contact_email_checked_at": contact_email_checked_at,
        "outreach_opt_out": outreach_opt_out,
        "contact_email": contact_email,
    }


def make_agent(
    max_per_run=20,
    max_scrapes_per_run=30,
    test_recipient="dev@example.com",
    inbound_domain="",
    sender_email="outreach@celiacmap.org",
    live_mode=False,
):
    db = MagicMock()
    db.fetch_needs_review_for_outreach.return_value = [make_place()]
    db.insert_outreach_message.return_value = {"id": "msg-1"}
    llm = MagicMock()
    llm.complete_json.return_value = {
        "subject": "Confirmacion sin TACC - Cafe X",
        "body": "Hola, somos el equipo de CeliacMap...",
    }
    resend_client = MagicMock()
    resend_client.send.return_value = "email-1"
    scraper = MagicMock()
    scraper.find_email.return_value = None
    agent = OutreachAgent(
        db,
        llm,
        resend_client,
        scraper,
        test_recipient=test_recipient,
        max_per_run=max_per_run,
        max_scrapes_per_run=max_scrapes_per_run,
        inbound_domain=inbound_domain,
        sender_email=sender_email,
        live_mode=live_mode,
    )
    return agent, db, llm, resend_client, scraper


# --- Selection filter -------------------------------------------------------


def test_select_candidates_keeps_phone_or_website():
    agent, db, _, _, _ = make_agent()
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(id="p1", phone="099", website=None),
        make_place(id="p2", phone=None, website="https://x.com"),
        make_place(id="p3", phone=None, website=None),
    ]
    selected = agent._select_candidates()
    assert [p["id"] for p in selected] == ["p1", "p2"]


def test_select_candidates_respects_cap():
    agent, db, _, _, _ = make_agent(max_per_run=1)
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(id="p1"),
        make_place(id="p2"),
    ]
    selected = agent._select_candidates()
    assert len(selected) == 1


def test_select_candidates_excludes_opt_out():
    agent, db, _, _, _ = make_agent()
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(id="p1", phone="099", outreach_opt_out=False),
        make_place(id="p2", phone="099", outreach_opt_out=True),
    ]
    selected = agent._select_candidates()
    assert [p["id"] for p in selected] == ["p1"]


def test_select_candidates_requires_contact_email_in_live_mode():
    agent, db, _, _, _ = make_agent(live_mode=True)
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(id="p1", phone="099", contact_email=None),
        make_place(id="p2", phone="099", contact_email="biz@example.com"),
    ]
    selected = agent._select_candidates()
    assert [p["id"] for p in selected] == ["p2"]


def test_select_candidates_ignores_contact_email_when_not_live():
    agent, db, _, _, _ = make_agent(live_mode=False)
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(id="p1", phone="099", contact_email=None),
    ]
    selected = agent._select_candidates()
    assert [p["id"] for p in selected] == ["p1"]


# --- Drafting ----------------------------------------------------------------


def test_draft_returns_none_on_llm_error():
    agent, _, llm, _, _ = make_agent()
    llm.complete_json.side_effect = RuntimeError("boom")
    assert agent._draft(make_place()) is None


def test_draft_returns_none_on_empty_subject_or_body():
    agent, _, llm, _, _ = make_agent()
    llm.complete_json.return_value = {"subject": "", "body": "algo"}
    assert agent._draft(make_place()) is None
    llm.complete_json.return_value = {"subject": "algo", "body": ""}
    assert agent._draft(make_place()) is None


def test_draft_appends_opt_out_footer():
    agent, _, llm, _, _ = make_agent()
    draft = agent._draft(make_place())
    assert draft["body"].endswith(
        "Si preferís no recibir más contactos de CeliacMap, respondé este email "
        "indicando que no querés ser contactado nuevamente."
    )


# --- Happy path ----------------------------------------------------------------


def test_successful_draft_and_send():
    agent, db, llm, resend_client, _ = make_agent()

    summary = agent.run()

    assert summary["candidates_seen"] == 1
    assert summary["drafted"] == 1
    assert summary["sent"] == 1
    assert summary["errors"] == 0

    expected_body = (
        "Hola, somos el equipo de CeliacMap...\n\n"
        "Si preferís no recibir más contactos de CeliacMap, respondé este email "
        "indicando que no querés ser contactado nuevamente."
    )
    resend_client.send.assert_called_once_with(
        to="dev@example.com",
        subject="Confirmacion sin TACC - Cafe X",
        text=expected_body,
        from_address="outreach@celiacmap.org",
        reply_to=None,
    )
    db.insert_outreach_message.assert_called_once()
    call = db.insert_outreach_message.call_args
    assert call.args[0] == "place-1"
    assert call.kwargs["direction"] == "sent"
    assert call.kwargs["channel"] == "email"

    db.update_place.assert_called_once_with(
        "place-1", {"outreach_status": "sent", "outreach_channel": "email"}
    )


# --- Error handling ------------------------------------------------------------


def test_candidate_without_contact_is_skipped():
    agent, db, llm, resend_client, _ = make_agent()
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(phone=None, website=None)
    ]

    summary = agent.run()

    assert summary["candidates_seen"] == 0
    assert summary["drafted"] == 0
    llm.complete_json.assert_not_called()
    resend_client.send.assert_not_called()


def test_draft_failure_is_counted_and_no_send_attempted():
    agent, db, llm, resend_client, _ = make_agent()
    llm.complete_json.side_effect = RuntimeError("boom")

    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["drafted"] == 0
    assert summary["sent"] == 0
    resend_client.send.assert_not_called()
    db.insert_outreach_message.assert_not_called()


def test_send_failure_leaves_no_db_writes():
    agent, db, llm, resend_client, _ = make_agent()
    resend_client.send.side_effect = RuntimeError("resend down")

    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["drafted"] == 1
    assert summary["sent"] == 0
    db.insert_outreach_message.assert_not_called()
    db.update_place.assert_not_called()


# --- Budget / cap ---------------------------------------------------------------


def test_zero_cap_does_nothing():
    agent, db, llm, resend_client, _ = make_agent(max_per_run=0)

    summary = agent.run()

    assert summary == {
        "candidates_seen": 0,
        "drafted": 0,
        "sent": 0,
        "errors": 0,
    }
    llm.complete_json.assert_not_called()
    resend_client.send.assert_not_called()


# --- Contact email scraping -----------------------------------------------------


def test_scrape_skips_places_without_website():
    agent, db, _, _, scraper = make_agent()
    db.fetch_needs_review_for_outreach.return_value = [make_place(website=None)]

    summary = agent._scrape_missing_emails()

    assert summary == {"scraped": 0, "found": 0}
    scraper.find_email.assert_not_called()
    db.update_place.assert_not_called()


def test_scrape_skips_social_websites():
    agent, db, _, _, scraper = make_agent()
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(website="https://www.instagram.com/cafex")
    ]

    summary = agent._scrape_missing_emails()

    assert summary == {"scraped": 0, "found": 0}
    scraper.find_email.assert_not_called()
    db.update_place.assert_not_called()


def test_scrape_skips_already_checked_places():
    agent, db, _, _, scraper = make_agent()
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(
            website="https://cafex.com",
            contact_email_checked_at="2026-08-01T00:00:00+00:00",
        )
    ]

    summary = agent._scrape_missing_emails()

    assert summary == {"scraped": 0, "found": 0}
    scraper.find_email.assert_not_called()
    db.update_place.assert_not_called()


def test_scrape_persists_found_email_and_checked_at():
    agent, db, _, _, scraper = make_agent()
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(id="p1", website="https://cafex.com")
    ]
    scraper.find_email.return_value = "hola@cafex.com"

    summary = agent._scrape_missing_emails()

    assert summary == {"scraped": 1, "found": 1}
    scraper.find_email.assert_called_once_with("https://cafex.com")
    db.update_place.assert_called_once()
    call = db.update_place.call_args
    assert call.args[0] == "p1"
    assert call.args[1]["contact_email"] == "hola@cafex.com"
    assert call.args[1]["contact_email_checked_at"] is not None


def test_scrape_persists_null_email_and_checked_at_when_not_found():
    agent, db, _, _, scraper = make_agent()
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(id="p1", website="https://cafex.com")
    ]
    scraper.find_email.return_value = None

    summary = agent._scrape_missing_emails()

    assert summary == {"scraped": 1, "found": 0}
    db.update_place.assert_called_once()
    call = db.update_place.call_args
    assert call.args[1]["contact_email"] is None
    assert call.args[1]["contact_email_checked_at"] is not None


def test_scrape_respects_max_scrapes_per_run_cap():
    agent, db, _, _, scraper = make_agent(max_scrapes_per_run=1)
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(id="p1", website="https://a.com"),
        make_place(id="p2", website="https://b.com"),
    ]

    summary = agent._scrape_missing_emails()

    assert summary["scraped"] == 1
    scraper.find_email.assert_called_once()


def test_run_scrapes_before_selecting_candidates():
    agent, db, llm, resend_client, scraper = make_agent()
    order = []
    with patch.object(
        agent,
        "_scrape_missing_emails",
        side_effect=lambda: order.append("scrape") or {"scraped": 0, "found": 0},
    ), patch.object(
        agent, "_select_candidates", side_effect=lambda: order.append("select") or []
    ):
        agent.run()

    assert order == ["scrape", "select"]


# --- Reply-to (Outreach Etapa 2) -------------------------------------------------


def test_reply_to_omitted_when_inbound_domain_not_set():
    agent, db, llm, resend_client, _ = make_agent(inbound_domain="")

    agent.run()

    assert resend_client.send.call_args.kwargs["reply_to"] is None


def test_reply_to_built_from_place_id_when_inbound_domain_set():
    agent, db, llm, resend_client, _ = make_agent(inbound_domain="abc123.resend.app")
    db.fetch_needs_review_for_outreach.return_value = [make_place(id="place-42")]

    agent.run()

    assert resend_client.send.call_args.kwargs["reply_to"] == "outreach+place-42@abc123.resend.app"


# --- Sender identity ---------------------------------------------------------


def test_send_uses_configured_sender_email():
    agent, db, llm, resend_client, _ = make_agent(sender_email="hola@celiacmap.org")

    agent.run()

    assert resend_client.send.call_args.kwargs["from_address"] == "hola@celiacmap.org"


# --- Live mode (ADR-003 final step) -------------------------------------------


def test_send_uses_contact_email_in_live_mode():
    agent, db, llm, resend_client, _ = make_agent(live_mode=True)
    db.fetch_needs_review_for_outreach.return_value = [
        make_place(id="p1", phone="099", contact_email="biz@example.com")
    ]

    agent.run()

    assert resend_client.send.call_args.kwargs["to"] == "biz@example.com"


def test_live_mode_skips_and_logs_missing_contact_email_defense_in_depth():
    agent, db, llm, resend_client, _ = make_agent(live_mode=True)
    # Simulate a bug/race condition: a candidate reaches the send step in
    # live mode despite lacking contact_email, bypassing _select_candidates()'s
    # own filter — proves there is no silent fallback to test_recipient.
    with patch.object(
        agent,
        "_select_candidates",
        return_value=[make_place(id="p1", contact_email=None)],
    ):
        summary = agent.run()

    assert summary["errors"] == 1
    assert summary["sent"] == 0
    resend_client.send.assert_not_called()
    db.insert_outreach_message.assert_not_called()
