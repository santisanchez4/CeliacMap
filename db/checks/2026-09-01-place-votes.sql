-- =====================================================================
-- CeliacMap — db/checks/2026-09-01-place-votes.sql
-- Fase B verification of the ADR-005 place_votes schema (Fase A + the
-- SECURITY DEFINER fix). Pattern: db/fixes/*.sql, but non-destructive by
-- BEGIN; ... ROLLBACK; — leaves NO test data behind.
--
-- Run:
--   node_modules/.bin/supabase db query --linked \
--     --file db/checks/2026-09-01-place-votes.sql
--
-- Fixtures (real production rows, stable):
--   approved     = 00000000-0000-0000-0000-000000000001  ("Sin Gluten Pocitos", db/seed.sql)
--   needs_review = 985fd078-41b6-4839-a3ad-882df3dbf24a  (an out-of-scope place, not on the map)
-- =====================================================================
begin;

create temp table _r (n int, step text, detail text, pass boolean) on commit drop;

do $$
declare
  p_ok  uuid := '00000000-0000-0000-0000-000000000001';
  b int; a int;
begin
  -- 1. INSERT bumps places.vote_count (trigger AFTER INSERT)
  select vote_count into b from public.places where id = p_ok;
  insert into public.place_votes (place_id, voter_token) values (p_ok, 'chk-20260901-01');
  select vote_count into a from public.places where id = p_ok;
  insert into _r values (1, 'INSERT bumps places.vote_count', format('%s -> %s', b, a), a = b + 1);

  -- 2. DELETE decrements places.vote_count (trigger AFTER DELETE)
  delete from public.place_votes where place_id = p_ok and voter_token = 'chk-20260901-01';
  select vote_count into a from public.places where id = p_ok;
  insert into _r values (2, 'DELETE decrements places.vote_count', format('back to %s', a), a = b);

  -- 3. greatest(vote_count - 1, 0) guard: force vote_count below the true
  --    count, then DELETE must clamp at 0 instead of going negative.
  insert into public.place_votes (place_id, voter_token) values (p_ok, 'chk-20260901-guard');
  update public.places set vote_count = 0 where id = p_ok;      -- simulate drift
  delete from public.place_votes where place_id = p_ok and voter_token = 'chk-20260901-guard';
  select vote_count into a from public.places where id = p_ok;
  insert into _r values (3, 'greatest() guard: 0 - 1 clamps to 0', format('vote_count = %s', a), a = 0);

  -- 4. duplicate (place_id, voter_token) rejected by place_votes_place_voter_key
  insert into public.place_votes (place_id, voter_token) values (p_ok, 'chk-20260901-dup');
  begin
    insert into public.place_votes (place_id, voter_token) values (p_ok, 'chk-20260901-dup');
    insert into _r values (4, 'duplicate (place_id, voter_token) rejected', 'NO ERROR (bad)', false);
  exception when unique_violation then
    insert into _r values (4, 'duplicate (place_id, voter_token) rejected',
      format('%s unique_violation', sqlstate), true);
  end;
  delete from public.place_votes where place_id = p_ok and voter_token = 'chk-20260901-dup';
end $$;

-- 5. RLS: anon INSERT on a NON-approved place is rejected by the
--    "public can cast a vote" policy (exists(status='approved') fails).
do $$
declare estate text := ''; emsg text := ''; inserted boolean := false;
begin
  begin
    set local role anon;
    insert into public.place_votes (place_id, voter_token)
      values ('985fd078-41b6-4839-a3ad-882df3dbf24a', 'chk-20260901-rls-bad');
    inserted := true;
  exception when others then
    estate := sqlstate; emsg := sqlerrm;
  end;
  reset role;
  insert into _r values (5, 'RLS: anon vote on needs_review place rejected',
    case when inserted then 'INSERTED (bad)' else format('%s | %s', estate, emsg) end,
    not inserted);
end $$;

-- 6. Positive control: anon INSERT on an APPROVED place succeeds AND the
--    (SECURITY DEFINER) trigger bumps vote_count — the real anon path.
do $$
declare b int; a int; estate text := ''; emsg text := ''; ok boolean := false;
begin
  select vote_count into b from public.places where id = '00000000-0000-0000-0000-000000000001';
  begin
    set local role anon;
    insert into public.place_votes (place_id, voter_token)
      values ('00000000-0000-0000-0000-000000000001', 'chk-20260901-rls-ok');
    ok := true;
  exception when others then
    estate := sqlstate; emsg := sqlerrm;
  end;
  reset role;
  select vote_count into a from public.places where id = '00000000-0000-0000-0000-000000000001';
  insert into _r values (6, 'RLS: anon vote on approved place inserts + trigger bumps',
    case when ok then format('inserted; vote_count %s -> %s', b, a)
         else format('%s | %s', estate, emsg) end,
    ok and a = b + 1);
end $$;

select n, step, detail, case when pass then 'PASS' else 'FAIL' end as result
from _r order by n;

rollback;

-- =====================================================================
-- PostgREST contract smoke test — NOT SQL, run against the live REST API
-- on 2026-09-02 (persists real rows; cleaned up right after). URL / anon
-- key from js/config.js. Fixtures as above.
--
--   BASE=https://pgblbyvetclllaqvknvc.supabase.co/rest/v1
--   H='-H "apikey: $ANON" -H "Authorization: Bearer $ANON"'
--
-- FIRST tried the ADR/plan's dedup approach:
--   POST "$BASE/place_votes?on_conflict=place_id,voter_token"
--        -H "Prefer: return=minimal, resolution=ignore-duplicates"
--   -> HTTP 401, code 42501: "permission denied for table place_votes",
--      hint "GRANT SELECT ON public.place_votes TO anon".
--   PostgREST's upsert / on_conflict path requires SELECT on the table,
--   which we deliberately do NOT grant (place_votes must stay unreadable).
--   => `resolution=ignore-duplicates` is NOT usable here.
--
-- THEN the plain-POST approach (same shape as js/report.js -> place_reports):
--   POST "$BASE/place_votes"  -H "Prefer: return=minimal"
--        -d '{"place_id": "...", "voter_token": "..."}'
--
--   (a) new vote, approved place    -> HTTP 201, empty body
--   (b) EXACT same POST again       -> HTTP 409,
--         {"code":"23505", "message":"duplicate key value violates unique
--          constraint \"place_votes_place_voter_key\""}
--   (c) non-approved (needs_review) -> HTTP 401,
--         {"code":"42501", "message":"new row violates row-level security
--          policy for table \"place_votes\""}
--   (d) end-to-end: POST vote -> GET places?id=eq.<OK>&select=vote_count
--         went 0 -> 1 (SECURITY DEFINER trigger fires through the anon
--         PostgREST path); anon GET place_votes -> 401 42501 (unreadable).
--
--   cleanup (anon has no DELETE on place_votes; run as service_role):
--     delete from public.place_votes where voter_token like 'curl-%20260901%';
--   -> place_votes back to 0 rows, all places.vote_count back to 0
--      (DELETE trigger decrements).
--
-- DEDUP VERDICT: NOT a silent server no-op. A duplicate returns HTTP 409 /
--   Postgres 23505. `resolution=ignore-duplicates` can't be used (needs a
--   SELECT grant we won't give).
--
-- -> ranking.js (Fase C): plain POST to /place_votes, and treat the 409
--    explicitly as success ("ya votaste"):
--      if (res.ok || res.status === 409) { markVotedLocally(); showThanks(); }
--      else { showGenericError(); }   // e.g. the 401/42501 on a bad place
--    The localStorage voted-set still prevents most repeat POSTs; the 409
--    is the server-side backstop. A non-approved place_id yields 401/42501
--    but the vote button only ever renders for approved ranking/panel rows.
-- =====================================================================
