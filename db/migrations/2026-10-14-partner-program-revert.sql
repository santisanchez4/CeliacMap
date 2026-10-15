-- Reverts 2026-10-14-partner-program.PENDING.sql (applied on staging only, not in production): drops the public view and the partner table (and every row in it).
-- Touches nothing else: places, place_votes and reviews were never changed by the partner program.
begin;

drop view if exists public.partners_public;
drop table if exists public.partner_applications;

commit;

notify pgrst, 'reload schema';
