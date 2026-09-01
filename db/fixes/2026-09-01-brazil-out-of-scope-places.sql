-- One-off data correction — 6 Brazilian places out of geographic scope
-- (5 approved in error in 2026-06 + Confeitaria Glúten Free Cascavel).
--
-- Context: the Search agent's Google Places Text Search for the Argentine
-- city "Paraná" (Entre Ríos) returned businesses located in the Brazilian
-- state of Paraná (Curitiba / Pinhais); a Fray Bentos query similarly leaked
-- to União da Vitória, PR. Text Search is location-BIASED, not bounded, and
-- "Paraná" is ambiguous (AR city vs BR state). GooglePlacesClient.to_candidate()
-- then stamped country/city from the SEARCH TARGET, because
-- parse_city_country_from_address() returns (None, None) for a Brazilian
-- address (out of the AR/UY SUPPORTED_COUNTRIES scope) and the code fell back
-- to the target. The old binary Validator rubric (pre three-tier, pre
-- needs_review) approved them on GF merits despite three of the five
-- validation_notes explicitly flagging the country mismatch. See CLAUDE.md
-- Decisions Log ("Brazil out-of-scope places — Curitiba cluster") for the full
-- investigation, and the same-day commits for the code fixes (Parts 2–4).
--
-- The 2026-08-08 border fix (db/fixes/2026-08-08-border-city-country-mismatch.sql)
-- did NOT catch these: it swept only for AR businesses mislabeled as Uruguay,
-- not for addresses in a third country.
--
-- Each row keeps its real lat/lng (correct — they ARE in Brazil) and its
-- validation_confidence (the GF-quality judgement was sound; only the
-- geographic scope is the problem — CLAUDE.md manual-override policy: never
-- inflate/deflate confidence to match a human decision). status -> needs_review
-- mirrors "Confeitaria Glúten Free Cascavel" (269a239e), already in
-- needs_review since 2026-06-22 for the identical reason.
--
-- outreach_opt_out = true is set on all six: needs_review is also the Outreach
-- agent's queue (fetch_needs_review_for_outreach), and the agent now runs in
-- live mode — an out-of-scope Brazilian business must never receive a
-- confirmation email. Statement 6 also fixes Cascavel's country/city columns
-- (still 'Argentina'/'Paraná') for consistency with the other five.
--
-- Run manually in the Supabase SQL Editor (or: node_modules/.bin/supabase
-- db query --linked --file <this file>). Idempotent: statements 1-5 guard on
-- status='approved'; statement 6 guards on outreach_opt_out=false.

-- 1. Glúten Pra Quê? — Almendras Emporium, R. Nilo Peçanha 1948, Bom Retiro,
--    Curitiba - PR, Brazil
update public.places
set status = 'needs_review',
    outreach_opt_out = true,
    country = 'Brasil',
    city = 'Curitiba',
    validation_notes = 'CORRECCIÓN MANUAL: este lugar está en Brasil, fuera del alcance geográfico del proyecto (solo Uruguay/Argentina). Aprobado incorrectamente en 2026-06 por un bug de estampado de país (el Search agent usaba el target de búsqueda, no la dirección real) — ver Decisions Log. Movido a needs_review para exclusión editorial, no por problema de calidad del negocio en sí.'
      || E'\n\n' || validation_notes
where id = 'f732f905-1573-4f19-adb6-58acfa213e51'
  and status = 'approved';

-- 2. LEVAIN GLÚTEN FREE — R. Ver. Washington Mansur 332, Ahú,
--    Curitiba - PR, Brazil
update public.places
set status = 'needs_review',
    outreach_opt_out = true,
    country = 'Brasil',
    city = 'Curitiba',
    validation_notes = 'CORRECCIÓN MANUAL: este lugar está en Brasil, fuera del alcance geográfico del proyecto (solo Uruguay/Argentina). Aprobado incorrectamente en 2026-06 por un bug de estampado de país (el Search agent usaba el target de búsqueda, no la dirección real) — ver Decisions Log. Movido a needs_review para exclusión editorial, no por problema de calidad del negocio en sí.'
      || E'\n\n' || validation_notes
where id = '15eb48e3-ad3c-4a2e-85cc-ce9457f87808'
  and status = 'approved';

-- 3. Sem Culpa - Sem Gluten — R. Schiller 1960, Hugo Lange,
--    Curitiba - PR, Brazil
update public.places
set status = 'needs_review',
    outreach_opt_out = true,
    country = 'Brasil',
    city = 'Curitiba',
    validation_notes = 'CORRECCIÓN MANUAL: este lugar está en Brasil, fuera del alcance geográfico del proyecto (solo Uruguay/Argentina). Aprobado incorrectamente en 2026-06 por un bug de estampado de país (el Search agent usaba el target de búsqueda, no la dirección real) — ver Decisions Log. Movido a needs_review para exclusión editorial, no por problema de calidad del negocio en sí.'
      || E'\n\n' || validation_notes
where id = 'a7fec799-96c2-49d6-b01a-29273c6ef161'
  and status = 'approved';

-- 4. Senza Glutine - comida sem glúten saudável (delivery) — R. Quinze de
--    Novembro 65, Centro, Pinhais - PR, Brazil
update public.places
set status = 'needs_review',
    outreach_opt_out = true,
    country = 'Brasil',
    city = 'Pinhais',
    validation_notes = 'CORRECCIÓN MANUAL: este lugar está en Brasil, fuera del alcance geográfico del proyecto (solo Uruguay/Argentina). Aprobado incorrectamente en 2026-06 por un bug de estampado de país (el Search agent usaba el target de búsqueda, no la dirección real) — ver Decisions Log. Movido a needs_review para exclusión editorial, no por problema de calidad del negocio en sí.'
      || E'\n\n' || validation_notes
where id = 'e3d18b5e-622a-43b4-8d0b-89745b6c8449'
  and status = 'approved';

-- 5. Empório Celíaco • Sem Glúten… — R. Barão do Rio Branco 56, Centro,
--    União da Vitória - PR, Brazil
update public.places
set status = 'needs_review',
    outreach_opt_out = true,
    country = 'Brasil',
    city = 'União da Vitória',
    validation_notes = 'CORRECCIÓN MANUAL: este lugar está en Brasil, fuera del alcance geográfico del proyecto (solo Uruguay/Argentina). Aprobado incorrectamente en 2026-06 por un bug de estampado de país (el Search agent usaba el target de búsqueda, no la dirección real) — ver Decisions Log. Movido a needs_review para exclusión editorial, no por problema de calidad del negocio en sí.'
      || E'\n\n' || validation_notes
where id = '985fd078-41b6-4839-a3ad-882df3dbf24a'
  and status = 'approved';

-- 6. Confeitaria Glúten Free Cascavel — R. Mal. Floriano 3221, Centro,
--    Cascavel - PR, Brazil. Already needs_review (Validator, 2026-06-22);
--    here we close the outreach gap and fix the country/city columns.
update public.places
set outreach_opt_out = true,
    country = 'Brasil',
    city = 'Cascavel',
    validation_notes = 'CORRECCIÓN MANUAL (2026-09-01): país/ciudad corregidos a Brasil/Cascavel y outreach_opt_out activado. Fuera del alcance geográfico del proyecto (solo Uruguay/Argentina); ya estaba en needs_review por decisión del Validator (2026-06-22). Ver Decisions Log.'
      || E'\n\n' || validation_notes
where id = '269a239e-804a-47d2-be81-9c1e610352af'
  and outreach_opt_out = false;
