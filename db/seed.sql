-- =====================================================================
-- CeliacMap — db/seed.sql
-- Community-ranking votes for REAL, already-approved places (ADR-005 Fase D).
-- Run AFTER db/schema.sql, in the Supabase SQL Editor. Idempotent
-- (ON CONFLICT DO NOTHING), so re-running is safe.
--
-- This file used to also insert 13 SAMPLE places (Sin Gluten Pocitos,
-- Palermo Sin TACC, ...) plus 4 sample reviews, all `approved` and
-- `verified`. They were INVENTED names at real neighbourhood coordinates,
-- not businesses, and they ended up live on the public map. They were
-- removed here and discarded in production on 2026-09-25 (see
-- db/fixes/2026-09-25-seed-and-data-quality.sql and CLAUDE.md, Decisions
-- Log). Do NOT add fictional places back: for local development, insert
-- them as status 'discarded' (or in a separate, never-production file).
--
-- NOTE: the votes below reference production place ids, so on a fresh
-- database (no agent-discovered places yet) they would violate the
-- place_votes foreign key and should be skipped.
-- =====================================================================

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
