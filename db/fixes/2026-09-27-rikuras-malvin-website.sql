-- One-off data correction — Rikuras Sin Gluten (Malvín, Hipólito Yrigoyen 1728, Montevideo): the website of the business card.
--
-- The row had https://rikurassingluten.ambit.la/ (an old ordering site). The card the business hands out says https://rikurassingluten.pidedirecto.uy/.
-- Only `website` changes (and updated_at, by its trigger). The phone (099 442 254) is already on the row, so it is not touched. No note header is added:
-- a header is for a decision about the place, and this changes a link.
--
-- Run (one transaction, all-or-nothing; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-27-rikuras-malvin-website.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.
-- Idempotent: the UPDATE is guarded by the old website, so a second run aborts at the count assertion.

begin;

create temp table _snap on commit drop as
select id, website, md5((to_jsonb(p) - 'website' - 'updated_at')::text) as h from public.places p;

do $$
declare n int;
begin
  update public.places
     set website = 'https://rikurassingluten.pidedirecto.uy/'
   where id = '339efc28-af19-4ce4-96ea-a9c1aa5176d4'
     and website = 'https://rikurassingluten.ambit.la/';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'expected 1 row (Malvín with its old website), updated %', n; end if;
end $$;

do $$
declare bad int;
begin
  select count(*) into bad from public.places p join _snap s using (id) where p.website is distinct from s.website;
  if bad <> 1 then raise exception 'expected exactly 1 row with a new website, found %', bad; end if;
  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'website' - 'updated_at')::text) <> s.h;
  if bad <> 0 then raise exception 'the update changed something other than website and updated_at on % rows', bad; end if;
  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'the number of places changed'; end if;
end $$;

commit;
