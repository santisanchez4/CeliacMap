"""Validator agent — the one quality gate before a place goes public.

Pulls every ``pending`` candidate (inserted by the Search agent) and asks
``claude-sonnet-4-6`` to judge it against a fixed rubric, returning a structured
verdict ``{verdict, category, safety_level, confidence, reason}``. The verdict
sets the candidate's ``status`` to ``approved`` or ``discarded`` and persists the
confidence/notes for auditing. Each validation — and a final run summary — is
written to ``agent_log``.

Health-sensitive by design: ``safety_level`` defaults conservative and
``verified`` stays ``false`` (a human confirms before a place is marked verified).
"""

from __future__ import annotations

import logging

from agents.base import BaseAgent
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient

logger = logging.getLogger("celiacmap.agent")

ALLOWED_CATEGORIES = {"restaurant", "cafe", "shop"}
ALLOWED_SAFETY = {"gluten_free_100", "celiac_friendly", "options_available"}
DEFAULT_SAFETY_LEVEL = "options_available"

# Fixed across every candidate in a run, so it is sent as a cached system block.
RUBRIC = """\
You are the Validator for CeliacMap, a curated directory of gluten-free / \
"sin TACC" (celiac-safe) places in Latin America. You receive a single candidate \
place that was discovered automatically via Google Places (so you only have its \
name, address, city/country and a guessed category). Decide whether it belongs in \
the directory, then classify it.

This data is used by people with celiac disease, for whom gluten is a health \
hazard. Never overstate how safe a place is. When unsure, be conservative.

Decide a verdict:
- "approve": the place plausibly serves or sells gluten-free / celiac-safe food \
(a restaurant, a cafe/bakery, or a shop with GF products). Names or addresses \
mentioning "sin TACC", "sin gluten", "gluten free", "celíaco/a", "apto celíacos" \
are strong positive signals.
- "discard": clearly not a food/place business, clearly unrelated to gluten-free \
needs, generic/ambiguous with no GF signal, or implausible as a directory entry.

Assign a category (exactly one):
- "restaurant": restaurants, takeaways, places to eat a meal.
- "cafe": cafes, coffee shops, bakeries, pastry shops.
- "shop": grocery stores, supermarkets, health-food / dietetica shops.

Assign a safety_level (exactly one), choosing the LOWER level whenever unsure:
- "gluten_free_100": a fully gluten-free / dedicated celiac establishment.
- "celiac_friendly": explicitly caters to celiacs (certified, "apto celíacos", \
dedicated preparation).
- "options_available": offers some gluten-free options but is not specialized. \
This is the default floor when evidence is thin.

You may also be given community review snippets that mention gluten-free / celiac \
terms. Weigh them as supporting evidence (they can raise confidence or sharpen the \
safety_level), but never let enthusiastic reviews push you above the evidence — \
when the signal is thin, stay conservative.

Respond with ONLY a JSON object, no prose, in exactly this shape:
{"verdict": "approve" | "discard",
 "category": "restaurant" | "cafe" | "shop",
 "safety_level": "gluten_free_100" | "celiac_friendly" | "options_available",
 "confidence": <number between 0 and 1>,
 "reason": "<one or two short sentences>"}
"""


class ValidatorAgent(BaseAgent):
    name = "validator"

    def __init__(
        self,
        db: SupabaseClient,
        llm: LLMClient,
        model: str | None = None,
        max_per_run: int = 50,
    ):
        super().__init__(db)
        self.llm = llm
        self.model = model  # None -> LLMClient.default_model (claude-sonnet-4-6)
        self.max_per_run = max_per_run

    @staticmethod
    def _build_user_prompt(place: dict, reviews: list[dict] | None = None) -> str:
        fields = {
            "name": place.get("name"),
            "address": place.get("address"),
            "city": place.get("city"),
            "country": place.get("country"),
            "guessed_category": place.get("category"),
            "source": place.get("source"),
        }
        lines = [f"{k}: {v}" for k, v in fields.items() if v is not None]
        prompt = "Candidate place:\n" + "\n".join(lines)

        snippets = [
            (r.get("text") or "").strip() for r in (reviews or []) if (r.get("text") or "").strip()
        ]
        if snippets:
            prompt += "\n\nCommunity review signals:\n" + "\n".join(
                f"- {text}" for text in snippets
            )
        return prompt

    @staticmethod
    def _clamp_confidence(raw) -> float | None:
        try:
            return max(0.0, min(1.0, float(raw)))
        except (TypeError, ValueError):
            return None

    def _normalize(self, verdict: dict, place: dict) -> dict:
        """Coerce the model output into safe, schema-valid values."""
        raw = str(verdict.get("verdict", "")).strip().lower()
        approved = raw in ("approve", "approved", "accept", "yes")

        category = verdict.get("category")
        if category not in ALLOWED_CATEGORIES:
            category = place.get("category")

        safety = verdict.get("safety_level")
        if safety not in ALLOWED_SAFETY:
            safety = place.get("safety_level") or DEFAULT_SAFETY_LEVEL

        return {
            "approved": approved,
            "category": category,
            "safety_level": safety,
            "confidence": self._clamp_confidence(verdict.get("confidence")),
            "reason": (str(verdict.get("reason", "")).strip() or None),
        }

    def run(self) -> dict:
        pending = self.db.fetch_places_by_status("pending", limit=self.max_per_run)
        approved = 0
        discarded = 0
        errors = 0

        for place in pending:
            place_id = place.get("id")
            try:
                reviews = self.db.fetch_reviews_for_place(place_id)
            except Exception:  # noqa: BLE001 - review context is best-effort
                logger.exception("fetching review context failed for %s", place_id)
                reviews = []
            try:
                raw_verdict = self.llm.complete_json(
                    RUBRIC,
                    self._build_user_prompt(place, reviews),
                    model=self.model,
                )
                v = self._normalize(raw_verdict, place)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.exception("validation failed for %s", place_id)
                self.log(
                    "validate_failed",
                    {"name": place.get("name"), "error": str(exc)},
                    status="error",
                    place_id=place_id,
                )
                continue

            status = "approved" if v["approved"] else "discarded"
            try:
                if v["approved"]:
                    self.db.update_place_validation(
                        place_id,
                        status=status,
                        confidence=v["confidence"],
                        notes=v["reason"],
                        category=v["category"],
                        safety_level=v["safety_level"],
                    )
                else:
                    self.db.update_place_validation(
                        place_id,
                        status=status,
                        confidence=v["confidence"],
                        notes=v["reason"],
                    )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.exception("persisting verdict failed for %s", place_id)
                self.log(
                    "validate_persist_failed",
                    {"name": place.get("name"), "error": str(exc)},
                    status="error",
                    place_id=place_id,
                )
                continue

            if v["approved"]:
                approved += 1
            else:
                discarded += 1

            self.log(
                "validate",
                {
                    "name": place.get("name"),
                    "verdict": status,
                    "category": v["category"],
                    "safety_level": v["safety_level"],
                    "confidence": v["confidence"],
                    "reason": v["reason"],
                },
                status="success",
                place_id=place_id,
            )

        summary = {
            "pending_seen": len(pending),
            "approved": approved,
            "discarded": discarded,
            "errors": errors,
        }
        self.log(
            "validator_run_complete",
            summary,
            status="error" if errors else "success",
        )
        return summary


def main() -> int:
    """Run the Validator agent standalone (manual pipeline validation)."""
    from config.settings import get_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    settings.require(
        "supabase_url", "supabase_service_role_key", "anthropic_api_key"
    )

    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    llm = LLMClient(settings.anthropic_api_key, settings.validator_model)
    agent = ValidatorAgent(
        db, llm, max_per_run=settings.max_validations_per_run
    )

    summary = agent.run()
    print("Validator run complete:", summary)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
