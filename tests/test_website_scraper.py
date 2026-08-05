"""Unit tests for WebsiteScraperClient (offline; requests.get is mocked).

First transport-level mock in this test suite: every other agents/clients/*
wrapper is only exercised indirectly (mocked at the client-object boundary by
the tests of the agent that consumes it), since resend_client.py /
tavily_client.py have no dedicated test files of their own.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.clients.website_scraper import WebsiteScraperClient, is_social_url


def _mock_response(text, status_ok=True):
    response = MagicMock()
    response.text = text
    if status_ok:
        response.raise_for_status.return_value = None
    else:
        response.raise_for_status.side_effect = Exception("HTTP error")
    return response


# --- is_social_url --------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.facebook.com/cafex",
        "https://m.facebook.com/cafex",
        "https://instagram.com/cafex",
        "https://www.instagram.com/cafex",
        "https://wa.me/59899123456",
        "https://api.whatsapp.com/send?phone=59899123456",
        "https://beacons.ai/cafex",
        "https://linktr.ee/cafex",
    ],
)
def test_is_social_url_true_for_known_platforms(url):
    assert is_social_url(url) is True


def test_is_social_url_false_for_a_real_business_site():
    assert is_social_url("https://cafex.com") is False


# --- find_email: skips without a network call ------------------------------------


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_skips_social_url_without_network_call(mock_get):
    client = WebsiteScraperClient()
    assert client.find_email("https://www.instagram.com/cafex") is None
    mock_get.assert_not_called()


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_returns_none_for_empty_url(mock_get):
    client = WebsiteScraperClient()
    assert client.find_email("") is None
    assert client.find_email(None) is None
    mock_get.assert_not_called()


# --- find_email: mailto / regex extraction ---------------------------------------


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_prefers_mailto_link(mock_get):
    mock_get.return_value = _mock_response(
        '<a href="mailto:hola@cafex.com">Escribinos</a> visible@other.com'
    )
    assert WebsiteScraperClient().find_email("https://cafex.com") == "hola@cafex.com"


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_strips_mailto_query_string(mock_get):
    mock_get.return_value = _mock_response(
        '<a href="mailto:hola@cafex.com?subject=Hola">Escribinos</a>'
    )
    assert WebsiteScraperClient().find_email("https://cafex.com") == "hola@cafex.com"


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_falls_back_to_generic_regex(mock_get):
    mock_get.return_value = _mock_response("Escribinos a hola@cafex.com para consultas.")
    assert WebsiteScraperClient().find_email("https://cafex.com") == "hola@cafex.com"


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_returns_none_when_nothing_found(mock_get):
    mock_get.return_value = _mock_response("<html><body>Bienvenidos a Cafe X</body></html>")
    assert WebsiteScraperClient().find_email("https://cafex.com") is None


# --- find_email: rejects image-filename false positives ---------------------------


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_rejects_real_world_image_filename_false_positive(mock_get):
    # Real false positive found in production: a retina image filename
    # ("nuvempago@2x.png") matches EMAIL_RE's shape exactly — "2x.png" looks
    # like a valid domain + 2+ letter TLD — but is never a real email.
    mock_get.return_value = _mock_response(
        '<img src="/assets/nuvempago@2x.png" alt="Nuvem Pago">'
    )
    assert WebsiteScraperClient().find_email("https://cafex.com") is None


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_rejects_known_image_extensions(mock_get):
    for filename in (
        "logo@2x.png",
        "icon@2x.jpg",
        "photo@2x.jpeg",
        "banner@2x.gif",
        "sprite@2x.svg",
        "hero@2x.webp",
        "favicon@2x.ico",
    ):
        mock_get.return_value = _mock_response(f'<img src="/assets/{filename}">')
        assert WebsiteScraperClient().find_email("https://cafex.com") is None, filename


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_rejects_image_filename_in_mailto_link(mock_get):
    mock_get.return_value = _mock_response('<a href="mailto:nuvempago@2x.png">Ver logo</a>')
    assert WebsiteScraperClient().find_email("https://cafex.com") is None


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_falls_back_to_generic_regex_when_mailto_is_image_filename(mock_get):
    mock_get.return_value = _mock_response(
        '<a href="mailto:nuvempago@2x.png">Ver logo</a> Escribinos a hola@cafex.com'
    )
    assert WebsiteScraperClient().find_email("https://cafex.com") == "hola@cafex.com"


# --- find_email: rejects platform/infrastructure domains --------------------------


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_rejects_wix_sentry_platform_domain(mock_get):
    # Real case (Sweetly): a Wix-built site embeds a Sentry DSN
    # ("key@sentry-next.wixpress.com") in its JS — matches EMAIL_RE's shape
    # but belongs to Wix's infra, not the business.
    mock_get.return_value = _mock_response(
        'Sentry.init({dsn: "https://a1b2c3d4e5f6@sentry-next.wixpress.com/123456"});'
    )
    assert WebsiteScraperClient().find_email("https://sweetly.com") is None


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_rejects_known_platform_domains(mock_get):
    for domain in (
        "wixpress.com",
        "sentry.io",
        "sentry-cdn.com",
        "godaddy.com",
        "squarespace.com",
    ):
        mock_get.return_value = _mock_response(f"Contacto: soporte@{domain}")
        assert WebsiteScraperClient().find_email("https://cafex.com") is None, domain


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_does_not_falsely_reject_lookalike_domain(mock_get):
    # "wixpress.com" must match as a domain suffix (exact or subdomain), not
    # a raw substring — an unrelated domain that merely contains the
    # pattern must NOT be rejected.
    mock_get.return_value = _mock_response("Contacto: hola@wearewixpress.com")
    assert WebsiteScraperClient().find_email("https://cafex.com") == "hola@wearewixpress.com"


# --- find_email: never raises -----------------------------------------------------


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_returns_none_on_timeout(mock_get):
    mock_get.side_effect = TimeoutError("timed out")
    assert WebsiteScraperClient().find_email("https://cafex.com") is None


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_returns_none_on_connection_error(mock_get):
    mock_get.side_effect = ConnectionError("dns failure")
    assert WebsiteScraperClient().find_email("https://cafex.com") is None


@patch("agents.clients.website_scraper.requests.get")
def test_find_email_returns_none_on_http_error_status(mock_get):
    mock_get.return_value = _mock_response("<html></html>", status_ok=False)
    assert WebsiteScraperClient().find_email("https://cafex.com") is None
