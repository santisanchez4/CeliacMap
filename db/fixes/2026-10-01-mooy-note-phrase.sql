-- One-off note correction — MOOY Real Café (La Plata): the admin's confirmation was saved with the example text of the command.
--
-- `review_queue --approve` was applied on 2026-10-01 with the placeholder «ACÁ LA FRASE QUE VISTE» instead of the phrase the admin read on the
-- business's Instagram. This replaces ONLY that text inside `validation_notes` with the real phrase. status, safety_level,
-- validation_confidence, verified and every other column stay as they are (updated_at moves, by its trigger).
--
-- BEFORE RUNNING: put the phrase in `new_phrase` below (the script aborts while it still says <FRASE REAL>). No health data in it.
--
-- Run (one transaction, all-or-nothing; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-01-mooy-note-phrase.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.
-- Idempotent: guarded by the example text, so a second run matches 0 rows and aborts at the count assertion.

begin;

create temp table _snap on commit drop as
select id, validation_notes, md5((to_jsonb(p) - 'validation_notes' - 'updated_at')::text) as h from public.places p;

do $$
declare
  n int;
  bad int;
  old_phrase constant text := 'ACÁ LA FRASE QUE VISTE';
  new_phrase constant text := '<FRASE REAL>';
begin
  if new_phrase like '<%' or btrim(new_phrase) = '' then raise exception 'falta la frase real en new_phrase'; end if;

  update public.places
     set validation_notes = replace(validation_notes, '«' || old_phrase || '»', '«' || new_phrase || '»')
   where id = '1495da11-3fd4-4883-92a5-7bc966d576f8'
     and validation_notes like 'APROBACIÓN MANUAL (2026-10-01, review_queue): Revisado por el admin. Su Instagram (@mooyrealcafe) dice: «' || old_phrase || '».%';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'MOOY: esperaba 1 fila con el texto de ejemplo en la nota, actualicé %', n; end if;

  select count(*) into bad from public.places where strpos(coalesce(validation_notes, ''), old_phrase) > 0;
  if bad <> 0 then raise exception 'el texto de ejemplo sigue apareciendo en % filas', bad; end if;

  select count(*) into bad from public.places p join _snap s using (id) where p.validation_notes is distinct from s.validation_notes;
  if bad <> 1 then raise exception 'esperaba exactamente 1 nota cambiada, encontré %', bad; end if;

  -- the note is the old one with the phrase swapped, nothing else
  select count(*) into bad from public.places p join _snap s using (id)
   where p.id = '1495da11-3fd4-4883-92a5-7bc966d576f8'
     and p.validation_notes is distinct from replace(s.validation_notes, old_phrase, new_phrase);
  if bad <> 0 then raise exception 'la nota cambió en algo más que la frase'; end if;

  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'validation_notes' - 'updated_at')::text) <> s.h;
  if bad <> 0 then raise exception 'cambió algo fuera de validation_notes / updated_at en % filas', bad; end if;
end $$;

commit;

-- VERIFICATION (read-only) — run AFTER the commit above.
select status, safety_level, validation_confidence, verified, left(validation_notes, 200) as nota,
       (strpos(validation_notes, 'ACÁ LA FRASE QUE VISTE') = 0) as ok
from public.places where id = '1495da11-3fd4-4883-92a5-7bc966d576f8';
