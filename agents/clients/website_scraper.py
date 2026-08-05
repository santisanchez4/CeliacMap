"""Deterministic best-effort scraper for a business's public contact email.

Google Places never exposes a business email (see CLAUDE.md's Outreach agent
design decisions), so the Outreach agent falls back to scraping a candidate's
own website home page for a ``mailto:`` link or a visible email address.

Unlike TavilySearchClient.search / ResendClient.send, this client never
raises: it exists purely to enrich a candidate that already has other
contact info (phone/website), so a dead site, timeout, redirect loop, or
expired cert must degrade to "no email found" rather than abort anything.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

logger = logging.getLogger("celiacmap.agent")

TIMEOUT = 5  # seconds; a slow/unresponsive site must not stall the pipeline

# Profile-page domains, not a business's own site — scraping them would only
# find Meta/Linktree/WhatsApp's own address, never the business's. Substring
# match covers m.facebook.com / l.instagram.com for free. Confirmed against
# real data: 40 of 68 needs_review places with a website on file match one
# of these (facebook.com / instagram.com / beacons.ai).
SOCIAL_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "wa.me",
    "whatsapp.com",
    "beacons.ai",
    "linktr.ee",
)

MAILTO_RE = re.compile(r'mailto:([^\s"\'<>]+)', re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
USER_AGENT = "CeliacMapBot/1.0 (+https://github.com/santisanchez4/CeliacMap)"

# EMAIL_RE's own shape already requires a dot + 2+ alpha chars at the end —
# which a 3-4 letter image extension satisfies just as well as a real TLD.
# Reject filename-shaped false positives like "nuvempago@2x.png" (a retina
# image asset, confirmed in production) explicitly rather than trust the
# extraction regex alone.
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")

# Platform/infrastructure domains — a technically valid-shaped email can
# still be garbage if it belongs to the site's tooling/host, not the
# business. Confirmed in production: sentry-next.wixpress.com (Sentry error
# tracking embedded in a Wix site — Sentry DSNs are literally a
# "key@ingest-host" string, which matches EMAIL_RE's shape by coincidence).
# Matched as a domain suffix (exact match or a subdomain) below, not a plain
# substring like SOCIAL_DOMAINS uses for URLs — a raw substring check would
# also match an unrelated domain like "wearewixpress.com".
PLATFORM_EMAIL_DOMAINS = (
    "wixpress.com",     # Wix's own infra (any subdomain, e.g. sentry-next.wixpress.com)
    "sentry.io",        # Sentry error tracking, any site
    "sentry-cdn.com",   # Sentry error tracking, any site
    "godaddy.com",      # GoDaddy default-template support address
    "squarespace.com",  # Squarespace default-template support address
)


def _is_platform_domain(domain: str) -> bool:
    domain = domain.lower()
    return any(
        domain == d or domain.endswith(f".{d}") for d in PLATFORM_EMAIL_DOMAINS
    )


def _is_valid_email(candidate: str) -> bool:
    """Extra validation applied after extraction, whether the candidate came
    from a mailto: link or the generic visible-text regex."""
    if not EMAIL_RE.fullmatch(candidate):
        return False
    if candidate.lower().endswith(IMAGE_EXTENSIONS):
        return False
    domain = candidate.rsplit("@", 1)[-1]
    tld = domain.rsplit(".", 1)[-1]
    if not (tld.isalpha() and len(tld) >= 2):
        return False
    return not _is_platform_domain(domain)


def is_social_url(url: str) -> bool:
    """True if url is a social/link-in-bio profile page, not a real site."""
    host = (urlparse(url).netloc or url).lower()
    return any(domain in host for domain in SOCIAL_DOMAINS)


class WebsiteScraperClient:
    def find_email(self, url: str) -> str | None:
        """Best-effort scrape of url's home page for a contact email.

        Returns None on a social URL, any transport/HTTP error, or when no
        email is found — never raises.
        """
        if not url or is_social_url(url):
            return None
        try:
            response = requests.get(
                url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
        except Exception:  # noqa: BLE001 - any transport/HTTP error means "no email found"
            logger.info("website scrape failed for %r", url)
            return None

        html = response.text
        mailto_match = MAILTO_RE.search(html)
        if mailto_match:
            candidate = mailto_match.group(1).split("?")[0]
            if _is_valid_email(candidate):
                return candidate

        for match in EMAIL_RE.finditer(html):
            if _is_valid_email(match.group(0)):
                return match.group(0)
        return None
