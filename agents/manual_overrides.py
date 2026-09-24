"""Markers of a human decision on a place (CLAUDE.md "Manual Validator overrides").

A place whose ``validation_notes`` carries one of these was set by the admin from
knowledge the model cannot reproduce. Automatic re-evaluations must not erase that
record or overturn the admin's safety level on their own.
"""

from __future__ import annotations

import unicodedata

MANUAL_OVERRIDE_MARKERS = (
    "override",           # "OVERRIDE MANUAL ...", "override del Validator"
    "aprobacion manual",  # "APROBACIÓN MANUAL (override del Validator)"
    "correccion manual",  # "CORRECCIÓN MANUAL ..." (label / geography fixes)
)


def _norm(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", (text or "").lower()) if not unicodedata.combining(c)
    )


def manual_override_marker(notes: str | None) -> str | None:
    """The marker found in ``notes`` (accent/case-insensitive), or None."""
    normalized = _norm(notes or "")
    return next((m for m in MANUAL_OVERRIDE_MARKERS if m in normalized), None)
