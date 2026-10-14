-- Admin decision (Santiago Sánchez, 2026-10-13) on the three rows of a general retail chain that the map scope audit found outside
-- `discarded` (db/checks/2026-10-13-map-scope-audit.md, "seguros"). Map scope rules: docs/DECISIONS.md, "Map scope rules".
--
--   1. Tienda Inglesa, Montevideo (1aab916e...):      approved     -> discarded. It was on the map (0.72, options_available).
--   2. Tienda Inglesa, Punta del Este (b735ee91...):  needs_review -> discarded.
--   3. Carrefour Market, La Plata (beb397c0...):      needs_review -> discarded.
--
-- A supermarket chain, general retail: it does not apply to the map, whatever its gluten-free shelf. In every case the earlier
-- Validator note stays below the new header, and validation_confidence / verified / safety_level / flags are not touched.
-- One transaction: it aborts if a row is not the expected one, changed its status or confidence, or carries a manual decision.
--
-- Run:      node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-13-map-scope-chain-discards.sql
-- Dry run:  the same statements with the final `commit;` replaced by `rollback;`.

begin;

create temp table _snap on commit drop as
select id, md5(to_jsonb(p)::text) as h,
       md5((to_jsonb(p) - 'status' - 'validation_notes' - 'updated_at')::text) as h_decision,
       validation_notes as old_notes
  from public.places p;
create temp table _ev on commit drop as select count(*) as total from public.place_evidence;

-- 0. Guards.
do $$
declare n int;
begin
  select count(*) into n from public.places
   where coalesce(validation_notes, '') !~* '(override|aprobaci[oó]n manual|correcci[oó]n manual|revisi[oó]n manual)'
     and coalesce(validation_notes, '') <> ''
     and (   (id = '1aab916e-ca08-4c50-bd04-f53d82f81c1f' and name = 'Tienda Inglesa'   and city = 'Montevideo'
              and status = 'approved'     and validation_confidence = 0.72)
          or (id = 'b735ee91-087b-4cf2-ae82-060835d39a9e' and name = 'Tienda Inglesa'   and city = 'Punta del Este'
              and status = 'needs_review' and validation_confidence = 0.52)
          or (id = 'beb397c0-7e27-4c8f-96f4-9e971e7e4fdc' and name = 'Carrefour Market' and city = 'La Plata'
              and status = 'needs_review' and validation_confidence = 0.52));
  if n <> 3 then raise exception 'guard: expected the 3 rows in their known status, unchanged and without a manual decision; found %', n; end if;
end $$;

-- 1. Tienda Inglesa, Montevideo: approved -> discarded.
update public.places
   set status = 'discarded',
       validation_notes = concat_ws(E'\n\n',
         'CORRECCIÓN MANUAL 2026-10-13: no aplica al mapa: cadena de supermercados, comercio general; descartado por decisión del admin.',
         nullif(validation_notes, ''))
 where id = '1aab916e-ca08-4c50-bd04-f53d82f81c1f' and status = 'approved';

-- 2. Tienda Inglesa, Punta del Este: needs_review -> discarded.
update public.places
   set status = 'discarded',
       validation_notes = concat_ws(E'\n\n',
         'CORRECCIÓN MANUAL 2026-10-13: no aplica al mapa: cadena de supermercados, comercio general; descartado por decisión del admin.',
         nullif(validation_notes, ''))
 where id = 'b735ee91-087b-4cf2-ae82-060835d39a9e' and status = 'needs_review';

-- 3. Carrefour Market, La Plata: needs_review -> discarded.
update public.places
   set status = 'discarded',
       validation_notes = concat_ws(E'\n\n',
         'CORRECCIÓN MANUAL 2026-10-13: no aplica al mapa: cadena de supermercados, comercio general; descartado por decisión del admin.',
         nullif(validation_notes, ''))
 where id = 'beb397c0-7e27-4c8f-96f4-9e971e7e4fdc' and status = 'needs_review';

-- 4. Assertions: any drift RAISES and rolls everything back.
do $$
declare n int;
begin
  select count(*) into n from public.places p join _snap s using (id) where md5(to_jsonb(p)::text) <> s.h;
  if n <> 3 then raise exception 'expected exactly 3 rows changed, found %', n; end if;

  -- only status, validation_notes (and updated_at) changed; the earlier note sits intact below the header
  select count(*) into n from public.places p join _snap s using (id)
   where p.id in ('1aab916e-ca08-4c50-bd04-f53d82f81c1f', 'b735ee91-087b-4cf2-ae82-060835d39a9e', 'beb397c0-7e27-4c8f-96f4-9e971e7e4fdc')
     and md5((to_jsonb(p) - 'status' - 'validation_notes' - 'updated_at')::text) = s.h_decision
     and p.status = 'discarded'
     and p.validation_notes = 'CORRECCIÓN MANUAL 2026-10-13: no aplica al mapa: cadena de supermercados, comercio general; descartado por decisión del admin.'
                              || E'\n\n' || s.old_notes;
  if n <> 3 then raise exception 'the three discards are not as intended (status, header, earlier note below, nothing else); ok = %', n; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'places row count changed'; end if;
  if (select count(*) from public.place_evidence) <> (select total from _ev) then raise exception 'place_evidence changed'; end if;
end $$;

commit;
