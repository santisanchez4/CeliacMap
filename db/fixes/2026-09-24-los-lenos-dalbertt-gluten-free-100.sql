-- Manual safety_level correction — Los Leños (Montevideo) and Dalbertt.
--
-- Both were approved manually on 2026-09-05 (OVERRIDE MANUAL) as
-- safety_level='options_available', on the admin's direct knowledge that they
-- "offer gluten-free options". On 2026-09-24 the admin (Santiago Sánchez, who has
-- first-hand knowledge of both businesses) clarified that both are 100% gluten
-- free establishments, so the public label must be "Espacio 100% sin gluten"
-- (gluten_free_100), not "Tiene opciones sin TACC".
--
-- Same rules as CLAUDE.md "Manual Validator overrides — allowed, but never silent":
--   * validation_notes: a CORRECCIÓN MANUAL header PREPENDED; the previous note
--     (the 2026-09-05 override + the Validator's own reasoning) kept verbatim below.
--   * validation_confidence: UNCHANGED (0.5 — reflects the real public evidence).
--   * status: UNCHANGED (already approved). verified: UNCHANGED (stays false).
--
-- Café Ramona - Centro, Café Ramona - WTC and La Panadería de Ramona are already
-- gluten_free_100 (overrides of 2026-09-07), so they are not touched here.
--
-- Run: node_modules/.bin/supabase db query --linked --file <this file>
-- Idempotent: each statement guards on `and safety_level = 'options_available'`.

-- Los Leños (Montevideo, S. José 909)
update public.places set
  safety_level = 'gluten_free_100',
  validation_notes =
    'CORRECCIÓN MANUAL (2026-09-24, Santiago Sánchez): el administrador, con conocimiento personal directo del lugar, confirma que Los Leños (Montevideo) es un establecimiento 100% sin gluten; se corrige safety_level de options_available a gluten_free_100. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota anterior: '
    || validation_notes
where id = '1079510f-a973-49a8-8efa-185d511dc647' and safety_level = 'options_available';

-- Dalbertt (Montevideo, Mercedes 799)
update public.places set
  safety_level = 'gluten_free_100',
  validation_notes =
    'CORRECCIÓN MANUAL (2026-09-24, Santiago Sánchez): el administrador, con conocimiento personal directo del lugar, confirma que Dalbertt (Montevideo) es un establecimiento 100% sin gluten; se corrige safety_level de options_available a gluten_free_100. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota anterior: '
    || validation_notes
where id = 'c6f1620c-8d9f-4c78-b187-4a6ad0b99e04' and safety_level = 'options_available';
