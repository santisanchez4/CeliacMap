"""Central, env-driven configuration for the CeliacMap agents.

Loads variables from a local ``.env`` (via python-dotenv) when present; in CI
the same variables come from GitHub Actions Secrets. Secrets are never hard-coded
here. Use :func:`get_settings` to read config and :func:`load_targets` to read the
data-driven geographic scope from ``config/targets.yaml``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
TARGETS_PATH = ROOT / "config" / "targets.yaml"

# Load .env once at import (no-op in CI where vars are already in the environment).
load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw not in (None, "") else default
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("true", "1", "yes", "on")


@dataclass(frozen=True)
class Settings:
    """Resolved configuration. Secrets may be empty until validated per use."""

    supabase_url: str
    supabase_service_role_key: str
    google_maps_api_key: str
    anthropic_api_key: str
    tavily_api_key: str = ""
    validator_model: str = "claude-sonnet-4-6"
    haiku_model: str = "claude-haiku-4-5"
    # Web discovery agent (v3): reasons freely + uses the Anthropic web search tool.
    # Haiku is sufficient here — the agent only discovers/extracts candidates; the
    # Validator (Sonnet) still makes every safety judgment downstream.
    web_search_model: str = "claude-haiku-4-5"
    max_search_results_per_query: int = 20
    # Cap on Google text-search queries per Search run (city x term matrix can be
    # large); keeps a run within the daily API budget. 0 = unlimited.
    # 104 keeps 3 search-terms/month coverage for all 32 cities (16 UY + 16 AR,
    # after the GBA Norte + Oeste cercano expansion) under the term-major job
    # order — 80 would only reach 2 terms for Argentina once GBA was added.
    max_search_queries_per_run: int = 104
    max_validations_per_run: int = 50
    max_updates_per_run: int = 50
    # Social agent caps: number of Tavily searches per run (free tier: 1000/month)
    # and number of Search-agent review enrichments per run.
    max_social_queries_per_run: int = 30
    # Independent cap on Google Find Place geocode calls per Social run. A
    # single Tavily query can surface multiple leads, each geocoded
    # separately — the query cap above does NOT bound this. Confirmed live
    # 2026-08-19: 25 queries triggered 102 geocode calls (4.1x), eating the
    # budget planned for the Validator's reserve. 40 covers the real volume
    # seen without leaving Social effectively uncapped.
    social_max_geocodes: int = 40
    max_review_enrichments_per_run: int = 30
    # Place Details lookups per Search run (rich panel fields + review enrichment).
    max_detail_lookups_per_run: int = 60
    # Web discovery agent (v3): number of cities researched per run (opt-in via
    # web: true in targets.yaml) and the web-search cap handed to the model per city.
    max_web_cities_per_run: int = 2
    max_web_searches_per_city: int = 8
    # Public "Suggest a Place" form: max submissions the daily Suggestion promoter
    # geocodes + promotes per run (each costs one Google Find Place call).
    max_suggestions_per_run: int = 30
    # Outreach agent (Etapa 1, outreach_send): sandbox sender can only deliver to
    # this fixed test recipient until a custom domain is verified with Resend.
    resend_api_key: str = ""
    outreach_test_recipient: str = ""
    # Outreach agent sender identity. Requires a domain verified with Resend
    # to actually deliver (see .env.example); the recipient stays the fixed
    # test address regardless (ADR-003 not yet resolved).
    outreach_sender_email: str = "outreach@celiacmap.org"
    # Outreach Etapa 2 (reply webhook): the account's <id>.resend.app inbound
    # receiving domain, used to build a unique outreach+<place_id>@<domain>
    # Reply-To per send so a business's reply can be matched back to its
    # place. Empty means no Reply-To header is set (degrades gracefully).
    outreach_inbound_domain: str = ""
    # Outreach agent cap: confirmation emails sent per run (7th pipeline stage).
    outreach_monthly_limit: int = 20
    # Outreach agent (ADR-003 final step): when true, routes real sends to
    # place["contact_email"] instead of outreach_test_recipient. Defaults to
    # false — nothing changes until this is deliberately flipped.
    outreach_live_mode: bool = False
    # Outreach agent's contact_email scraper: websites scraped per run. Mirrors
    # every other agent's per-run cap, bounding worst-case latency (each site
    # gets a synchronous 5s-timeout GET) as the eligible pool grows.
    max_email_scrapes_per_run: int = 30
    # Community reports (place_reports) monthly sweep (8th pipeline stage,
    # ReviewHandler.sweep()): re-drives negative reports left stuck in
    # 'new'/'dispatched' because the real-time webhook path never reached
    # 'processed' (Supabase Database Webhooks don't auto-retry). Default is
    # low because in the normal case the real-time path already handled
    # everything and this finds nothing to sweep.
    max_review_sweep_per_run: int = 20
    # Combined cap on paid API calls for one full pipeline run (search +
    # validator + updater), enforced by scripts/run_agents.py.
    agent_daily_budget: int = 350

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", "").strip(),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
            google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY", "").strip(),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
            validator_model=os.getenv("VALIDATOR_MODEL", "claude-sonnet-4-6").strip(),
            haiku_model=os.getenv("HAIKU_MODEL", "claude-haiku-4-5").strip(),
            web_search_model=os.getenv("WEB_SEARCH_MODEL", "claude-haiku-4-5").strip(),
            max_search_results_per_query=_int("MAX_SEARCH_RESULTS_PER_QUERY", 20),
            max_search_queries_per_run=_int("MAX_SEARCH_QUERIES_PER_RUN", 104),
            max_validations_per_run=_int("MAX_VALIDATIONS_PER_RUN", 50),
            max_updates_per_run=_int("MAX_UPDATES_PER_RUN", 50),
            max_social_queries_per_run=_int("MAX_SOCIAL_QUERIES_PER_RUN", 30),
            social_max_geocodes=_int("SOCIAL_MAX_GEOCODES", 40),
            max_review_enrichments_per_run=_int("MAX_REVIEW_ENRICHMENTS_PER_RUN", 30),
            max_detail_lookups_per_run=_int("MAX_DETAIL_LOOKUPS_PER_RUN", 60),
            max_web_cities_per_run=_int("MAX_WEB_CITIES_PER_RUN", 2),
            max_web_searches_per_city=_int("MAX_WEB_SEARCHES_PER_CITY", 8),
            max_suggestions_per_run=_int("MAX_SUGGESTIONS_PER_RUN", 30),
            resend_api_key=os.getenv("RESEND_API_KEY", "").strip(),
            outreach_test_recipient=os.getenv("OUTREACH_TEST_RECIPIENT", "").strip(),
            outreach_sender_email=os.getenv(
                "OUTREACH_SENDER_EMAIL", "outreach@celiacmap.org"
            ).strip(),
            outreach_inbound_domain=os.getenv("OUTREACH_INBOUND_DOMAIN", "").strip(),
            outreach_monthly_limit=_int("OUTREACH_MONTHLY_LIMIT", 20),
            outreach_live_mode=_bool("OUTREACH_LIVE_MODE", False),
            max_email_scrapes_per_run=_int("MAX_EMAIL_SCRAPES_PER_RUN", 30),
            max_review_sweep_per_run=_int("MAX_REVIEW_SWEEP_PER_RUN", 20),
            agent_daily_budget=_int("AGENT_DAILY_BUDGET", 350),
        )

    def require(self, *names: str) -> None:
        """Raise a clear error if any of the named settings are empty.

        Each agent calls this for only the keys it needs, so e.g. the Validator
        can run without a Google key and vice-versa.
        """
        missing = [n for n in names if not getattr(self, n, "")]
        if missing:
            raise RuntimeError(
                "Missing required configuration: "
                + ", ".join(sorted(missing))
                + ". Set them in .env (see .env.example) or in CI secrets."
            )


def get_settings() -> Settings:
    return Settings.from_env()


def load_targets(path: Path | None = None) -> dict:
    """Read the geographic scope + search configuration from targets.yaml."""
    p = path or TARGETS_PATH
    with open(p, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
