#!/usr/bin/env bash
# Aprobaciones manuales del admin (Santiago Sánchez, 2026-10-13) sobre tres filas de la capa IM Montevideo - Locales_Gluten_Free.
# Sin argumentos es un DRY RUN; con --apply escribe en producción. La evidencia va antes, con db/fixes/2026-10-13-imm-admin-evidence.sql.
set -euo pipefail
PY=".venv/Scripts/python -X utf8 -m scripts.review_queue"

$PY --approve 7362c23b-b02d-4930-9dba-8e00a9fc6bf6 --level 100 "$@" --note "Decisión manual de Santiago Sánchez (admin): revisó redes y web del local (https://www.cooperativahelix.com.uy/index.html, WhatsApp 092 410 428) y lo aprueba como 100% libre de gluten. Figura en IM Montevideo - Locales_Gluten_Free (habilitación 28/05/2019 a 28/05/2024, vencida en la fuente capturada el 2026-10-13)"

$PY --approve 61fa7e8b-3366-4724-b09c-fb7150e35653 --level 100 "$@" --note "Decisión manual de Santiago Sánchez (admin): revisó el Instagram @fernilanduy (bio: \"Somos una empresa dedicada a alimentos sin gluten. Industria Uruguaya. Aptos celiacos. Aptos Veganos\"), tel 092921922 y el sitio www.ferniland.com.uy, y lo aprueba como 100% libre de gluten. Figura en IM Montevideo - Locales_Gluten_Free (habilitación 21/10/2022 a 21/10/2027, vigente en la fuente capturada el 2026-10-13)"

$PY --approve dbc2db5e-3078-44a3-9e03-f0cbcf19d07d --level 100 "$@" --note "Decisión manual de Santiago Sánchez (admin): revisó el Instagram @megusta_uy (bio: \"Restaurante - Comida Saludable GLUTEN FREE - Productos congelados - Servicio de catering\"), tel +598 2402 77 54 y +598 092056917, y lo aprueba como 100% libre de gluten. Figura en IM Montevideo - Locales_Gluten_Free (habilitación 04/08/2023 a 04/08/2028, vigente en la fuente capturada el 2026-10-13)"
