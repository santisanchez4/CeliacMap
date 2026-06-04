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


@dataclass(frozen=True)
class Settings:
    """Resolved configuration. Secrets may be empty until validated per use."""

    supabase_url: str
    supabase_service_role_key: str
    google_maps_api_key: str
    anthropic_api_key: str
    validator_model: str = "claude-sonnet-4-6"
    haiku_model: str = "claude-haiku-4-5"
    max_search_results_per_query: int = 20
    max_validations_per_run: int = 50
    max_updates_per_run: int = 50
    # Combined cap on paid API calls for one full pipeline run (search +
    # validator + updater), enforced by scripts/run_agents.py.
    agent_daily_budget: int = 200

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", "").strip(),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
            google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY", "").strip(),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            validator_model=os.getenv("VALIDATOR_MODEL", "claude-sonnet-4-6").strip(),
            haiku_model=os.getenv("HAIKU_MODEL", "claude-haiku-4-5").strip(),
            max_search_results_per_query=_int("MAX_SEARCH_RESULTS_PER_QUERY", 20),
            max_validations_per_run=_int("MAX_VALIDATIONS_PER_RUN", 50),
            max_updates_per_run=_int("MAX_UPDATES_PER_RUN", 50),
            agent_daily_budget=_int("AGENT_DAILY_BUDGET", 200),
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
