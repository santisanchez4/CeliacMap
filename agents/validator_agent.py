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
import re
import unicodedata

from agents.base import BaseAgent
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient

logger = logging.getLogger("celiacmap.agent")

ALLOWED_CATEGORIES = {"restaurant", "cafe", "shop"}
ALLOWED_SAFETY = {"gluten_free_100", "celiac_friendly", "options_available"}
ALLOWED_VERDICTS = {"approved", "rejected", "needs_review"}
DEFAULT_SAFETY_LEVEL = "options_available"

# Community kitchen declarations (docs/superpowers/specs/2026-09-24-kitchen-info-design.md).
MAX_CLAIMS = 5
PENDING_ADMIN_FLAG = "100% pendiente de confirmación del administrador"
_PREP_LABELS = {
    "separate_kitchen": "cocina separada",
    "separate_prep": "preparación aparte",
    "shared_kitchen": "misma cocina",
}

# Discovery / community / admin evidence (audit plan step 1): server-only place_evidence rows.
MAX_EVIDENCE = 5
MAX_EVIDENCE_CHARS = 400
_EVIDENCE_LABELS = {
    "social": "redes sociales",
    "web": "web",
    "user": "aporte de una persona (formulario)",
    "admin": "administrador de CeliacMap",
}

# Tope C (audit plan step 2): an automatic "gluten_free_100" needs an explicit exclusivity
# phrase in the evidence the model was given (reviews + place_evidence). The place's NAME
# never counts: it is not in the texts searched here. Matched after lower-casing and
# stripping accents.
_EXCLUSIVE_SIGNAL_RE = re.compile(
    r"100\s*%\s*(?:sin (?:gluten|tacc)|libre de gluten|gluten[ -]?free|apto|celiac)"
    r"|(?:todo|toda|totalmente|exclusivamente|solo|solamente|unicamente)\s+(?:es\s+|lo que \w+\s+es\s+)?"
    r"(?:sin (?:gluten|tacc)|libre de gluten|gluten[ -]?free|apto para celiac)"
    r"|cocina (?:exclusiva|dedicada|100\s*%)"
    r"|(?:espacio|local|lugar|panaderia|restaurante|cafe) (?:100\s*% )?libre de gluten"
)
_NEGATION_RE = re.compile(r"\bno\s+(?:es\s+|son\s+|tiene\s+)?$")
# Sentences that tie a person (owner) to celiac disease: a third party's health condition,
# never persisted to the publicly readable places columns (ADR-007).
_OWNER_HEALTH_RE = re.compile(r"(?:due[nñ]|propietari|owner)\w*[^.;\n]{0,60}cel[ií]ac|cel[ií]ac\w*[^.;\n]{0,60}(?:due[nñ]|propietari|owner)", re.IGNORECASE)

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
- "gluten_free_100": establecimiento donde se cocinan y venden ÚNICAMENTE \
productos aptos para celíacos (cocina exclusiva / dedicada). Un local que \
cocina con gluten pero ofrece menú, preparación aparte o cocina separada para \
celíacos NO es "gluten_free_100".
- "celiac_friendly": atiende explícitamente a celíacos (certificado, "apto \
celíacos", preparación dedicada).
- "options_available": ofrece algunas opciones sin gluten pero no está \
especializado. Es el piso por defecto cuando la evidencia es escasa.

También se te pueden dar fragmentos de reseñas de la comunidad que mencionan \
términos sin gluten / celíaco. Pésalos como evidencia de apoyo, pero nunca dejes \
que reseñas entusiastas te empujen por encima de la evidencia: cuando la señal es \
escasa, mantente conservador.

Si el mensaje incluye "declaraciones_comunidad" (un bloque aparte de las reseñas), son afirmaciones de personas sobre la cocina del lugar (si es exclusivamente sin gluten, cómo preparan lo apto para celíacos). NO están verificadas: úsalas para orientar la revisión, pero por sí solas NO justifican "approved" ni "gluten_free_100". Si una declaración indica que el local también cocina con gluten, el nivel no puede ser "gluten_free_100". Si ese bloque es la única evidencia de que la cocina es exclusiva, el safety_level no puede ser "gluten_free_100": como máximo "celiac_friendly". Estas declaraciones no cambian cómo pesas las reseñas ni el resto de la evidencia: sin ese bloque, evalúa exactamente como siempre.

Si el mensaje incluye "ubicacion_geocode", significa que solo se geocodificó la \
dirección de texto del candidato: NO hay una ficha de Google Places que confirme \
que el negocio existe y opera en ese lugar (sin reseñas de Google, sin \
verificación de existencia). Tratá esto como evidencia debilitada — NO asignes \
"approved" salvo que el resto de la evidencia (mención explícita de "sin TACC", \
reseñas claras de la comunidad) sea fuerte por sí sola. Ante la duda, "needs_review".

Si el mensaje incluye "evidencia_descubrimiento", son textos tomados de fuentes públicas (publicaciones o perfiles de redes sociales, páginas web) o aportados por personas o por el administrador, con su URL cuando existe. Son la evidencia principal para distinguir un espacio 100% sin gluten de un lugar con opciones: úsalos. No están verificados: una fuente aislada no alcanza para "approved" si el resto de la evidencia la contradice, y lo que aporta una persona pesa como las declaraciones_comunidad.

Basá el veredicto y el safety_level SOLO en la evidencia que viene en este mensaje. No uses lo que creas saber del negocio por tu cuenta, ni tomes el nombre o una parte del nombre como evidencia: que el nombre diga "sin gluten" no prueba que la cocina sea exclusiva, y que no lo diga no prueba lo contrario. No menciones en reasoning, flags ni recommendation datos de salud de ninguna persona (por ejemplo, si el dueño o la dueña es celíaco/a).

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
    def _build_user_prompt(
        place: dict,
        reviews: list[dict] | None = None,
        claims: list[dict] | None = None,
        evidence: list[dict] | None = None,
    ) -> str:
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

        # Health-sensitive: a candidate resolved only by geocoding its street
        # address has no Google Place backing it — the RUBRIC tells the model to
        # treat this as weaker evidence (see CLAUDE.md Decisions Log / prompts.md).
        if place.get("geocode_method") == "address_only":
            prompt += (
                "\n\nubicacion_geocode: SOLO se geocodificó la dirección de texto "
                "de este candidato — NO existe una ficha de Google Places que "
                "confirme que el negocio opera en ese lugar."
            )

        snippets = [
            (r.get("text") or "").strip() for r in (reviews or []) if (r.get("text") or "").strip()
        ]
        if snippets:
            prompt += "\n\nCommunity review signals:\n" + "\n".join(
                f"- {text}" for text in snippets
            )

        evidence_block = ValidatorAgent._evidence_block(evidence)
        if evidence_block:
            prompt += "\n\n" + evidence_block

        claims_block = ValidatorAgent._claims_block(claims)
        if claims_block:
            prompt += "\n\n" + claims_block
        return prompt

    @staticmethod
    def _evidence_block(evidence) -> str:
        """Discovery / community / admin evidence (place_evidence), rendered as UNVERIFIED.

        Best-effort like the claims block: anything that is not a list of dicts renders
        nothing, so a place without evidence gets exactly the prompt it got before.
        """
        lines = []
        for e in list(evidence or [])[:MAX_EVIDENCE]:
            if not isinstance(e, dict):
                continue
            text = " ".join(str(e.get("text") or "").split())[:MAX_EVIDENCE_CHARS]
            url = str(e.get("url") or "").strip()
            if not text and not url:
                continue
            label = _EVIDENCE_LABELS.get(e.get("source"), "otra fuente")
            body = text or "(sin texto)"
            lines.append(f"- [{label}] {body}" + (f" (fuente: {url})" if url else ""))
        if not lines:
            return ""
        return "evidencia_descubrimiento (NO verificada):\n" + "\n".join(lines)

    @staticmethod
    def _claims_block(claims) -> str:
        """Community kitchen declarations, rendered as clearly UNVERIFIED context.

        Best-effort on purpose: anything that is not a list of dicts (None, a mock,
        a failed read) renders nothing, so the prompt is byte-identical to today's.

        ``owner_celiac`` is deliberately NEVER rendered: it is a named third party's health
        condition, and whatever the model sees can end up in its free text (reasoning / flags /
        recommendation), which is persisted to publicly readable ``places`` columns.
        """

        def tri(value) -> str:
            return "sí" if value is True else "no" if value is False else "sin dato"

        groups = []
        for c in list(claims or [])[:MAX_CLAIMS]:
            if not isinstance(c, dict):
                continue
            groups.append(
                [
                    f"- cocina exclusivamente sin gluten: {tri(c.get('kitchen_exclusive'))}",
                    f"- preparación para celíacos: {_PREP_LABELS.get(c.get('celiac_prep'), 'sin dato')}",
                ]
            )
        if not groups:
            return ""
        lines = ["declaraciones_comunidad (NO verificadas):"]
        for i, group in enumerate(groups, start=1):
            if len(groups) > 1:
                lines.append(f"Declaración {i}:")
            lines.extend(group)
        return "\n".join(lines)

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

    def evaluate(
        self,
        place: dict,
        reviews: list[dict] | None = None,
        claims: list[dict] | None = None,
        evidence: list[dict] | None = None,
    ) -> dict:
        """Run the full model evaluation for a single place and return the
        normalized verdict dict (``verdict``, ``status``, ``category``,
        ``safety_level``, ``confidence``, ``reason``, ``flags``,
        ``recommendation``).

        Pure: no DB reads or writes — the caller supplies any review / community
        claim context and persists the result. This is the single-place core of
        ``run()``; the retroactive re-validation script
        (``scripts/revalidate_low_confidence.py``) reuses it so batch and one-off
        re-evaluation share one code path.
        """
        raw = self.llm.complete_json(
            RUBRIC, self._build_user_prompt(place, reviews, claims, evidence), model=self.model
        )
        return self._normalize(raw, place, claims, reviews=reviews, evidence=evidence)

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

    def _normalize(
        self,
        verdict: dict,
        place: dict,
        claims: list[dict] | None = None,
        *,
        reviews: list[dict] | None = None,
        evidence: list[dict] | None = None,
    ) -> dict:
        """Coerce the model output into safe, schema-valid values."""
        raw = str(verdict.get("verdict", "")).strip().lower()
        verdict_label = raw if raw in ALLOWED_VERDICTS else "needs_review"

        category = verdict.get("category")
        if category not in ALLOWED_CATEGORIES:
            category = place.get("category")

        safety = verdict.get("safety_level")
        if safety not in ALLOWED_SAFETY:
            safety = place.get("safety_level") or DEFAULT_SAFETY_LEVEL
        safety, cap_flags = self._apply_kitchen_caps(safety, place, claims)
        safety, signal_flags = self._apply_exclusive_signal_cap(safety, reviews, evidence)
        cap_flags += [f for f in signal_flags if f not in cap_flags]

        # Accept both the new field name and the legacy ones, defensively.
        confidence = self._clamp_confidence(
            verdict.get("confidence_score", verdict.get("confidence"))
        )
        reasoning = self._scrub_owner_health(
            str(verdict.get("reasoning", verdict.get("reason", ""))).strip()
        )

        flags = [f for f in self._coerce_flags(verdict.get("flags")) if not _OWNER_HEALTH_RE.search(f)]
        flags += [f for f in cap_flags if f not in flags]

        return {
            "verdict": verdict_label,
            "status": self._decide_status(verdict_label, confidence),
            "category": category,
            "safety_level": safety,
            "confidence": confidence,
            "reason": reasoning or None,
            "flags": flags,
            "recommendation": self._scrub_owner_health(
                str(verdict.get("recommendation", "")).strip()
            )
            or None,
        }

    @staticmethod
    def _apply_kitchen_caps(safety: str, place: dict, claims) -> tuple[str, list[str]]:
        """Deterministic ceilings on ``safety_level`` (defense in depth, like the
        confidence gates): they only ever LOWER the level and never touch ``status``.

        A) A community-suggested place (``source='user'``) never leaves the Validator
           as ``gluten_free_100`` — only the admin raises a place to 100%.
        B) If any community declaration says the kitchen is NOT exclusively gluten
           free, the level is at most ``celiac_friendly``, whatever the source.
        ``owner_celiac`` never participates: it is context for the model only.
        Returns the (possibly lowered) level plus the fixed admin-pending flag when
        a 100% is awaiting the admin (community place, and either the model said 100%
        or a declaration says the kitchen is exclusive).
        """
        declared = [c for c in list(claims or []) if isinstance(c, dict)]
        said_100 = safety == "gluten_free_100"
        says_exclusive = any(c.get("kitchen_exclusive") is True for c in declared)
        # A preparation method for celiac food implies the place also cooks with gluten, so it counts as
        # "not exclusive" even if the exclusivity answer itself is missing.
        says_not_exclusive = any(
            c.get("kitchen_exclusive") is False or c.get("celiac_prep") is not None for c in declared
        )
        if said_100 and says_not_exclusive:
            safety = "celiac_friendly"
        flags: list[str] = []
        if place.get("source") == "user":
            if safety == "gluten_free_100":
                safety = "celiac_friendly"
            if said_100 or says_exclusive:
                flags.append(PENDING_ADMIN_FLAG)
        return safety, flags

    @staticmethod
    def has_exclusive_signal(texts) -> bool:
        """True if any text states the place is exclusively gluten free ("100% sin TACC",
        "todo es sin gluten", "cocina exclusiva"...), and the phrase is not negated."""
        for raw in texts or []:
            text = unicodedata.normalize("NFKD", str(raw or ""))
            text = "".join(c for c in text if not unicodedata.combining(c)).lower()
            for m in _EXCLUSIVE_SIGNAL_RE.finditer(text):
                if not _NEGATION_RE.search(text[max(0, m.start() - 20): m.start()]):
                    return True
        return False

    @classmethod
    def _apply_exclusive_signal_cap(cls, safety: str, reviews, evidence) -> tuple[str, list[str]]:
        """Tope C: "gluten_free_100" only survives with an explicit exclusivity phrase in the
        evidence the model saw (reviews + place_evidence) — never from the name, never from the
        model's own knowledge. Without it the level drops to "celiac_friendly" (public label
        "Tiene opciones sin TACC") and the place is flagged for the admin, who confirms 100%.

        The reverse case is flagged too: the evidence DOES state exclusivity but the model kept a
        lower level (measured 2026-09-25: a Los Leños-like place with "todo es sin gluten" on its
        Instagram stays "celiac_friendly" 4/4 — the rubric says "the lowest level when in doubt").
        The level is not raised here; the flag puts the place in the admin's 100% queue with its
        evidence, so the 100% comes from a person, as the labeling rule requires."""
        texts = [r.get("text") for r in list(reviews or []) if isinstance(r, dict)]
        texts += [e.get("text") for e in list(evidence or []) if isinstance(e, dict)]
        signal = cls.has_exclusive_signal(texts)
        if safety != "gluten_free_100":
            return safety, ([PENDING_ADMIN_FLAG] if signal else [])
        if signal:
            return safety, []
        return "celiac_friendly", [PENDING_ADMIN_FLAG]

    @staticmethod
    def _scrub_owner_health(text: str) -> str:
        """Drop sentences that tie an owner to celiac disease (a third party's health
        condition); what's left is persisted to publicly readable places columns."""
        if not text or not _OWNER_HEALTH_RE.search(text):
            return text
        sentences = re.split(r"(?<=[.;!?])\s+", text)
        return " ".join(x for x in sentences if not _OWNER_HEALTH_RE.search(x)).strip()

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
                claims = list(self.db.fetch_community_claims(place_id) or [])
            except Exception:  # noqa: BLE001 - claims context is best-effort
                logger.exception("fetching community claims failed for %s", place_id)
                claims = []
            try:
                evidence = list(self.db.fetch_place_evidence(place_id) or [])
            except Exception:  # noqa: BLE001 - evidence context is best-effort
                logger.exception("fetching evidence failed for %s", place_id)
                evidence = []
            try:
                v = self.evaluate(place, reviews, claims, evidence)
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
