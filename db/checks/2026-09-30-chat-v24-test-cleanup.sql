-- Cleanup of the chat v24 test (2026-09-30 02:44 UTC: "recommend a new place" up to the draft, never sent).
-- Baseline before the test (02:43:19 UTC): 0 chat_usage rows for 2026-09-30, 58 chat_usage rows in total, 100 chatbot
-- agent_log rows, 2 suggestions, 2 place_reports. Every delete is guarded: a different count (for instance, real traffic
-- in between) raises and nothing is kept.
begin;

do $$
declare n int;
begin
  delete from public.chat_usage
   where day = '2026-09-30' and bucket_key = 'session:celiac-test-privacy-kitchen-20260930' and count = 4;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'test session: expected 1 row with count 4, got %', n; end if;

  delete from public.chat_usage where day = '2026-09-30' and bucket_key like 'ip:dc1d87d62%' and count = 4;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'ip bucket: expected 1 row with count 4, got %', n; end if;

  delete from public.chat_usage where day = '2026-09-30' and bucket_key = 'global' and count = 4;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'global: expected 1 row with count 4, got %', n; end if;

  delete from public.agent_log
   where agent = 'chatbot'
     and id in ('b93ce17e-bc00-4e17-8699-e786ed279184', '89c21530-f547-4056-985c-26738facc332',
                'dd44d010-1261-4b99-b983-f787438d4c19', '03ed423f-2841-4e3e-b54e-5cc92327f4c4');
  get diagnostics n = row_count;
  if n <> 4 then raise exception 'agent_log: expected 4 rows, got %', n; end if;
end $$;

commit;

-- Read-only verification against the baseline: 0, 58, 100, 2, 2.
select (select count(*) from public.chat_usage where day = '2026-09-30') as usage_today,
       (select count(*) from public.chat_usage) as usage_rows,
       (select count(*) from public.agent_log where agent = 'chatbot') as chat_logs,
       (select count(*) from public.suggestions) as sugg,
       (select count(*) from public.place_reports) as reps;
