-- One-off data correction — fictional seed places + wrong country / city / non-business rows.
--
-- Found by the read-only audit of 2026-09-25 (see CLAUDE.md, Decisions Log, "Audit data-quality pass
-- 2026-09-25"). Every id below was verified against production before this file was written; the
-- city / country values come from each row's own `address` column (reviewed by hand, not auto-applied).
-- Nothing here touches lat / lng / validation_confidence / safety_level / flags — a snapshot table and
-- a final invariants check abort the whole transaction if any of them changes.
--
-- Run (all-or-nothing; every block asserts its exact row count and RAISES on any drift):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-25-seed-and-data-quality.sql
-- Then run the VERIFICATION block at the bottom (read-only).
--
-- Idempotent: each UPDATE is guarded by the state it corrects, so a second run matches 0 rows and the
-- row-count assertion aborts it (nothing is written twice).
--
-- Rule (CLAUDE.md "Manual Validator overrides"): every change is announced in validation_notes by a
-- prepended `CORRECCIÓN MANUAL` header; the previous text is kept below it.

begin;

-- ---------------------------------------------------------------------------------------------
-- 0. Snapshot of every row this file may touch (dropped at commit). Used by the invariants check.
-- ---------------------------------------------------------------------------------------------
create temp table _snap on commit drop as
select id, name, city, country, status, verified, outreach_opt_out, safety_level,
       validation_confidence, lat, lng, flags, validation_notes
from public.places
where id in (
  -- 1. seed sample places (13)
  '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000003',
  '00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000006',
  '00000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000009',
  '00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000012',
  '00000000-0000-0000-0000-000000000013',
  -- 2. Argentine places labelled Uruguay (8 approved + 15 needs_review)
  'b83bfeff-c953-4b2d-b235-8e389529a9d9', '8631209e-4c8a-4065-b594-f33c8dad39d8', '45338a64-d4e5-4f0e-8944-ddcec2372f4d',
  'b45a13a0-2a87-47fa-9cfc-b6f68666b889', 'dd9758ce-1ff0-4a48-aba4-78a17e87ebe9', '8f8e59b7-f962-4b01-86cd-c9e2972d4ad3',
  'd3cae022-2d1d-4d05-bcf7-a9f473d55d86', 'bd6251f6-4c82-4a2c-911d-b4553a21345f',
  'caf1d702-9118-4719-a87f-da7401024eec', '954a9ada-dca3-4b4c-82ea-a65587d9354f', 'ed0c06f5-1b42-4497-bc16-360c730d6426',
  '0190a759-7891-4c3b-9d4a-c8b03dfcbd25', '20c3ea9a-8505-4186-8218-956b73be2778', 'f86e568d-0f3f-4eba-b382-8bdca3622638',
  '23788208-b540-40d5-b828-790dacc34c7e', '09e549fa-c139-4f76-9a54-31dc3b5c18c9', '1255f0ff-4dee-4b3c-bf2d-5e5173ad3b89',
  '311faa57-37f0-4895-b736-c472366c9946', '92f88609-171d-4549-acd4-47d4e71a908c', 'f72f8a44-c679-4102-bc3c-49927339d61c',
  '0f31d9b8-f853-4888-a0ce-006ce91356c0', '435a6c9f-bbb9-4b87-85ea-75ead0123ebd', 'd323d8d3-e18a-4a14-abb3-bee1f2c678da',
  -- 3. not a business (1 more; the other two are already in block 2)
  'f1b5af9c-41c9-4868-8dff-c1462074b8af',
  -- 4. city only (5)
  'ff8e95b2-806e-4127-b711-6f912285c03a', '0505597e-12f8-4b6a-95b7-0cafb5b2808c', 'b8f1d744-a22a-4bb8-859b-d526066beafc',
  '0ae93217-7bbe-4d54-b971-8c1a221d02fd', 'a524388a-bccc-4e26-904a-50b8502611e7'
);

do $$
declare n int;
begin
  select count(*) into n from _snap;
  if n <> 42 then raise exception 'snapshot: esperaba 42 filas, encontré %', n; end if;
end $$;

-- ---------------------------------------------------------------------------------------------
-- 1. The 13 sample places of db/seed.sql were INVENTED (plausible names + real neighbourhoods) and
--    are live on the public map as approved + verified=true. They are not real businesses.
--    Kept as rows (auditable; deleting would also cascade the 4 fake seed reviews and the test
--    outreach_messages row): discarded, unverified, and never to be contacted.
-- ---------------------------------------------------------------------------------------------
do $$
declare n int;
begin
  update public.places
  set status = 'discarded',
      verified = false,
      outreach_opt_out = true,
      validation_notes = concat_ws(E'\n\n',
        'CORRECCIÓN MANUAL 2026-09-25: lugar de ejemplo del seed, no es un negocio real.',
        nullif(validation_notes, ''))
  where id in (
    '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000003',
    '00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000006',
    '00000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000009',
    '00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000012',
    '00000000-0000-0000-0000-000000000013')
    and status = 'approved' and source = 'manual';
  get diagnostics n = row_count;
  if n <> 13 then raise exception 'bloque 1 (seed): esperaba 13 filas, actualicé %', n; end if;
end $$;

-- ---------------------------------------------------------------------------------------------
-- 2. Argentine places stamped country='Uruguay' (all source='social', created 2026-06-04 .. 2026-08-01,
--    i.e. BEFORE the Social agent took the country from the matched address on 2026-08-19 — commit
--    03cb7c2). Same class as db/fixes/2026-08-08-border-city-country-mismatch.sql: country (and, where
--    the stamped city was wrong, city) corrected from the row's own address. 8 approved + 15
--    needs_review. Cities that were already right for the address are re-stated unchanged.
--    Only the 12 discarded rows of this same kind are left as they are (not public; known debt).
-- ---------------------------------------------------------------------------------------------
do $$
declare n int;
begin
  update public.places p
  set country = 'Argentina',
      city = v.city,
      validation_notes = concat_ws(E'\n\n',
        'CORRECCIÓN MANUAL 2026-09-25: país/ciudad corregidos según la dirección.',
        nullif(p.validation_notes, ''))
  from (values
    -- approved
    ('b83bfeff-c953-4b2d-b235-8e389529a9d9'::uuid, 'San Justo'),        -- ALITA GLUTEN FREE — Pampa 4067, San Justo, Pcia. de Buenos Aires
    ('8631209e-4c8a-4065-b594-f33c8dad39d8'::uuid, 'Bella Vista'),      -- Bella Vista SINTACC — O''Higgins 1295, Bella Vista, Pcia. de Buenos Aires
    ('45338a64-d4e5-4f0e-8944-ddcec2372f4d'::uuid, 'Viedma'),           -- Comarca Sin Gluten — Alvaro Barros 256, Viedma, Río Negro
    ('b45a13a0-2a87-47fa-9cfc-b6f68666b889'::uuid, 'Buenos Aires'),     -- La Union gluten Free Triunvirato — Av. Triunvirato 4002, CABA
    ('dd9758ce-1ff0-4a48-aba4-78a17e87ebe9'::uuid, 'Buenos Aires'),     -- MisiaMasa Sin Gluten — Franco 2860, CABA (city was the barrio "Villa Pueyrredón"; CABA = 'Buenos Aires', as the other 108 rows)
    ('8f8e59b7-f962-4b01-86cd-c9e2972d4ad3'::uuid, 'Maschwitz'),        -- QQ - Quinoa Queen — Mendoza 1578, Ingeniero Maschwitz, Pcia. de Buenos Aires
    ('d3cae022-2d1d-4d05-bcf7-a9f473d55d86'::uuid, 'Tucumán'),          -- Sin tacc tucuman — Sta. Fe 704, San Miguel de Tucumán
    ('bd6251f6-4c82-4a2c-911d-b4553a21345f'::uuid, 'Berisso'),          -- Vaceliac sin tacc — Av. Montevideo e 17 y 18, Berisso, Pcia. de Buenos Aires
    -- needs_review
    ('caf1d702-9118-4719-a87f-da7401024eec'::uuid, 'Buenos Aires'),     -- Almacén Natural del Mercado — Carlos Calvo 455, CABA
    ('954a9ada-dca3-4b4c-82ea-a65587d9354f'::uuid, 'Buenos Aires'),     -- Almacén Natural Santa Anita — Estados Unidos 3619, CABA
    ('ed0c06f5-1b42-4497-bc16-360c730d6426'::uuid, 'La Plata'),         -- Asociación Celíaca Argentina — C. 24 1907, La Plata (city was "Mar del Plata")
    ('0190a759-7891-4c3b-9d4a-c8b03dfcbd25'::uuid, 'Buenos Aires'),     -- Celi events — Av. Rivadavia 4702, CABA (city was "CABA")
    ('20c3ea9a-8505-4186-8218-956b73be2778'::uuid, 'Boulogne'),         -- Dietéticas Tomy — Av. Avelino Rolón 2101, Boulogne, Pcia. de Buenos Aires (city was "Montevideo")
    ('f86e568d-0f3f-4eba-b382-8bdca3622638'::uuid, 'San Miguel'),       -- Duke Resto — Av. León Gallardo 330, Muñiz (partido de San Miguel)
    ('23788208-b540-40d5-b828-790dacc34c7e'::uuid, 'Buenos Aires'),     -- Eleven Helados de Autor — Castillo 309, CABA
    ('09e549fa-c139-4f76-9a54-31dc3b5c18c9'::uuid, 'Salta'),            -- Filipo Cafe Resto Bar — Av. del Bicentenario 1401, Salta
    ('1255f0ff-4dee-4b3c-bf2d-5e5173ad3b89'::uuid, 'Buenos Aires'),     -- La Carnicería — Thames 2317, CABA
    ('311faa57-37f0-4895-b736-c472366c9946'::uuid, 'Salta'),            -- La Chipacería — Los Perales 170, Salta
    ('92f88609-171d-4549-acd4-47d4e71a908c'::uuid, 'Jardín América'),   -- Punto Sano — Av. Antártida Argentina, Jardín América, Misiones
    ('f72f8a44-c679-4102-bc3c-49927339d61c'::uuid, 'Buenos Aires'),     -- Selvático — Mendoza 5320, CABA
    ('0f31d9b8-f853-4888-a0ce-006ce91356c0'::uuid, 'Temperley'),        -- Sin Gluten Club — Conscripto Bernardi 150, Temperley, Pcia. de Buenos Aires (city was "Buenos Aires")
    ('435a6c9f-bbb9-4b87-85ea-75ead0123ebd'::uuid, 'Vicente López'),    -- Sin Gluten Olivos — Roque Sáenz Peña 1526, Olivos (partido de Vicente López)
    ('d323d8d3-e18a-4a14-abb3-bee1f2c678da'::uuid, 'Villa Bosch')       -- Siroppo Helados - Villa Bosch — San Miguel Garicoits 1092, Villa Bosch
  ) as v(id, city)
  where p.id = v.id
    and p.country = 'Uruguay'
    and p.status in ('approved', 'needs_review');
  get diagnostics n = row_count;
  if n <> 23 then raise exception 'bloque 2 (país): esperaba 23 filas, actualicé %', n; end if;
end $$;

-- ---------------------------------------------------------------------------------------------
-- 3. Rows that are not a business: an event (ExpoCelíaca, approved as a 100% "shop" at 0.85 — a
--    trade fair at Costa Salguero) and two organisations (Celi events, Asociación Celíaca
--    Argentina — both already needs_review, so not public). status -> discarded. Runs AFTER block 2 so
--    the two that also had their country fixed keep both headers (this one on top).
-- ---------------------------------------------------------------------------------------------
do $$
declare n int;
begin
  update public.places
  set status = 'discarded',
      validation_notes = concat_ws(E'\n\n',
        'CORRECCIÓN MANUAL 2026-09-25: no es un comercio (es un evento o una organización), no corresponde a este mapa; descartado.',
        nullif(validation_notes, ''))
  where id in (
    'f1b5af9c-41c9-4868-8dff-c1462074b8af',   -- ExpoCelíaca (approved)
    '0190a759-7891-4c3b-9d4a-c8b03dfcbd25',   -- Celi events (needs_review)
    'ed0c06f5-1b42-4497-bc16-360c730d6426')   -- Asociación Celíaca Argentina (needs_review)
    and status in ('approved', 'needs_review');
  get diagnostics n = row_count;
  if n <> 3 then raise exception 'bloque 3 (no comercio): esperaba 3 filas, actualicé %', n; end if;
end $$;

-- ---------------------------------------------------------------------------------------------
-- 4. City that is not a city: two postal codes (Venekafe "C1425ESA", Pilar Sin Gluten "B1629ETD") and
--    three more of the same class found in the sweep — a barrio (TACCOFF "Palermo"), the official long
--    form (Cucinetta "Cdad. Autónoma de Buenos Aires") and a stale query target (Donato "Salto", for a
--    CABA address). CABA is 'Buenos Aires' everywhere else (108 rows). Country was already right.
-- ---------------------------------------------------------------------------------------------
do $$
declare n int;
begin
  update public.places p
  set city = v.new_city,
      validation_notes = concat_ws(E'\n\n',
        'CORRECCIÓN MANUAL 2026-09-25: ciudad corregida según la dirección.',
        nullif(p.validation_notes, ''))
  from (values
    ('ff8e95b2-806e-4127-b711-6f912285c03a'::uuid, 'C1425ESA', 'Buenos Aires'),                       -- Venekafe Sin Tacc — Jean Jaures 1187, CABA
    ('0505597e-12f8-4b6a-95b7-0cafb5b2808c'::uuid, 'B1629ETD', 'Pilar'),                              -- Pilar Sin Gluten — San Martín 132, Pilar
    ('b8f1d744-a22a-4bb8-859b-d526066beafc'::uuid, 'Salto', 'Buenos Aires'),                          -- Donato (sin tacc) — Arévalo 1538, CABA
    ('0ae93217-7bbe-4d54-b971-8c1a221d02fd'::uuid, 'Palermo', 'Buenos Aires'),                        -- TACCOFF - 100% Gluten Free — Nicaragua 5977, Palermo, CABA
    ('a524388a-bccc-4e26-904a-50b8502611e7'::uuid, 'Cdad. Autónoma de Buenos Aires', 'Buenos Aires')  -- Cucinetta — Mcal. A. J. de Sucre 1302, CABA
  ) as v(id, old_city, new_city)
  where p.id = v.id and p.city = v.old_city;
  get diagnostics n = row_count;
  if n <> 5 then raise exception 'bloque 4 (ciudad): esperaba 5 filas, actualicé %', n; end if;
end $$;

-- ---------------------------------------------------------------------------------------------
-- 5. Invariants. Fields this file must never change, and the exact set of status / verified changes.
-- ---------------------------------------------------------------------------------------------
do $$
declare n int;
begin
  select count(*) into n from _snap s join public.places p on p.id = s.id
  where p.lat is distinct from s.lat or p.lng is distinct from s.lng
     or p.validation_confidence is distinct from s.validation_confidence
     or p.safety_level is distinct from s.safety_level
     or p.flags is distinct from s.flags;
  if n <> 0 then raise exception 'invariante: % filas cambiaron lat/lng/confidence/safety_level/flags', n; end if;

  select count(*) into n from _snap s join public.places p on p.id = s.id where p.status is distinct from s.status;
  if n <> 16 then raise exception 'invariante: esperaba 16 cambios de status (13 seed + 3 no comercios), hubo %', n; end if;

  select count(*) into n from _snap s join public.places p on p.id = s.id where p.verified is distinct from s.verified;
  if n <> 13 then raise exception 'invariante: esperaba 13 cambios de verified (solo el seed), hubo %', n; end if;

  -- literal search (strpos), not LIKE: an old note containing % _ or \ must not act as a wildcard
  select count(*) into n from _snap s join public.places p on p.id = s.id
  where strpos(coalesce(p.validation_notes, ''), 'CORRECCIÓN MANUAL 2026-09-25') = 0
     or strpos(coalesce(p.validation_notes, ''), coalesce(nullif(s.validation_notes, ''), '')) = 0;
  if n <> 0 then raise exception 'invariante: % filas sin el encabezado o sin el texto original', n; end if;
end $$;

commit;

-- =============================================================================================
-- VERIFICATION (read-only) — run AFTER the commit above, as a single statement:
--   node_modules/.bin/supabase db query --linked -o table "<the select below>"
-- Every row must read ok = true.
-- =============================================================================================
select check_name, expected, actual, (expected = actual) as ok from (
  select 1 as n, 'seed places now discarded + unverified + opt-out' as check_name, 13 as expected,
         (select count(*) from public.places
           where id::text ~ '^00000000-0000-0000-0000-0000000000(0[1-9]|1[0-3])$'
             and status = 'discarded' and verified = false and outreach_opt_out = true) as actual
  union all
  select 2, 'seed places still visible on the map (approved)', 0,
         (select count(*) from public.places
           where id::text ~ '^00000000-0000-0000-0000-0000000000(0[1-9]|1[0-3])$' and status = 'approved')
  union all
  select 3, 'approved/needs_review with an Argentine address labelled Uruguay', 0,
         (select count(*) from public.places
           where status in ('approved', 'needs_review') and address ~* 'argentina' and country = 'Uruguay')
  union all
  select 4, 'approved/needs_review/pending whose city looks like a postal code', 0,
         (select count(*) from public.places
           where status in ('approved', 'needs_review', 'pending')
             and (city ~ '^[A-Za-z]?[0-9]{4}[A-Za-z]{0,3}$' or city ~ '[0-9]{4}'))
  union all
  select 5, 'CABA rows (address) with a city other than Buenos Aires, approved/needs_review', 0,
         (select count(*) from public.places
           where status in ('approved', 'needs_review') and address ~* 'Aut[oó]noma de Buenos Aires' and city <> 'Buenos Aires')
  union all
  select 6, 'rows carrying the 2026-09-25 correction header (13 + 23 + 1 + 5)', 42,
         (select count(*) from public.places where validation_notes like '%CORRECCIÓN MANUAL 2026-09-25%')
  union all
  select 7, 'approved gluten_free_100 places (313 before − 6 seed − ExpoCelíaca)', 306,
         (select count(*) from public.places where status = 'approved' and safety_level = 'gluten_free_100')
  union all
  select 8, 'ExpoCelíaca / Celi events / Asociación Celíaca Argentina discarded', 3,
         (select count(*) from public.places
           where id in ('f1b5af9c-41c9-4868-8dff-c1462074b8af', '0190a759-7891-4c3b-9d4a-c8b03dfcbd25',
                        'ed0c06f5-1b42-4497-bc16-360c730d6426') and status = 'discarded')
) c order by n;
