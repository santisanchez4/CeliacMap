-- One-off data correction — contact data of the two places the admin approved on 2026-10-01 (ChocAra MVD, Alimentos NutriCiencia SRL).
--
-- Run AFTER the two approvals (the UPDATEs are guarded by status = 'approved' and the APROBACIÓN MANUAL header, so this aborts otherwise):
--   python -m scripts.review_queue --approve 1becc778-212c-49ac-b2de-7e6417265385 --level 100 --note "…" --apply
--   python -m scripts.review_queue --approve 7f145df1-b613-470b-8748-b5ee19d383ad --level 100 --note "…" --apply
--
--   1. ChocAra MVD - Sabores Que Unen (20 de Setiembre 1520, Montevideo): Instagram, and Sunday hours (Google says closed; the admin's
--      data says 11:00-19:00). Address, phone (095 621 971) and website (https://chocara.com/) are already right and are not touched.
--   2. Alimentos NutriCiencia SRL (Gral. Urquiza 2828, Montevideo): website to https, weekday hours 10:00-17:00 without Google's 15:00-15:30 gap.
--      Address, phone and category ('shop') are already right. The contact email stays in the server-only column; it is not written here.
--
-- `address` does not change on either row (it already is Google's formatted address for that street and number), so lat/lng and region stay.
-- Columns set: social_url, website, opening_hours (and updated_at, by its trigger). No note header is added, as in
-- db/fixes/2026-09-27-rikuras-malvin-website.sql: a header is for a decision about the place, and this changes contact data. The change is
-- recorded in docs/DECISIONS.md.
-- Known limit (accepted by the admin): both rows are source = 'google_places', so the monthly Updater rewrites website / opening_hours
-- whenever Google's value differs. social_url is not a Google field and stays.
--
-- Run (one transaction, all-or-nothing; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-01-chocara-nutriciencia-data.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.
-- Idempotent: guarded by the old values, so a second run matches 0 rows and aborts at the count assertion.

begin;

create temp table _snap on commit drop as
select id, social_url, website, opening_hours,
       md5((to_jsonb(p) - 'social_url' - 'website' - 'opening_hours' - 'updated_at')::text) as h
from public.places p;

do $$
declare n int;
begin
  update public.places p
     set social_url = 'https://www.instagram.com/chocara.saboresqueunen/',
         opening_hours = '["lunes: 7:30–20:00","martes: 7:30–20:00","miércoles: 7:30–20:00","jueves: 7:30–20:00","viernes: 7:30–20:00","sábado: 11:00–20:00","domingo: 11:00–19:00"]'::jsonb
   where p.id = '1becc778-212c-49ac-b2de-7e6417265385'
     and p.status = 'approved' and p.safety_level = 'gluten_free_100'
     and p.validation_notes like 'APROBACIÓN MANUAL%'
     and p.social_url is null;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'ChocAra: esperaba 1 fila (aprobada por el admin, sin social_url), actualicé %', n; end if;

  update public.places p
     set website = 'https://cerogluten.uy/',
         opening_hours = '["lunes: 10:00–17:00","martes: 10:00–17:00","miércoles: 10:00–17:00","jueves: 10:00–17:00","viernes: 10:00–17:00","sábado: Cerrado","domingo: Cerrado"]'::jsonb
   where p.id = '7f145df1-b613-470b-8748-b5ee19d383ad'
     and p.status = 'approved' and p.safety_level = 'gluten_free_100' and p.category = 'shop'
     and p.validation_notes like 'APROBACIÓN MANUAL%'
     and p.website = 'http://www.cerogluten.uy/';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'NutriCiencia: esperaba 1 fila (aprobada por el admin, con la web vieja), actualicé %', n; end if;
end $$;

do $$
declare bad int;
begin
  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'social_url' - 'website' - 'opening_hours' - 'updated_at')::text) <> s.h;
  if bad <> 0 then raise exception 'cambió algo fuera de social_url / website / opening_hours / updated_at en % filas', bad; end if;

  select count(*) into bad from public.places p join _snap s using (id)
   where p.social_url is distinct from s.social_url or p.website is distinct from s.website or p.opening_hours is distinct from s.opening_hours;
  if bad <> 2 then raise exception 'esperaba exactamente 2 filas con datos cambiados, encontré %', bad; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'cambió la cantidad de lugares'; end if;
end $$;

commit;

-- =============================================================================================
-- VERIFICATION (read-only) — run AFTER the commit above, as a single statement. Every row ok = true.
-- =============================================================================================
select check_name, expected, actual, (expected = actual) as ok from (
  select 1 as n, 'ChocAra: approved 100% with Instagram and Sunday hours' as check_name, 1 as expected,
         (select count(*) from public.places
           where id = '1becc778-212c-49ac-b2de-7e6417265385' and status = 'approved' and safety_level = 'gluten_free_100'
             and social_url = 'https://www.instagram.com/chocara.saboresqueunen/'
             and opening_hours ->> 6 = 'domingo: 11:00–19:00') as actual
  union all
  select 2, 'NutriCiencia: approved 100% shop with https site and weekday hours', 1,
         (select count(*) from public.places
           where id = '7f145df1-b613-470b-8748-b5ee19d383ad' and status = 'approved' and safety_level = 'gluten_free_100'
             and category = 'shop' and website = 'https://cerogluten.uy/' and opening_hours ->> 0 = 'lunes: 10:00–17:00')
) c order by n;
