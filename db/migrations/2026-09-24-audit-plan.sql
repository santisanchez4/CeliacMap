-- Audit plan 2026-09-24 (docs/plans/PLAN-auditoria-2026-09-24.md) — every schema change in one file.
-- Copied from db/schema.sql (the source of truth); idempotent, safe to run twice.
-- Apply: node_modules/.bin/supabase db query --linked --file db/migrations/2026-09-24-audit-plan.sql
-- (or paste it in the Supabase SQL Editor). Wrapped in a transaction: all or nothing.
begin;

-- SUGGESTION-NEEDS-LOCATION-BEGIN
-- Audit plan step 8: a suggestion whose address could not be placed waits for the admin
-- instead of being rejected silently. Widens the inline CHECK above for databases created
-- before this value existed (the anon INSERT policy still forces status='new').
do $$
begin
  alter table public.suggestions drop constraint if exists suggestions_status_check;
  alter table public.suggestions
    add constraint suggestions_status_check
    check (status in ('new', 'promoted', 'rejected', 'duplicate', 'needs_location'));
end $$;
-- SUGGESTION-NEEDS-LOCATION-END

-- COMMUNITY-WARNING-BEGIN
-- Audit plan step 7 (owner decision 2026-09-24). One or two distinct negative reports in 30
-- days keep a place on the map with a public "reportado por la comunidad" warning; the third
-- (or one credible contamination report) sends it to needs_review. community_warning_at is
-- when the last warning was set; the frontend shows it for 30 days. It says only that a report
-- exists — the report text is never public.
alter table public.places add column if not exists community_warning_at timestamptz;
-- One anonymous id per browser (like place_votes.voter_token), so "distinct reports" can be
-- counted. Optional: the chatbot and older rows carry none and count one by one.
alter table public.place_reports add column if not exists reporter_token text;
do $$
begin
  alter table public.place_reports drop constraint if exists place_reports_reporter_token_check;
  alter table public.place_reports
    add constraint place_reports_reporter_token_check
    check (reporter_token is null or char_length(reporter_token) between 8 and 64);
end $$;
create index if not exists place_reports_negative_recent_idx
  on public.place_reports (place_id, created_at) where report_type = 'negative';
-- COMMUNITY-WARNING-END

-- PLACE-EVIDENCE-BEGIN
-- ---------------------------------------------------------------------
-- Table: place_evidence  (audit plan 2026-09-24, step 1)
-- ---------------------------------------------------------------------
-- The text a discovery agent or a person gave us about a place: the Instagram /
-- Facebook snippet (Social), the "why is this GF" sentence + URL (Web), the note +
-- link from the suggest form (user), or the admin's own evidence (admin). The
-- Validator reads it and nothing ever overwrites it (validation_notes is rewritten on
-- every validation, so evidence kept there was lost). SERVER-ONLY: it can carry
-- unverified claims and third-party details, and places is publicly readable.
create table if not exists public.place_evidence (
  id         uuid primary key default gen_random_uuid(),
  place_id   uuid not null references public.places(id) on delete cascade,
  source     text not null
               check (source in ('social', 'web', 'user', 'admin')),
  text       text
               check (text is null or char_length(text) between 1 and 1000),
  url        text
               check (url is null or char_length(url) <= 500),
  created_at timestamptz not null default now(),
  constraint place_evidence_has_content check (text is not null or url is not null)
);
create index if not exists place_evidence_place_id_idx on public.place_evidence (place_id);
-- PLACE-EVIDENCE-END

do $$
begin
  alter table public.agent_log drop constraint if exists agent_log_agent_check;
  alter table public.agent_log
    add constraint agent_log_agent_check
    check (agent in
      ('search', 'validator', 'updater', 'social', 'web', 'pipeline', 'suggestion',
       'outreach', 'outreach_reply', 'review_handler', 'chatbot', 'admin_notify'));
end $$;

-- place_evidence is server-only (same as agent_log).
alter table public.place_evidence enable row level security;
revoke all on public.place_evidence from anon, authenticated;

commit;
