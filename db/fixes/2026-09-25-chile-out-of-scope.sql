-- One-off data correction — 2 Chilean places out of geographic scope, stamped country='Uruguay'.
--
-- Context: the Social agent (source='social') geocodes each lead with Google Find Place, which is
-- location-BIASED, not bounded: a lead searched under a Uruguayan city can match a real business in Chile.
-- parse_city_country_from_address() returns (None, None) for a Chilean address (outside the AR/UY scope) and
-- the country then fell back to the QUERY's ("Uruguay") — the same hole as the Brazil cluster of 2026-09-01
-- (db/fixes/2026-09-01-brazil-out-of-scope-places.sql), which that day was closed for the Search agent only.
-- Closed for Social/Web/Suggestion on 2026-09-25 in GooglePlacesClient.resolve_location (is_foreign_address).
-- A third row of the same kind, "Goût Gluten Free" (Vitacura), is already `discarded` by the Validator and is
-- left as it is. See CLAUDE.md Decisions Log, "Audit data-quality pass 2026-09-25".
--
-- Same precedent as Brazil: status stays needs_review (editorial exclusion, not a quality judgement on the
-- business), country/city fixed from the row's own address, outreach_opt_out=true (needs_review is also the
-- Outreach agent's queue, in live mode: an out-of-scope business must never receive an email — neither row has
-- contact data today, this keeps it that way), CORRECCIÓN MANUAL header prepended with the old text kept below.
-- lat/lng and validation_confidence are NOT touched (the places are real and where Google says they are).
--
-- Run (all-or-nothing; asserts exactly 2 rows and that nothing but the four columns above changed):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-25-chile-out-of-scope.sql
-- Idempotent: guarded by country='Uruguay' and outreach_opt_out=false, so a second run matches 0 rows and aborts.

begin;

create temp table _snap on commit drop as
select id, name, status, country, city, outreach_opt_out, lat, lng, validation_confidence, safety_level, flags, validation_notes
from public.places
where id in ('3527545f-3f43-45cf-97c4-432518a80c42', 'e530f08b-ae6e-4b16-9c8e-b37cfc717c08');

do $$
declare n int;
begin
  update public.places p
  set country = 'Chile',
      city = v.city,
      outreach_opt_out = true,
      validation_notes = concat_ws(E'\n\n',
        'CORRECCIÓN MANUAL 2026-09-25: este lugar está en Chile, fuera del alcance geográfico del proyecto (solo Uruguay/Argentina). '
        || 'Figuraba con country=''Uruguay'' porque el match de Find Place caía al país de la búsqueda cuando la dirección era de otro país '
        || '(mismo hueco que Brasil, corregido en resolve_location el 2026-09-25) — ver Decisions Log. '
        || 'Se mantiene en needs_review por exclusión editorial, no por la calidad del negocio; outreach_opt_out activado.',
        nullif(p.validation_notes, ''))
  from (values
    ('3527545f-3f43-45cf-97c4-432518a80c42'::uuid, 'Vitacura'),      -- Las Petunias Pastelería sin azúcar y sin gluten — San Patricio 4270, Vitacura, Región Metropolitana, Chile
    ('e530f08b-ae6e-4b16-9c8e-b37cfc717c08'::uuid, 'Viña del Mar')  -- Quimey Fusion & Gluten Free — Av. José Manuel Balmaceda 287, Viña del Mar, Valparaíso, Chile
  ) as v(id, city)
  where p.id = v.id
    and p.status = 'needs_review'
    and p.country = 'Uruguay'
    and p.outreach_opt_out = false;
  get diagnostics n = row_count;
  if n <> 2 then raise exception 'chile: esperaba 2 filas, actualicé %', n; end if;

  -- Invariants: only country, city, outreach_opt_out and validation_notes may change.
  select count(*) into n from _snap s join public.places p on p.id = s.id
  where p.status is distinct from s.status
     or p.lat is distinct from s.lat or p.lng is distinct from s.lng
     or p.validation_confidence is distinct from s.validation_confidence
     or p.safety_level is distinct from s.safety_level
     or p.flags is distinct from s.flags;
  if n <> 0 then raise exception 'invariante: % filas cambiaron status/lat/lng/confidence/safety_level/flags', n; end if;

  select count(*) into n from _snap s join public.places p on p.id = s.id
  where strpos(coalesce(p.validation_notes, ''), 'CORRECCIÓN MANUAL 2026-09-25') = 0
     or strpos(coalesce(p.validation_notes, ''), coalesce(nullif(s.validation_notes, ''), '')) = 0;
  if n <> 0 then raise exception 'invariante: % filas sin el encabezado o sin el texto original', n; end if;
end $$;

commit;

-- =============================================================================================
-- VERIFICATION (read-only) — run AFTER the commit above, as a single statement. Every row ok = true.
-- =============================================================================================
select check_name, expected, actual, (expected = actual) as ok from (
  select 1 as n, 'the 2 rows: needs_review + Chile + opt-out' as check_name, 2 as expected,
         (select count(*) from public.places
           where id in ('3527545f-3f43-45cf-97c4-432518a80c42', 'e530f08b-ae6e-4b16-9c8e-b37cfc717c08')
             and status = 'needs_review' and country = 'Chile' and outreach_opt_out = true) as actual
  union all
  select 2, 'their cities are Vitacura / Viña del Mar', 2,
         (select count(*) from public.places
           where (id = '3527545f-3f43-45cf-97c4-432518a80c42' and city = 'Vitacura')
              or (id = 'e530f08b-ae6e-4b16-9c8e-b37cfc717c08' and city = 'Viña del Mar'))
  union all
  select 3, 'approved/needs_review/pending with a Chilean address labelled Argentina/Uruguay', 0,
         (select count(*) from public.places
           where status in ('approved', 'needs_review', 'pending') and address ~* 'chile\s*$' and country in ('Argentina', 'Uruguay'))
  union all
  select 4, 'both rows carry the 2026-09-25 header', 2,
         (select count(*) from public.places
           where id in ('3527545f-3f43-45cf-97c4-432518a80c42', 'e530f08b-ae6e-4b16-9c8e-b37cfc717c08')
             and validation_notes like 'CORRECCIÓN MANUAL 2026-09-25%')
) c order by n;
