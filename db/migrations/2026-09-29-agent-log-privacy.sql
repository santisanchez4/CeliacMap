-- agent_log.agent accepts 'privacy' (privacy phase 1, 2026-09-29): scripts/delete_personal_data.py records
-- each deletion request it answers there. Copied from db/schema.sql; idempotent, safe to run twice.
-- Apply: node_modules/.bin/supabase db query --linked --file db/migrations/2026-09-29-agent-log-privacy.sql
begin;

alter table public.agent_log drop constraint if exists agent_log_agent_check;
alter table public.agent_log
  add constraint agent_log_agent_check
  check (agent in
    ('search', 'validator', 'updater', 'social', 'web', 'pipeline', 'suggestion',
     'outreach', 'outreach_reply', 'review_handler', 'chatbot', 'admin_notify', 'privacy'));

commit;
