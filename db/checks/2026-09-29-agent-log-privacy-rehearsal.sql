-- Rehearsal of db/migrations/2026-09-29-agent-log-privacy.sql: applies it, inserts one 'privacy' row,
-- checks that every existing row still passes and ROLLS BACK. Nothing persists.
begin;

alter table public.agent_log drop constraint if exists agent_log_agent_check;
alter table public.agent_log
  add constraint agent_log_agent_check
  check (agent in
    ('search', 'validator', 'updater', 'social', 'web', 'pipeline', 'suggestion',
     'outreach', 'outreach_reply', 'review_handler', 'chatbot', 'admin_notify', 'privacy'));

insert into public.agent_log (agent, action, result, status)
  values ('privacy', 'personal_data_deleted', '{"request": "rehearsal"}', 'success');

select
  (select count(*) from public.agent_log where agent = 'privacy') as privacy_rows,
  (select count(*) from public.agent_log) as total_rows,
  (select pg_get_constraintdef(oid) from pg_constraint where conname = 'agent_log_agent_check') as check_def;

rollback;
