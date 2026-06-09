"""Validator agent — the one quality gate before a place goes public.

Pulls every ``pending`` candidate (inserted by the Search agent) and asks
``claude-sonnet-4-6`` to judge it against a fixed rubric, returning a structured
verdict ``{verdict, confidence_score, category, safety_level, reasoning, flags,
recommendation}``. A three-tier verdict (``approved`` / ``needs_review`` /
``rejected``) maps to the candidate's ``status``: ``approved`` → ``approved``,
``rejected`` → ``discarded``, ``needs_review`` → ``needs_review`` (the human-review
queue, held back from the map). Confidence, reasoning, flags and the suggested
operator action are persisted for auditing. Each validation — and a final run
summary — is written to ``agent_log``.

Health-sensitive by design: a confidence floor of 0.7 forces ``needs_review`` no
matter what the model says (auto-approval requires ``confidence_score >= 0.85``),
``safety_level`` defaults conservative, and ``verified`` stays ``false`` (a human
confirms before a place is marked verified).
"""

from __future__ import annotations

import logging

from agents.base import BaseAgent
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient

logger = logging.getLogger("celiacmap.agent")

ALLOWED_CATEGORIES = {"restaurant", "cafe", "shop"}
ALLOWED_SAFETY = {"gluten_free_100", "celiac_friendly", "options_available"}
ALLOWED_VERDICTS = {"approved", "rejected", "needs_review"}
DEFAULT_SAFETY_LEVEL = "options_available"

# Confidence gates (health-sensitive). Auto-approval needs strong evidence; the
# 0.7 floor is below 0.85, so any place the model would "approve" with weak
# confidence still falls back to needs_review for a human.
APPROVE_THRESHOLD = 0.85
REJECT_THRESHOLD = 0.50

# Maps the rubric verdict to the database status (additive: 'rejected' reuses the
# existing 'discarded' state; 'needs_review' is the new human-review queue).
VERDICT_TO_STATUS = {
    "approved": "approved",
    "rejected": "discarded",
    "needs_review": "needs_review",
}

# Fixed across every candidate in a run, so it is sent as a cached system block.
RUBRIC = """\
Eres el Validator Agent de CeliacMap, un sistema de validación conservador para \
lugares gluten free / sin TACC en Uruguay y Argentina. Recibes un único lugar \
candidato descubierto automáticamente — vía Google Places, páginas públicas de \
redes sociales o investigación web — así que normalmente solo tienes su nombre, \
dirección, ciudad/país y una categoría estimada.

Tu responsabilidad es NUNCA sobreestimar la seguridad. La salud de personas \
celíacas depende de tu criterio. Ante la duda, siempre escala a revisión humana.

Rubric de validación (veredicto):
- "approved" (confidence_score >= 0.85): Evidencia explícita y clara de que el \
lugar ofrece opciones sin TACC, con mención directa de "sin TACC", "sin gluten" \
certificado, o descripción de protocolo anti-contaminación cruzada.
- "needs_review" (0.5 <= confidence_score < 0.85): Evidencia parcial, ambigua o \
que requiere confirmación humana.
- "rejected" (confidence_score < 0.5): Sin evidencia suficiente, información \
contradictoria o señales de riesgo para celíacos.

Flags de alerta a detectar (cada una reduce la confianza):
- Menciona "sin gluten" pero no "sin TACC" (puede ser marketing, no médico)
- No menciona protocolo de contaminación cruzada
- Solo tiene opciones vegetarianas/veganas sin mención explícita sin TACC
- Información desactualizada (> 12 meses)
- Reseñas negativas de celíacos
- Descripción ambigua ("apto para dietas especiales")

Asigna una categoría (exactamente una):
- "restaurant": restaurantes, comida para llevar, lugares para comer una comida.
- "cafe": cafés, cafeterías, panaderías, pastelerías.
- "shop": almacenes, supermercados, dietéticas / comercios de alimentos saludables.

Asigna un safety_level (exactamente uno), eligiendo el nivel MÁS BAJO ante la duda:
- "gluten_free_100": establecimiento totalmente sin gluten / dedicado a celíacos.
- "celiac_friendly": atiende explícitamente a celíacos (certificado, "apto \
celíacos", preparación dedicada).
- "options_available": ofrece algunas opciones sin gluten pero no está \
especializado. Es el piso por defecto cuando la evidencia es escasa.

También se te pueden dar fragmentos de reseñas de la comunidad que mencionan \
términos sin gluten / celíaco. Pésalos como evidencia de apoyo, pero nunca dejes \
que reseñas entusiastas te empujen por encima de la evidencia: cuando la señal es \
escasa, mantente conservador.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, \
exactamente con esta forma:
{"verdict": "approved" | "rejected" | "needs_review",
 "confidence_score": <número entre 0.0 y 1.0>,
 "category": "restaurant" | "cafe" | "shop",
 "safety_level": "gluten_free_100" | "celiac_friendly" | "options_available",
 "reasoning": "<explicación clara en español, máximo 3 oraciones>",
 "flags": ["<flag detectado>", ...],
 "recommendation": "<acción concreta sugerida para el operador>"}
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

    @staticmethod
    def _coerce_flags(raw) -> list[str]:
        """Normalize the model's flags into a clean list of short strings."""
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            return []
        return [s.strip() for item in raw if (s := str(item).strip())]

    @staticmethod
    def _decide_status(verdict: str, confidence: float | None) -> str:
        """Map the model verdict + confidence to a DB status, code-enforced.

        Defense in depth: regardless of the model's stated verdict, auto-approval
        requires confidence >= 0.85; confidence < 0.5 (or an explicit 'rejected')
        rejects; everything in between (and the < 0.7 safety floor) is held for a
        human as 'needs_review'.
        """
        conf = confidence if confidence is not None else 0.0
        if verdict == "rejected" or conf < REJECT_THRESHOLD:
            return "discarded"
        if verdict == "approved" and conf >= APPROVE_THRESHOLD:
            return "approved"
        return "needs_review"

    def _normalize(self, verdict: dict, place: dict) -> dict:
        """Coerce the model output into safe, schema-valid values."""
        raw = str(verdict.get("verdict", "")).strip().lower()
        verdict_label = raw if raw in ALLOWED_VERDICTS else "needs_review"

        category = verdict.get("category")
        if category not in ALLOWED_CATEGORIES:
            category = place.get("category")

        safety = verdict.get("safety_level")
        if safety not in ALLOWED_SAFETY:
            safety = place.get("safety_level") or DEFAULT_SAFETY_LEVEL

        # Accept both the new field name and the legacy ones, defensively.
        confidence = self._clamp_confidence(
            verdict.get("confidence_score", verdict.get("confidence"))
        )
        reasoning = str(verdict.get("reasoning", verdict.get("reason", ""))).strip()

        return {
            "verdict": verdict_label,
            "status": self._decide_status(verdict_label, confidence),
            "category": category,
            "safety_level": safety,
            "confidence": confidence,
            "reason": reasoning or None,
            "flags": self._coerce_flags(verdict.get("flags")),
            "recommendation": (str(verdict.get("recommendation", "")).strip() or None),
        }

    def run(self) -> dict:
        pending = self.db.fetch_places_by_status("pending", limit=self.max_per_run)
        approved = 0
        needs_review = 0
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

            status = v["status"]
            # NOTE: update_place_validation only patches the validation columns —
            # never social_url, so the Social/Web agents' source URL is preserved
            # through validation. The classification is stored for every verdict so
            # a human reviewing a needs_review row sees the validator's best guess.
            try:
                self.db.update_place_validation(
                    place_id,
                    status=status,
                    confidence=v["confidence"],
                    notes=v["reason"],
                    category=v["category"],
                    safety_level=v["safety_level"],
                    flags=v["flags"],
                    recommendation=v["recommendation"],
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

            if status == "approved":
                approved += 1
            elif status == "needs_review":
                needs_review += 1
            else:
                discarded += 1

            self.log(
                "validate",
                {
                    "name": place.get("name"),
                    "verdict": v["verdict"],
                    "status": status,
                    "category": v["category"],
                    "safety_level": v["safety_level"],
                    "confidence": v["confidence"],
                    "reasoning": v["reason"],
                    "flags": v["flags"],
                    "recommendation": v["recommendation"],
                },
                status="success",
                place_id=place_id,
            )

        summary = {
            "pending_seen": len(pending),
            "approved": approved,
            "needs_review": needs_review,
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
