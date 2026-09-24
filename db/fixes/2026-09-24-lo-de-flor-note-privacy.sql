-- Privacy correction — "Pastas Lo de Flor" (Fray Bentos), 2026-09-24.
--
-- The manual-approval note written earlier the same day for this business stated a named third party's
-- health condition. places.validation_notes is readable through the public
-- REST API (anon has SELECT on public.places and RLS publishes every approved row), so that sentence was
-- public. Replace ONLY that sentence with a neutral one; the rest of the note (address, source, the fact
-- that this is an admin override with no Validator judgment) is kept. validation_confidence, status,
-- safety_level and verified are untouched.
--
-- Idempotent: after the first run the pattern no longer matches, so re-running changes nothing.
-- Run: node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-24-lo-de-flor-note-privacy.sql
update public.places
set validation_notes = regexp_replace(
      validation_notes,
      'Sugerido por la comunidad.*?100% sin gluten\.',
      'Sugerido por la comunidad. Etiqueta 100% sin gluten por criterio del administrador, con información directa sobre la cocina del emprendimiento (el detalle no se publica por privacidad).'
    )
where name = 'Pastas Lo de Flor'
  and city = 'Fray Bentos'
  and country = 'Uruguay'
  and validation_notes ~ 'Sugerido por la comunidad.*?100% sin gluten\.';
