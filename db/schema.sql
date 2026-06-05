-- =====================================================================
-- CeliacMap — db/schema.sql
-- Supabase (PostgreSQL). Run in the Supabase SQL Editor.
-- Idempotent: safe to re-run (uses IF NOT EXISTS / DROP POLICY IF EXISTS).
--
-- Security model:
--   * Frontend uses the public ANON key and may only read APPROVED places
--     (and reviews of approved places). No anon writes; no anon access to logs.
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
  -- Agent flow: search inserts 'pending'; validator sets 'approved'/'discarded';
  -- the frontend shows only 'approved'.
  status                text not null default 'pending'
                          check (status in ('pending', 'approved', 'discarded')),
  address               text,
  source                text not null default 'manual'
                          check (source in ('google_places', 'manual', 'user', 'social', 'web')),
  external_id           text,                 -- e.g. Google place_id (for dedup)
  validation_confidence numeric,              -- validator output (0..1)
  validation_notes      text,                 -- validator rationale
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
                check (agent in ('search', 'validator', 'updater', 'social', 'web', 'pipeline')),
  action      text not null,
  result      jsonb,
  status      text check (status in ('success', 'error')),
  place_id    uuid references public.places(id) on delete set null,
  created_at  timestamptz not null default now()
);

create index if not exists agent_log_created_at_idx on public.agent_log (created_at);
create index if not exists agent_log_agent_idx      on public.agent_log (agent);

-- Allow the Social agent (agent='social'), the Web discovery agent (agent='web')
-- and the pipeline orchestrator (agent='pipeline') to log under agent_log. On an
-- already-created table the inline check above is a no-op, so widen it in place.
do $$
begin
  alter table public.agent_log drop constraint if exists agent_log_agent_check;
  alter table public.agent_log
    add constraint agent_log_agent_check
    check (agent in ('search', 'validator', 'updater', 'social', 'web', 'pipeline'));
end $$;

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
-- Row Level Security
-- ---------------------------------------------------------------------
alter table public.places    enable row level security;
alter table public.reviews   enable row level security;
alter table public.agent_log enable row level security;

-- Table-level privileges (RLS still gates rows).
grant select on public.places  to anon, authenticated;
grant select on public.reviews to anon, authenticated;
-- agent_log is server-only: make sure public roles cannot touch it.
revoke all on public.agent_log from anon, authenticated;

-- places: anyone may read ONLY approved rows.
drop policy if exists "public read approved places" on public.places;
create policy "public read approved places"
  on public.places
  for select
  to anon, authenticated
  using (status = 'approved');

-- reviews: readable only when their place is approved.
drop policy if exists "public read reviews of approved places" on public.reviews;
create policy "public read reviews of approved places"
  on public.reviews
  for select
  to anon, authenticated
  using (
    exists (
      select 1 from public.places p
      where p.id = reviews.place_id
        and p.status = 'approved'
    )
  );

-- agent_log: no policy for anon/authenticated => fully denied to the public.
-- (service_role bypasses RLS and retains full access.)
