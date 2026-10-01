-- One-off data correction — the 6 Brazilian and 2 Chilean places leave the needs_review queue (admin decision, 2026-10-01).
--
-- Context: both clusters were kept in `needs_review` as an "editorial exclusion" (db/fixes/2026-09-01-brazil-out-of-scope-places.sql,
-- db/fixes/2026-09-25-chile-out-of-scope.sql). They can never be approved (CeliacMap covers Uruguay and Argentina only), so they only
-- add noise to the admin's queue (8 of 508 rows on 2026-10-01). The admin moves them to `discarded`: the standing way to fix a bad row
-- (auditable, no DELETE). This is not a judgement on the businesses.
--
-- Only `status` and `validation_notes` change (and updated_at, by its trigger). The header uses the data phrase
-- "fuera del alcance geográfico" (DATA_CORRECTION_PHRASES in agents/manual_overrides.py): it states where the place is and protects nothing.
-- country, city, outreach_opt_out (already true), lat/lng, validation_confidence, safety_level and flags are NOT touched.
--
-- Run (one transaction, all-or-nothing; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-01-out-of-scope-discard.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.
-- Idempotent: guarded by status = 'needs_review', so a second run matches 0 rows and aborts at the count assertion.

begin;

create temp table _snap on commit drop as
select id, validation_notes, md5((to_jsonb(p) - 'status' - 'validation_notes' - 'updated_at')::text) as h from public.places p;

do $$
declare n int;
begin
  update public.places p
     set status = 'discarded',
         validation_notes = concat_ws(E'\n\n',
           'CORRECCIÓN MANUAL (2026-10-01): fuera del alcance geográfico (el lugar está en ' || p.country
           || '; CeliacMap cubre solo Uruguay y Argentina). Pasa de needs_review a discarded por decisión del admin para sacarlo de la cola de revisión; '
           || 'no es un juicio sobre el negocio.',
           nullif(p.validation_notes, ''))
   where p.id in (
           '269a239e-804a-47d2-be81-9c1e610352af',  -- Confeitaria Glúten Free Cascavel — Cascavel, Brasil
           '985fd078-41b6-4839-a3ad-882df3dbf24a',  -- Empório Celíaco • Sem Glúten, … — União da Vitória, Brasil
           'f732f905-1573-4f19-adb6-58acfa213e51',  -- Glúten Pra Quê? — Curitiba, Brasil
           '15eb48e3-ad3c-4a2e-85cc-ce9457f87808',  -- LEVAIN GLÚTEN FREE — Curitiba, Brasil
           'a7fec799-96c2-49d6-b01a-29273c6ef161',  -- Sem Culpa - Sem Gluten — Curitiba, Brasil
           'e3d18b5e-622a-43b4-8d0b-89745b6c8449',  -- Senza Glutine - comida sem glúten saudável — Pinhais, Brasil
           '3527545f-3f43-45cf-97c4-432518a80c42',  -- Las Petunias Pastelería sin azúcar y sin gluten — Vitacura, Chile
           'e530f08b-ae6e-4b16-9c8e-b37cfc717c08')  -- Quimey Fusion & Gluten Free — Viña del Mar, Chile
     and p.status = 'needs_review'
     and p.country in ('Brasil', 'Chile');
  get diagnostics n = row_count;
  if n <> 8 then raise exception 'esperaba 8 filas (6 Brasil + 2 Chile en needs_review), actualicé %', n; end if;
end $$;

do $$
declare bad int;
begin
  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'status' - 'validation_notes' - 'updated_at')::text) <> s.h;
  if bad <> 0 then raise exception 'cambió algo más que status / validation_notes / updated_at en % filas', bad; end if;

  select count(*) into bad from public.places p join _snap s using (id)
   where p.validation_notes is distinct from s.validation_notes;
  if bad <> 8 then raise exception 'esperaba exactamente 8 filas con la nota cambiada, encontré %', bad; end if;

  select count(*) into bad from public.places p join _snap s using (id)
   where p.validation_notes is distinct from s.validation_notes
     and (p.validation_notes not like 'CORRECCIÓN MANUAL (2026-10-01): fuera del alcance geográfico%'
          or strpos(p.validation_notes, coalesce(s.validation_notes, '')) = 0);
  if bad <> 0 then raise exception '% filas sin el encabezado nuevo o sin el texto original debajo', bad; end if;

  select count(*) into bad from public.places
   where status <> 'discarded' and (country is null or country not in ('Uruguay', 'Argentina'));
  if bad <> 0 then raise exception 'quedan % filas vivas fuera de Uruguay/Argentina', bad; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'cambió la cantidad de lugares'; end if;
end $$;

commit;

-- =============================================================================================
-- VERIFICATION (read-only) — run AFTER the commit above, as a single statement. Every row ok = true.
-- =============================================================================================
select check_name, expected, actual, (expected = actual) as ok from (
  select 1 as n, 'the 8 rows: discarded + the 2026-10-01 header' as check_name, 8 as expected,
         (select count(*) from public.places
           where country in ('Brasil', 'Chile') and status = 'discarded'
             and validation_notes like 'CORRECCIÓN MANUAL (2026-10-01): fuera del alcance geográfico%') as actual
  union all
  select 2, 'live rows outside Uruguay/Argentina', 0,
         (select count(*) from public.places
           where status <> 'discarded' and (country is null or country not in ('Uruguay', 'Argentina')))
) c order by n;
