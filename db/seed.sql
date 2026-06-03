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
