-- Manual place — Rikuras Sin Gluten El Pinar (Canelones): a second branch of the brand of Rikuras Sin Gluten (Malvín, Montevideo).
--
-- Data: the business card (Perez Butler esquina Santa Paula, El Pinar; tel 095 714 329; https://rikurassingluten.pidedirecto.uy/) and the admin's own check.
-- Following the manual-place rule (CLAUDE.md): Find Place on name + city FIRST, on 2026-09-27. Google has its OWN listing for this branch:
--   place_id ChIJH05jRj-Ln5URB3xgh46-Mck, "Rikuras Sin Gluten", Guillermo Perez Butler Manzana 249 Solar 2, 15800 Ciudad de la Costa, Canelones,
--   OPERATIONAL, (-34.8043848, -55.9063936); the corner geocoded independently lands ~70 m away (Santa Paula & Guillermo Perez Butler). It is NOT the
--   Malvín listing (ChIJ64hoV1KHn5URvCEqq2PDcI4): the external_id is the branch's own, so the two rows can never collide.
-- Decisions to review:
--   * city = 'Ciudad de la Costa': Google's locality for 15800 and the convention of the other rows there (Celilife, Pagana). "El Pinar" is in the name and
--     in the address text, so it is found by name. Change the city here if you prefer 'El Pinar'.
--   * source = 'manual' with Google's place_id as external_id, as for Café Ramona - WTC. The monthly Search agent dedups only on (source, external_id): it
--     could later insert the same Google place as a 'google_places' pending row. After a monthly run, look for two rows with this external_id.
--   * safety_level = 'gluten_free_100', the same as Malvín; status approved; validation_confidence NULL and verified false (a person decided, not the
--     Validator). The note repeats the evidence of Malvín's approval.
--
-- Run (one transaction, all-or-nothing; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-27-rikuras-el-pinar.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.
-- Idempotent: the INSERT is guarded by `where not exists`, and the assertion demands exactly one new row.

begin;

create temp table _snap on commit drop as
select id, md5(to_jsonb(p)::text) as h from public.places p;

insert into public.places
  (name, lat, lng, category, country, city, region, safety_level, status, address, source, external_id, geocode_method,
   phone, website, validation_confidence, verified, validation_notes)
select
  'Rikuras Sin Gluten El Pinar', -34.8043848, -55.9063936, 'restaurant', 'Uruguay', 'Ciudad de la Costa', 'Canelones',
  'gluten_free_100', 'approved',
  'Guillermo Perez Butler esquina Santa Paula, 15800 Ciudad de la Costa, Departamento de Canelones, Uruguay',
  'manual', 'ChIJH05jRj-Ln5URB3xgh46-Mck', 'find_place',
  '095 714 329', 'https://rikurassingluten.pidedirecto.uy/', null, false,
  'APROBACIÓN MANUAL (2026-09-27, admin): Revisado por el admin: su Instagram (rikuras_singluten) indica cocina apta para celíacos. Sucursal El Pinar de la misma marca que Rikuras Sin Gluten (Malvín); datos de la tarjeta del local (Perez Butler esquina Santa Paula). Ficha de Google propia verificada con Find Place el 2026-09-27.'
 where not exists (
   select 1 from public.places
    where external_id = 'ChIJH05jRj-Ln5URB3xgh46-Mck' or name = 'Rikuras Sin Gluten El Pinar'
 );

do $$
declare n int; bad int;
begin
  select count(*) into n from public.places where source = 'manual' and external_id = 'ChIJH05jRj-Ln5URB3xgh46-Mck';
  if n <> 1 then raise exception 'expected exactly 1 new El Pinar row, found %', n; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) + 1 then
    raise exception 'expected exactly one more place';
  end if;

  select count(*) into bad from public.places p join _snap s using (id) where md5(to_jsonb(p)::text) <> s.h;
  if bad <> 0 then raise exception 'the insert changed % existing rows', bad; end if;

  select count(*) into n from public.places
   where external_id = 'ChIJH05jRj-Ln5URB3xgh46-Mck' and status = 'approved' and safety_level = 'gluten_free_100'
     and verified = false and validation_confidence is null and region = 'Canelones' and geocode_method = 'find_place'
     and validation_notes like 'APROBACIÓN MANUAL (2026-09-27, admin):%';
  if n <> 1 then raise exception 'the new row is not as intended (status, level, verified, confidence, region, geocode, note)'; end if;
end $$;

commit;
