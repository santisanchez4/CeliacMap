#!/usr/bin/env bash
# Aprobación manual del admin (Santiago Sánchez, 2026-10-13) de Alárabi Cocina Inclusiva como 100% libre de gluten.
# Paso 2 de 2: antes va la evidencia, con db/fixes/2026-10-13-alarabi-admin-evidence.sql.
# Sin argumentos es un DRY RUN; con --apply escribe en producción. Las notas anteriores (OVERRIDE MANUAL + Validator) quedan debajo;
# validation_confidence y verified no se tocan.
set -euo pipefail

.venv/Scripts/python -X utf8 -m scripts.review_queue --approve 09713c52-85d5-41ab-b746-6c1440996a48 --level 100 "$@" --note "Decisión manual de Santiago Sánchez (admin): revisó su Instagram (@alarabi__glutenfree, bio: «Alarabi | Disfrutá sin preocupaciones 🌾 - Restaurante - Lunes a Domingo - Montevideo, Uruguay - Zona Cordón, Colonia 1779») y lo aprueba como 100% libre de gluten. Corroboran: el nombre de la cuenta, la dirección coincidente con IM Montevideo - Locales_Gluten_Free (habilitación vencida el 30/11/2025 en la fuente capturada el 2026-10-13) y el blog pajaritosviajeros.com. Quedan registradas, sin refutar, dos reseñas negativas de Google sobre contaminación (ver OVERRIDE MANUAL de abajo)"
