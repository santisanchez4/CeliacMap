-- Partner program «CeliacMap Aliado», phase 1 (ADR-011, docs/plans/PLAN-partner-program.md §4).
-- Copied from db/schema.sql (the PARTNER-PROGRAM block is the source of truth); idempotent, safe to run twice.
-- Staging first: python -m scripts.staging_db --project-ref <staging> --file db/migrations/2026-10-14-partner-program.sql --apply
-- Production only in phase 3, with the SQL shown and the owner's «dale». Revert: 2026-10-14-partner-program-revert.sql
begin;

-- PARTNER-PROGRAM-BEGIN
-- One row per partner request: the request, its payment state and its publication state. Contracting and
-- publishing are separate steps (ADR-011): Mercado Pago sets payment_status, only the admin sets
-- publication_status, and nothing here ever touches places, place_votes, reviews or the Validator. place_id is an
-- informational link the admin may set; it is never written back to places.
-- The public form (anon key) may only INSERT the request columns; it never reads anything back. The only public
-- read is the view partners_public, whose WHERE is the visibility rule.
create table if not exists public.partner_applications (
  id                 uuid primary key default gen_random_uuid(),
  ref_code           text not null
                       check (ref_code ~ '^CM-[A-Z0-9]{6}$'),
  business_name      text not null
                       check (char_length(btrim(business_name)) between 2 and 120),
  city               text not null
                       check (char_length(btrim(city)) between 2 and 80),
  country            text not null
                       check (country in ('Uruguay', 'Argentina')),
  contact_name       text not null
                       check (char_length(btrim(contact_name)) between 2 and 120),
  contact_email      text not null
                       check (char_length(contact_email) between 6 and 254
                              and contact_email ~ '^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$'),
  contact_phone      text
                       check (contact_phone is null or char_length(contact_phone) between 6 and 40),
  links              text
                       check (links is null or char_length(links) <= 500),
  description        text
                       check (description is null or char_length(description) <= 300),
  on_map_claim       text not null
                       check (on_map_claim in ('yes', 'no', 'unsure')),
  consent_version    text not null
                       check (char_length(consent_version) between 1 and 40),
  place_id           uuid references public.places(id) on delete set null,
  payment_status     text not null default 'pending'
                       check (payment_status in ('pending', 'active', 'past_due', 'cancelled')),
  publication_status text not null default 'requested'
                       check (publication_status in
                         ('requested', 'eligible', 'approved', 'suspended', 'ended', 'rejected')),
  mp_preapproval_id  text
                       check (mp_preapproval_id is null or char_length(mp_preapproval_id) <= 100),
  payer_email        text
                       check (payer_email is null or char_length(payer_email) <= 254),
  paid_through       date,
  approved_at        timestamptz,
  admin_notes        text
                       check (admin_notes is null or char_length(admin_notes) <= 2000),
  public_name        text
                       check (public_name is null or char_length(btrim(public_name)) between 2 and 80),
  public_text_es     text
                       check (public_text_es is null or char_length(public_text_es) <= 400),
  public_text_en     text
                       check (public_text_en is null or char_length(public_text_en) <= 400),
  logo_path          text
                       check (logo_path is null or char_length(logo_path) <= 200),
  public_links       jsonb
                       check (public_links is null or jsonb_typeof(public_links) = 'array'),
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  constraint partner_applications_ref_code_key unique (ref_code),
  constraint partner_applications_mp_preapproval_id_key unique (mp_preapproval_id)
);

-- One open request per email + business: the form shows "ya tenemos tu solicitud" on this violation, and
-- generates a new ref_code and retries on partner_applications_ref_code_key. Partial on purpose: no ON CONFLICT
-- uses it, and a rejected or ended request does not block a new one.
create unique index if not exists partner_applications_open_request_idx
  on public.partner_applications (lower(contact_email), lower(business_name))
  where publication_status in ('requested', 'eligible', 'approved');

drop trigger if exists partner_applications_set_updated_at on public.partner_applications;
create trigger partner_applications_set_updated_at
  before update on public.partner_applications
  for each row
  execute function public.set_updated_at();

alter table public.partner_applications enable row level security;

-- INSERT only, and only on the request columns: anon cannot even name a state, a payment or a public field.
revoke all on public.partner_applications from anon, authenticated;
grant insert (
  ref_code, business_name, city, country, contact_name, contact_email, contact_phone, links, description,
  on_map_claim, consent_version
) on public.partner_applications to anon, authenticated;

-- Defense in depth behind the column grant: a public row always starts unpaid, unreviewed and unpublished.
drop policy if exists "public can request a partnership" on public.partner_applications;
create policy "public can request a partnership"
  on public.partner_applications
  for insert
  to anon, authenticated
  with check (
    payment_status = 'pending'
    and publication_status = 'requested'
    and place_id is null
    and mp_preapproval_id is null
    and payer_email is null
    and paid_through is null
    and approved_at is null
    and admin_notes is null
    and public_name is null
    and public_text_es is null
    and public_text_en is null
    and logo_path is null
    and public_links is null
  );

-- The only public read. It runs with its owner's rights, so this WHERE is the only barrier: approved by the admin
-- AND paid up. A cancelled partnership stays visible until the end of the period already paid; a missed payment
-- (past_due) hides it until it is paid; after 30 days without payment the admin script ends it.
create or replace view public.partners_public as
select public_name,
       public_text_es,
       public_text_en,
       logo_path,
       public_links
from public.partner_applications
where publication_status = 'approved'
  and public_name is not null
  and (
    payment_status = 'active'
    or (payment_status = 'cancelled' and paid_through >= current_date)
  );

revoke all on public.partners_public from anon, authenticated;
grant select on public.partners_public to anon, authenticated;
-- PARTNER-PROGRAM-END

commit;

-- PostgREST caches the schema; reload it so the new table, view and privileges are seen right away.
notify pgrst, 'reload schema';
