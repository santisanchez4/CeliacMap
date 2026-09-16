-- =====================================================================
-- CeliacMap — db/checks/2026-09-16-chat-usage.sql
-- Fase A verification of chat_usage + bump_chat_usage (ADR-006 decision 2b,
-- docs/plans/PLAN-chatbot-rag.md). Pattern: db/checks/2026-09-01-place-votes.sql
-- — non-destructive via BEGIN; ... ROLLBACK; leaves NO test data behind.
--
-- Run:
--   node_modules/.bin/supabase db query --linked \
--     --file db/checks/2026-09-16-chat-usage.sql
--
-- Same lesson as sync_place_vote_count (see the CREATE TRIGGER comment in
-- db/schema.sql): a SECURITY DEFINER function that "compiles" and works when
-- called as the connecting owner role can still behave differently for the
-- real caller. Here the real caller is TWO roles, both tested explicitly by
-- switching into them with `set local role`, not assumed from reading the code:
--   - service_role — the chat Edge Function's actual caller. Must succeed.
--   - anon / authenticated — must be REJECTED. Left ungranted, either could
--     call bump_chat_usage directly via POST /rest/v1/rpc/bump_chat_usage
--     (Supabase auto-exposes it) and pre-exhaust the shared 'global' bucket,
--     denying the chat to everyone — bypassing the Edge Function's actual
--     rate-limit-then-bump order entirely. Postgres grants EXECUTE on new
--     functions to PUBLIC by default, so this is not hypothetical without
--     the explicit revoke in db/schema.sql.
-- =====================================================================
begin;

create temp table _r (n int, step text, detail text, pass boolean) on commit drop;

-- 1. bump_chat_usage as service_role (the real caller), called twice for the
--    same keys/day: the ON CONFLICT upsert must increment, not reset to 1.
do $$
declare
  d date := current_date;
  c1 int; c2 int;
begin
  set local role service_role;
  perform public.bump_chat_usage(
    array['session:chk-20260916-a', 'ip:chk-20260916-a', 'global'], d);
  perform public.bump_chat_usage(
    array['session:chk-20260916-a', 'ip:chk-20260916-a', 'global'], d);
  reset role;
  select count into c1 from public.chat_usage where bucket_key = 'session:chk-20260916-a' and day = d;
  select count into c2 from public.chat_usage where bucket_key = 'global' and day = d;
  insert into _r values (1, 'bump_chat_usage as service_role: 2 calls -> count=2 per key',
    format('session=%s global=%s', c1, c2), c1 = 2 and c2 = 2);
end $$;

-- 2. bump_chat_usage as service_role, one call bumping multiple distinct
--    keys at once (the actual per-turn shape: session + ip + global together).
do $$
declare d date := current_date; c1 int; c2 int;
begin
  set local role service_role;
  perform public.bump_chat_usage(array['session:chk-20260916-b', 'session:chk-20260916-c'], d);
  reset role;
  select count into c1 from public.chat_usage where bucket_key = 'session:chk-20260916-b' and day = d;
  select count into c2 from public.chat_usage where bucket_key = 'session:chk-20260916-c' and day = d;
  insert into _r values (2, 'bump_chat_usage: one call bumps multiple distinct keys',
    format('b=%s c=%s', c1, c2), c1 = 1 and c2 = 1);
end $$;

-- 3. RLS: anon cannot SELECT chat_usage directly (no grant, no policy).
do $$
declare estate text := ''; emsg text := ''; leaked boolean := false;
begin
  begin
    set local role anon;
    perform 1 from public.chat_usage limit 1;
    leaked := true;
  exception when others then
    estate := sqlstate; emsg := sqlerrm;
  end;
  reset role;
  insert into _r values (3, 'RLS: anon SELECT on chat_usage rejected',
    case when leaked then 'READABLE (bad)' else format('%s | %s', estate, emsg) end,
    not leaked);
end $$;

-- 4. RLS: anon cannot INSERT into chat_usage directly.
do $$
declare estate text := ''; emsg text := ''; inserted boolean := false;
begin
  begin
    set local role anon;
    insert into public.chat_usage (bucket_key, day, count)
      values ('chk-20260916-anon-direct', current_date, 1);
    inserted := true;
  exception when others then
    estate := sqlstate; emsg := sqlerrm;
  end;
  reset role;
  insert into _r values (4, 'RLS: anon direct INSERT on chat_usage rejected',
    case when inserted then 'INSERTED (bad)' else format('%s | %s', estate, emsg) end,
    not inserted);
end $$;

-- 5. EXECUTE: anon CANNOT call bump_chat_usage via RPC. This is the real
--    griefing vector the explicit revoke in db/schema.sql closes — without
--    it, PUBLIC's default EXECUTE grant would let anon reach this function
--    straight from PostgREST (POST /rest/v1/rpc/bump_chat_usage).
do $$
declare estate text := ''; emsg text := ''; called boolean := false;
begin
  begin
    set local role anon;
    perform public.bump_chat_usage(array['global'], current_date);
    called := true;
  exception when others then
    estate := sqlstate; emsg := sqlerrm;
  end;
  reset role;
  insert into _r values (5, 'EXECUTE: anon cannot call bump_chat_usage directly',
    case when called then 'CALLED (bad)' else format('%s | %s', estate, emsg) end,
    not called and estate = '42501');
end $$;

-- 6. EXECUTE: authenticated is ALSO blocked. Auth is deferred project-wide,
--    but the revoke names 'authenticated' defensively -- confirm it actually
--    holds rather than assume it from the same line that already covers anon.
do $$
declare estate text := ''; emsg text := ''; called boolean := false;
begin
  begin
    set local role authenticated;
    perform public.bump_chat_usage(array['global'], current_date);
    called := true;
  exception when others then
    estate := sqlstate; emsg := sqlerrm;
  end;
  reset role;
  insert into _r values (6, 'EXECUTE: authenticated cannot call bump_chat_usage directly',
    case when called then 'CALLED (bad)' else format('%s | %s', estate, emsg) end,
    not called and estate = '42501');
end $$;

select n, step, detail, case when pass then 'PASS' else 'FAIL' end as result
from _r order by n;

rollback;
