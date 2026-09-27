-- One-off data correction — Delirio Sin Gluten (Montevideo): the address gets the house number the business publishes.
--
-- Google's listing (place_id ChIJwTX928WBn5URE2DVhyrVGNQ) has the street without a number ("Luis Franzini, 11300 Montevideo, ..."); the business's own
-- Instagram (@deliriosingluten) says "Pocitos - Luis Franzini 970". Checked 2026-09-27 with the Geocoding API: "Luis Franzini 970, Montevideo" resolves
-- (ROOFTOP) to (-34.9131763, -56.1588037), 23 m from the coordinates the row already has (-34.912976, -56.1588556): the pin is on the same block, so lat / lng
-- are NOT changed here. Only `address` and `validation_notes` change; places.region stays 'Montevideo' (it parses from the new address the same way).
--
-- The header is a DATA correction (agents/manual_overrides.py, "dirección corregida"): it protects nothing and the previous notes stay intact below it.
-- tests/test_manual_row_fixes.py pins the wording, the assignments and the guards.
--
-- Run (one transaction, all-or-nothing; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-27-delirio-address.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.
-- Idempotent: the UPDATE is guarded by the old address, so a second run aborts at the guard.

begin;

-- 0. Snapshot (dropped at commit): address and notes to compare, and a hash of everything else.
create temp table _snap on commit drop as
select id, address, validation_notes,
       md5((to_jsonb(p) - 'address' - 'validation_notes' - 'updated_at')::text) as h
  from public.places p;

-- 1. Guard, then the correction.
do $$
declare n int;
begin
  select count(*) into n from public.places
   where id = '7af0d1a1-5603-454a-a578-7b7bc05c8423' and status = 'approved'
     and address = 'Luis Franzini, 11300 Montevideo, Departamento de Montevideo, Uruguay';
  if n <> 1 then raise exception 'guard: expected the Delirio row approved and with its old address, found % rows', n; end if;

  update public.places
     set address = 'Luis Franzini 970, 11300 Montevideo, Departamento de Montevideo, Uruguay',
         validation_notes = concat_ws(E'\n\n',
           'CORRECCIÓN MANUAL 2026-09-27: dirección corregida a "Luis Franzini 970" según el Instagram del local (antes "Luis Franzini", sin número).',
           nullif(validation_notes, ''))
   where id = '7af0d1a1-5603-454a-a578-7b7bc05c8423'
     and address = 'Luis Franzini, 11300 Montevideo, Departamento de Montevideo, Uruguay';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'expected 1 row updated, updated %', n; end if;
end $$;

-- 2. Assertions: any drift RAISES and rolls the whole transaction back.
do $$
declare bad int;
begin
  select count(*) into bad from public.places p join _snap s using (id)
   where p.address is distinct from s.address or p.validation_notes is distinct from s.validation_notes;
  if bad <> 1 then raise exception 'expected 1 row with a new address or notes, found %', bad; end if;

  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'address' - 'validation_notes' - 'updated_at')::text) <> s.h;
  if bad <> 0 then raise exception 'the fix changed something other than address, notes and updated_at on % rows', bad; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) then
    raise exception 'the number of places changed';
  end if;

  select count(*) into bad from public.places p join _snap s on s.id = p.id
   where p.id = '7af0d1a1-5603-454a-a578-7b7bc05c8423'
     and p.address = 'Luis Franzini 970, 11300 Montevideo, Departamento de Montevideo, Uruguay'
     and p.region = 'Montevideo'
     and p.validation_notes like 'CORRECCIÓN MANUAL 2026-09-27: dirección corregida a "Luis Franzini 970"%'
     and right(p.validation_notes, length(s.validation_notes)) = s.validation_notes;
  if bad <> 1 then raise exception 'the Delirio row is not as expected after the fix (address, region, header, original notes kept)'; end if;
end $$;

commit;
