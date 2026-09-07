-- Manual curation — real Montevideo/Uruguay gluten-free businesses missing from
-- the map, plus fixes to rows the agents got wrong. Investigated 2026-09-06/07
-- (see the conversation log and CLAUDE.md). Every business here was cross-checked
-- against community sources (findmeglutenfree, viajosingluten, infonegocios,
-- ACELU) and every place_id re-verified live in Google on 2026-09-07.
--
-- Serendipia is handled OUTSIDE this file (applied 2026-09-07):
--   * d9fd1d57 "Serendipia-cea" approved -> discarded (FALSE POSITIVE: it is an
--     autism-spectrum education center "Serendipia - CEA", not a food business;
--     the Validator read the "-cea" suffix as "sin TACC"). See CLAUDE.md
--     "Validator — interpretación de substring del nombre".
--   * "Serendipia Gluten Free" (@serendipia.glutenfree, Capitán Videla 3059)
--     inserted as a new pending row (id 82fd31e9), geocode_method='address_only'.
--
-- Run: node_modules/.bin/supabase db query --linked --file <this file>
-- Idempotent: every UPDATE guards on the current status; every INSERT uses
-- ON CONFLICT (source, external_id) DO NOTHING.
--
-- Note text is PREPENDED to validation_notes (|| E'\n\n--- ' || ...), never
-- replaced — same pattern as db/fixes/2026-09-01-brazil-out-of-scope-places.sql
-- and the Dalbertt/Los Leños manual overrides.

-- =====================================================================
-- 1. Café Ramona — Centro. Three rows at the San José 894-900 corner are
--    NOT one place: 03ea2fae = the café (place_id ...J7Y, "Café Ramona" in
--    Google, 4.1*/4907), 0c8ed54c = "La Panadería de Ramona" (San José 894,
--    a DISTINCT contiguous business — the ACELU-approved dedicated GF bakery),
--    f62b8851 = a Google street-address pin (types: street_address/subpremise),
--    not a business. Keep the two real businesses as separate rows (same as
--    GOUT / Pain Du Jour / La Unión in the DB), discard the pin.
--    Both real businesses are 100% gluten-free.
-- =====================================================================

-- 1a. 03ea2fae -> Café Ramona sucursal Centro (el café). discarded -> pending.
--     source social -> google_places: closes the only real dedup gap — the
--     Search agent inserts via ON CONFLICT (source, external_id) and does NOT
--     call place_exists_by_external_id, so a future Search hit on place_id
--     ...J7Y as 'google_places' would NOT conflict with a 'social' row and
--     would create a duplicate. As 'google_places' it conflicts and is
--     ignored. The row is anchored to a real Google place_id, so the label
--     is also more accurate.
update public.places set
  name         = 'Café Ramona - Centro',
  source       = 'google_places',
  safety_level = 'gluten_free_100',
  status       = 'pending',
  social_url   = 'https://www.instagram.com/caferamona_uy',
  phone        = '2900 5247',
  validation_notes =
    'REVISIÓN MANUAL (2026-09-07, Santiago Sánchez): reseteado a pending. Sucursal CENTRO de Café Ramona (San José 900 esq. Convención; place_id ChIJT9xztCyAn5URUtT784grJ7Y = "Café Ramona" en Google, 4.1 estrellas / 4907 reseñas). Café/panadería de comida natural y artesanal, 100% sin gluten segun fuentes de la comunidad celiaca (viajosingluten, findmeglutenfree). NO se consolida con 0c8ed54c: esa fila es "La Panadería de Ramona" (San José 894), un negocio distinto y contiguo — la panadería GF dedicada habilitada por ACELU. source cambiado social -> google_places para cerrar el hueco de deduplicación del Search agent. IG @caferamona_uy, tel 2900 5247.'
    || E'\n\n--- Nota previa del Validator (discarded, confidence 0.15): '
    || coalesce(validation_notes, '')
where id = '03ea2fae-834c-48c0-9f7e-b43b089dc4b4'
  and status = 'discarded';

-- 1b. 0c8ed54c -> La Panadería de Ramona (panadería GF dedicada, ACELU).
--     needs_review -> pending.
update public.places set
  name         = 'La Panadería de Ramona',
  safety_level = 'gluten_free_100',
  status       = 'pending',
  social_url   = 'https://www.facebook.com/lapanaderiaderamona',
  validation_notes =
    'REVISIÓN MANUAL (2026-09-07, Santiago Sánchez): reseteado a pending. "La Panadería de Ramona" (San José 894; place_id ChIJGxvKy-KBn5URQ_J2NkjKFj4): primera panadería del Uruguay con productos 100% para celiacos, TODO sin gluten sin riesgo de contaminación cruzada, HABILITADA POR ACELU (infonegocios.biz, findmeglutenfree, viajosingluten). Negocio distinto y contiguo a Café Ramona Centro (fila 03ea2fae, San José 900). tel 2900 5247, FB /lapanaderiaderamona.'
    || E'\n\n--- Nota previa (RE-VALIDACIÓN RETROACTIVA 2026-09-06, needs_review, confidence 0.5): '
    || coalesce(validation_notes, '')
where id = '0c8ed54c-b0ef-430d-aa99-1a05da52be19'
  and status = 'needs_review';

-- 1c. f62b8851 -> Google street-address pin, not a business. Stays discarded;
--     note explains why so it is never "recovered".
update public.places set
  validation_notes =
    'CORRECCIÓN MANUAL (2026-09-07, Santiago Sánchez): descartada permanente. place_id ChIJhZj2tCyAn5URmHyGRuz-HFo es un pin de dirección de Google (types: street_address, subpremise), NO un negocio. El Social agent lo tomó de un post de IG y lo geocodeó a la esquina de San José 900. El negocio real de esa esquina (Café Ramona Centro) está en la fila 03ea2fae. No re-evaluar.'
    || E'\n\n--- Nota previa del Validator (discarded, confidence 0.1): '
    || coalesce(validation_notes, '')
where id = 'f62b8851-f1dd-4872-aff4-e5d2db5cc967'
  and status = 'discarded'
  and validation_notes not like 'CORRECCIÓN MANUAL (2026-09-07%';

-- =====================================================================
-- 2. Café Ramona — WTC (Pocitos/Buceo). Found by the Web agent 2026-06-09
--    with this exact place_id but the INSERT failed on the old
--    places_source_check (source='web', since fixed). place_id re-verified
--    2026-09-07: "Ramona WTC", OPERATIONAL, tel 2623 6228, web @caferamona_uy,
--    4.0*/2356. findmeglutenfree: "Dedicated Gluten-Free Restaurant".
-- =====================================================================
insert into public.places
  (name, lat, lng, category, country, city, safety_level, status, address,
   source, external_id, social_url, phone, rating, user_ratings_total, validation_notes)
values
  ('Café Ramona - WTC', -34.9058688, -56.1364671, 'cafe', 'Uruguay', 'Montevideo',
   'gluten_free_100', 'pending',
   'Av. Luis Alberto de Herrera 1196, 11300 Montevideo, Departamento de Montevideo, Uruguay',
   'manual', 'ChIJc7h_pFCBn5URzCT8m000Ig4',
   'https://www.instagram.com/caferamona_uy', '2623 6228', 4.0, 2356,
   'Agregado manualmente por el administrador (2026-09-07). Sucursal WTC (Pocitos/Buceo) de Café Ramona, 100% sin gluten (findmeglutenfree: "Dedicated Gluten-Free Restaurant"). Descubierto por el Web agent el 2026-06-09 con este mismo place_id, pero el INSERT falló por el bug de places_source_check (source=web, ya corregido). place_id re-verificado en Google 2026-09-07: OPERATIONAL, tel 2623 6228, web @caferamona_uy, 4.0 estrellas / 2356 reseñas.')
on conflict (source, external_id) do nothing;

-- =====================================================================
-- 3. Casa & Dispensa (1e21c93a) — Solano García 2496, Punta Carretas.
--    discarded -> pending. Confirmed 100% GF: boutique patisserie + café +
--    mini-market, "everything is gluten-free, no risk of cross-contamination"
--    (findmeglutenfree; formerly "Goût Gluten Free"). tel 091 021 273,
--    web casadispensa.uy, 4.5*/37.
-- =====================================================================
update public.places set
  status       = 'pending',
  safety_level = 'gluten_free_100',
  social_url   = 'https://www.instagram.com/casadispensa',
  phone        = '091 021 273',
  website      = 'https://casadispensa.uy/',
  rating       = 4.5,
  user_ratings_total = 37,
  validation_notes =
    'REVISIÓN MANUAL (2026-09-07, Santiago Sánchez): reseteado de discarded a pending. Casa & Dispensa (Solano García 2496, Punta Carretas) es pasteleria boutique + café + mini-market 100% sin gluten — "everything is gluten-free, no risk of cross-contamination" (findmeglutenfree; antes operaba como "Gout Gluten Free"). WhatsApp 091 021 273, web casadispensa.uy, IG @casadispensa. La ficha de Google no lo declaraba, por eso el Validator lo descartó solo por el nombre en 2026-06; el Social agent lo detectó ("CASA & DISPENSA 100% GLUTEN FREE") pero el geocode falló repetidamente por bugs de API.'
    || E'\n\n--- Nota previa del Validator (discarded, confidence 0.65): '
    || coalesce(validation_notes, '')
where id = '1e21c93a-0030-4c99-8ef1-eab8d487130f'
  and status = 'discarded';

-- =====================================================================
-- 4. La Commedia (7363c257) — El Viejo Pancho 2414. discarded -> pending.
--    Confirmed 100% GF: dedicated kitchen, celiac owner, no cross-contamination;
--    one of the most celiac-friendly restaurants in Montevideo (findmeglutenfree,
--    wanderlog, viajosingluten). Operating since 1995. tel 2706 6997,
--    IG @lacommedia, 4.2*/1850.
-- =====================================================================
update public.places set
  status       = 'pending',
  safety_level = 'gluten_free_100',
  social_url   = 'https://www.instagram.com/lacommedia',
  phone        = '2706 6997',
  rating       = 4.2,
  user_ratings_total = 1850,
  validation_notes =
    'REVISIÓN MANUAL (2026-09-07, Santiago Sánchez): reseteado de discarded a pending. La Commedia (El Viejo Pancho 2414) es un restaurante italiano 100% sin gluten — cocina totalmente dedicada, dueño celiaco, sin contaminación cruzada; de los más celiaco-friendly de Montevideo (findmeglutenfree, wanderlog, viajosingluten). Opera desde 1995. La ficha de Google no lo declaraba, por eso el Validator lo descartó solo por el nombre en 2026-06. IG @lacommedia, tel 2706 6997, 4.2 estrellas / 1850 reseñas.'
    || E'\n\n--- Nota previa del Validator (discarded, confidence 0.75): '
    || coalesce(validation_notes, '')
where id = '7363c257-9596-4aa1-a329-29d994d2eb65'
  and status = 'discarded';

-- =====================================================================
-- 5a. Croc — local principal (8ffbc4ee) — Andes 1206 (= renamed
--     "José Germán Araujo 1206"). Confirmed = @crocpanaderiasingluten
--     ("Croc Panadería y Rotisería Sin Gluten"), 100% GF since 2016.
--     needs_review -> pending: a needs_review row is NEVER re-evaluated
--     automatically (ValidatorAgent.run fetches status='pending' only), so
--     "let the Validator re-check it with the expanded context" requires
--     pending. tel 093 321 619 / 2904 8277, 4.7*/168.
-- =====================================================================
update public.places set
  status       = 'pending',
  safety_level = 'gluten_free_100',
  social_url   = 'https://www.instagram.com/crocpanaderiasingluten',
  user_ratings_total = 168,
  validation_notes =
    'REVISIÓN MANUAL (2026-09-07, Santiago Sánchez): reseteado de needs_review a pending para que el Validator lo re-evalúe con el contexto ampliado. "CROC Galletas Artesanales" (Andes 1206) es la misma "Croc Panadería y Rotisería Sin Gluten" (@crocpanaderiasingluten), cocina inclusiva 100% sin gluten desde 2016. "Andes 1206" = tramo renombrado "José Germán Araujo 1206". FB "Croc Productos Artesanales sin Gluten", tel 093 321 619 / 2904 8277, 4.7 estrellas / 168 reseñas en Google.'
    || E'\n\n--- Nota previa (RE-VALIDACIÓN RETROACTIVA 2026-09-06, needs_review, confidence 0.52): '
    || coalesce(validation_notes, '')
where id = '8ffbc4ee-69f6-41e0-af31-2dc46be9ec79'
  and status = 'needs_review';

-- 5b. "Crocs Tres Cruces" (7e64127d) — the Social agent geocoded "Croc"
--     (from a crocpanaderiasingluten FB video) and Find Place matched the
--     CROCS SHOE STORE in Tres Cruces mall (place_id ...L2c, name "Crocs",
--     types: shoe_store, crocs.com.uy, tel 2406 8952). NOT the bakery.
--     needs_review -> discarded.
update public.places set
  status = 'discarded',
  validation_notes =
    'CORRECCIÓN MANUAL (2026-09-07, Santiago Sánchez): descartada. El Social agent geocodeó "Croc" (de un video de FB de @crocpanaderiasingluten) y Google Find Place matcheó la TIENDA DE ZAPATILLAS "Crocs" del shopping Tres Cruces — place_id ChIJt0X56VOAn5URw0aPBuH5L2c, "Crocs", type=shoe_store, crocs.com.uy, tel 2406 8952, Local 153. NO es la panadería sin gluten. Bug conocido "resolve_location devuelve el negocio equivocado" (CLAUDE.md, Key risks). La sucursal "perdida" de junio en Montevideo Shopping (place_id ChIJNawJAD6Bn5URzc4DohUEvhE) también es la zapatería Crocs — no se recupera.'
    || E'\n\n--- Nota previa del Validator (needs_review, confidence 0.62): '
    || coalesce(validation_notes, '')
where id = '7e64127d-8a86-4803-8a0e-960d057bebfc'
  and status = 'needs_review';

-- =====================================================================
-- 8. La Molienda — 9 physical stores (lamolienda.uy/tiendas). Uruguayan
--    natural-products / dietética chain with a wide sin-TACC section and
--    cafeterías (NOT a dedicated GF business). All 9 resolved via Google
--    Find Place to real "La Molienda" listings (OPERATIONAL), none present
--    in `places` (dedup clean). category='shop', safety_level='options_available'
--    — the Validator adjusts each. geocode_method NULL (real Google Places,
--    same as Search-agent rows).
-- =====================================================================
insert into public.places
  (name, lat, lng, category, country, city, safety_level, status, address, source, external_id, social_url, validation_notes)
values
 ('La Molienda - 18 de Julio',    -34.9064628, -56.1974314, 'shop', 'Uruguay', 'Montevideo',         'options_available', 'pending', 'Av. 18 de Julio 888, 11100 Montevideo, Departamento de Montevideo, Uruguay',                                     'manual', 'ChIJv9aooiyAn5UR-fAE1Wu1bWc', 'https://www.lamolienda.uy/tiendas', 'Agregado manualmente por el administrador (2026-09-07). Sucursal de La Molienda (cadena uruguaya de dietéticas / productos naturales, con sección sin TACC y cafetería). Direcciones de lamolienda.uy/tiendas; coords + place_id via Google Find Place (OPERATIONAL).'),
 ('La Molienda - Ejido',          -34.9042405, -56.1871319, 'shop', 'Uruguay', 'Montevideo',         'options_available', 'pending', 'Ejido 1423, 11100 Montevideo, Departamento de Montevideo, Uruguay',                                              'manual', 'ChIJ5wcHWzOAn5URILUQINxXj1I', 'https://www.lamolienda.uy/tiendas', 'Agregado manualmente por el administrador (2026-09-07). Sucursal de La Molienda (dietética con sección sin TACC y cafetería). lamolienda.uy/tiendas; place_id via Google Find Place (OPERATIONAL).'),
 ('La Molienda - Sarandí',        -34.9072767, -56.2038858, 'shop', 'Uruguay', 'Montevideo',         'options_available', 'pending', 'Sarandí 550, 11000 Montevideo, Departamento de Montevideo, Uruguay',                                             'manual', 'ChIJF7lrX4B_n5URMaeTDs0BrFA', 'https://www.lamolienda.uy/tiendas', 'Agregado manualmente por el administrador (2026-09-07). Sucursal de La Molienda (dietética con sección sin TACC y cafetería). lamolienda.uy/tiendas; place_id via Google Find Place (OPERATIONAL).'),
 ('La Molienda - Costa Urbana',   -34.8415267, -55.9935543, 'shop', 'Uruguay', 'Ciudad de la Costa', 'options_available', 'pending', 'Av. Giannattasio Km 21, Costa Urbana Shopping, 15000 Ciudad de la Costa, Departamento de Canelones, Uruguay',    'manual', 'ChIJ52k8OOqJn5URLw4uIf-Jw2Y', 'https://www.lamolienda.uy/tiendas', 'Agregado manualmente por el administrador (2026-09-07). Sucursal de La Molienda en Costa Urbana Shopping (Canelones). lamolienda.uy/tiendas; place_id via Google Find Place (OPERATIONAL).'),
 ('La Molienda - Punta Carretas', -34.9246571, -56.1584938, 'shop', 'Uruguay', 'Montevideo',         'options_available', 'pending', 'José Ellauri 350, Punta Carretas Shopping, 11300 Montevideo, Departamento de Montevideo, Uruguay',              'manual', 'ChIJrQ9dNoaBn5URHVr_D-EWJzQ', 'https://www.lamolienda.uy/tiendas', 'Agregado manualmente por el administrador (2026-09-07). Sucursal de La Molienda en Punta Carretas Shopping. lamolienda.uy/tiendas; place_id via Google Find Place (OPERATIONAL).'),
 ('La Molienda - ACJ (Colonia)',  -34.9010859, -56.1764612, 'shop', 'Uruguay', 'Montevideo',         'options_available', 'pending', 'Colonia 1870, 11200 Montevideo, Departamento de Montevideo, Uruguay',                                            'manual', 'ChIJ6_LKcQCBn5URJjqw8jfuvQg', 'https://www.lamolienda.uy/tiendas', 'Agregado manualmente por el administrador (2026-09-07). Sucursal de La Molienda (dietética con sección sin TACC y cafetería). lamolienda.uy/tiendas; place_id via Google Find Place (OPERATIONAL).'),
 ('La Molienda - Carrasco',       -34.8805097, -56.0618337, 'shop', 'Uruguay', 'Montevideo',         'options_available', 'pending', 'Av. Alfredo Arocena 2014, 11500 Montevideo, Departamento de Montevideo, Uruguay',                                'manual', 'ChIJTTnAwHiHn5UR34qclj8snIU', 'https://www.lamolienda.uy/tiendas', 'Agregado manualmente por el administrador (2026-09-07). Sucursal de La Molienda en Carrasco (dietética con sección sin TACC y cafetería). lamolienda.uy/tiendas; place_id via Google Find Place (OPERATIONAL).'),
 ('La Molienda - Parque Rodó',    -34.9102754, -56.1703544, 'shop', 'Uruguay', 'Montevideo',         'options_available', 'pending', 'Dr. Pablo de María 1018, 11200 Montevideo, Departamento de Montevideo, Uruguay',                                 'manual', 'ChIJBzPKEv2Bn5UR5gxHBtswjIU', 'https://www.lamolienda.uy/tiendas', 'Agregado manualmente por el administrador (2026-09-07). Sucursal de La Molienda (dietética con sección sin TACC). lamolienda.uy/tiendas; place_id via Google Find Place (OPERATIONAL).'),
 ('La Molienda - Tres Cruces',    -34.8938251, -56.1663526, 'shop', 'Uruguay', 'Montevideo',         'options_available', 'pending', 'Bulevar Artigas 1825, Terminal Tres Cruces, 11800 Montevideo, Departamento de Montevideo, Uruguay',             'manual', 'ChIJp51nAQCBn5URtKDpdhuIBXM', 'https://www.lamolienda.uy/tiendas', 'Agregado manualmente por el administrador (2026-09-07). Sucursal de La Molienda en la Terminal Tres Cruces. lamolienda.uy/tiendas; place_id via Google Find Place (OPERATIONAL).')
on conflict (source, external_id) do nothing;
