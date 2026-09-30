-- Cleanup of the chat test turns of 2026-09-29/30 (privacy phase 1): the smoke-test turn of the column grant
-- (00:27 UTC) and the two turns that verified chat v23 (01:14 UTC). Baseline before any test that UTC day: 0
-- chat_usage rows for 2026-09-30 and 100 chatbot agent_log rows. Every delete is guarded: if a row count or a
-- counter differs from what the tests wrote (for instance, real traffic in between), it raises and nothing is kept.
begin;

do $$
declare n int;
begin
  -- The two test sessions (fixed tokens 'celiac-test-privacy-…').
  delete from public.chat_usage
   where day = '2026-09-30' and bucket_key like 'session:celiac-test-privacy-%';
  get diagnostics n = row_count;
  if n <> 2 then raise exception 'test sessions: expected 2 rows, got %', n; end if;

  -- The IP buckets of this machine: the old unkeyed SHA-256 (1 turn) and the new HMAC (2 turns).
  delete from public.chat_usage
   where day = '2026-09-30'
     and ((bucket_key like 'ip:7cbfad721%' and count = 1) or (bucket_key like 'ip:dc1d87d62%' and count = 2));
  get diagnostics n = row_count;
  if n <> 2 then raise exception 'ip buckets: expected 2 rows with counts 1 and 2, got %', n; end if;

  -- The global counter: the 3 test turns are all it holds (baseline 0).
  delete from public.chat_usage where day = '2026-09-30' and bucket_key = 'global' and count = 3;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'global: expected 1 row with count 3, got %', n; end if;

  -- The three chat_turn log rows of the tests.
  delete from public.agent_log
   where agent = 'chatbot'
     and id in ('481ce461-dac0-41b2-8ff5-77f1144a0754', 'fc904aef-cd5f-4ca1-b456-5236abd5ffb2',
                '47355292-9fc4-4582-85a4-770108cfbc90');
  get diagnostics n = row_count;
  if n <> 3 then raise exception 'agent_log: expected 3 rows, got %', n; end if;
end $$;

commit;

-- Read-only verification against the baseline: 0 and 100.
select (select count(*) from public.chat_usage where day = '2026-09-30') as usage_today,
       (select count(*) from public.agent_log where agent = 'chatbot') as chat_logs;
