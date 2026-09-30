-- places: public read as a column allowlist (privacy phase 1, 2026-09-29).
-- Copied from db/schema.sql (the source of truth); idempotent, safe to run twice.
-- Apply: node_modules/.bin/supabase db query --linked --file db/migrations/2026-09-29-places-public-columns.sql
-- Verify afterwards (read-only): python db/checks/places_public_columns_smoke.py
begin;

-- PLACES-PUBLIC-COLUMNS-BEGIN
-- places: the public read is a COLUMN allowlist (privacy phase 1, 2026-09-29). The anon key is
-- public, and places also holds business contact data and internal review columns
-- (contact_email, contact_email_checked_at, outreach_*, validation_notes, validation_confidence,
-- flags, recommendation, external_id, verified, geocode_method, created_at, updated_at): none of
-- them is granted. The list is exactly what the public readers select, filter or order by:
-- js/map.js, js/ranking.js, js/report.js and the chat Edge Function (anon key). id and status are
-- also read by the place_votes WITH CHECK subquery, which runs as anon. community_opinions runs
-- with its owner's rights and is not affected. tests/test_places_public_columns.py keeps this list
-- and the readers in step. A new public column needs a grant here (and a migration).
revoke all on public.places from anon, authenticated;
grant select (
  id, name, lat, lng, category, country, city, region, address, safety_level, status, source,
  phone, website, opening_hours, social_url, rating, user_ratings_total, vote_count,
  community_warning_at
) on public.places to anon, authenticated;
-- PLACES-PUBLIC-COLUMNS-END

commit;

-- PostgREST caches the schema; reload it so the new privileges are seen right away.
notify pgrst, 'reload schema';
