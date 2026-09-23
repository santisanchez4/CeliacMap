-- Manual correction — ACELU (Asociación Celíaca del Uruguay, Montevideo):
-- safety_level celiac_friendly -> gluten_free_100.
--
-- The Validator judged ACELU from name + address + guessed category only and
-- returned approved @ celiac_friendly (confidence 0.72, June 2026 binary-rubric
-- era), so the public map showed "Tiene opciones sin TACC". ACELU is the
-- national celiac patient association of Uruguay, and although it is an
-- organization it sells exclusively 100% gluten-free products (direct
-- knowledge of the platform admin) — which is exactly what gluten_free_100
-- means. The public label for gluten_free_100 is "Espacio 100% sin gluten"
-- (see CLAUDE.md "Map explorer — two public safety labels").
--
-- Documented manual-override path (CLAUDE.md "Manual Validator overrides —
-- allowed, but never silent"):
--   * validation_notes: CORRECCIÓN MANUAL header PREPENDED; the Validator's own
--     text kept verbatim below it.
--   * validation_confidence: UNCHANGED (0.72 — never inflated to match).
--   * verified: UNCHANGED (stays false).
--   * status: UNCHANGED (already approved).
--
-- Run: node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-21-acelu-gluten-free-100.sql
-- Idempotent: guarded on `safety_level = 'celiac_friendly'`, so a second run
-- matches 0 rows and does not stack a second header.

update public.places set
  safety_level = 'gluten_free_100',
  validation_notes =
    'CORRECCIÓN MANUAL (2026-09-21, Santiago Sánchez): safety_level cambiado de celiac_friendly a gluten_free_100 por conocimiento directo del administrador. ACELU es la Asociación Celíaca del Uruguay y, aunque es una organización, vende productos 100% sin gluten (venta exclusiva de productos sin gluten, sin productos con gluten en el local). El Validator solo recibe nombre + dirección + categoría estimada, por eso lo dejó en celiac_friendly — es una limitación de evidencia del pipeline, no una señal de riesgo. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (approved @ celiac_friendly, confidence 0.72): '
    || validation_notes
where id = 'd6d5375b-7ceb-44dc-9c3a-dac847f4a670' and safety_level = 'celiac_friendly';
