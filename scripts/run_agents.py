"""Pipeline orchestrator — runs Search -> Social -> Web -> Suggestion -> Validator -> Updater.

This is the CI entrypoint for the daily GitHub Actions cron (and for manual
``workflow_dispatch`` validation). It:

- runs the discovery + validation agents in sequence (each stage feeds the next);
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
from agents.clients.tavily_client import TavilySearchClient
from agents.search_agent import SearchAgent
from agents.social_agent import SocialAgent
from agents.suggestion_agent import SuggestionAgent
from agents.updater_agent import UpdaterAgent
from agents.validator_agent import ValidatorAgent
from agents.web_agent import WebAgent
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

    def fetch_reviews_for_place(self, place_id: str, limit: int = 5) -> list[dict]:
        return self._inner.fetch_reviews_for_place(place_id, limit=limit)

    def place_exists_by_external_id(self, external_id: str) -> bool:
        return self._inner.place_exists_by_external_id(external_id)

    def fetch_new_suggestions(self, limit: int = 50) -> list[dict]:
        return self._inner.fetch_new_suggestions(limit=limit)

    # --- writes become no-ops ----------------------------------------
    def update_suggestion_status(
        self, suggestion_id: str, status: str, promoted_place_id: str | None = None
    ) -> None:
        logger.info(
            "[dry-run] would mark suggestion %s -> %s", suggestion_id, status
        )

    def insert_place_candidate(self, candidate: dict[str, Any]) -> None:
        logger.info("[dry-run] would insert candidate %r", candidate.get("name"))
        return None

    def insert_review(self, place_id: str, text: str, **kwargs: Any) -> None:
        logger.info("[dry-run] would insert review for place %s", place_id)
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


def _transient_error_count(overall: dict[str, Any]) -> int:
    """Total per-item errors agents tallied while still completing the run.

    Each agent catches per-item failures (e.g. a single flaky geocode, search
    query, web-research call or place_details lookup), records them in its summary's
    ``errors`` count and in ``agent_log``, and keeps going. These are **non-fatal**:
    they are reported but must not fail the daily CI job — only a fatal error that
    prevents the pipeline from completing does (see ``main``).
    """
    total = 0
    for summary in overall.values():
        if isinstance(summary, dict) and isinstance(summary.get("errors"), int):
            total += summary["errors"]
    return total


def run_pipeline(
    settings: Settings, *, dry_run: bool, budget_total: int
) -> dict[str, Any]:
    """Run search -> social -> web -> suggestion -> validator -> updater under one combined budget."""
    targets = load_targets()
    raw_db = SupabaseClient(
        settings.supabase_url, settings.supabase_service_role_key
    )
    db = DryRunSupabase(raw_db) if dry_run else raw_db

    places = GooglePlacesClient(settings.google_maps_api_key)
    llm = LLMClient(settings.anthropic_api_key, settings.validator_model)
    haiku = (
        LLMClient(settings.anthropic_api_key, settings.haiku_model)
        if settings.anthropic_api_key
        else None
    )
    budget = Budget(budget_total)

    # Keep the daily pipeline self-sufficient: discovery (Search/Social/Web) is
    # clamped so it can never consume the slice reserved for the Validator, and
    # the Updater takes whatever remains. Per-run shape (budget 350):
    #   Search <= 80 | Social <= 25 | Web <= 40 | Validator reserve 80 | Updater = rest.
    SOCIAL_MAX = 25
    WEB_MAX = 40
    SUGGEST_MAX = 30
    VALIDATOR_RESERVE = 80

    summaries: dict[str, Any] = {}
    started = time.monotonic()

    # 1. Search — bounded by targets.yaml x max_results_per_query; consumes its
    #    Google text-search queries plus one Place Details call per new candidate
    #    (rich panel fields + review enrichment) from the combined budget.
    search = SearchAgent(
        db,
        places,
        targets,
        max_results_per_query=settings.max_search_results_per_query,
        max_review_enrichments=settings.max_review_enrichments_per_run,
        max_detail_lookups=settings.max_detail_lookups_per_run,
        # Cap by setting, and never plan into the Validator's reserved slice.
        max_queries_per_run=min(
            settings.max_search_queries_per_run,
            max(0, budget.remaining - VALIDATOR_RESERVE),
        ),
    )
    summaries["search"] = search.run()
    budget.consume(
        summaries["search"].get("queries", 0)
        + summaries["search"].get("details_fetched", 0)
    )

    # 2. Social — Tavily search + Find Place geocoding. Capped at SOCIAL_MAX to
    #    curb geocoding waste, and never planned into the Validator's reserve.
    soc_cap = min(SOCIAL_MAX, max(0, budget.remaining - VALIDATOR_RESERVE))
    if soc_cap > 0 and settings.tavily_api_key and haiku:
        search_client = TavilySearchClient(settings.tavily_api_key)
        social = SocialAgent(
            db,
            search_client,
            places,
            haiku,
            targets,
            haiku_model=settings.haiku_model,
            max_queries=soc_cap,
        )
        summaries["social"] = social.run()
        # Consume the metered calls: Tavily searches + Google Find Place geocodes.
        budget.consume(
            summaries["social"].get("queries", 0)
            + summaries["social"].get("geocoded", 0)
        )
    else:
        summaries["social"] = {"skipped": "budget exhausted or social not configured"}

    # 3. Web (v3) — autonomous web-search discovery for the cities flagged
    #    web:true in targets.yaml. Each city costs its web-search budget + one
    #    Find Place geocode per lead. Capped at WEB_MAX and never planned into
    #    the Validator's reserve.
    web_room = min(WEB_MAX, max(0, budget.remaining - VALIDATOR_RESERVE))
    if web_room > 0 and settings.anthropic_api_key:
        web = WebAgent(
            db,
            places,
            llm,  # reuse the Sonnet client; model overridden per-call below
            targets,
            model=settings.web_search_model,
            max_cities=settings.max_web_cities_per_run,
            max_searches_per_city=settings.max_web_searches_per_city,
        )
        summaries["web"] = web.run()
        # Consume the metered calls: web searches + Google Find Place geocodes.
        budget.consume(
            summaries["web"].get("searches", 0)
            + summaries["web"].get("geocoded", 0)
        )
    else:
        summaries["web"] = {"skipped": "budget exhausted or web not configured"}

    # 4. Suggestions — promote public "Suggest a Place" form submissions into
    #    pending `places` candidates (one Google Find Place geocode each). Runs
    #    before the Validator so freshly promoted user places are judged this run.
    #    Capped at SUGGEST_MAX and never planned into the Validator's reserve.
    sug_cap = min(
        settings.max_suggestions_per_run,
        SUGGEST_MAX,
        max(0, budget.remaining - VALIDATOR_RESERVE),
    )
    if sug_cap > 0:
        suggestion = SuggestionAgent(db, places, max_per_run=sug_cap)
        summaries["suggestion"] = suggestion.run()
        budget.consume(summaries["suggestion"].get("geocodes", 0))
    else:
        summaries["suggestion"] = {"skipped": "budget exhausted"}

    # 5. Validator — one Sonnet call per pending candidate (with any stored
    #    review snippets as context). Guaranteed the reserved slice so discovery
    #    can never starve publishing; validates up to VALIDATOR_RESERVE per run.
    val_cap = budget.allow(VALIDATOR_RESERVE)
    if val_cap > 0:
        validator = ValidatorAgent(db, llm, max_per_run=val_cap)
        summaries["validator"] = validator.run()
        budget.consume(summaries["validator"].get("pending_seen", 0))
    else:
        summaries["validator"] = {"skipped": "budget exhausted"}

    # 6. Updater — one Google details call per approved place, clamped to budget.
    upd_cap = budget.allow(settings.max_updates_per_run)
    if upd_cap > 0:
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
        "social": summaries["social"],
        "web": summaries["web"],
        "suggestion": summaries["suggestion"],
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
        description="Run the CeliacMap agent pipeline (search -> social -> web -> suggestion -> validator -> updater)."
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

    try:
        overall = run_pipeline(settings, dry_run=args.dry_run, budget_total=budget_total)
    except Exception:
        # The pipeline did NOT complete (a stage crashed, the DB was unreachable,
        # config was invalid, etc.). This is the only condition that fails the CI
        # job, so the run is investigated.
        logger.exception("pipeline run failed before completing")
        return 1

    print("\nPipeline run complete:")
    print(f"  dry_run          : {overall['dry_run']}")
    print(f"  budget           : {overall['budget_total'] - overall['budget_remaining']}"
          f" / {overall['budget_total']} used")
    print(f"  duration_s       : {overall['duration_s']}")
    print(f"  search           : {overall['search']}")
    print(f"  social           : {overall['social']}")
    print(f"  web              : {overall['web']}")
    print(f"  suggestion       : {overall['suggestion']}")
    print(f"  validator        : {overall['validator']}")
    print(f"  updater          : {overall['updater']}")

    # Exit code reflects whether the pipeline COMPLETED, not whether every external
    # call succeeded. Reaching here means it did, so the CI job is green. The agents
    # catch per-item failures (a flaky geocode / search / details call), tally them
    # as transient `errors`, and keep going; those are surfaced here and recorded in
    # agent_log, but must not fail the daily run. (A transient blip used to flip the
    # whole pipeline to a CI failure even when all places were processed.)
    transient = _transient_error_count(overall)
    if transient:
        print(f"  note             : {transient} transient per-item error(s) "
              "handled and logged to agent_log (non-fatal).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
