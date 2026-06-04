"""Unit tests for config.settings validation and pipeline budget clamping."""

from __future__ import annotations

import pytest

from config.settings import Settings
from scripts.run_agents import Budget


def make_settings(**overrides):
    base = {
        "supabase_url": "",
        "supabase_service_role_key": "",
        "google_maps_api_key": "",
        "anthropic_api_key": "",
    }
    base.update(overrides)
    return Settings(**base)


# --- Required env var validation ------------------------------------------


def test_require_raises_for_missing_keys():
    settings = make_settings(supabase_url="https://x.supabase.co")
    with pytest.raises(RuntimeError) as exc:
        settings.require("supabase_url", "google_maps_api_key", "anthropic_api_key")

    message = str(exc.value)
    assert "google_maps_api_key" in message
    assert "anthropic_api_key" in message
    assert "supabase_url" not in message  # the one that was set


def test_require_passes_when_all_present():
    settings = make_settings(
        supabase_url="https://x.supabase.co",
        supabase_service_role_key="key",
    )
    # Should not raise.
    settings.require("supabase_url", "supabase_service_role_key")


def test_from_env_reads_and_strips(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "  https://x.supabase.co  ")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_DAILY_BUDGET", "120")

    settings = Settings.from_env()

    assert settings.supabase_url == "https://x.supabase.co"
    assert settings.google_maps_api_key == ""
    assert settings.agent_daily_budget == 120


def test_from_env_falls_back_on_invalid_int(monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_BUDGET", "not-a-number")
    monkeypatch.delenv("MAX_VALIDATIONS_PER_RUN", raising=False)

    settings = Settings.from_env()

    assert settings.agent_daily_budget == 200  # default
    assert settings.max_validations_per_run == 50  # default


# --- Budget clamping logic ------------------------------------------------


def test_budget_allow_clamps_to_remaining():
    budget = Budget(10)
    assert budget.allow(5) == 5
    assert budget.allow(50) == 10  # cannot exceed what is left


def test_budget_consume_reduces_remaining():
    budget = Budget(10)
    budget.consume(7)
    assert budget.remaining == 3
    assert budget.allow(50) == 3


def test_budget_never_goes_negative():
    budget = Budget(5)
    budget.consume(100)
    assert budget.remaining == 0
    assert budget.allow(5) == 0


def test_budget_ignores_negative_inputs():
    budget = Budget(-5)
    assert budget.total == 0
    assert budget.remaining == 0
    budget = Budget(10)
    budget.consume(-3)  # negative usage treated as zero
    assert budget.remaining == 10
    assert budget.allow(-1) == 0
