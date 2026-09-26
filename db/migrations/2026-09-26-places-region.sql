-- places.region (department / province) — schema change of 2026-09-26.
-- Copied from db/schema.sql (the source of truth); idempotent, safe to run twice.
-- Apply: node_modules/.bin/supabase db query --linked --file db/migrations/2026-09-26-places-region.sql
-- Then backfill the existing rows: db/fixes/2026-09-26-places-region-backfill.sql
-- Apply this BEFORE deploying agent code that writes `region` (an upsert with an unknown column fails).
begin;

alter table public.places add column if not exists region text;

commit;
