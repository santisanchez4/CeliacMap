"""What counts as "a human decision on this place" — and what is only a data correction.

A ``CORRECCIÓN MANUAL`` header protects a place (the cap/flag pass skips it, a report cannot overturn its
admin level) UNLESS its text is one of the explicit data-correction phrases (geography, not-a-business,
sample place). Every header is judged on its own: a data header on top of a safety header still protects.
OVERRIDE MANUAL and APROBACIÓN MANUAL always protect, exactly as before.
"""
from __future__ import annotations

import pytest

from agents.manual_overrides import DATA_CORRECTION_PHRASES, manual_override_marker

# Production notes (2026-09-24), verbatim: the admin's safety-label correction + the override it replaced.
LOS_LENOS = (
    "CORRECCIÓN MANUAL (2026-09-24, Santiago Sánchez): el administrador, con conocimiento personal directo del lugar, "
    "confirma que Los Leños (Montevideo) es un establecimiento 100% sin gluten; se corrige safety_level de "
    "options_available a gluten_free_100. validation_confidence se mantiene sin cambios; verified sigue en false.\n\n"
    "--- Nota anterior: OVERRIDE MANUAL (2026-09-05): Aprobado manualmente por Santiago Sánchez (administrador de la "
    "plataforma) en base a conocimiento personal directo del lugar — lo visitó y confirma que ofrece opciones sin "
    "gluten. El Validator no tiene forma de evaluar contenido de Instagram ni conocimiento personal, solo evidencia "
    "pública textual; por eso lo había dejado en needs_review pese a que el lugar es real y seguro. La "
    "validation_confidence se mantiene sin modificar para reflejar la evidencia pública real, no la certeza personal "
    "del administrador.\n"
    "--- Nota del Validator (needs_review, confidence 0.5): El lugar aparece como resultado de Google Places pero no se "
    "cuenta con evidencia explícita de que ofrezca opciones sin TACC, menciones de certificación o protocolo "
    "anti-contaminación cruzada. El nombre 'Los Leños' sugiere un restaurante de carnes o parrilla, categoría donde "
    "puede haber opciones naturalmente sin gluten, pero sin confirmación directa no es posible validar su seguridad "
    "para celíacos. Se requiere revisión humana para confirmar si el establecimiento ofrece menú sin TACC o cuenta "
    "con protocolo adecuado."
)
DALBERTT = (
    "CORRECCIÓN MANUAL (2026-09-24, Santiago Sánchez): el administrador, con conocimiento personal directo del lugar, "
    "confirma que Dalbertt (Montevideo) es un establecimiento 100% sin gluten; se corrige safety_level de "
    "options_available a gluten_free_100. validation_confidence se mantiene sin cambios; verified sigue en false.\n\n"
    "--- Nota anterior: OVERRIDE MANUAL (2026-09-05): Aprobado manualmente por Santiago Sánchez (administrador de la "
    "plataforma) en base a conocimiento personal directo del lugar — lo visitó y confirma que ofrece opciones sin "
    "gluten. El Validator no tiene forma de evaluar contenido de Instagram ni conocimiento personal, solo evidencia "
    "pública textual; por eso lo había dejado en needs_review pese a que el lugar es real y seguro. La "
    "validation_confidence se mantiene sin modificar para reflejar la evidencia pública real, no la certeza personal "
    "del administrador.\n"
    "--- Nota del Validator (needs_review, confidence 0.5): No se encontró evidencia explícita de opciones sin TACC, "
    "certificación celíaca ni protocolo anti-contaminación cruzada para este establecimiento. La fuente es Google "
    "Places pero no se aportaron reseñas ni descripción del menú que confirmen opciones aptas para celíacos. Se "
    "requiere verificación humana directa antes de recomendar el lugar."
)
SAFETY_HEADER_ONLY = LOS_LENOS.split("\n\n")[0]  # the label correction alone, without the embedded OVERRIDE

VALIDATOR_TEXT = "El nombre sugiere sin gluten, pero no hay evidencia explícita de exclusividad."

# The data-correction headers written on 2026-09-25 (literal), and the Brazil one of 2026-09-01.
DATA_HEADERS = [
    "CORRECCIÓN MANUAL 2026-09-25: país/ciudad corregidos según la dirección.",
    "CORRECCIÓN MANUAL 2026-09-25: ciudad corregida según la dirección.",
    "CORRECCIÓN MANUAL 2026-09-25: lugar de ejemplo del seed, no es un negocio real.",
    "CORRECCIÓN MANUAL 2026-09-25: no es un comercio (es un evento o una organización), no corresponde a este mapa; descartado.",
    "CORRECCIÓN MANUAL 2026-09-25: este lugar está en Chile, fuera del alcance geográfico del proyecto (solo "
    "Uruguay/Argentina). Se mantiene en needs_review por exclusión editorial, no por la calidad del negocio.",
    "CORRECCIÓN MANUAL: este lugar está en Brasil, fuera del alcance geográfico del proyecto (solo Uruguay/Argentina). "
    "Movido a needs_review para exclusión editorial, no por problema de calidad del negocio en sí.",
]


def test_the_data_correction_phrases_are_an_explicit_reviewed_list():
    assert DATA_CORRECTION_PHRASES == (
        "país/ciudad corregidos",
        "ciudad corregida",
        "lugar de ejemplo del seed",
        "no es un comercio",
        "fuera del alcance geográfico",
    )


@pytest.mark.parametrize("header", DATA_HEADERS)
def test_a_row_with_only_a_data_correction_header_is_not_protected(header):
    assert manual_override_marker(f"{header}\n\n{VALIDATOR_TEXT}") is None
    assert manual_override_marker(header) is None


def test_data_headers_are_matched_without_regard_to_case_or_accents():
    assert manual_override_marker("correccion manual 2026-09-25: PAIS/CIUDAD CORREGIDOS segun la direccion.") is None


def test_several_data_headers_on_one_row_still_protect_nothing():
    notes = "\n\n".join([DATA_HEADERS[3], DATA_HEADERS[0], VALIDATOR_TEXT])  # discarded + country fixed (Celi events)
    assert manual_override_marker(notes) is None


def test_a_data_header_on_top_of_a_safety_header_still_protects():
    notes = f"{DATA_HEADERS[0]}\n\n{SAFETY_HEADER_ONLY}\n\n{VALIDATOR_TEXT}"
    assert manual_override_marker(notes) == "correccion manual"


@pytest.mark.parametrize("underneath", [
    "APROBACIÓN MANUAL (2026-09-05, review_queue): conozco el local. El Validator había dejado: needs_review @ 0.52.",
    "OVERRIDE MANUAL (2026-09-05): aprobado por el administrador.",
])
def test_a_data_header_on_top_of_an_approval_or_override_still_protects(underneath):
    assert manual_override_marker(f"{DATA_HEADERS[0]}\n\n{underneath}") is not None


@pytest.mark.parametrize("notes", [LOS_LENOS, DALBERTT])
def test_the_real_label_corrections_of_los_lenos_and_dalbertt_stay_protected(notes):
    assert manual_override_marker(notes) is not None
    # ... also with a data header prepended (the fix of 2026-09-25 could have touched them)
    assert manual_override_marker(f"{DATA_HEADERS[0]}\n\n{notes}") is not None


@pytest.mark.parametrize("notes", [LOS_LENOS, DALBERTT])
def test_the_label_correction_header_protects_on_its_own_without_the_embedded_override(notes):
    header = notes.split("\n\n")[0]
    assert "OVERRIDE" not in header.upper()
    assert manual_override_marker(header) == "correccion manual"


@pytest.mark.parametrize("notes, expected", [
    ("OVERRIDE MANUAL (2026-09-05): aprobado por Santiago ...", "override"),
    ("APROBACIÓN MANUAL (override del Validator): conocimiento directo", "override"),
    ("APROBACIÓN MANUAL (2026-09-05, review_queue): lo conozco.", "aprobacion manual"),
    # a data phrase next to one of these two never releases the row: only CORRECCIÓN MANUAL headers are releasable
    ("OVERRIDE MANUAL: no es un comercio, pero el dueño confirma opciones.", "override"),
    ("APROBACIÓN MANUAL: ciudad corregida y además lo conozco.", "aprobacion manual"),
])
def test_override_and_approval_markers_protect_exactly_as_before(notes, expected):
    assert manual_override_marker(notes) == expected


@pytest.mark.parametrize("notes", [
    "CORRECCIÓN MANUAL 2026-09-02: city mislabelled (Paraná -> Santa Fe).",
    "CORRECCIÓN MANUAL 2026-09-07: falso positivo, es un centro educativo y no un negocio de comida.",
    "CORRECCIÓN MANUAL 2026-09-24: cocina exclusivamente sin gluten (admin).",
    "CORRECCIÓN MANUAL: cualquier otro texto sigue protegiendo.",
])
def test_any_other_manual_correction_keeps_protecting(notes):
    assert manual_override_marker(notes) == "correccion manual"


def test_a_place_without_notes_or_markers_is_not_protected():
    assert manual_override_marker(None) is None
    assert manual_override_marker("") is None
    assert manual_override_marker(VALIDATOR_TEXT) is None
