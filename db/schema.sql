-- =====================================================================
-- CeliacMap — db/schema.sql
-- Supabase (PostgreSQL). Run in the Supabase SQL Editor.
-- Idempotent: safe to re-run (uses IF NOT EXISTS / DROP POLICY IF EXISTS).
--
-- Security model:
--   * Frontend uses the public ANON key and may only read APPROVED places.
--     No anon writes; no anon access to logs. reviews is server-only (Google
--     Places ToS -- see CLAUDE.md Decisions Log "Google Places reviews").
--   * Python agents use the SERVICE_ROLE key (server-side only), which
--     bypasses RLS, to insert candidates, change status and write logs.
-- =====================================================================

-- gen_random_uuid() lives in pgcrypto (preinstalled on Supabase).
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- Table: places
-- ---------------------------------------------------------------------
create table if not exists public.places (
  id                    uuid primary key default gen_random_uuid(),
  name                  text not null,
  lat                   double precision not null,
  lng                   double precision not null,
  category              text not null
                          check (category in ('restaurant', 'cafe', 'shop')),
  country               text not null,
  city                  text,
  safety_level          text not null
                          check (safety_level in
                            ('gluten_free_100', 'celiac_friendly', 'options_available')),
  verified              boolean not null default false,
  -- Agent flow: search inserts 'pending'; validator sets
  -- 'approved'/'rejected'(=discarded)/'needs_review'; the frontend shows only
  -- 'approved'. 'needs_review' is the human-review queue (held back from the map
  -- when the validator's confidence is below the 0.7 safety floor).
  status                text not null default 'pending'
                          check (status in
                            ('pending', 'approved', 'discarded', 'needs_review')),
  address               text,
  source                text not null default 'manual'
                          check (source in ('google_places', 'manual', 'user', 'social', 'web')),
  external_id           text,                 -- e.g. Google place_id (for dedup)
  validation_confidence numeric,              -- validator output: confidence_score (0..1)
  validation_notes      text,                 -- validator rationale: reasoning
  -- Validator rubric output (adopted Jun 2026): alert signals detected and the
  -- concrete action suggested for a human operator. See the Validator rubric in
  -- CLAUDE.md / skills/validator-rubric/SKILL.md.
  flags                 jsonb,                -- list of detected alert flags
  recommendation        text,                 -- suggested operator action
  -- Discovery agents (Social v2, Web v3) keep the originating profile / source
  -- URL here so the Validator (which overwrites validation_notes) can't clobber it.
  social_url            text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- Deduplication: a given external source id appears at most once.
-- A FULL (non-partial) unique constraint is required so the agents' upsert can
-- use ON CONFLICT (source, external_id) — PostgreSQL cannot infer a partial
-- index without its WHERE predicate, which PostgREST/supabase-py do not send.
-- Multiple manual rows with external_id = NULL stay allowed, because NULLs are
-- treated as distinct in a multi-column unique key.
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'places_source_external_id_key'
  ) then
    -- Drop the legacy partial index if a previous schema created it.
    drop index if exists public.places_source_external_id_key;
    alter table public.places
      add constraint places_source_external_id_key unique (source, external_id);
  end if;
end $$;

create index if not exists places_status_idx        on public.places (status);
create index if not exists places_category_idx      on public.places (category);
create index if not exists places_country_city_idx  on public.places (country, city);

-- Allow places discovered by the Social agent (source='social') and the Web
-- discovery agent (source='web'). On an already-created table the inline check
-- above is a no-op, so widen it in place.
do $$
begin
  alter table public.places drop constraint if exists places_source_check;
  alter table public.places
    add constraint places_source_check
    check (source in ('google_places', 'manual', 'user', 'social', 'web'));
end $$;

-- The discovery agents store the originating source URL in its own column so the
-- Validator's validation_notes update can't overwrite it. Added idempotently for
-- databases created before this column existed.
alter table public.places add column if not exists social_url text;

-- The Validator now also persists its detected flags and suggested operator
-- action. Added idempotently for databases created before these columns existed.
alter table public.places add column if not exists flags jsonb;
alter table public.places add column if not exists recommendation text;

-- How a discovery agent (Social / Web / Suggestion promoter) resolved this
-- candidate's coordinates. 'find_place' = matched a real Google Place (a
-- business). 'address_only' = Find Place found no business, but the street
-- address geocoded to a real point in UY/AR (the place_id is the address, not a
-- business — the Validator treats this as weaker evidence). NULL for rows
-- predating this column and for the Search agent (always a real Google Place).
alter table public.places add column if not exists geocode_method text
  check (geocode_method is null or geocode_method in ('find_place', 'address_only'));

-- Rich Place Details fields the Search agent already fetches per candidate
-- (agents/clients/google_places.py DEFAULT_DETAIL_FIELDS: formatted_phone_number,
-- website, opening_hours, rating, user_ratings_total) and has attempted to
-- persist since _apply_place_details shipped — until now every one of these
-- five writes failed at the DB/PostgREST layer (no matching column) and was
-- silently caught + logged by the try/except in search_agent.py:95-100, so
-- the API cost was already being paid with the data discarded. Same root
-- cause for all five; added together, idempotently, for databases created
-- before these columns existed.
alter table public.places add column if not exists phone              text;
alter table public.places add column if not exists website            text;
-- opening_hours stores only weekday_text (a JSON array of strings), the same
-- shape as `flags` above — not Google's full nested opening_hours object.
alter table public.places add column if not exists opening_hours      jsonb;
alter table public.places add column if not exists rating             numeric;
alter table public.places add column if not exists user_ratings_total integer;

-- Outreach Agent (docs/plans/PLAN-outreach-agent.md): track whether a
-- needs_review place's business has been contacted for confirmation, and
-- through which channel, so the pipeline's send stage doesn't re-contact the
-- same place every run. outreach_channel stays null until the first attempt,
-- since not every place has resolvable contact info.
alter table public.places add column if not exists outreach_status text
  not null default 'not_sent'
  check (outreach_status in ('not_sent', 'sent', 'replied', 'no_response'));
alter table public.places add column if not exists outreach_channel text
  check (outreach_channel is null or outreach_channel in ('email', 'whatsapp'));

-- Outreach Agent (ADR-002): a business's outreach reply that strengthens
-- needs_review evidence lands in a new 'outreach_confirmed' status — still
-- awaiting final human approval, never auto-'approved'. On an already-created
-- table the inline check above is a no-op, so widen it in place.
do $$
begin
  alter table public.places drop constraint if exists places_status_check;
  alter table public.places
    add constraint places_status_check
    check (status in
      ('pending', 'approved', 'discarded', 'needs_review', 'outreach_confirmed'));
end $$;

-- Outreach Agent (PLAN-outreach-agent.md, ADR-002): full send/reply audit
-- thread, one row per message, so the Validator's re-evaluation and any human
-- review see the complete back-and-forth, not just the latest state.
create table if not exists public.outreach_messages (
  id          uuid primary key default gen_random_uuid(),
  place_id    uuid not null references public.places(id) on delete cascade,
  direction   text not null
                check (direction in ('sent', 'received')),
  channel     text not null
                check (channel in ('email', 'whatsapp')),
  content     text not null,
  created_at  timestamptz not null default now()
);

create index if not exists outreach_messages_place_id_idx on public.outreach_messages (place_id);

-- Outreach Agent Etapa 2 (reply webhook, supabase/functions/outreach-reply/):
-- stores Resend's email_id for a received reply so a redelivered webhook
-- (Resend retries on any non-2xx response) doesn't insert the same reply
-- twice. A FULL (non-partial) unique constraint, same reasoning as
-- places_source_external_id_key above: PostgREST/supabase-py's ON CONFLICT
-- can't infer a partial index. Sent messages keep external_id null (NULLs
-- are distinct in a multi-column unique key, so this doesn't dedup sends).
alter table public.outreach_messages add column if not exists external_id text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'outreach_messages_place_id_external_id_key'
  ) then
    alter table public.outreach_messages
      add constraint outreach_messages_place_id_external_id_key
      unique (place_id, external_id);
  end if;
end $$;

-- Outreach Agent (contact_email discovery): Google Places never exposes a
-- business email (see the sandbox-recipient constraint in the Outreach agent
-- design decisions above), so contact_email is populated separately by
-- scraping the place's own website (already stored in places.website) when
-- one is on file. contact_email_checked_at records the last scrape attempt
-- — found or not — so the same website isn't re-scraped every pipeline run.
-- Both nullable: not every place has a website, and not every website yields
-- an email.
alter table public.places add column if not exists contact_email text;
alter table public.places add column if not exists contact_email_checked_at timestamptz;

-- Outreach Agent (ADR-003, opt-out mechanism): a business's reply can
-- explicitly request no further contact. Once true, the place must never be
-- reselected as an outreach candidate again, regardless of outreach_status.
-- Not enforced by a DB constraint: like outreach_status/outreach_channel
-- above, eligibility is filtered in application code
-- (OutreachAgent._select_candidates / SupabaseClient.fetch_needs_review_for_outreach
-- must exclude outreach_opt_out = true once ADR-003 lands).
alter table public.places add column if not exists outreach_opt_out boolean
  not null default false;

-- Community ranking (ADR-005 / docs/plans/PLAN-community-ranking.md): a
-- denormalized vote counter, kept in sync with the place_votes table by the
-- sync_place_vote_count trigger below. Same denormalized-column pattern as
-- rating / user_ratings_total / outreach_status above. The frontend reads the
-- ranking straight off this column via the existing "public read approved
-- places" policy — place_votes itself is never exposed for read.
alter table public.places add column if not exists vote_count integer not null default 0;

-- Supports the ranking query (status='approved' & country=X order by
-- vote_count desc). Optional at 1.3k rows, but cheap and consistent with the
-- other places indexes.
create index if not exists places_country_vote_count_idx
  on public.places (country, vote_count desc);

-- ---------------------------------------------------------------------
-- Table: reviews
-- ---------------------------------------------------------------------
create table if not exists public.reviews (
  id          uuid primary key default gen_random_uuid(),
  place_id    uuid not null references public.places(id) on delete cascade,
  text        text,
  rating      int check (rating between 1 and 5),
  user_id     uuid references auth.users(id) on delete set null,  -- nullable: auth deferred
  source      text not null default 'seed'
                check (source in ('seed', 'agent', 'user', 'google')),
  created_at  timestamptz not null default now()
);

create index if not exists reviews_place_id_idx on public.reviews (place_id);

-- Allow review snippets harvested from Google Places (source='google') by the
-- Search agent's review enrichment. Widen the inline check on existing tables.
do $$
begin
  alter table public.reviews drop constraint if exists reviews_source_check;
  alter table public.reviews
    add constraint reviews_source_check
    check (source in ('seed', 'agent', 'user', 'google'));
end $$;

-- ---------------------------------------------------------------------
-- Table: agent_log
-- ---------------------------------------------------------------------
create table if not exists public.agent_log (
  id          uuid primary key default gen_random_uuid(),
  agent       text not null
                check (agent in ('search', 'validator', 'updater', 'social', 'web', 'pipeline', 'suggestion')),
  action      text not null,
  result      jsonb,
  status      text check (status in ('success', 'error')),
  place_id    uuid references public.places(id) on delete set null,
  created_at  timestamptz not null default now()
);

create index if not exists agent_log_created_at_idx on public.agent_log (created_at);
create index if not exists agent_log_agent_idx      on public.agent_log (agent);

-- agent_log.agent was widened incrementally over time as new agents shipped:
-- base (search/validator/updater/social/web/pipeline/suggestion) -> +outreach
-- (Phase 15) -> +outreach_reply (Etapa 2) -> +review_handler (ADR-004,
-- docs/plans/PLAN-community-reviews.md). Collapsed into a single widening
-- here instead of that chain of separate DO blocks: applied one at a time,
-- incrementally, each was always safe — but with real production rows
-- already using 'outreach' (19) and 'outreach_reply' (6) (confirmed live via
-- `supabase db query --linked`), re-running the OLDER, narrower intermediate
-- blocks against a fully-populated table fails outright on a full fresh
-- apply — the same bug class found and fixed in places_status_check above.
do $$
begin
  alter table public.agent_log drop constraint if exists agent_log_agent_check;
  alter table public.agent_log
    add constraint agent_log_agent_check
    check (agent in
      ('search', 'validator', 'updater', 'social', 'web', 'pipeline', 'suggestion',
       'outreach', 'outreach_reply', 'review_handler'));
end $$;

-- ---------------------------------------------------------------------
-- Table: suggestions  (public "Suggest a Place" form intake)
-- ---------------------------------------------------------------------
-- The public form (anon key) writes RAW user input here — no coordinates.
-- A place has NOT NULL lat/lng and needs the secret Google key to geocode, so
-- the browser cannot write to `places` directly. Instead the daily pipeline's
-- Suggestion promoter reads new suggestions, geocodes each via Google Find Place,
-- dedups, and inserts a real `places` candidate (source='user', status='pending')
-- for the Validator to judge. This keeps `places` always-mappable and every
-- secret server-side. `status` here is the promoter's processing state, NOT the
-- place's publish state.
create table if not exists public.suggestions (
  id                uuid primary key default gen_random_uuid(),
  name              text not null
                      check (char_length(name) between 2 and 120),
  -- Street address — required on the form. Used (with name + city) to geocode the
  -- lead via Google Find Place; without it the promoter often cannot resolve a
  -- real place_id, so the suggestion never reaches the map.
  address           text not null
                      check (char_length(address) between 2 and 200),
  city              text not null
                      check (char_length(city) between 2 and 80),
  country           text not null
                      check (country in ('Uruguay', 'Argentina')),
  -- Provisional; the Validator assigns the real category. Optional on the form.
  category          text
                      check (category is null or category in ('restaurant', 'cafe', 'shop')),
  evidence_url      text
                      check (evidence_url is null or char_length(evidence_url) <= 500),
  notes             text
                      check (notes is null or char_length(notes) <= 1000),
  -- Promoter processing state (not the place's publish state):
  --   new       -> awaiting the next pipeline run
  --   promoted  -> a places row was created (promoted_place_id set)
  --   duplicate -> geocoded place_id already exists in places
  --   rejected  -> could not geocode to a real Google place_id
  status            text not null default 'new'
                      check (status in ('new', 'promoted', 'rejected', 'duplicate')),
  promoted_place_id uuid references public.places(id) on delete set null,
  created_at        timestamptz not null default now()
);

create index if not exists suggestions_status_idx on public.suggestions (status);

-- Address column added after the table first shipped. On an already-created DB the
-- inline NOT NULL above is a no-op, so add it idempotently here (nullable, since a
-- pre-existing row may lack it); required-ness for new public submissions is
-- enforced by the RLS WITH CHECK below.
alter table public.suggestions add column if not exists address text;

-- Community reports (PLAN-community-reviews.md): distinguishes who a
-- suggestions row came from. Every current writer (js/suggest.js, and the
-- new report form's no-match fallback) sends 'community' explicitly — see
-- the RLS WITH CHECK below, which enforces it server-side too. 'business' is
-- reserved for a future self-onboarding flow (none exists yet); the column
-- ships now so that flow won't need its own migration later.
alter table public.suggestions add column if not exists origin text
  not null default 'community'
  check (origin in ('community', 'business'));

-- ---------------------------------------------------------------------
-- Table: place_reports  (community "recommend / report" form intake)
-- ---------------------------------------------------------------------
-- The public form (anon key) writes a report about a place ALREADY on the
-- map — unlike `suggestions`, which is for places not yet published. Per
-- ADR-004, a report never modifies `places` directly: it is evidence
-- reinjected into the same Validator rubric. A 'negative' report on an
-- 'approved' place triggers an automatic re-evaluation (real-time via a
-- Supabase Database Webhook -> Edge Function -> repository_dispatch, with a
-- monthly sweep as a safety net — see PLAN-community-reviews.md, "Barrido
-- mensual + idempotencia"); a 'positive' report, or a 'negative' report on a
-- place that isn't 'approved', or a report with no place_id match, never
-- triggers anything automatic (ADR-004 points 2-4) and stays for manual review.
create table if not exists public.place_reports (
  id               uuid primary key default gen_random_uuid(),
  -- Nullable: a report with no autocomplete match keeps place_id null and
  -- records the free-text name instead (see place_reports_has_target below).
  place_id         uuid references public.places(id) on delete set null,
  place_name_text  text
                     check (place_name_text is null or char_length(place_name_text) between 2 and 120),
  report_type      text not null
                     check (report_type in ('positive', 'negative')),
  description      text not null
                     check (char_length(description) between 5 and 2000),
  -- Processing state (not the place's publish state):
  --   new        -> just inserted; also the TERMINAL state for 'positive'
  --                 reports, 'negative' reports on a non-approved place, and
  --                 reports with no place_id match (ADR-004 points 2-4) —
  --                 nothing automated moves them past this.
  --   dispatched -> negative + place approved: the Edge Function fired the
  --                 repository_dispatch (best-effort — Supabase Database
  --                 Webhooks do not auto-retry on non-2xx/timeout, unlike
  --                 the Resend webhook Etapa 2 of outreach relies on; the
  --                 monthly sweep covers whatever is left stuck here).
  --   processing -> ReviewHandler.handle() atomically claimed this report
  --                 (CAS: new/dispatched -> processing) and is evaluating
  --                 it now. This state is what makes the real-time path and
  --                 the monthly sweep safe to race against each other.
  --   processed  -> review_handler.py finished re-evaluating and persisted
  --                 a Validator verdict.
  --   skipped    -> claimed, but the place was no longer 'approved' by the
  --                 time this ran (another report already moved it).
  --   error      -> the re-evaluation itself failed (LLM or persistence).
  status           text not null default 'new'
                     check (status in
                       ('new', 'dispatched', 'processing', 'processed', 'skipped', 'error')),
  created_at       timestamptz not null default now(),
  constraint place_reports_has_target
    check (place_id is not null or place_name_text is not null)
);

create index if not exists place_reports_place_id_idx on public.place_reports (place_id);
create index if not exists place_reports_status_idx   on public.place_reports (status);

-- ---------------------------------------------------------------------
-- Table: place_votes  (community "recommend / upvote" — the ranking signal)
-- ---------------------------------------------------------------------
-- One row per (place, browser). A vote is a single click, no text — the
-- qualitative channel stays place_reports 'positive' (ADR-004). The public
-- anon key may only INSERT here (never read back); the ranking count is read
-- via the denormalized places.vote_count column above, which the existing
-- "public read approved places" policy already exposes. Votes have NO
-- authority over places.status — the ranking only orders places the Validator
-- already approved. See ADR-005 / docs/plans/PLAN-community-ranking.md.
create table if not exists public.place_votes (
  id          uuid primary key default gen_random_uuid(),
  place_id    uuid not null references public.places(id) on delete cascade,
  -- Random client-minted dedup key (crypto.randomUUID or fallback). Not a
  -- secret — just prevents the same browser double-counting one place.
  voter_token text not null check (char_length(voter_token) between 8 and 64),
  source      text not null default 'community'
                check (source in ('community', 'seed')),
  created_at  timestamptz not null default now(),
  -- FULL (non-partial) unique constraint, same reasoning as
  -- places_source_external_id_key: PostgREST's on_conflict needs the plain
  -- column list. One vote per browser per place.
  constraint place_votes_place_voter_key unique (place_id, voter_token)
);

create index if not exists place_votes_place_id_idx on public.place_votes (place_id);

-- ---------------------------------------------------------------------
-- Trigger: keep places.updated_at fresh on UPDATE
-- ---------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists places_set_updated_at on public.places;
create trigger places_set_updated_at
  before update on public.places
  for each row
  execute function public.set_updated_at();

-- ---------------------------------------------------------------------
-- Trigger: keep places.vote_count in sync with place_votes (ADR-005)
-- ---------------------------------------------------------------------
-- SECURITY DEFINER is REQUIRED, not optional: an AFTER INSERT fired by the
-- anon role runs this function as anon (SECURITY INVOKER is the default), and
-- its "update public.places" is then subject to the places RLS for anon —
-- which has a SELECT policy but NO update policy, so Postgres silently
-- filters the UPDATE to 0 rows instead of erroring. Result without DEFINER:
-- every community vote inserts a place_votes row but vote_count never moves.
-- As DEFINER the function runs as its owner (postgres), which owns places and
-- bypasses its (non-forced) RLS. It only ever touches vote_count for the
-- place_id of a row that already passed place_votes' own RLS with-check, so
-- this is not a privilege-escalation surface. set search_path pins name
-- resolution (SECURITY DEFINER best practice).
create or replace function public.sync_place_vote_count()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if (tg_op = 'INSERT') then
    update public.places set vote_count = vote_count + 1 where id = new.place_id;
    return new;
  elsif (tg_op = 'DELETE') then
    -- greatest(): never let vote_count go negative, even if it drifts.
    update public.places set vote_count = greatest(vote_count - 1, 0) where id = old.place_id;
    return old;
  end if;
  return null;
end;
$$;

drop trigger if exists place_votes_sync_count on public.place_votes;
create trigger place_votes_sync_count
  after insert or delete on public.place_votes
  for each row
  execute function public.sync_place_vote_count();

-- Reconciliation (NOT run automatically — run by hand only if vote_count ever
-- drifts, e.g. after bulk-deleting fraudulent rows):
--   update public.places p set vote_count = coalesce(v.n, 0)
--     from (select place_id, count(*) n from public.place_votes group by place_id) v
--     where v.place_id = p.id;
--   update public.places set vote_count = 0
--     where vote_count <> 0 and id not in (select place_id from public.place_votes);

-- ---------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------
alter table public.places      enable row level security;
alter table public.reviews     enable row level security;
alter table public.agent_log   enable row level security;
alter table public.suggestions enable row level security;
alter table public.outreach_messages enable row level security;
alter table public.place_reports enable row level security;
alter table public.place_votes enable row level security;

-- Table-level privileges (RLS still gates rows).
grant select on public.places  to anon, authenticated;
-- agent_log is server-only: make sure public roles cannot touch it.
revoke all on public.agent_log from anon, authenticated;
-- reviews is server-only as of 2026-09 (Google Places ToS: only place_id is
-- exempt from caching restrictions -- reviews must be requested live, not
-- served indefinitely from our own store. See CLAUDE.md Decisions Log
-- "Google Places reviews -- ToS-driven access restriction + 30-day
-- expiration"). The only legitimate reader, ValidatorAgent.fetch_reviews_for_place,
-- uses the service_role key and bypasses RLS. Explicit revoke (not just
-- omitting the old grant line) so re-running this file against the
-- already-migrated production database actually removes the prior access.
revoke select on public.reviews from anon, authenticated;
-- outreach_messages is server-only (Outreach Agent), same as agent_log: make
-- sure public roles cannot touch it.
revoke all on public.outreach_messages from anon, authenticated;
-- suggestions: the public form may INSERT only — never read back others'
-- submissions, update or delete. (Reads/updates happen server-side via the
-- service_role key, which bypasses RLS.)
revoke all on public.suggestions from anon, authenticated;
grant insert on public.suggestions to anon, authenticated;
-- place_reports: same INSERT-only shape as suggestions — the public can
-- submit a report but never read back others' submissions, update or delete.
revoke all on public.place_reports from anon, authenticated;
grant insert on public.place_reports to anon, authenticated;
-- place_votes: same INSERT-only shape — the public casts a vote but never
-- reads back place_votes rows (the count is read via places.vote_count).
revoke all on public.place_votes from anon, authenticated;
grant insert on public.place_votes to anon, authenticated;

-- places: anyone may read ONLY approved rows.
drop policy if exists "public read approved places" on public.places;
create policy "public read approved places"
  on public.places
  for select
  to anon, authenticated
  using (status = 'approved');

-- reviews: no public read policy (server-only, see the revoke above and
-- CLAUDE.md Decisions Log). This drop is kept so re-running this file
-- against a database created before 2026-09 removes the old policy.
drop policy if exists "public read reviews of approved places" on public.reviews;

-- agent_log: no policy for anon/authenticated => fully denied to the public.
-- (service_role bypasses RLS and retains full access.)

-- outreach_messages: no policy for anon/authenticated => fully denied to the
-- public, same as agent_log. (service_role bypasses RLS and retains full access.)

-- suggestions: the public may only INSERT a fresh submission. The WITH CHECK
-- forces a safe initial state (status='new', not pre-promoted), requires a
-- non-empty address (needed to geocode), and forces origin='community' (the
-- only writer today is js/suggest.js and the report form's no-match
-- fallback — 'business' has no flow yet, so RLS refuses it defense-in-depth
-- even if a client tried); the column CHECKs above bound every field's
-- length so the table can't be abused as free storage. No SELECT/UPDATE/
-- DELETE policy => those are denied to anon.
drop policy if exists "public can submit suggestions" on public.suggestions;
create policy "public can submit suggestions"
  on public.suggestions
  for insert
  to anon, authenticated
  with check (
    status = 'new'
    and promoted_place_id is null
    and address is not null
    and char_length(address) between 2 and 200
    and origin = 'community'
  );

-- place_reports: the public may only INSERT a fresh report. The WITH CHECK
-- forces a safe initial state (status='new'), requires either a matched
-- place_id or a free-text place_name_text (place_reports_has_target already
-- enforces this at the column level, restated here for defense-in-depth),
-- and re-bounds description length; the column CHECKs above are the primary
-- enforcement. No SELECT/UPDATE/DELETE policy => those are denied to anon
-- (ReviewHandler reads/writes via the service_role key, which bypasses RLS).
drop policy if exists "public can submit place reports" on public.place_reports;
create policy "public can submit place reports"
  on public.place_reports
  for insert
  to anon, authenticated
  with check (
    status = 'new'
    and (place_id is not null or place_name_text is not null)
    and char_length(description) between 5 and 2000
  );

-- place_votes: the public may only INSERT a community vote. The WITH CHECK
-- forces source='community', bounds the token length, and — crucially —
-- requires the target place to be 'approved': the subquery runs as the anon
-- role, subject to the places RLS, so a non-approved place_id is rejected at
-- the DB level, not just hidden in the client (ADR-005 point 3). No SELECT/
-- UPDATE/DELETE policy => those are denied to anon; the ranking count is read
-- via places.vote_count.
drop policy if exists "public can cast a vote" on public.place_votes;
create policy "public can cast a vote"
  on public.place_votes
  for insert
  to anon, authenticated
  with check (
    source = 'community'
    and char_length(voter_token) between 8 and 64
    and exists (
      select 1 from public.places p
      where p.id = place_votes.place_id
        and p.status = 'approved'
    )
  );
