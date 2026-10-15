-- Public privilege checks, run AS anon inside one transaction that ALWAYS aborts: the block ends with RAISE EXCEPTION,
-- so the test rows (one suggestion, one vote) and anything else it touched are rolled back, whatever happens.
-- The message carries the result: "PUBLIC-GRANTS PASSED" or "PUBLIC-GRANTS FAILED", then one item per check.
-- place_reports is checked by privilege only: production has a webhook trigger on its INSERT.
do $$
declare
  out text := '';
  bad int := 0;
  n int;
  pid uuid;
begin
  select id into pid from public.places where status = 'approved' order by id limit 1;
  execute 'set local role anon';

  -- The site, the ranking and the chat read these columns of approved places.
  select count(*) into n from (
    select id, name, lat, lng, category, country, city, region, address, safety_level, status, source, phone,
           website, opening_hours, social_url, rating, user_ratings_total, vote_count, community_warning_at
    from public.places where status = 'approved' limit 5) s;
  if n > 0 then out := out || 'places read ok; '; else out := out || 'places read EMPTY; '; bad := bad + 1; end if;

  begin
    perform contact_email from public.places limit 1;
    out := out || 'places.contact_email READABLE; '; bad := bad + 1;
  exception when insufficient_privilege then out := out || 'places.contact_email denied; ';
  end;

  perform 1 from public.community_opinions limit 1;
  out := out || 'community_opinions read ok; ';

  insert into public.suggestions (name, address, city, country, origin)
  values ('Ensayo de permisos', 'Calle de ensayo 1', 'Fray Bentos', 'Uruguay', 'community');
  out := out || 'suggestions insert ok; ';

  insert into public.place_votes (place_id, voter_token, source)
  values (pid, 'grants-rehearsal-2026-10-15', 'community');
  out := out || 'place_votes insert ok; ';

  if has_table_privilege('anon', 'public.place_reports', 'INSERT')
     and not has_table_privilege('anon', 'public.place_reports', 'SELECT') then
    out := out || 'place_reports insert-only ok; ';
  else
    out := out || 'place_reports privileges WRONG; '; bad := bad + 1;
  end if;

  begin
    perform 1 from public.suggestions limit 1;
    out := out || 'suggestions READABLE; '; bad := bad + 1;
  exception when insufficient_privilege then out := out || 'suggestions read denied; ';
  end;

  -- An INSERT blocked by RLS raises the same SQLSTATE (42501) as a missing privilege: ask for the privilege itself.
  if has_table_privilege('anon', 'public.reviews', 'INSERT') or has_table_privilege('anon', 'public.reviews', 'UPDATE')
     or has_table_privilege('anon', 'public.reviews', 'DELETE') then
    out := out || 'reviews INSERT/UPDATE/DELETE granted; '; bad := bad + 1;
  else
    out := out || 'reviews insert/update/delete not granted; ';
  end if;

  -- TRUNCATE is not stopped by RLS: try it for real (this transaction aborts anyway).
  begin
    execute 'truncate public.reviews';
    out := out || 'reviews TRUNCATE allowed; '; bad := bad + 1;
  exception when insufficient_privilege then out := out || 'reviews truncate denied; ';
  end;

  execute 'reset role';
  select count(*) into n
  from information_schema.role_table_grants
  where table_schema = 'public' and grantee in ('anon', 'authenticated')
    and privilege_type in ('UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER');
  if n = 0 then out := out || 'no update/delete/truncate/references/trigger grants; ';
  else out := out || n || ' update/delete/truncate/references/trigger grants LEFT; '; bad := bad + 1; end if;

  raise exception 'PUBLIC-GRANTS % (rolled back): %', case when bad = 0 then 'PASSED' else 'FAILED' end, out;
end $$;
