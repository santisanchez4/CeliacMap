"""Retroactive re-validation of low-confidence approved places.

**Why this exists.** The three-tier Validator rubric (``approved`` /
``needs_review`` / ``rejected``) and its code-enforced confidence gates
(auto-approval needs ``confidence_score >= 0.85``; ``< 0.7`` is held for a human)
were adopted in Jun 2026. Places approved *before* that — under the old binary
``approve`` / ``discard`` rubric — were never re-evaluated against the new gates.
A read-only audit (2026-09-06) found ~176 ``status='approved'`` places on the
public map with ``validation_confidence < 0.7``: they would be held for human
review if the current rubric saw them today.

**What this does.** Re-runs the *current* ``ValidatorAgent`` evaluation (same
``RUBRIC``, same review context, same ``_decide_status`` gates) against every
approved place below a confidence threshold and moves each row directly to the
verdict the current rubric gives it — ``approved`` / ``needs_review`` /
``discarded``. It is **retroactive re-validation, not new-candidate validation**:
the row never passes through ``status='pending'``.

**Traceability.** On ``--apply`` every touched row gets a
``RE-VALIDACIÓN RETROACTIVA`` header prepended to ``validation_notes`` (stating
the old confidence/status, the new verdict, and that it was not a new candidate),
the original Validator note is preserved below it, and an ``agent_log`` row is
written (``agent='validator'``, ``action='revalidate_retroactive'``).
``validation_confidence`` is set to whatever the model now produces — never
inflated or deflated to match a decision. ``verified`` is left untouched.

Run from the repo root:

    python -m scripts.revalidate_low_confidence                 # DRY RUN (no writes)
    python -m scripts.revalidate_low_confidence --limit 10      # dry run, first 10 only
    python -m scripts.revalidate_low_confidence --threshold 0.5 # dry run, only < 0.5
    python -m scripts.revalidate_low_confidence --apply         # WRITE to the database

The dry run still makes real Sonnet calls (that is how the projected distribution
is produced) but suppresses every database write via ``DryRunSupabase``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import unicodedata
from datetime import date

from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient
from agents.validator_agent import ValidatorAgent
from config.settings import get_settings
from scripts.run_agents import DryRunSupabase

logger = logging.getLogger("celiacmap.agent")

# claude-sonnet-4-6 list price (USD per 1M tokens). Cache read = 0.1x input,
# ephemeral (5 min) cache write = 1.25x input.
SONNET_INPUT_PER_M = 3.00
SONNET_OUTPUT_PER_M = 15.00
SONNET_CACHE_READ_PER_M = SONNET_INPUT_PER_M * 0.10
SONNET_CACHE_WRITE_PER_M = SONNET_INPUT_PER_M * 1.25

DEFAULT_THRESHOLD = 0.7

# A row whose validation_notes carries one of these markers is NEVER re-validated:
# a human already made a deliberate call on it that the model cannot reproduce
# (first-hand knowledge of the business), or a prior run of this script already
# re-evaluated it. Matched accent- and case-insensitively. See CLAUDE.md
# "Manual Validator overrides — allowed, but never silent".
PROTECTED_NOTE_MARKERS = (
    "override",              # "OVERRIDE MANUAL ...", "override del Validator"
    "aprobacion manual",     # "APROBACIÓN MANUAL (override del Validator)"
    "correccion manual",     # "CORRECCIÓN MANUAL ..." (geography fixes)
    "validacion retroactiva",  # a previous run of this script (idempotency)
)

# Places whose new verdict must be forced to 'needs_review' regardless of what
# the model returns — reviewed by hand and found unsafe to auto-publish. The
# value is the human reason, prepended to validation_notes.
FORCED_NEEDS_REVIEW: dict[str, str] = {
    # Enharinate Mendoza — the dry-run's only 'approved'. The model gave 0.87 /
    # celiac_friendly with NO reviews attached, citing its own knowledge of the
    # chain ("existen múltiples reseñas públicas ... que identifican a
    # 'Enharinate' como una cadena dedicada a productos sin TACC"). That is
    # parametric knowledge, not evidence in the prompt — exactly the kind of
    # approval the RUBRIC is meant to prevent. Held for human confirmation.
    "ff4da9ce-2635-43e0-9612-2f4257cade55": (
        "AJUSTE MANUAL en la re-validación retroactiva: el modelo devolvió "
        "'approved' (confidence 0.87, celiac_friendly) SIN reseñas en el prompt, "
        "apoyándose en conocimiento propio del negocio ('Enharinate' como cadena "
        "sin TACC conocida) y no en evidencia provista. Ese tipo de aprobación "
        "por conocimiento paramétrico es justo lo que el RUBRIC busca evitar, así "
        "que se fuerza a needs_review para confirmación humana. La "
        "validation_confidence se deja en el valor del modelo (no se desinfla)."
    ),
}


def _safe_print(text: str) -> None:
    """print() that survives a legacy console encoding (Windows cp1252)."""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"))


def _norm(text: str) -> str:
    """Lowercase + strip accents, for tolerant marker matching."""
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(c)
    )


def protected_marker(place: dict) -> str | None:
    """Return the marker that makes this row off-limits, or None."""
    notes = _norm(place.get("validation_notes") or "")
    return next((m for m in PROTECTED_NOTE_MARKERS if m in notes), None)


class MeteredLLMClient(LLMClient):
    """LLMClient that accumulates token usage across calls, for a real cost figure."""

    def __init__(self, api_key: str, default_model: str):
        super().__init__(api_key, default_model)
        self.calls = 0
        self.usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }

    def _create(self, system: str, user: str, model, max_tokens: int):
        resp = super()._create(system, user, model, max_tokens)
        u = getattr(resp, "usage", None)
        if u is not None:
            self.calls += 1
            for k in self.usage:
                self.usage[k] += getattr(u, k, 0) or 0
        return resp

    def cost_usd(self) -> float:
        u = self.usage
        return (
            u["input_tokens"] * SONNET_INPUT_PER_M / 1e6
            + u["output_tokens"] * SONNET_OUTPUT_PER_M / 1e6
            + u["cache_read_input_tokens"] * SONNET_CACHE_READ_PER_M / 1e6
            + u["cache_creation_input_tokens"] * SONNET_CACHE_WRITE_PER_M / 1e6
        )


def compose_notes(
    place: dict, verdict: dict, forced_reason: str | None = None
) -> str:
    """Build the traceable validation_notes for a re-validated row.

    ``forced_reason`` (when set) means the status was overridden by hand after
    review — it is prepended and the header names the model's own verdict so the
    override is never silent.
    """
    today = date.today().isoformat()
    old_conf = place.get("validation_confidence")
    created = str(place.get("created_at") or "")[:10]
    old_note = (place.get("validation_notes") or "").strip()

    header = (
        f"RE-VALIDACIÓN RETROACTIVA ({today}): fila re-evaluada con el rubric de "
        f"tres niveles vigente (mismo RUBRIC que el Validator del pipeline). "
        f"Aprobada originalmente ~{created} bajo el rubric binario anterior con "
        f"validation_confidence {old_conf}. Resultado nuevo: status "
        f"'{verdict['status']}' (veredicto del modelo '{verdict['verdict']}', "
        f"confidence {verdict['confidence']}). NO es la validación de un candidato "
        f"nuevo — la fila nunca volvió a status='pending'."
    )
    parts = []
    if forced_reason:
        parts.append(forced_reason)
    parts.append(header)
    if verdict.get("reason"):
        parts.append(f"--- Razonamiento nuevo del Validator: {verdict['reason']}")
    if old_note:
        parts.append(f"--- Nota original (rubric binario): {old_note}")
    return "\n".join(parts)


def _fmt_conf(value) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _example_lines(records: list[dict], limit: int) -> list[str]:
    lines = []
    for r in records[:limit]:
        safety = ""
        if r["old_safety"] != r["new_safety"]:
            safety = f"  [safety {r['old_safety']} -> {r['new_safety']}]"
        reason = (r["reasoning"] or "").replace("\n", " ")
        if len(reason) > 240:
            reason = reason[:237] + "..."
        lines.append(
            f"  - {r['name']} ({r['city']}) — approved @ {_fmt_conf(r['old_confidence'])}"
            f" -> {r['new_status']} @ {_fmt_conf(r['new_confidence'])}"
            f" (verdict={r['verdict']}, reseñas={r['reviews_seen']}){safety}\n"
            f"      {reason}"
        )
        if r["flags"]:
            lines.append(f"      flags: {'; '.join(r['flags'])}")
    return lines


def build_report(
    *,
    apply: bool,
    threshold: float,
    below_threshold: int,
    protected: list[tuple[dict, str]],
    seen: int,
    buckets: dict[str, list[dict]],
    errors: list[tuple[dict, str]],
    llm: MeteredLLMClient,
    duration_s: float,
    examples: int,
) -> str:
    stayed = len(buckets["approved"])
    to_review = len(buckets["needs_review"])
    to_discard = len(buckets["discarded"])
    safety_changed = [r for r in buckets["approved"] if r["old_safety"] != r["new_safety"]]

    out = []
    out.append("# Re-validación retroactiva — " + ("APPLY" if apply else "DRY RUN"))
    out.append("")
    out.append(f"- Fecha: {date.today().isoformat()}")
    out.append(f"- Umbral: validation_confidence < {threshold}  (status='approved', NOT NULL)")
    out.append(f"- Lugares bajo el umbral: {below_threshold}")
    out.append(f"- Excluidos (override manual / ya re-validados): {len(protected)}")
    out.append(f"- Lugares re-evaluados: {seen}")
    out.append("")
    if protected:
        out.append("## Excluidos del barrido")
        out.append("")
        out.append("Filas con una decisión humana deliberada que el modelo no puede reproducir:")
        for place, marker in protected:
            out.append(
                f"  - {place.get('name')} ({place.get('city')}) — "
                f"confidence {place.get('validation_confidence')}, marcador `{marker}`"
            )
        out.append("")
    out.append("## Distribución " + ("aplicada" if apply else "proyectada"))
    out.append("")
    out.append(f"| Resultado | Lugares | % |")
    out.append(f"|---|---:|---:|")
    denom = seen or 1
    out.append(f"| approved -> approved (se mantienen en el mapa) | {stayed} | {stayed*100//denom}% |")
    out.append(f"| approved -> needs_review (salen del mapa, cola humana) | {to_review} | {to_review*100//denom}% |")
    out.append(f"| approved -> discarded (salen del mapa) | {to_discard} | {to_discard*100//denom}% |")
    out.append(f"| errores | {len(errors)} | — |")
    out.append("")
    forced = [r for b in buckets.values() for r in b if r.get("forced")]
    if forced:
        out.append(
            f"**{len(forced)} forzado(s) a needs_review** (override manual del veredicto "
            f"del modelo): "
            + ", ".join(f"{r['name']} (modelo dijo {r['model_status']})" for r in forced)
        )
        out.append("")
    if safety_changed:
        out.append(
            f"De los {stayed} que se mantienen approved, **{len(safety_changed)}** "
            f"cambian de safety_level (ver ejemplos abajo)."
        )
        out.append("")
    out.append("## Costo real (medido)")
    out.append("")
    u = llm.usage
    out.append(f"- Llamadas a {llm.default_model}: {llm.calls}")
    out.append(f"- Tokens input (sin cache): {u['input_tokens']:,}")
    out.append(f"- Tokens cache-read: {u['cache_read_input_tokens']:,}")
    out.append(f"- Tokens cache-write: {u['cache_creation_input_tokens']:,}")
    out.append(f"- Tokens output: {u['output_tokens']:,}")
    out.append(f"- **Costo total: ${llm.cost_usd():.4f} USD**")
    out.append("")
    out.append("## Tiempo")
    out.append("")
    out.append(f"- Duración: {duration_s:.0f} s  ({duration_s/60:.1f} min)")
    per = duration_s / seen if seen else 0
    out.append(f"- Promedio por lugar: {per:.1f} s")
    out.append("")

    for key, title in (
        ("needs_review", "Ejemplos: approved -> needs_review"),
        ("discarded", "Ejemplos: approved -> discarded"),
        ("approved", "Ejemplos: approved -> approved"),
    ):
        recs = buckets[key]
        if not recs:
            continue
        out.append(f"## {title}  ({len(recs)})")
        out.append("")
        if key == "approved" and safety_changed:
            out.append("(los que cambian safety_level primero)")
            recs = safety_changed + [r for r in recs if r not in safety_changed]
        out.extend(_example_lines(recs, examples))
        out.append("")

    if errors:
        out.append(f"## Errores ({len(errors)})")
        out.append("")
        for place, msg in errors[:examples]:
            out.append(f"  - {place.get('name')} ({place.get('id')}): {msg}")
        out.append("")

    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retroactively re-validate low-confidence approved places "
        "against the current three-tier rubric."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the new verdicts to the database. Without this flag the "
        "script is a dry run (real Sonnet calls, zero writes).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Re-validate approved places with validation_confidence below this "
        f"(default {DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of places processed (for a quick sample). Default: all.",
    )
    parser.add_argument(
        "--examples",
        type=int,
        default=10,
        help="How many before/after examples to show per bucket (default 10).",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Write the full markdown report to this path.",
    )
    args = parser.parse_args()

    # Spanish reasoning text + em-dashes must not crash logging / print on a
    # legacy Windows console (cp1252). Degrade unencodable chars, don't die.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key", "anthropic_api_key")

    raw_db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    db = raw_db if args.apply else DryRunSupabase(raw_db)
    llm = MeteredLLMClient(settings.anthropic_api_key, settings.validator_model)
    agent = ValidatorAgent(db, llm)

    mode = "APPLY — writing to the database" if args.apply else "DRY RUN — no writes"
    logger.info("Retroactive re-validation: %s", mode)

    fetched = db.fetch_places_for_revalidation(
        max_confidence=args.threshold,
        limit=args.limit if args.limit is not None else 500,
    )

    # Never re-validate a deliberate human override (or a row a prior run of this
    # script already touched) — the model can't reproduce first-hand knowledge.
    protected: list[tuple[dict, str]] = []
    targets: list[dict] = []
    for place in fetched:
        marker = protected_marker(place)
        if marker:
            protected.append((place, marker))
        else:
            targets.append(place)

    logger.info(
        "%d approved place(s) with validation_confidence < %s — %d to re-validate, "
        "%d protected (manual override / already re-validated), skipped",
        len(fetched),
        args.threshold,
        len(targets),
        len(protected),
    )
    for place, marker in protected:
        logger.info("  protected: %s (%s) — marker %r", place.get("name"), place.get("id"), marker)
    if not targets:
        return 0

    buckets: dict[str, list[dict]] = {"approved": [], "needs_review": [], "discarded": []}
    errors: list[tuple[dict, str]] = []
    started = time.monotonic()

    for i, place in enumerate(targets, 1):
        pid = place.get("id")
        try:
            reviews = db.fetch_reviews_for_place(pid)
        except Exception:  # noqa: BLE001 - review context is best-effort
            logger.exception("fetching reviews failed for %s", pid)
            reviews = []

        try:
            v = agent.evaluate(place, reviews)
        except Exception as exc:  # noqa: BLE001
            logger.exception("re-validation failed for %s", pid)
            errors.append((place, str(exc)))
            continue

        model_status = v["status"]
        forced_reason = FORCED_NEEDS_REVIEW.get(pid)
        new_status = "needs_review" if forced_reason else model_status

        record = {
            "id": pid,
            "name": place.get("name"),
            "city": place.get("city"),
            "old_status": "approved",
            "old_confidence": place.get("validation_confidence"),
            "new_status": new_status,
            "model_status": model_status,
            "forced": bool(forced_reason),
            "new_confidence": v["confidence"],
            "verdict": v["verdict"],
            "reasoning": v["reason"],
            "flags": v["flags"],
            "recommendation": v["recommendation"],
            "old_safety": place.get("safety_level"),
            "new_safety": v["safety_level"],
            "reviews_seen": len(reviews),
        }
        buckets[new_status].append(record)

        notes = compose_notes(place, v, forced_reason=forced_reason)
        db.update_place_validation(
            pid,
            status=new_status,
            confidence=v["confidence"],
            notes=notes,
            category=v["category"],
            safety_level=v["safety_level"],
            flags=v["flags"],
            recommendation=v["recommendation"],
        )
        db.insert_agent_log(
            "validator",
            "revalidate_retroactive",
            {
                "name": place.get("name"),
                "old_status": "approved",
                "old_confidence": place.get("validation_confidence"),
                "new_status": new_status,
                "model_status": model_status,
                "forced_needs_review": bool(forced_reason),
                "new_confidence": v["confidence"],
                "verdict": v["verdict"],
                "reasoning": v["reason"],
                "flags": v["flags"],
                "recommendation": v["recommendation"],
            },
            status="success",
            place_id=pid,
        )

        if not args.apply:
            forced_note = " (FORZADO desde %s)" % model_status if forced_reason else ""
            logger.info(
                "[dry-run] %s: approved @ %s -> %s @ %s%s",
                place.get("name"),
                _fmt_conf(place.get("validation_confidence")),
                new_status,
                _fmt_conf(v["confidence"]),
                forced_note,
            )
        if i % 25 == 0:
            logger.info("... %d / %d", i, len(targets))

    duration_s = time.monotonic() - started

    summary = {
        "apply": args.apply,
        "threshold": args.threshold,
        "below_threshold": len(fetched),
        "protected_skipped": len(protected),
        "seen": len(targets),
        "stayed_approved": len(buckets["approved"]),
        "to_needs_review": len(buckets["needs_review"]),
        "to_discarded": len(buckets["discarded"]),
        "forced_needs_review": sum(
            1 for b in buckets.values() for r in b if r.get("forced")
        ),
        "errors": len(errors),
        "safety_level_changed": sum(
            1 for r in buckets["approved"] if r["old_safety"] != r["new_safety"]
        ),
        "llm_calls": llm.calls,
        "cost_usd": round(llm.cost_usd(), 4),
        "duration_s": round(duration_s, 1),
    }
    db.insert_agent_log(
        "validator",
        "revalidate_retroactive_complete",
        summary,
        status="error" if errors else "success",
    )

    report = build_report(
        apply=args.apply,
        threshold=args.threshold,
        below_threshold=len(fetched),
        protected=protected,
        seen=len(targets),
        buckets=buckets,
        errors=errors,
        llm=llm,
        duration_s=duration_s,
        examples=args.examples,
    )

    # Persist BEFORE printing: a Windows console that can't encode the report's
    # accents / em-dashes must not lose the whole run to a UnicodeEncodeError.
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(report)
        logger.info("report written to %s", args.report)
    _safe_print("\n" + report)
    _safe_print("\nJSON summary: " + json.dumps(summary, ensure_ascii=False))

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
