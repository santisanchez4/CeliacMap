-- One-off data correction — a social profile is not a website: 190 rows carry one in `website`.
--
-- Google's "website" field is often the business's Instagram / Facebook / WhatsApp / link-in-bio page, and Search and the Updater stored it in
-- `website` as it came (MOOY Real Café: https://www.instagram.com/mooyrealcafe/). Fixed at the root on 2026-10-01: `extract_rich_fields`
-- hands such a URL out as `social_url`, and Search / the Updater write it only when the row has none (agents/clients/google_places.py).
-- This script brings the existing rows to the same rule. The host list is SOCIAL_DOMAINS (agents/clients/website_scraper.py): instagram.com,
-- facebook.com, wa.me, whatsapp.com, linktr.ee, beacons.ai, tiktok.com.
--
--   188 rows with an empty social_url: the profile moves to `social_url`, `website` becomes NULL.
--     2 rows that already have a social_url: `website` becomes NULL and `social_url` is kept:
--       La Panadería de Ramona (website = social_url, the same Facebook page; nothing is lost)
--       CROC Galletas Artesanales (social_url = its Instagram; the Facebook page in `website` is dropped)
--
-- Only `website` and `social_url` change (and updated_at, by its trigger). No note header: this moves a link, not a decision about a place.
-- None of the 190 is a single post / reel link (checked 2026-10-01), so every moved URL is a profile, a channel or a chat link.
--
-- Run (one transaction, all-or-nothing; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-01-social-profile-out-of-website.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.
-- Idempotent: after it no `website` matches the rule, so a second run aborts at the count assertion.

begin;

create temp table _snap on commit drop as
select id, website, social_url, md5((to_jsonb(p) - 'website' - 'social_url' - 'updated_at')::text) as h from public.places p;

create temp table _social on commit drop as
select id from public.places
where website ~* '^(https?://)?([a-z0-9-]+\.)*(instagram\.com|facebook\.com|wa\.me|whatsapp\.com|linktr\.ee|beacons\.ai|tiktok\.com)([/?#]|$)';

do $$
declare n int;
begin
  if (select count(*) from _social) <> 190 then
    raise exception 'esperaba 190 filas con un perfil de redes en website, hay %', (select count(*) from _social);
  end if;

  update public.places p
     set social_url = p.website, website = null
   where p.id in (select id from _social) and p.social_url is null;
  get diagnostics n = row_count;
  if n <> 188 then raise exception 'esperaba mover 188 perfiles a social_url, moví %', n; end if;

  update public.places p
     set website = null
   where p.id in (select id from _social) and p.website is not null;
  get diagnostics n = row_count;
  if n <> 2 then raise exception 'esperaba vaciar website en 2 filas que ya tenían social_url, vacié %', n; end if;
end $$;

do $$
declare bad int;
begin
  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'website' - 'social_url' - 'updated_at')::text) <> s.h;
  if bad <> 0 then raise exception 'cambió algo fuera de website / social_url / updated_at en % filas', bad; end if;

  select count(*) into bad from public.places p join _snap s using (id)
   where p.website is distinct from s.website or p.social_url is distinct from s.social_url;
  if bad <> 190 then raise exception 'esperaba exactamente 190 filas cambiadas, encontré %', bad; end if;

  -- every changed row: website emptied; social_url is the old website, or the social_url it already had
  select count(*) into bad from public.places p join _snap s using (id)
   where (p.website is distinct from s.website or p.social_url is distinct from s.social_url)
     and (p.website is not null or p.social_url is distinct from coalesce(s.social_url, s.website));
  if bad <> 0 then raise exception '% filas donde social_url no es el perfil esperado o website no quedó vacío', bad; end if;

  select count(*) into bad from public.places
   where website ~* '^(https?://)?([a-z0-9-]+\.)*(instagram\.com|facebook\.com|wa\.me|whatsapp\.com|linktr\.ee|beacons\.ai|tiktok\.com)([/?#]|$)';
  if bad <> 0 then raise exception 'quedan % filas con un perfil de redes en website', bad; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'cambió la cantidad de lugares'; end if;
end $$;

commit;

-- =============================================================================================
-- VERIFICATION (read-only) — run AFTER the commit above, as a single statement. Every row ok = true.
-- =============================================================================================
select check_name, expected, actual, (expected = actual) as ok from (
  select 1 as n, 'rows with a social profile in website' as check_name, 0 as expected,
         (select count(*)::int from public.places
           where website ~* '^(https?://)?([a-z0-9-]+\.)*(instagram\.com|facebook\.com|wa\.me|whatsapp\.com|linktr\.ee|beacons\.ai|tiktok\.com)([/?#]|$)') as actual
  union all
  select 2, 'MOOY Real Café: Instagram in social_url, website empty', 1,
         (select count(*)::int from public.places
           where id = '1495da11-3fd4-4883-92a5-7bc966d576f8' and website is null
             and social_url = 'https://www.instagram.com/mooyrealcafe/')
) c order by n;
