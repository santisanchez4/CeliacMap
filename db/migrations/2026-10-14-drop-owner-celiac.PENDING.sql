-- NOT APPLIED YET. Stage 3 of docs/legal/owner-celiac-plan.md: drop suggestions.owner_celiac and place_reports.owner_celiac
-- (a named third party's health condition; the question left the form on 2026-09-29 and the chat on 2026-09-30).
-- Planned from 2026-10-07 (one week after the later of the two deploys, so a cached page cannot lose a suggestion to an
-- unknown-column error); prepared as 2026-10-07-drop-owner-celiac.PENDING.sql, applied 2026-10-14 if the admin says "dale".
--
-- Read-only inventory of 2026-10-14 (production): the columns exist only in public.suggestions and public.place_reports, with
-- 0 non-null values (2 and 2 rows in all, none created since 2026-09-30); the only object that uses them is the CHECK
-- place_reports_kitchen_positive_only_check; no view, function, trigger, policy, index or column grant (anon / authenticated
-- have the table INSERT grant only). The deployed chat (v25) equals main and deletes owner_celiac before any insert; the live
-- site's form files do not contain it; no agent, script or Edge Function reads or writes it.
--
-- One transaction with guards: it aborts if any row holds a value, if anything other than that CHECK depends on the columns, or
-- if the result is not exactly the intended one. The row counts must not move.
--
-- Apply:    node_modules/.bin/supabase db query --linked --file db/migrations/2026-10-14-drop-owner-celiac.PENDING.sql
-- Dry run:  the same statements with the final `commit;` replaced by `rollback;`.
-- After applying: rename this file without ".PENDING".

begin;

create temp table _counts on commit drop as
select (select count(*) from public.suggestions) as suggestions, (select count(*) from public.place_reports) as place_reports;

-- 0. Guards.
do $$
declare n int;
begin
  select count(*) into n from information_schema.columns
   where table_schema = 'public' and column_name = 'owner_celiac' and table_name in ('suggestions', 'place_reports');
  if n <> 2 then raise exception 'guard: expected owner_celiac on suggestions and place_reports; found % column(s)', n; end if;

  select count(*) into n from information_schema.columns
   where column_name = 'owner_celiac' and not (table_schema = 'public' and table_name in ('suggestions', 'place_reports'));
  if n <> 0 then raise exception 'guard: owner_celiac exists in % other table(s)', n; end if;

  select (select count(*) from public.suggestions where owner_celiac is not null)
       + (select count(*) from public.place_reports where owner_celiac is not null) into n;
  if n <> 0 then raise exception 'guard: % row(s) hold an owner_celiac value; look at them before dropping', n; end if;

  -- Nothing but the one CHECK may depend on the columns (a view would block the drop; a function would break silently).
  select count(*) into n from pg_depend d
    join pg_attribute a on a.attrelid = d.refobjid and a.attnum = d.refobjsubid
   where a.attname = 'owner_celiac' and d.deptype <> 'a'
     and not (d.classid = 'pg_constraint'::regclass
              and d.objid = (select oid from pg_constraint where conname = 'place_reports_kitchen_positive_only_check'));
  if n <> 0 then raise exception 'guard: % unexpected object(s) depend on owner_celiac', n; end if;

  select count(*) into n from pg_proc where prosrc ilike '%owner_celiac%';
  if n <> 0 then raise exception 'guard: % function(s) mention owner_celiac', n; end if;
  select count(*) into n from pg_views where definition ilike '%owner_celiac%';
  if n <> 0 then raise exception 'guard: % view(s) mention owner_celiac', n; end if;
  select count(*) into n from pg_policies where coalesce(qual, '') ilike '%owner_celiac%' or coalesce(with_check, '') ilike '%owner_celiac%';
  if n <> 0 then raise exception 'guard: % policy(ies) mention owner_celiac', n; end if;
end $$;

-- 1. The reports CHECK names the column: recreate it without it (same rule for the two kitchen columns that stay).
alter table public.place_reports drop constraint place_reports_kitchen_positive_only_check;
alter table public.place_reports add constraint place_reports_kitchen_positive_only_check
  check (report_type = 'positive' or (kitchen_exclusive is null and celiac_prep is null));

-- 2. Drop the columns.
alter table public.suggestions   drop column owner_celiac;
alter table public.place_reports drop column owner_celiac;

-- 3. Assertions: any drift RAISES and rolls everything back.
do $$
declare n int;
begin
  select count(*) into n from information_schema.columns where column_name = 'owner_celiac';
  if n <> 0 then raise exception 'owner_celiac still exists in % table(s)', n; end if;

  if (select pg_get_constraintdef(oid) from pg_constraint where conname = 'place_reports_kitchen_positive_only_check')
     <> 'CHECK (((report_type = ''positive''::text) OR ((kitchen_exclusive IS NULL) AND (celiac_prep IS NULL))))'
     then raise exception 'place_reports_kitchen_positive_only_check is not the intended rule'; end if;

  if (select count(*) from public.suggestions) <> (select suggestions from _counts)
     or (select count(*) from public.place_reports) <> (select place_reports from _counts)
     then raise exception 'row counts changed'; end if;
end $$;

-- PostgREST reloads its schema cache on commit (the notification is delivered only if the transaction commits).
notify pgrst, 'reload schema';

commit;
