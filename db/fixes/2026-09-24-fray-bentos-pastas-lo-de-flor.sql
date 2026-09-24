-- Manual curation — "Pastas Lo de Flor" (Fray Bentos, UY), a community suggestion
-- (suggestions 25777f56-a333-4cb7-9834-7975ff05cb8e, 2026-09-23, address "JC 23"
-- — not geocodable) resolved by the admin (Santiago Sánchez) on 2026-09-24.
--
-- Small home-based business (homemade sin-TACC pasta, orders Mon-Thu, delivered
-- on Saturdays), Instagram-only, no Google Place. Labelled 100% gluten free by the
-- admin's own criterion, based on direct information about the business's kitchen.
-- That detail is deliberately NOT written down here or in the row's validation_notes:
-- places.validation_notes is publicly readable and the detail concerns a named third
-- party (see db/fixes/2026-09-24-lo-de-flor-note-privacy.sql).
--
-- Address per the admin: "Eugenio Guevara 128, Fray Bentos" (may be off by a
-- small house-number variation, admin-accepted). Google Geocoding API resolves
-- "Eugenio 128, Fray Bentos 65000" to Eugenio Guevara 128, ROOFTOP
-- (-33.1127619, -58.3011576); every misspelling of the street name resolves to
-- the same route. geocode_method='address_only', external_id=NULL (same shape as
-- the 2026-09-22 Ta Bacana / Caneladesayunos rows).
--
-- Same rules as CLAUDE.md "Manual Validator overrides — allowed, but never silent"
-- (second use on a brand-new row): inserted directly as status='approved' with no
-- Validator judgment, validation_notes says so explicitly, validation_confidence
-- stays NULL (never fabricated), verified stays false.
--
-- The originating suggestion is flipped new -> promoted and linked to the new
-- place, so the monthly SuggestionAgent never tries to geocode "JC 23".
--
-- Run: node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-24-fray-bentos-pastas-lo-de-flor.sql
-- Idempotent: the insert is guarded by NOT EXISTS (external_id is NULL, so the
-- (source, external_id) unique key cannot dedup it); the suggestion update
-- guards on status = 'new'.

with new_place as (
  insert into public.places
    (name, lat, lng, category, country, city, safety_level, status, address,
     source, external_id, geocode_method, social_url, validation_notes)
  select
    'Pastas Lo de Flor', -33.1127619, -58.3011576, 'shop', 'Uruguay', 'Fray Bentos',
    'gluten_free_100', 'approved',
    'Eugenio Guevara 128, 65000 Fray Bentos, Departamento de Río Negro, Uruguay',
    'user', null, 'address_only',
    'https://www.instagram.com/pastas_lodeflor/',
    'APROBACIÓN MANUAL (2026-09-24, Santiago Sánchez): agregado y aprobado directamente por el administrador, sin evaluación del Validator. Emprendimiento casero de pastas sin TACC en Fray Bentos (Instagram @pastas_lodeflor: "Pastas caseras sin TACC — pedidos de lunes a jueves, se entregan los sábados"; trabaja por encargo). Sugerido por la comunidad. Etiqueta 100% sin gluten por criterio del administrador, con información directa sobre la cocina del emprendimiento (el detalle no se publica por privacidad). Dirección informada por el administrador: Eugenio Guevara 128 (el número puede tener una pequeña variación). Sin ficha de Google Place: coordenadas por Google Geocoding API a nivel de puerta (ROOFTOP), geocode_method address_only. validation_confidence se deja en null (no hay puntaje real del Validator); verified sigue en false.'
  where not exists (
    select 1 from public.places
    where name = 'Pastas Lo de Flor' and city = 'Fray Bentos' and country = 'Uruguay'
  )
  returning id
)
update public.suggestions
set status = 'promoted',
    promoted_place_id = (select id from new_place)
where id = '25777f56-a333-4cb7-9834-7975ff05cb8e'
  and status = 'new'
  and exists (select 1 from new_place);
