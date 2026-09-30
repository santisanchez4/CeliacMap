-- EMERGENCY REVERT of 2026-09-29-places-public-columns.sql: only if the public site breaks.
-- Restores the table-wide SELECT the public roles had before (contact_email etc. readable again).
-- Apply: node_modules/.bin/supabase db query --linked --file db/migrations/2026-09-29-places-public-columns-revert.sql
grant select on public.places to anon, authenticated;
notify pgrst, 'reload schema';
