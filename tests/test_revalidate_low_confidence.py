"""Unit tests for the retroactive re-validation script's pure helpers."""

from __future__ import annotations

import pytest

from scripts.revalidate_low_confidence import (
    FORCED_NEEDS_REVIEW,
    MeteredLLMClient,
    compose_notes,
    protected_marker,
)


def test_forced_needs_review_covers_enharinate():
    # The dry-run's only 'approved' — model approved it on parametric knowledge,
    # not prompt evidence. Must be held for a human on --apply.
    assert "ff4da9ce-2635-43e0-9612-2f4257cade55" in FORCED_NEEDS_REVIEW
    reason = FORCED_NEEDS_REVIEW["ff4da9ce-2635-43e0-9612-2f4257cade55"]
    assert "conocimiento" in reason.lower() and "needs_review" in reason


def test_compose_notes_prepends_forced_reason():
    notes = compose_notes(
        {"validation_confidence": 0.45, "created_at": "2026-06-05", "validation_notes": "vieja"},
        {"verdict": "approved", "status": "needs_review", "confidence": 0.87, "reason": "x"},
        forced_reason="AJUSTE MANUAL: forzado a needs_review.",
    )
    assert notes.startswith("AJUSTE MANUAL: forzado a needs_review.")
    # header still names what the model actually said
    assert "veredicto del modelo 'approved'" in notes


@pytest.mark.parametrize(
    "notes, expected",
    [
        ("OVERRIDE MANUAL (2026-09-05): aprobado por Santiago ...", "override"),
        ("APROBACIÓN MANUAL (override del Validator): conocimiento directo", "override"),
        ("CORRECCIÓN MANUAL 2026-09-02: city mislabelled", "correccion manual"),
        ("RE-VALIDACIÓN RETROACTIVA (2026-09-06): fila re-evaluada ...", "validacion retroactiva"),
        ("El lugar aparece en Google Places pero no hay evidencia ...", None),
        ("", None),
        (None, None),
    ],
)
def test_protected_marker_detection(notes, expected):
    assert protected_marker({"validation_notes": notes}) == expected


def test_compose_notes_prepends_traceable_header_and_keeps_original():
    place = {
        "validation_confidence": 0.45,
        "created_at": "2026-06-05T16:03:36.918422+00:00",
        "validation_notes": "Nota vieja del rubric binario.",
    }
    verdict = {
        "verdict": "needs_review",
        "status": "needs_review",
        "confidence": 0.52,
        "reason": "Evidencia parcial.",
    }

    notes = compose_notes(place, verdict)

    assert notes.startswith("RE-VALIDACIÓN RETROACTIVA (")
    assert "validation_confidence 0.45" in notes
    assert "2026-06-05" in notes
    assert "nunca volvió a status='pending'" in notes
    assert "status 'needs_review'" in notes
    assert "veredicto del modelo 'needs_review'" in notes
    assert "Razonamiento nuevo del Validator: Evidencia parcial." in notes
    assert "Nota original (rubric binario): Nota vieja del rubric binario." in notes


def test_compose_notes_handles_missing_original_note():
    notes = compose_notes(
        {"validation_confidence": 0.3, "created_at": "2026-06-01", "validation_notes": None},
        {"verdict": "rejected", "status": "discarded", "confidence": 0.2, "reason": None},
    )
    assert "Nota original" not in notes
    assert "Razonamiento nuevo" not in notes
    assert "RE-VALIDACIÓN RETROACTIVA" in notes


def test_metered_client_cost_is_zero_before_any_call():
    client = MeteredLLMClient("test-key", "claude-sonnet-4-6")
    assert client.calls == 0
    assert client.cost_usd() == 0.0


def test_metered_client_cost_uses_sonnet_rates():
    client = MeteredLLMClient("test-key", "claude-sonnet-4-6")
    client.usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
        "cache_creation_input_tokens": 1_000_000,
    }
    # 3.00 + 15.00 + 0.30 + 3.75
    assert round(client.cost_usd(), 2) == 22.05
