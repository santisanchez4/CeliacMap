-- One-off data correction — `city` that contradicts the row's own address (13 rows).
--
-- Found by the read-only sweep of 2026-09-27 after the region backfill made the mismatch visible: three rules over every
-- status (city not in the address; the city's other rows are in another region; 'Buenos Aires' outside CABA). The new
-- city is the locality of the row's own address, and its region already agrees with the stored `region` (which comes from
-- that same address). It is the "search target stamped as city" bug of before 2026-08-08 (CLAUDE.md, Key risks), not retroactive.
--
-- APPROVED (11): 'Buenos Aires' on 6 places of the province (CABA stays 'Buenos Aires'), 'Fray Bentos' on 3 places of
-- Soriano / Maldonado, and 2 places of Ciudad de la Costa filed as Maldonado / Montevideo.
--   Kanu Sushi - Delivery Vicente Lopez - Sin gl 'buenos aires' -> 'Vicente López'  [Buenos Aires]  address segment 'vicente lopez' (and the name says Vicente Lopez)
--   Celihaus                                     'Buenos Aires' -> 'San Fernando'  [Buenos Aires]  address: 'B1646 San Fernando'
--   esencia sin tacc                             'Buenos Aires' -> 'Villa Bosch'  [Buenos Aires]  address: 'B1682BQL Villa Bosch'
--   La Union Bakery Gluten Free San Isidro       'Buenos Aires' -> 'San Isidro'  [Buenos Aires]  NOT literal: address says 'B1642 Buenos Aires'; the name says San Isidro, B1642 is San Isidro's postal code
--   Nuestro espacio sin tacc                     'Buenos Aires' -> 'Loma Hermosa'  [Buenos Aires]  address: 'B1657 Loma Hermosa'
--   Yoda gluten free                             'Buenos Aires' -> 'Mar del Plata'  [Buenos Aires]  address: 'B7600FJH Mar del Plata'
--   Mi espacio sin TACC                          'Fray Bentos' -> 'Dolores'  [Soriano]  address: '75100 Dolores, Departamento de Soriano'
--   Quiero Sin Gluten                            'Fray Bentos' -> 'Maldonado'  [Maldonado]  address: '20000 Maldonado, Departamento de Maldonado'
--   Rico Rico Gluten Free                        'Fray Bentos' -> 'Mercedes'  [Soriano]  address: '75000 Mercedes, Departamento de Soriano'
--   Celilife                                     'Maldonado' -> 'Ciudad de la Costa'  [Canelones]  address: '15800 Ciudad de la Costa, Departamento de Canelones'
--   Pagana Gluten Free                           'Montevideo' -> 'Ciudad de la Costa'  [Canelones]  address: '15800 Ciudad de la Costa, Departamento de Canelones'
-- NEEDS_REVIEW (2, a separate block so it can be dropped on its own): same problem, not public.
--   El Nido del Cuco                             'Montevideo' -> 'Rodríguez'  [San José]  address: '80400 Rodríguez, Departamento de San José'
--   Pontevedra Alimentos                         'Pontevedra' -> 'Paysandú'  [Paysandú]  address: '60000 Paysandú, Departamento de Paysandú' (the city 'Pontevedra' looks taken from the business name)
--
-- Deliberately NOT touched (a label that differs from Google's locality, not a place in the wrong town; the region agrees):
-- the 'Punta del Este' places whose address says Maldonado / La Barra (a resort-area label the chat searches by),
-- 'Ing. Maschwitz', 'Paraná' for Oro Verde, 'Berisso' (hand-corrected earlier, its address has no locality), 'San Miguel' for
-- Muñiz, 'Vicente López' for Olivos, 'Carrasco', 'Barra del Chuy'. The discarded rows with the same problem stay as debt.
--
-- Only `city` and `validation_notes` change: a snapshot hash of every other column (region and updated_at included) is
-- compared at the end, and places_set_updated_at is switched off inside the transaction (asserted back on), like the
-- region backfill. The header is a DATA correction (agents/manual_overrides.py, "ciudad corregida"): it protects nothing;
-- tests/test_city_from_address_fix.py pins the wording. The previous notes are kept below it.
--
-- Run (one transaction, all-or-nothing; every block asserts its exact row count and RAISES on any drift):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-27-city-from-address.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`. Then run the VERIFICATION queries below.
-- Idempotent: each UPDATE is guarded by the old city, so a second run matches 0 rows and the count assertion aborts it.

begin;

-- 0. Snapshot (dropped at commit): city and notes to compare, and a hash of everything else.
create temp table _snap on commit drop as
select id, city, validation_notes, md5((to_jsonb(p) - 'city' - 'validation_notes')::text) as h from public.places p;

create temp table _fix (
  id uuid primary key, old_city text not null, new_city text not null, status text not null
) on commit drop;
insert into _fix (id, old_city, new_city, status) values
  ('ad0ee75e-2026-45ef-9cc4-bb45edf20441', 'buenos aires', 'Vicente López', 'approved'),
  ('2c9bbad0-38b1-4f77-bfb3-dcfc17e58f18', 'Buenos Aires', 'San Fernando', 'approved'),
  ('0cd2e60d-dc61-4105-b1f4-e6b387964d41', 'Buenos Aires', 'Villa Bosch', 'approved'),
  ('3efed1b0-2161-4a0a-89a2-c5440ff94dc9', 'Buenos Aires', 'San Isidro', 'approved'),
  ('f6e391fd-d289-4230-901c-85726b69a289', 'Buenos Aires', 'Loma Hermosa', 'approved'),
  ('da15c446-b8b5-4955-823b-161a2dad894f', 'Buenos Aires', 'Mar del Plata', 'approved'),
  ('0274deb6-ba10-43fc-b35c-411e871d7505', 'Fray Bentos', 'Dolores', 'approved'),
  ('51ab73ce-8ff4-41dd-a724-76b375d863ed', 'Fray Bentos', 'Maldonado', 'approved'),
  ('df4a1078-15da-44d6-b275-6e1d26d1182a', 'Fray Bentos', 'Mercedes', 'approved'),
  ('8e0758b6-7568-4c2e-973d-adefefec45c2', 'Maldonado', 'Ciudad de la Costa', 'approved'),
  ('77ef6ceb-08ac-4b34-b4cf-598331869bef', 'Montevideo', 'Ciudad de la Costa', 'approved'),
  ('662e1f82-a6b7-45f9-9f63-c81ed0b7caa4', 'Montevideo', 'Rodríguez', 'needs_review'),
  ('d98c8a29-1e67-4cda-ae8e-bacec427b9cb', 'Pontevedra', 'Paysandú', 'needs_review');

do $$
declare n int;
begin
  select count(*) into n from _fix f join public.places p on p.id = f.id
   where p.city = f.old_city and p.status = f.status and p.validation_notes is not null and p.validation_notes <> '';
  if n <> 13 then raise exception 'guard: expected 13 rows in their expected state (old city, status, some notes), found %', n; end if;
end $$;

-- 1. Correct the city and announce it. places_set_updated_at is off so 13 places do not look edited by a robot today.
alter table public.places disable trigger places_set_updated_at;

-- A. approved (11)
do $$
declare n int;
begin
  update public.places p
     set city = f.new_city,
         validation_notes = concat_ws(E'\n\n',
           'CORRECCIÓN MANUAL 2026-09-27: ciudad corregida según la dirección (era ' || f.old_city || ')',
           nullif(p.validation_notes, ''))
    from _fix f
   where p.id = f.id and f.status = 'approved' and p.status = 'approved' and p.city = f.old_city;
  get diagnostics n = row_count;
  if n <> 11 then raise exception 'approved: expected 11 rows, updated %', n; end if;
end $$;

-- B. needs_review (2)
do $$
declare n int;
begin
  update public.places p
     set city = f.new_city,
         validation_notes = concat_ws(E'\n\n',
           'CORRECCIÓN MANUAL 2026-09-27: ciudad corregida según la dirección (era ' || f.old_city || ')',
           nullif(p.validation_notes, ''))
    from _fix f
   where p.id = f.id and f.status = 'needs_review' and p.status = 'needs_review' and p.city = f.old_city;
  get diagnostics n = row_count;
  if n <> 2 then raise exception 'needs_review: expected 2 rows, updated %', n; end if;
end $$;

alter table public.places enable trigger places_set_updated_at;

-- 2. Assertions: any drift RAISES and rolls the whole transaction back.
do $$
declare bad int;
begin
  -- exactly the 13 rows changed city or notes, and nothing else changed anywhere (updated_at and region included)
  select count(*) into bad from public.places p join _snap s using (id)
   where p.city is distinct from s.city or p.validation_notes is distinct from s.validation_notes;
  if bad <> 13 then raise exception 'expected 13 rows with a new city or notes, found %', bad; end if;
  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'city' - 'validation_notes')::text) <> s.h;
  if bad <> 0 then raise exception 'the fix changed something other than city and validation_notes on % rows', bad; end if;
  if (select count(*) from public.places) <> (select count(*) from _snap) then
    raise exception 'the number of places changed';
  end if;

  -- each of the 13: the new city, the header on top and the original notes kept intact below it
  select count(*) into bad from _fix f join public.places p on p.id = f.id join _snap s on s.id = f.id
   where p.city = f.new_city
     and p.validation_notes like 'CORRECCIÓN MANUAL 2026-09-27: ciudad corregida según la dirección (era ' || f.old_city || E')\n\n%'
     and right(p.validation_notes, length(s.validation_notes)) = s.validation_notes;
  if bad <> 13 then raise exception 'original notes are not kept below the header on % of 13 rows', 13 - bad; end if;

  -- the city now agrees with the region wherever it used to contradict it
  select count(*) into bad from public.places
   where status = 'approved' and city = 'Buenos Aires' and region <> 'Ciudad Autónoma de Buenos Aires';
  if bad <> 0 then raise exception 'approved places called Buenos Aires outside CABA: %', bad; end if;
  select count(*) into bad from public.places
   where status in ('approved', 'needs_review')
     and ((city = 'Fray Bentos' and region <> 'Río Negro') or (city = 'Maldonado' and region <> 'Maldonado')
       or (city = 'Montevideo' and region <> 'Montevideo'));
  if bad <> 0 then raise exception 'places whose city contradicts their region (Fray Bentos / Maldonado / Montevideo): %', bad; end if;

  if exists (
    select 1 from pg_trigger
     where tgrelid = 'public.places'::regclass and tgname = 'places_set_updated_at' and tgenabled <> 'O'
  ) then raise exception 'places_set_updated_at was left disabled'; end if;
end $$;

commit;

-- VERIFICATION (read-only; run after the commit).
--   select id, name, city, region, status, left(validation_notes, 100) from public.places where validation_notes like 'CORRECCIÓN MANUAL 2026-09-27%' order by status, city;   -- 13 rows
--   select city, region, count(*) from public.places where status = 'approved' and city in ('Buenos Aires','Fray Bentos','Maldonado','Montevideo','Ciudad de la Costa') group by 1, 2 order by 1, 3 desc;
--   select count(*) from public.places where updated_at >= now() - interval '1 day';   -- 0 (the trigger was off)
--   select tgname, tgenabled from pg_trigger where tgrelid = 'public.places'::regclass and not tgisinternal;   -- 'O'
