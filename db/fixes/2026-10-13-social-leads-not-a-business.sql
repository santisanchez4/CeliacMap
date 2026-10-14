-- Two Social-agent candidates of 2026-10-01 that are not businesses (audit: db/checks/2026-10-13-social-attribution-audit.md).
-- Both are `needs_review` (never on the map), geocoded by address only, with a single `place_evidence` row from a post whose
-- author cannot be verified. Decision of the admin (Santiago Sánchez, 2026-10-13): discard, with a visible data correction.
--
--   * "Empieza entero" (cbbc7983...): the name is the first words of an Instagram post ("Empieza entero. Termina así...") of GOUT,
--     a chain in Argentina ("Recoleta: Montevideo 1480, CABA. Rosario II: Montevideo 319"); "Montevideo" there is a street.
--   * "Pan Sin Gluten En Panetera" (9e6b2dd5...): the source is an Instagram topic page (instagram.com/popular/...), not an account.
--
-- `status = 'discarded'` plus a CORRECCIÓN MANUAL header ("no es un comercio": a data correction, DATA_CORRECTION_PHRASES); no DELETE,
-- the earlier Validator note stays below. validation_confidence and verified are not touched. The "100% pendiente" flag leaves
-- "Empieza entero" (the pending-100 queue has no status filter). place_evidence is not touched.
--
-- Run (one transaction; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-13-social-leads-not-a-business.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.

begin;

create temp table _snap on commit drop as
select id, md5(to_jsonb(p)::text) as h,
       md5((to_jsonb(p) - 'status' - 'validation_notes' - 'flags' - 'updated_at')::text) as h_rest
  from public.places p;

do $$
declare n int;
begin
  select count(*) into n from public.places
   where (id = 'cbbc7983-0143-405a-b749-a46ac6bdb054' and name = 'Empieza entero')
      or (id = '9e6b2dd5-465b-4a3b-9a11-fa6d96485282' and name = 'Pan Sin Gluten En Panetera');
  if n <> 2 then raise exception 'guard: the two rows are not the expected places (found %)', n; end if;

  select count(*) into n from public.places
   where id in ('cbbc7983-0143-405a-b749-a46ac6bdb054', '9e6b2dd5-465b-4a3b-9a11-fa6d96485282')
     and status = 'needs_review' and source = 'social' and geocode_method = 'address_only'
     and validation_notes !~* '(override|aprobaci[oó]n manual|correcci[oó]n manual)';
  if n <> 2 then raise exception 'guard: a row is not needs_review / social / address_only, or has a manual decision (found %)', n; end if;
end $$;

do $$
declare n int;
begin
  update public.places
     set status = 'discarded',
         flags = coalesce((select jsonb_agg(f) from jsonb_array_elements(coalesce(flags, '[]'::jsonb)) f
                            where f <> to_jsonb('100% pendiente de confirmación del administrador'::text)), '[]'::jsonb),
         validation_notes = concat_ws(E'\n\n',
           'CORRECCIÓN MANUAL 2026-10-13: no es un comercio (el agente Social tomó como nombre el comienzo del texto de una publicación de Instagram de GOUT, una cadena de Argentina), no corresponde a este mapa; descartado por decisión del admin.',
           nullif(validation_notes, ''))
   where id = 'cbbc7983-0143-405a-b749-a46ac6bdb054' and status = 'needs_review';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'Empieza entero: expected 1 row updated, updated %', n; end if;

  update public.places
     set status = 'discarded',
         validation_notes = concat_ws(E'\n\n',
           'CORRECCIÓN MANUAL 2026-10-13: no es un comercio (la fuente es una página de tema de Instagram, no la cuenta de un negocio), no corresponde a este mapa; descartado por decisión del admin.',
           nullif(validation_notes, ''))
   where id = '9e6b2dd5-465b-4a3b-9a11-fa6d96485282' and status = 'needs_review';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'Pan Sin Gluten En Panetera: expected 1 row updated, updated %', n; end if;
end $$;

do $$
declare n int;
begin
  -- exactly these two rows changed, and only in status, validation_notes, flags (and updated_at)
  select count(*) into n from public.places p join _snap s using (id) where md5(to_jsonb(p)::text) <> s.h;
  if n <> 2 then raise exception 'expected exactly 2 rows changed, found %', n; end if;
  select count(*) into n from public.places p join _snap s using (id)
   where p.id in ('cbbc7983-0143-405a-b749-a46ac6bdb054', '9e6b2dd5-465b-4a3b-9a11-fa6d96485282')
     and md5((to_jsonb(p) - 'status' - 'validation_notes' - 'flags' - 'updated_at')::text) = s.h_rest
     and p.status = 'discarded' and p.validation_notes like 'CORRECCIÓN MANUAL 2026-10-13: no es un comercio%'
     and not coalesce(p.flags, '[]'::jsonb) @> to_jsonb(array['100% pendiente de confirmación del administrador']);
  if n <> 2 then raise exception 'the two rows are not as intended (only status, notes and flags; discarded; no pending-100 flag)'; end if;
  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'places row count changed'; end if;
end $$;

commit;
