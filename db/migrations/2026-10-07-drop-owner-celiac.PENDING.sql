-- NOT APPLIED. Stage 3 of docs/legal/owner-celiac-plan.md: drop suggestions.owner_celiac and
-- place_reports.owner_celiac. Run no earlier than 2026-10-07: one week after the later of the two deploys
-- (frontend without the owner question: Pages, 2026-09-29; chat v23 that discards it: 2026-09-30 01:14 UTC).
-- A page cached before that could still
-- send owner_celiac, and PostgREST rejects an INSERT with an unknown column (the whole suggestion is lost).
-- Before running: show it, rehearse it (begin; ... rollback;), wait for the owner's "dale".
-- After running: rename this file without ".PENDING", update db/schema.sql (KITCHEN-DECLARATIONS block
-- and its comments, the place_reports_kitchen_positive_only_check CHECK) and tests/test_schema_kitchen_checks.py.
-- Apply: node_modules/.bin/supabase db query --linked --file db/migrations/2026-10-07-drop-owner-celiac.PENDING.sql

-- 0) Read-only check first (2026-09-29: 0 and 0). Anything above 0 is looked at before going on.
select (select count(*) from public.suggestions   where owner_celiac is not null) as suggestions_with_owner,
       (select count(*) from public.place_reports where owner_celiac is not null) as reports_with_owner;

begin;

-- 1) Erase whatever is stored (expected: 0 rows each).
update public.suggestions   set owner_celiac = null where owner_celiac is not null;
update public.place_reports set owner_celiac = null where owner_celiac is not null;

-- 2) The reports CHECK names the column: recreate it without it.
alter table public.place_reports drop constraint if exists place_reports_kitchen_positive_only_check;
alter table public.place_reports add constraint place_reports_kitchen_positive_only_check
  check (report_type = 'positive' or (kitchen_exclusive is null and celiac_prep is null));

-- 3) Drop the columns.
alter table public.suggestions   drop column if exists owner_celiac;
alter table public.place_reports drop column if exists owner_celiac;

commit;

notify pgrst, 'reload schema';

-- 4) Read-only verification: must return 0 rows.
select table_name, column_name from information_schema.columns
where table_schema = 'public' and column_name = 'owner_celiac';
