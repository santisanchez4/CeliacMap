"""Pipeline orchestrator — runs Search -> Validator -> Updater in order.

This is the CI entrypoint for the daily GitHub Actions cron (and for manual
``workflow_dispatch`` validation). It:

- runs the three agents in sequence (each stage feeds the next);
- enforces a single **combined daily budget** across all paid API calls — search
  consumes its query count, then the validator/updater per-run sizes are clamped
  to whatever budget is left, so the day's total stays bounded;
- writes one consolidated ``pipeline_run_complete`` summary to ``agent_log``;
- supports ``--dry-run`` to exercise the whole pipeline without persisting
  anything (Supabase reads still happen so the agents see real data, but every
  write becomes a logged no-op).

Run from the repo root:

    python scripts/run_agents.py              # real run, budget from settings
    python scripts/run_agents.py --dry-run    # no DB writes
    python scripts/run_agents.py --budget 120 # override the combined cap
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any

from agents.clients.google_places import GooglePlacesClient
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient
from agents.search_agent import SearchAgent
from agents.updater_agent import UpdaterAgent
from agents.validator_agent import ValidatorAgent
from config.settings import Settings, get_settings, load_targets

logger = logging.getLogger("celiacmap.agent")


class DryRunSupabase:
    """Read-through, write-suppressing wrapper around :class:`SupabaseClient`.

    Reads (``fetch_places_by_status``, ``health_check``) pass straight through so
    the agents operate on real data; every write is logged and dropped. This lets
    ``--dry-run`` verify the full pipeline's logic without touching the database.
    """

    def __init__(self, inner: SupabaseClient):
        self._inner = inner

    # --- reads pass through ------------------------------------------
    def health_check(self) -> int:
        return self._inner.health_check()

    def fetch_places_by_status(self, status: str, limit: int = 100) -> list[dict]:
        return self._inner.fetch_places_by_status(status, limit=limit)

    # --- writes become no-ops ----------------------------------------
    def insert_place_candidate(self, candidate: dict[str, Any]) -> None:
        logger.info("[dry-run] would insert candidate %r", candidate.get("name"))
        return None

    def update_place(self, place_id: str, patch: dict[str, Any]) -> None:
        logger.info("[dry-run] would update place %s -> %s", place_id, patch)

    def update_place_validation(self, place_id: str, **kwargs: Any) -> None:
        logger.info("[dry-run] would set validation on %s -> %s", place_id, kwargs)

    def insert_agent_log(self, *args: Any, **kwargs: Any) -> None:
        # Keep the audit trail clean during dry runs — nothing is persisted.
        return None


class Budget:
    """A single combined cap on paid API calls, shared across the pipeline."""

    def __init__(self, total: int):
        self.total = max(0, total)
        self.remaining = self.total

    def allow(self, requested: int) -> int:
        """Largest batch size still affordable (never negative)."""
        return max(0, min(requested, self.remaining))

    def consume(self, used: int) -> None:
        self.remaining = max(0, self.remaining - max(0, used))


def _overall_status(summaries: dict[str, Any]) -> str:
    for summary in summaries.values():
        if isinstance(summary, dict) and summary.get("errors"):
            return "error"
    return "success"


def run_pipeline(
    settings: Settings, *, dry_run: bool, budget_total: int
) -> dict[str, Any]:
    """Run search -> validator -> updater under one combined budget."""
    targets = load_targets()
    raw_db = SupabaseClient(
        settings.supabase_url, settings.supabase_service_role_key
    )
    db = DryRunSupabase(raw_db) if dry_run else raw_db

    places = GooglePlacesClient(settings.google_maps_api_key)
    llm = LLMClient(settings.anthropic_api_key, settings.validator_model)
    budget = Budget(budget_total)

    summaries: dict[str, Any] = {}
    started = time.monotonic()

    # 1. Search — bounded by targets.yaml x max_results_per_query; consumes its
    #    Google text-search queries from the combined budget.
    search = SearchAgent(
        db,
        places,
        targets,
        max_results_per_query=settings.max_search_results_per_query,
    )
    summaries["search"] = search.run()
    budget.consume(summaries["search"].get("queries", 0))

    # 2. Validator — one Sonnet call per pending candidate, clamped to budget.
    val_cap = budget.allow(settings.max_validations_per_run)
    if val_cap > 0:
        validator = ValidatorAgent(db, llm, max_per_run=val_cap)
        summaries["validator"] = validator.run()
        budget.consume(summaries["validator"].get("pending_seen", 0))
    else:
        summaries["validator"] = {"skipped": "budget exhausted"}

    # 3. Updater — one Google details call per approved place, clamped to budget.
    upd_cap = budget.allow(settings.max_updates_per_run)
    if upd_cap > 0:
        haiku = (
            LLMClient(settings.anthropic_api_key, settings.haiku_model)
            if settings.anthropic_api_key
            else None
        )
        updater = UpdaterAgent(
            db,
            places,
            targets,
            max_checks_per_run=upd_cap,
            llm=haiku,
            haiku_model=settings.haiku_model,
        )
        summaries["updater"] = updater.run()
        budget.consume(summaries["updater"].get("checked", 0))
    else:
        summaries["updater"] = {"skipped": "budget exhausted"}

    overall = {
        "dry_run": dry_run,
        "budget_total": budget.total,
        "budget_remaining": budget.remaining,
        "duration_s": round(time.monotonic() - started, 1),
        "search": summaries["search"],
        "validator": summaries["validator"],
        "updater": summaries["updater"],
    }

    status = _overall_status(summaries)
    if dry_run:
        logger.info("[dry-run] would log pipeline summary: %s", overall)
    else:
        try:
            raw_db.insert_agent_log(
                "pipeline", "pipeline_run_complete", overall, status=status
            )
        except Exception:  # logging must never crash the run
            logger.exception("failed to write pipeline summary to agent_log")

    return overall


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the CeliacMap agent pipeline (search -> validator -> updater)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exercise the pipeline without any database writes.",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=None,
        help="Override the combined paid-API-call cap (default: AGENT_DAILY_BUDGET).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    settings.require(
        "supabase_url",
        "supabase_service_role_key",
        "google_maps_api_key",
        "anthropic_api_key",
    )

    budget_total = args.budget if args.budget is not None else settings.agent_daily_budget
    if args.dry_run:
        logger.info("Running pipeline in DRY-RUN mode — no database writes.")

    overall = run_pipeline(settings, dry_run=args.dry_run, budget_total=budget_total)

    print("\nPipeline run complete:")
    print(f"  dry_run          : {overall['dry_run']}")
    print(f"  budget           : {overall['budget_total'] - overall['budget_remaining']}"
          f" / {overall['budget_total']} used")
    print(f"  duration_s       : {overall['duration_s']}")
    print(f"  search           : {overall['search']}")
    print(f"  validator        : {overall['validator']}")
    print(f"  updater          : {overall['updater']}")

    return 1 if _overall_status(overall) == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
