-- Manual curation — two Fray Bentos businesses reported directly by Santiago
-- Sánchez (2026-09-22), not yet discovered by any agent.
--
-- DELIBERATE DEVIATION from this project's usual "fresh insert -> pending,
-- let the Validator judge" convention: Santiago explicitly asked for these to
-- be visible on the public map immediately, so both are inserted directly as
-- status='approved' — a manual override on first insert, not a Validator
-- verdict. This follows the same documented path as CLAUDE.md's "Manual
-- Validator overrides — allowed, but never silent" (until now only ever used
-- to correct an EXISTING Validator verdict, e.g. ACELU / Bienestar Gluten
-- Free — this is its first use on a brand-new row): validation_notes states
-- explicitly that this is an admin override with no Validator judgment behind
-- it, validation_confidence is left NULL (never fabricated to look like a
-- real score), and verified stays false.
--
-- Neither business has a Google Place listing, so there is no Find Place
-- match to anchor to (geocode_method='address_only', external_id=NULL).
-- Coordinates come from Uruguay's official cadastral address-point dataset
-- (AGESIC, distributed via OpenStreetMap: ref:AGESIC tag, EWKB point in
-- EPSG:32721 / UTM 21S, converted to WGS84 here with pyproj):
--   * Caneladesayunos (18 de Julio 1125): EXACT house-number match in the
--     cadastre -> -33.1153995, -58.3133631.
--   * Ta Bacana (18 de Julio 1400): house number 1400 itself isn't in the
--     cadastre; linearly interpolated between its neighbours 1394
--     (-33.1190672, -58.3092896) and 1404 (-33.1191883, -58.3090970) at
--     weight 0.6 -> -33.1191399, -58.3091740. Accurate to a few meters, not
--     Google-Place precision.
--
-- safety_level = 'options_available' ("Tiene opciones sin TACC") is
-- Santiago's own direct assessment of both businesses, not a Validator
-- verdict — this row is never touched by the Validator (status is already a
-- terminal 'approved', not 'pending'), and validation_confidence stays NULL
-- so nothing looks like a real confidence score that was never computed.
--
-- Run: node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-22-fray-bentos-ta-bacana-canela.sql
-- Idempotent: ON CONFLICT (source, external_id) DO NOTHING (both external_id
-- are NULL, so this is a no-op safeguard, not a real dedup key here).

insert into public.places
  (name, lat, lng, category, country, city, safety_level, status, address,
   source, external_id, geocode_method, social_url, phone, validation_notes)
values
  ('Ta Bacana Resto Bar', -33.1191399, -58.3091740, 'restaurant', 'Uruguay', 'Fray Bentos',
   'options_available', 'approved',
   '18 de Julio 1400, 65000 Fray Bentos, Departamento de Río Negro, Uruguay',
   'manual', null, 'address_only',
   'https://www.instagram.com/ta_bacana/', '099 561 693',
   'APROBACIÓN MANUAL (2026-09-22, Santiago Sánchez): agregado y aprobado directamente por el administrador, sin evaluación del Validator. Resto bar en 18 de Julio 1400, Villa Fray Bentos, Río Negro — tiene opciones sin TACC según conocimiento directo del administrador. Instagram @ta_bacana, tel 099 561 693 (+598 99 561 693). Sin ficha de Google Place: coordenadas geocodificadas por interpolación del catastro oficial (AGESIC/OpenStreetMap) entre los números de puerta 1394 y 1404 de 18 de Julio, ya que el 1400 exacto no está catastrado individualmente. validation_confidence se deja en null (no hay puntaje real del Validator); verified sigue en false.'),
  ('Caneladesayunos', -33.1153995, -58.3133631, 'cafe', 'Uruguay', 'Fray Bentos',
   'options_available', 'approved',
   '18 de Julio 1125, 65000 Fray Bentos, Departamento de Río Negro, Uruguay',
   'manual', null, 'address_only',
   'https://www.instagram.com/caneladesayunosfb/', '099 570 707',
   'APROBACIÓN MANUAL (2026-09-22, Santiago Sánchez): agregado y aprobado directamente por el administrador, sin evaluación del Validator. Cafetería de desayunos en 18 de Julio 1125, Villa Fray Bentos, Río Negro — tiene opciones sin TACC según conocimiento directo del administrador. Horario: lunes a viernes 7:30-12:00 y 16:30-19:30hs, sábados y domingos cerrado. Instagram @caneladesayunosfb, cel. 099 570 707. Sin ficha de Google Place: coordenadas del catastro oficial (AGESIC/OpenStreetMap), número de puerta 1125 exacto. validation_confidence se deja en null (no hay puntaje real del Validator); verified sigue en false.')
on conflict (source, external_id) do nothing;
