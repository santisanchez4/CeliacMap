-- Manual curation — Dispensario (cafetería), Fray Bentos, reported directly by Santiago
-- Sánchez (2026-09-24), not yet discovered by any agent.
--
-- Same documented path as db/fixes/2026-09-22-fray-bentos-ta-bacana-canela.sql (CLAUDE.md, "Manual
-- Validator overrides — allowed, but never silent"): the admin asked for it to be visible on the
-- public map, so it is inserted directly as status='approved' — a manual override on first insert,
-- not a Validator verdict. validation_notes says so explicitly, validation_confidence stays NULL
-- (never fabricated to look like a real score) and verified stays false. It is never touched by the
-- Validator (status is a terminal 'approved', not 'pending').
--
-- Unlike Ta Bacana / Caneladesayunos, this business DOES have a Google Place listing ("Dispensario
-- Espresso Bar", 18 de Julio 1446), found with Find Place and confirmed to be the same business by
-- three independent matches against the Instagram bio: address, phone (098 715 659) and hours
-- (Tuesday to Sunday 16:00-20:00, Monday closed). So the row is anchored to it: real coordinates
-- (Geocoding + Place geometry, ROOFTOP), geocode_method='find_place', and the Google place_id as
-- external_id — which is what stops the monthly Search agent from inserting the same place again as
-- a pending "Dispensario Espresso Bar" (place_exists_by_external_id). rating / user_ratings_total /
-- opening_hours are the values Google returned on 2026-09-24, stored the way the agents store them
-- (the Updater refreshes them for rows that have an external_id).
--
-- safety_level = 'options_available' ("Tiene opciones sin TACC") is the admin's own direct
-- assessment ("opciones para celíacos"); it is NOT declared a 100% gluten-free venue.
--
-- Run: node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-24-fray-bentos-dispensario.sql
-- Idempotent: ON CONFLICT (source, external_id) DO NOTHING (a real dedup key here: external_id is set).

insert into public.places
  (name, lat, lng, category, country, city, safety_level, status, address,
   source, external_id, geocode_method, social_url, phone, opening_hours,
   rating, user_ratings_total, validation_notes)
values
  ('Dispensario', -33.1195818, -58.3086072, 'cafe', 'Uruguay', 'Fray Bentos',
   'options_available', 'approved',
   '18 de Julio 1446, 65000 Fray Bentos, Departamento de Río Negro, Uruguay',
   'manual', 'ChIJYy4Ik-pNpZURecUGibFharQ', 'find_place',
   'https://www.instagram.com/dispensario.1916/', '098 715 659',
   '["lunes: Cerrado", "martes: 16:00–20:00", "miércoles: 16:00–20:00", "jueves: 16:00–20:00", "viernes: 16:00–20:00", "sábado: 16:00–20:00", "domingo: 16:00–20:00"]'::jsonb,
   4.8, 47,
   'APROBACIÓN MANUAL (2026-09-24, Santiago Sánchez): agregado y aprobado directamente por el administrador, sin evaluación del Validator. Cafetería (Instagram "Dispensario - Cafetería") en 18 de Julio 1446, Villa Fray Bentos, Río Negro — tiene opciones para celíacos ("Tiene opciones sin TACC") según validación directa del administrador; no se declara Espacio 100% sin gluten. Instagram @dispensario.1916, tel 098 715 659 (+598 98 715 659), martes a domingo de 16:00 a 20:00. Coincide con la ficha de Google "Dispensario Espresso Bar" (mismo domicilio, teléfono y horario), cuyo place_id se usa como external_id para que el agente de Search no lo duplique. validation_confidence se deja en null (no hay puntaje real del Validator); verified sigue en false.')
on conflict (source, external_id) do nothing
returning id, name, category, safety_level, status, address;
