"""Markers of a human decision on a place (CLAUDE.md "Manual Validator overrides").

A place whose ``validation_notes`` carries one of these was set by the admin from
knowledge the model cannot reproduce. Automatic re-evaluations must not erase that
record or overturn the admin's safety level on their own.

Exception: a ``CORRECCIÓN MANUAL`` header whose text is a pure *data* correction (a geography fix,
"not a business", a sample place) is not a decision about the place's safety and protects nothing —
see ``DATA_CORRECTION_PHRASES``.
"""

from __future__ import annotations

import unicodedata

MANUAL_OVERRIDE_MARKERS = (
    "override",           # "OVERRIDE MANUAL ...", "override del Validator"
    "aprobacion manual",  # "APROBACIÓN MANUAL (override del Validator)"
    "correccion manual",  # "CORRECCIÓN MANUAL ..." (label fixes; data-only ones are excluded below)
)

# A header line that starts with "CORRECCIÓN MANUAL" and contains one of these phrases is a DATA correction:
# it states where a place is or that it is not a business, never how safe it is, so it must not protect the
# place from the cap/flag pass or from a community report. The list is explicit and reviewed on purpose: any
# other CORRECCIÓN MANUAL (label corrections such as Los Leños / Dalbertt, discards with a reason, ...) keeps
# protecting. Each header line is judged on its own, so a data header on top of a safety header still
# protects. Only CORRECCIÓN MANUAL lines are releasable: OVERRIDE MANUAL / APROBACIÓN MANUAL always protect.
# A header that mixes a data phrase and a safety statement in ONE line would be released: write them apart.
DATA_CORRECTION_PHRASES = (
    "país/ciudad corregidos",
    "ciudad corregida",
    "lugar de ejemplo del seed",
    "no es un comercio",
    "fuera del alcance geográfico",
)


def _norm(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", (text or "").lower()) if not unicodedata.combining(c)
    )


_CORRECTION = "correccion manual"
_DATA_PHRASES_NORM = tuple(_norm(p) for p in DATA_CORRECTION_PHRASES)


def _is_data_correction_line(line: str) -> bool:
    return _CORRECTION in line and any(phrase in line for phrase in _DATA_PHRASES_NORM)


def manual_override_marker(notes: str | None) -> str | None:
    """The marker found in ``notes`` (accent/case-insensitive), or None.

    Header lines that are only a data correction (``DATA_CORRECTION_PHRASES``) are ignored first."""
    kept = "\n".join(
        line for line in _norm(notes or "").split("\n") if not _is_data_correction_line(line)
    )
    return next((m for m in MANUAL_OVERRIDE_MARKERS if m in kept), None)
