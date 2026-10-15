-- Public grants: revoke all, then only the minimal grant each object needs today (2026-10-15).
-- Found on staging and confirmed read-only on production: anon and authenticated kept INSERT, UPDATE, DELETE,
-- TRUNCATE, REFERENCES and TRIGGER on public.reviews (db/schema.sql revoked only SELECT there). RLS stops row writes
-- through the API, but not TRUNCATE. Every other table / view already matched; they are re-asserted here so this
-- file is the full list of public privileges. Same statements as db/schema.sql; idempotent, one transaction.
-- Staging first: python -m scripts.staging_db --project-ref <staging> --file <this file> --apply
-- Production: only after the rollback rehearsal (db/checks/2026-10-15-public-grants-rehearsal.sql) and the «dale».
begin;

-- Server-only: no privilege at all for the public roles.
revoke all on public.reviews           from anon, authenticated;
revoke all on public.agent_log         from anon, authenticated;
revoke all on public.outreach_messages from anon, authenticated;
revoke all on public.chat_usage        from anon, authenticated;
revoke all on public.place_evidence    from anon, authenticated;

-- Intake: INSERT only (js/suggest.js, js/report.js, js/ranking.js and the chat function's insertIntakeRow).
revoke all on public.suggestions   from anon, authenticated;
grant insert on public.suggestions   to anon, authenticated;
revoke all on public.place_reports from anon, authenticated;
grant insert on public.place_reports to anon, authenticated;
revoke all on public.place_votes   from anon, authenticated;
grant insert on public.place_votes   to anon, authenticated;

-- Public reads: the places column allowlist (PLACES-PUBLIC-COLUMNS) and the opinions view.
revoke all on public.places from anon, authenticated;
grant select (
  id, name, lat, lng, category, country, city, region, address, safety_level, status, source,
  phone, website, opening_hours, social_url, rating, user_ratings_total, vote_count,
  community_warning_at
) on public.places to anon, authenticated;
revoke all on public.community_opinions from anon, authenticated;
grant select on public.community_opinions to anon, authenticated;

commit;

notify pgrst, 'reload schema';
