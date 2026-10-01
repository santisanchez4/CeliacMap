-- One-off note correction — MOOY Real Café (La Plata): the admin's confirmation was saved with the example text of the command.
--
-- `review_queue --approve` was applied on 2026-10-01 with the placeholder «ACÁ LA FRASE QUE VISTE» instead of the phrase the admin read on the
-- business's Instagram. This replaces ONLY that sentence inside `validation_notes` with the admin's wording: the confirmation comes from
-- reviewing the Instagram profile, and the quoted phrase is from the Google reviews. status, safety_level, validation_confidence, verified
-- and every other column stay as they are (updated_at moves, by its trigger).
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
  example constant text := 'ACÁ LA FRASE QUE VISTE';
  old_phrase constant text := 'Su Instagram (@mooyrealcafe) dice: «ACÁ LA FRASE QUE VISTE»';
  new_phrase constant text := 'Confirmado por el admin revisando su Instagram (@mooyrealcafe); reseñas de Google dicen «Todo lo que sirven es sin gluten y sin azúcar!!»';
begin

  update public.places
     set validation_notes = replace(validation_notes, old_phrase, new_phrase)
   where id = '1495da11-3fd4-4883-92a5-7bc966d576f8'
     and validation_notes like 'APROBACIÓN MANUAL (2026-10-01, review_queue): Revisado por el admin. ' || old_phrase || '. El Validator había dejado: approved @ 0.91.%';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'MOOY: esperaba 1 fila con el texto de ejemplo en la nota, actualicé %', n; end if;

  select count(*) into bad from public.places where strpos(coalesce(validation_notes, ''), example) > 0;
  if bad <> 0 then raise exception 'el texto de ejemplo sigue apareciendo en % filas', bad; end if;

  select count(*) into bad from public.places p join _snap s using (id) where p.validation_notes is distinct from s.validation_notes;
  if bad <> 1 then raise exception 'esperaba exactamente 1 nota cambiada, encontré %', bad; end if;

  -- the note is the old one with that one sentence swapped, nothing else
  select count(*) into bad from public.places p join _snap s using (id)
   where p.id = '1495da11-3fd4-4883-92a5-7bc966d576f8'
     and p.validation_notes is distinct from replace(s.validation_notes, old_phrase, new_phrase);
  if bad <> 0 then raise exception 'la nota cambió en algo más que la frase'; end if;

  select count(*) into bad from public.places
   where id = '1495da11-3fd4-4883-92a5-7bc966d576f8'
     and validation_notes like 'APROBACIÓN MANUAL (2026-10-01, review_queue): Revisado por el admin. ' || new_phrase || '. El Validator había dejado: approved @ 0.91.%';
  if bad <> 1 then raise exception 'la nota no empieza con el encabezado y la oración nueva'; end if;

  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'validation_notes' - 'updated_at')::text) <> s.h;
  if bad <> 0 then raise exception 'cambió algo fuera de validation_notes / updated_at en % filas', bad; end if;
end $$;

commit;

-- VERIFICATION (read-only) — run AFTER the commit above.
select status, safety_level, validation_confidence, verified, left(validation_notes, 200) as nota,
       (strpos(validation_notes, 'ACÁ LA FRASE QUE VISTE') = 0) as ok
from public.places where id = '1495da11-3fd4-4883-92a5-7bc966d576f8';
