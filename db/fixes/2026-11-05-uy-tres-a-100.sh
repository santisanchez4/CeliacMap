#!/usr/bin/env bash
# APLICADO en producción el 2026-11-05 (dry-run primero, después con --apply). Registro de auditoría.
# Sin argumentos es un DRY RUN; con --apply escribe. validation_confidence y verified no se tocan.
set -euo pipefail
# EMPATIA, Gluten Out y Mi espacio sin TACC: 100% por averiguación directa del admin. Paso 2 de 2; antes va 2026-11-05-uy-tres-a-100-evidencia.sql.
.venv/Scripts/python.exe -m scripts.review_queue --approve 7212e339-5011-484e-92df-19e4caf4ebf0 --level 100 "$@" --note "El administrador averiguó directamente (2026-11-05) y confirma que es un establecimiento 100% sin gluten"
.venv/Scripts/python.exe -m scripts.review_queue --approve a6493fc7-279c-4e30-81d3-d79a7e89cc9c --level 100 "$@" --note "El administrador averiguó directamente (2026-11-05) y confirma que es un establecimiento 100% sin gluten"
.venv/Scripts/python.exe -m scripts.review_queue --approve 0274deb6-ba10-43fc-b35c-411e871d7505 --level 100 "$@" --note "El administrador averiguó directamente (2026-11-05) y confirma que es un establecimiento 100% sin gluten"
