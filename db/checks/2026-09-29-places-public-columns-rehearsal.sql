-- Rehearsal of db/migrations/2026-09-29-places-public-columns.sql: applies it inside a
-- transaction, checks it AS the anon role, and ROLLS BACK. Nothing persists (the test vote too).
-- Run: node_modules/.bin/supabase db query --linked --file db/checks/2026-09-29-places-public-columns-rehearsal.sql
begin;

revoke all on public.places from anon, authenticated;
grant select (
  id, name, lat, lng, category, country, city, region, address, safety_level, status, source,
  phone, website, opening_hours, social_url, rating, user_ratings_total, vote_count,
  community_warning_at
) on public.places to anon, authenticated;

set local role anon;

-- A community vote still passes the place_votes WITH CHECK (it reads places.id / places.status as anon).
insert into public.place_votes (place_id, voter_token)
  values ((select id from public.places where status = 'approved' order by id limit 1), 'rehearsal-privacy-2026-09-29');

select
  (select count(*) from (select id, name, lat, lng, category, city, safety_level, address, source, phone, website,
          opening_hours, social_url, rating, user_ratings_total, community_warning_at
          from public.places where status = 'approved') m) as anon_map_rows,
  (select count(*) from (select id, name, city, country, region, vote_count from public.places
          where status = 'approved' and region is not null) c) as anon_chat_rows,
  (select count(*) from public.community_opinions) as anon_opinions_rows,
  (select string_agg(attname, ',' order by attname) from pg_attribute
     where attrelid = 'public.places'::regclass and attnum > 0 and not attisdropped
       and has_column_privilege('anon', 'public.places', attname, 'SELECT')) as anon_select_columns,
  (select count(*) from pg_attribute
     where attrelid = 'public.places'::regclass and attnum > 0 and not attisdropped
       and has_column_privilege('anon', 'public.places', attname, 'SELECT')) as anon_select_count,
  (select string_agg(attname, ',' order by attname) from pg_attribute
     where attrelid = 'public.places'::regclass and attnum > 0 and not attisdropped
       and not has_column_privilege('anon', 'public.places', attname, 'SELECT')) as anon_denied_columns,
  has_table_privilege('anon', 'public.places', 'INSERT')   as anon_insert,
  has_table_privilege('anon', 'public.places', 'UPDATE')   as anon_update,
  has_table_privilege('anon', 'public.places', 'DELETE')   as anon_delete,
  has_table_privilege('anon', 'public.places', 'TRUNCATE') as anon_truncate,
  has_column_privilege('authenticated', 'public.places', 'contact_email', 'SELECT') as authenticated_contact_email;

rollback;
