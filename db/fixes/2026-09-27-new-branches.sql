-- Manual places of 2026-09-27, in ONE transaction: two new branches and the update of one row that already existed.
--
--   1. Rikuras Sin Gluten El Pinar (Canelones): a second branch of Rikuras Sin Gluten (Malvín). Google has its OWN listing
--      (ChIJH05jRj-Ln5URB3xgh46-Mck, Guillermo Perez Butler Manzana 249 Solar 2, 15800 Ciudad de la Costa; the corner geocoded independently lands ~70 m
--      away), different from Malvín's (ChIJ64hoV1KHn5URvCEqq2PDcI4). city = 'Ciudad de la Costa' (Google's locality for 15800 and the convention of the
--      other rows there); "El Pinar" is in the name and the address text. Phone in local format.
--   2. Piu Helados Prado (Av. Millán 3665, Montevideo): a new place with its own Google listing (ChIJu6y8K8EroJUR5Y38idweSEk, "Heladería Piú", OPERATIONAL,
--      Google's phone +598 98 858 031 = the card's).
--   3. Piu Helados Cordón (Constituyente 2039): NOT inserted. It already is a row (d1420754..., "Heladería Piú", source google_places, ChIJU0NqfQCBn5URvFcSbHMvFQs,
--      discarded by the Validator in June 2026: "no signals of gluten-free specialization"). A second row with the same Google place would be a duplicate,
--      so the existing row gets its data here (name, category, Instagram, phone) and stays `discarded` until the last step below.
--
-- The two new rows are anchored to their Google place_id with source = 'manual'; since 2026-09-27 `insert_place_candidate` skips a Search candidate whose
-- place_id already belongs to any row, so the monthly Search agent cannot duplicate them ("One Google place, one row", docs/DECISIONS.md).
--
-- Run (one transaction, all-or-nothing; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-27-new-branches.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.
--
-- AFTER the commit, and only then, the Cordón row is approved with the admin's note (its own atomic UPDATE, so nothing is published unless the whole
-- transaction above went through; if this last step failed, Cordón would stay discarded, which is invisible and safe):
--   python -m scripts.review_queue --approve d1420754-dca8-47e2-8d60-97ac779de1c2 --level 100 --note "Revisado por el admin: su Instagram (piuheladosmontevideo) se presenta como heladería artesanal Gluten Free" --apply
-- That writes the APROBACIÓN MANUAL header (with "El Validator había dejado: discarded @ 0.75", the earlier verdict stays visible), sets status approved and
-- gluten_free_100, and leaves validation_confidence (0.75) and verified untouched: a confidence is never inflated or deflated.

begin;

-- 0. Snapshot (dropped at commit): a hash of every existing row, and of Cordón without the columns this script sets.
create temp table _snap on commit drop as
select id, md5(to_jsonb(p)::text) as h,
       md5((to_jsonb(p) - 'name' - 'category' - 'social_url' - 'phone' - 'updated_at')::text) as h_cordon
  from public.places p;

-- 1. Guards: the two new places are not there yet, and the Cordón row is in the state this script was written for.
do $$
declare n int;
begin
  select count(*) into n from public.places
   where external_id in ('ChIJH05jRj-Ln5URB3xgh46-Mck', 'ChIJu6y8K8EroJUR5Y38idweSEk')
      or name in ('Rikuras Sin Gluten El Pinar', 'Piu Helados Prado');
  if n <> 0 then raise exception 'guard: a new branch already exists (% rows)', n; end if;

  select count(*) into n from public.places
   where id = 'd1420754-dca8-47e2-8d60-97ac779de1c2' and status = 'discarded'
     and external_id = 'ChIJU0NqfQCBn5URvFcSbHMvFQs' and name = 'Heladería Piú';
  if n <> 1 then raise exception 'guard: the Cordón row is not in the expected state (found % rows)', n; end if;
end $$;

-- 2. Rikuras Sin Gluten El Pinar.
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

-- 3. Piu Helados Prado.
insert into public.places
  (name, lat, lng, category, country, city, region, safety_level, status, address, source, external_id, geocode_method,
   phone, social_url, validation_confidence, verified, validation_notes)
select
  'Piu Helados Prado', -34.8603244, -56.1953583, 'cafe', 'Uruguay', 'Montevideo', 'Montevideo',
  'gluten_free_100', 'approved',
  'Av. Millán 3665, 11700 Montevideo, Departamento de Montevideo, Uruguay',
  'manual', 'ChIJu6y8K8EroJUR5Y38idweSEk', 'find_place',
  '098 858 031', 'https://www.instagram.com/piuheladosmontevideo/', null, false,
  'APROBACIÓN MANUAL (2026-09-27, admin): Revisado por el admin: su Instagram (piuheladosmontevideo) se presenta como heladería artesanal Gluten Free.'
 where not exists (
   select 1 from public.places
    where external_id = 'ChIJu6y8K8EroJUR5Y38idweSEk' or name = 'Piu Helados Prado'
 );

-- 4. Piu Helados Cordón: the existing row gets its data. Status, level and the approval note come from `review_queue --approve` afterwards.
do $$
declare n int;
begin
  update public.places
     set name = 'Piu Helados Cordón',
         category = 'cafe',
         social_url = 'https://www.instagram.com/piuheladosmontevideo/',
         phone = '091 651 051'
   where id = 'd1420754-dca8-47e2-8d60-97ac779de1c2' and status = 'discarded'
     and external_id = 'ChIJU0NqfQCBn5URvFcSbHMvFQs' and name = 'Heladería Piú';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'expected 1 Cordón row updated, updated %', n; end if;
end $$;

-- 5. Assertions: any drift RAISES and rolls the whole transaction back.
do $$
declare n int; bad int;
begin
  select count(*) into n from public.places
   where source = 'manual' and external_id in ('ChIJH05jRj-Ln5URB3xgh46-Mck', 'ChIJu6y8K8EroJUR5Y38idweSEk');
  if n <> 2 then raise exception 'expected exactly 2 new manual rows, found %', n; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) + 2 then
    raise exception 'expected exactly two more places';
  end if;

  -- no existing row changed except Cordón, and Cordón only in name, category, social_url, phone (and updated_at)
  select count(*) into bad from public.places p join _snap s using (id) where md5(to_jsonb(p)::text) <> s.h;
  if bad <> 1 then raise exception 'expected exactly 1 existing row changed (Cordón), found %', bad; end if;
  select count(*) into bad from public.places p join _snap s using (id)
   where p.id = 'd1420754-dca8-47e2-8d60-97ac779de1c2'
     and md5((to_jsonb(p) - 'name' - 'category' - 'social_url' - 'phone' - 'updated_at')::text) = s.h_cordon
     and p.name = 'Piu Helados Cordón' and p.category = 'cafe' and p.phone = '091 651 051'
     and p.social_url = 'https://www.instagram.com/piuheladosmontevideo/' and p.status = 'discarded';
  if bad <> 1 then raise exception 'the Cordón row is not as intended (only its four columns changed, still discarded)'; end if;

  -- the two new rows, as intended
  select count(*) into n from public.places
   where source = 'manual' and external_id in ('ChIJH05jRj-Ln5URB3xgh46-Mck', 'ChIJu6y8K8EroJUR5Y38idweSEk')
     and status = 'approved' and safety_level = 'gluten_free_100' and verified = false and validation_confidence is null
     and geocode_method = 'find_place' and validation_notes like 'APROBACIÓN MANUAL (2026-09-27, admin):%';
  if n <> 2 then raise exception 'the new rows are not as intended (status, level, verified, confidence, geocode method, note)'; end if;
end $$;

commit;
