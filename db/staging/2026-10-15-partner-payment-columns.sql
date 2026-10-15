-- STAGING ONLY (2026-10-15). Brings staging's partner_applications, created from the first version of
-- db/migrations/2026-10-14-partner-program.PENDING.sql, in line with the current one: the payer's email is no longer
-- stored (payer_email out) and the first payment id is (mp_first_payment_id in), with the insert policy recreated.
-- Production never runs this file: it gets the final shape from the PENDING migration in phase 3.
-- Apply: python -m scripts.staging_db --project-ref <staging> --file db/staging/2026-10-15-partner-payment-columns.sql --apply
begin;

alter table public.partner_applications add column if not exists mp_first_payment_id text
  check (mp_first_payment_id is null or char_length(mp_first_payment_id) <= 40);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'partner_applications_mp_first_payment_id_key') then
    alter table public.partner_applications
      add constraint partner_applications_mp_first_payment_id_key unique (mp_first_payment_id);
  end if;
end $$;

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
    and mp_first_payment_id is null
    and paid_through is null
    and approved_at is null
    and admin_notes is null
    and public_name is null
    and public_text_es is null
    and public_text_en is null
    and logo_path is null
    and public_links is null
  );

alter table public.partner_applications drop column if exists payer_email;

commit;

notify pgrst, 'reload schema';
