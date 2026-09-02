-- =====================================================================
-- CeliacMap — db/seed.sql
-- Phase 1 manual seed: ~13 places across Montevideo (UY) and Buenos
-- Aires (AR), a mix of restaurants, cafés and shops, marked approved.
-- Run AFTER db/schema.sql, in the Supabase SQL Editor.
--
-- Idempotent: fixed UUIDs + ON CONFLICT DO NOTHING, so re-running is safe.
--
-- NOTE: these are realistic SAMPLE entries (plausible names, real
-- neighborhoods and coordinates) for development/demo. They are NOT
-- verified safety claims about specific real businesses. Real, agent-
-- and community-validated data will replace/augment this over time.
-- =====================================================================

insert into public.places
  (id, name, lat, lng, category, country, city, safety_level, verified, status, address, source)
values
  -- ----------------------- Montevideo, Uruguay -----------------------
  ('00000000-0000-0000-0000-000000000001', 'Sin Gluten Pocitos',   -34.90870, -56.15160, 'restaurant', 'Uruguay', 'Montevideo', 'gluten_free_100',  true, 'approved', 'Av. Brasil 2700, Pocitos',        'manual'),
  ('00000000-0000-0000-0000-000000000002', 'Café Cordón Verde',    -34.90110, -56.17890, 'cafe',       'Uruguay', 'Montevideo', 'celiac_friendly',  true, 'approved', 'Av. 18 de Julio 1500, Cordón',    'manual'),
  ('00000000-0000-0000-0000-000000000003', 'Almacén Celíaco',      -34.92300, -56.15600, 'shop',       'Uruguay', 'Montevideo', 'gluten_free_100',  true, 'approved', 'Ellauri 800, Punta Carretas',     'manual'),
  ('00000000-0000-0000-0000-000000000004', 'La Pasta Libre',       -34.90550, -56.20100, 'restaurant', 'Uruguay', 'Montevideo', 'celiac_friendly',  true, 'approved', 'Sarandí 600, Ciudad Vieja',       'manual'),
  ('00000000-0000-0000-0000-000000000005', 'Dulce Sin TACC',       -34.90600, -56.19250, 'cafe',       'Uruguay', 'Montevideo', 'gluten_free_100',  true, 'approved', 'Río Negro 1300, Centro',          'manual'),
  ('00000000-0000-0000-0000-000000000006', 'Mercado Sano',         -34.91220, -56.14850, 'shop',       'Uruguay', 'Montevideo', 'options_available', true, 'approved', 'Av. Rivera 2500, Pocitos',        'manual'),

  -- --------------------- Buenos Aires, Argentina ---------------------
  ('00000000-0000-0000-0000-000000000007', 'Palermo Sin TACC',     -34.58890, -58.43060, 'restaurant', 'Argentina', 'Buenos Aires', 'gluten_free_100',  true, 'approved', 'Thames 1800, Palermo',         'manual'),
  ('00000000-0000-0000-0000-000000000008', 'Café Recoleta Libre',  -34.58750, -58.39740, 'cafe',       'Argentina', 'Buenos Aires', 'celiac_friendly',  true, 'approved', 'Av. Callao 1200, Recoleta',    'manual'),
  ('00000000-0000-0000-0000-000000000009', 'Dietética Belgrano',   -34.56270, -58.45830, 'shop',       'Argentina', 'Buenos Aires', 'options_available', true, 'approved', 'Av. Cabildo 2200, Belgrano',   'manual'),
  ('00000000-0000-0000-0000-000000000010', 'La Spiga Senza',       -34.59900, -58.43800, 'restaurant', 'Argentina', 'Buenos Aires', 'gluten_free_100',  true, 'approved', 'Av. Corrientes 5400, Villa Crespo', 'manual'),
  ('00000000-0000-0000-0000-000000000011', 'San Telmo Gluten Free',-34.62100, -58.37300, 'cafe',       'Argentina', 'Buenos Aires', 'celiac_friendly',  true, 'approved', 'Defensa 900, San Telmo',       'manual'),
  ('00000000-0000-0000-0000-000000000012', 'Caballito Celíaco',    -34.61900, -58.44000, 'shop',       'Argentina', 'Buenos Aires', 'gluten_free_100',  true, 'approved', 'Av. Rivadavia 5000, Caballito','manual'),
  ('00000000-0000-0000-0000-000000000013', 'Almacén Natural Palermo',-34.58000, -58.42500, 'restaurant', 'Argentina', 'Buenos Aires', 'options_available', true, 'approved', 'Gorriti 5500, Palermo',      'manual')
on conflict (id) do nothing;

-- A few seed reviews (display-only; user_id NULL while auth is deferred).
insert into public.reviews
  (id, place_id, text, rating, source)
values
  ('00000000-0000-0000-0000-0000000a0001', '00000000-0000-0000-0000-000000000001', 'Cocina 100% sin TACC y separada. Comí tranquila por primera vez en años.', 5, 'seed'),
  ('00000000-0000-0000-0000-0000000a0002', '00000000-0000-0000-0000-000000000003', 'Gran variedad de productos sin gluten y el personal sabe del tema.',        5, 'seed'),
  ('00000000-0000-0000-0000-0000000a0003', '00000000-0000-0000-0000-000000000007', 'Menú sin TACC enorme. Las pastas son increíbles.',                          5, 'seed'),
  ('00000000-0000-0000-0000-0000000a0004', '00000000-0000-0000-0000-000000000008', 'Buenas opciones aptas, aunque conviene avisar sobre contaminación cruzada.', 4, 'seed')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- Community ranking seed (ADR-005 Fase D / docs/plans/PLAN-community-ranking.md)
-- ---------------------------------------------------------------------
-- 15 already-approved places chosen by OBJECTIVE criteria (not random, not
-- personal curation): validation_confidence >= 0.85, Google rating >= 4.5 with
-- >= 30 ratings, one place per city, geographic spread across 9 Argentine
-- provinces/metros + 6 Uruguayan departments. Vote counts vary 3..15
-- (quality-correlated) so the ranking isn't an artificial flat staircase.
-- source='seed' keeps these transparent and removable once organic votes
-- dominate. generate_series expands each (place, n) into n rows with token
-- 'seed:<slug>:NN'. Idempotent via ON CONFLICT DO NOTHING. The
-- sync_place_vote_count trigger bumps places.vote_count as these insert.
--
-- DATA DEBT (not blocking): 'JANA GLUTEN FREE | Pizzeria' has TWO approved
-- rows at the same address (Remedios 3400, CABA) — 6797f10b (cafe, rating
-- 4.8/792, seeded here) and 27e34f52 (restaurant, no rating). Same pattern as
-- the Il Porto duplicate; left for a future dedup sweep. See CLAUDE.md
-- Decisions Log, "Community ranking seed — data-quality findings".
insert into public.place_votes (place_id, voter_token, source)
select v.place_id, 'seed:' || v.slug || ':' || lpad(g::text, 2, '0'), 'seed'
from (values
  -- Argentina (9)
  ('6797f10b-800e-4ce3-b070-b265894d1d27'::uuid, 'jana-gluten-free-pizzeria',              15),
  ('5e1e9020-eaa2-4a59-af2e-094240cf0bb7'::uuid, 'gustazo-gluten-free',                     13),
  ('4eae7e88-eeb9-42cc-90fe-5893a3f635a5'::uuid, 'fiambreria-almacen-sin-gluten-martinez',  11),
  ('56fb6f14-de4e-4371-b3a5-88bc428127ff'::uuid, 'alaia-sin-tacc',                           9),
  ('eab30658-e05e-4dd5-ad6d-e97ff0ae1975'::uuid, 'lucha-ldg',                                8),
  ('c236debc-2090-463f-bad3-9551e6de9357'::uuid, 'by-dona-chipa',                            6),
  ('95119cfe-d77c-44bf-b9fe-f66c60a94657'::uuid, 'freee-by-atipico',                         5),
  ('f2a1b0d2-fd3e-411f-b5f3-e370f6a2035b'::uuid, 'jsintacc',                                 4),
  ('19b937f3-92c9-4abf-8dce-0833e032cf6f'::uuid, 'concepcion-sin-tacc',                      3),
  -- Uruguay (6)
  ('06065939-2465-466a-a751-041a6abe0bb4'::uuid, 'sin-gluten-colonia',                      13),
  ('a6a15ba0-eb8c-4579-8fba-7dd3a67e68ec'::uuid, 'glutenoff',                               11),
  ('48a1af62-c888-4c59-9ab0-98592773e7e2'::uuid, 'cafe-nasazzi',                            10),
  ('a6493fc7-279c-4e30-81d3-d79a7e89cc9c'::uuid, 'gluten-out',                               7),
  ('6a73f37f-2ffb-4795-ad2b-a14b1856283b'::uuid, 'casa-campos-paysandu',                     5),
  ('45626955-3ab7-45be-9264-2f349434fcb0'::uuid, 'celisano',                                 4)
) as v(place_id, slug, n)
cross join lateral generate_series(1, v.n) as g
on conflict (place_id, voter_token) do nothing;
