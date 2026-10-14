-- Admin clarification (Santiago Sánchez, 2026-10-13) on the nine approved branches of La Molienda, after the map scope audit
-- (db/checks/2026-10-13-map-scope-audit.md) listed them as doubtful: their OVERRIDE MANUAL of 2026-09-07 calls the business a
-- "supermercado/mercado general", which under the map scope rules would put it outside the map. By its own site it is a natural
-- food shop with a curated gluten-free section, so it stays in scope.
--
-- Only validation_notes changes: one line is added on top. The OVERRIDE MANUAL and the Validator note stay below, untouched;
-- status, safety_level, validation_confidence and verified are not touched.
-- One transaction: it aborts if a row is not the expected one, is not approved / options_available, or its note is not the known one.
--
-- Run:      node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-13-la-molienda-scope-note.sql
-- Dry run:  the same statements with the final `commit;` replaced by `rollback;`.

begin;

create temp table _ids on commit drop as
select unnest(array[
  '16305a09-8773-42ad-ae82-f849bdd44582',  -- La Molienda - 18 de Julio
  'ab09d6d4-e88a-40c0-9fb9-6f8550aff383',  -- La Molienda - ACJ (Colonia)
  '9dd64b4e-3e13-4d2d-88ea-931219dc5c2b',  -- La Molienda - Carrasco
  '59df8880-41b2-4354-b183-ab7bc577178d',  -- La Molienda - Costa Urbana
  'a2135458-3092-4398-9dae-8c79ab432e04',  -- La Molienda - Ejido
  'b41cc805-f877-4b37-8a1e-5df0f27174df',  -- La Molienda - Parque Rodó
  '3892f08f-eccf-499f-bd93-e0c199d7c92c',  -- La Molienda - Punta Carretas
  'c1199194-a936-4a31-95cc-2a430b226601',  -- La Molienda - Sarandí
  '32dc14f4-ced7-4c36-8d6a-2942c64e0367'   -- La Molienda - Tres Cruces
]::uuid[]) as id;

create temp table _snap on commit drop as
select id, md5(to_jsonb(p)::text) as h,
       md5((to_jsonb(p) - 'validation_notes' - 'updated_at')::text) as h_rest,
       validation_notes as old_notes
  from public.places p;
create temp table _ev on commit drop as select count(*) as total from public.place_evidence;

-- 0. Guards.
do $$
declare n int;
begin
  select count(*) into n from public.places p join _ids using (id)
   where p.name like 'La Molienda - %'
     and p.status = 'approved' and p.safety_level = 'options_available'
     and p.validation_notes like 'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten\_free\_100). La Molienda es un supermercado/mercado general%'
     and p.validation_notes not like '%ACLARACIÓN%';
  if n <> 9 then raise exception 'guard: expected the 9 branches approved, options_available, with the known override on top; found %', n; end if;

  select count(*) into n from public.places where name ilike '%molienda%';
  if n <> 9 then raise exception 'guard: expected exactly 9 rows named La Molienda; found %', n; end if;
end $$;

-- 1. The clarification goes on top; everything else stays below.
update public.places p
   set validation_notes = 'ACLARACIÓN 2026-10-13 (admin): por su propio sitio, La Molienda es una tienda natural (no un supermercado general) con una sección sin gluten curada y verificada; queda dentro del alcance del mapa y se mantiene como options_available.'
                          || E'\n\n' || p.validation_notes
  from _ids i
 where p.id = i.id and p.status = 'approved';

-- 2. Assertions: any drift RAISES and rolls everything back.
do $$
declare n int;
begin
  select count(*) into n from public.places p join _snap s using (id) where md5(to_jsonb(p)::text) <> s.h;
  if n <> 9 then raise exception 'expected exactly 9 rows changed, found %', n; end if;

  -- only validation_notes (and updated_at) changed; the earlier note sits intact below the new line
  select count(*) into n from public.places p join _snap s using (id) join _ids using (id)
   where md5((to_jsonb(p) - 'validation_notes' - 'updated_at')::text) = s.h_rest
     and p.status = 'approved' and p.safety_level = 'options_available'
     and p.validation_notes = 'ACLARACIÓN 2026-10-13 (admin): por su propio sitio, La Molienda es una tienda natural (no un supermercado general) con una sección sin gluten curada y verificada; queda dentro del alcance del mapa y se mantiene como options_available.'
                              || E'\n\n' || s.old_notes;
  if n <> 9 then raise exception 'the nine notes are not as intended (new line on top, earlier note below, nothing else); ok = %', n; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'places row count changed'; end if;
  if (select count(*) from public.places where status = 'approved') <> (select count(*) from _snap s join public.places p using (id) where p.status = 'approved')
     then raise exception 'approved count changed'; end if;
  if (select count(*) from public.place_evidence) <> (select total from _ev) then raise exception 'place_evidence changed'; end if;
end $$;

commit;
