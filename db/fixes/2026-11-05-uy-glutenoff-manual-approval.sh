#!/usr/bin/env bash
# APLICADO en producción el 2026-11-05 (dry-run primero, después con --apply). Registro de auditoría.
# Sin argumentos es un DRY RUN; con --apply escribe. validation_confidence y verified no se tocan.
set -euo pipefail
# GLUTENOFF (Punta del Este): 100% por conocimiento directo del admin. La evidencia va en 2026-11-05-uy-glutenoff-admin-evidence.sql.
.venv/Scripts/python.exe -m scripts.review_queue --approve a6a15ba0-eb8c-4579-8fba-7dd3a67e68ec --level 100 "$@" --note "El administrador confirma, por conocimiento directo del lugar, que GLUTENOFF (Punta del Este) es un establecimiento 100% sin gluten; la búsqueda de evidencia del 2026-11-05 solo había encontrado una cita de una línea de productos («Apto celiaco») en su Instagram"
