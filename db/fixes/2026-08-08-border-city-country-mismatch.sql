-- One-off data correction — Search agent city/country mismatch.
--
-- Context: SearchAgent.to_candidate() used to stamp every candidate's
-- city/country from the search QUERY target (config/targets.yaml), not from
-- the actual Google Places result's own address. Google's Text Search for a
-- Uruguayan border city (Fray Bentos / Rivera / Salto) can legitimately
-- return a real business located across the border in Argentina; the
-- candidate still got the Uruguayan query's city/country. See CLAUDE.md's
-- "Key risks to keep in mind" for the full investigation (16 rows found: 1,
-- San Felipa - Sin gluten, corrected separately on 2026-08-08 via
-- `supabase db query --linked`; these are the other 15) and the code fix
-- (agents/clients/google_places.py: parse_city_country_from_address /
-- city_country_from_components), applied in the same-day commit that adds
-- this file.
--
-- Every row below already has status='approved' or 'needs_review' and a
-- correct lat/lng (only city/country text was wrong) — verified read-only
-- against production before this file was written; city/country values
-- were derived from each row's own `address` column and reviewed by hand
-- (not auto-applied from a parser) before running.
--
-- Run manually in the Supabase SQL Editor. Idempotent: re-running is a
-- no-op once applied (WHERE clauses target city/country, which won't match
-- again after the first successful run).

-- 1. La Cocina de Matías — Concepción Arenal 3519, C1427EKC Cdad. Autónoma
--    de Buenos Aires, Argentina
update places
set city = 'Buenos Aires', country = 'Argentina'
where id = '29e8f921-b428-4e49-b7ed-5be86650b62e'
  and city = 'Colonia del Sacramento' and country = 'Uruguay';

-- 2. "El veloz" sin TACC — Suipacha 843, Concepción del Uruguay, Entre
--    Ríos, Argentina
update places
set city = 'Concepción del Uruguay', country = 'Argentina'
where id = '37c91881-c4d8-4890-ac48-d1f1b0d7c010'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 3. Concepción sin TACC — Blvd. los Constituyentes 39 E3260, Concepción
--    del Uruguay, Entre Ríos, Argentina
update places
set city = 'Concepción del Uruguay', country = 'Argentina'
where id = '19b937f3-92c9-4abf-8dce-0833e032cf6f'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 4. Dulces Tentaciones (Sin TACC) — E3269 Gualeguaychú, Entre Ríos
--    Province, Argentina
update places
set city = 'Gualeguaychú', country = 'Argentina'
where id = '5553bbc1-9596-412a-9176-3beff6fb5416'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 5. Flor de Postre sin tacc — Sarmiento 999, Concepción del Uruguay,
--    Entre Ríos, Argentina
update places
set city = 'Concepción del Uruguay', country = 'Argentina'
where id = 'e24385bb-01bf-43d9-a678-e72cd6903acb'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 6. La Cocina Sin Gluten — Chalup 161, E2820 Gualeguaychú, Entre Ríos,
--    Argentina
update places
set city = 'Gualeguaychú', country = 'Argentina'
where id = '4d9e7129-9091-4577-9729-51248b5aadec'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 7. Ls sin tacc — 11 de Abril 286, B8000 Bahía Blanca, Provincia de
--    Buenos Aires, Argentina
update places
set city = 'Bahía Blanca', country = 'Argentina'
where id = 'd4378fc5-dc47-4528-be22-a88d0a839793'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 8. Mundo sin TACC — España 824, B6700 Luján, Provincia de Buenos Aires,
--    Argentina
update places
set city = 'Luján', country = 'Argentina'
where id = '88bb052a-f719-4170-9a30-faeecef4c937'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 9. Rotiseria EL MAESTRO SIN GLUTEN — Rocamora 257, E2820 Gualeguaychú,
--    Entre Ríos, Argentina
update places
set city = 'Gualeguaychú', country = 'Argentina'
where id = '95028e87-1725-417d-bd45-4ede4131f182'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 10. Sapori Gluten Free — Sarmiento 375, E3260 Concepción del Uruguay,
--     Entre Ríos, Argentina
update places
set city = 'Concepción del Uruguay', country = 'Argentina'
where id = 'f73250fb-21b3-4cea-9f88-a2a1f6354092'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 11. SinTacc / Libre De Gluten/ por pedidos únicamente — Av. del Valle
--     738 BIS, E2820 Gualeguaychú, Entre Ríos, Argentina
update places
set city = 'Gualeguaychú', country = 'Argentina'
where id = 'e5b20b64-b5bd-44e2-b2d7-9c049c81c0fe'
  and city = 'Fray Bentos' and country = 'Uruguay';

-- 12. Apto Libre de Gluten — León Guruciaga 161, B2900 San Nicolás de Los
--     Arroyos, Provincia de Buenos Aires, Argentina
update places
set city = 'San Nicolás de los Arroyos', country = 'Argentina'
where id = '102f1557-9d12-494d-bd4a-b4395c006b6d'
  and city = 'Rivera' and country = 'Uruguay';

-- 13. "Boa Noite" gluten free — Alvear 844, E3200 Concordia, Entre Ríos,
--     Argentina
update places
set city = 'Concordia', country = 'Argentina'
where id = 'e499828c-2b87-46a0-8b21-7ce5084f2989'
  and city = 'Salto' and country = 'Uruguay';

-- 14. BY DOÑA CHIPA - TRADICIÓN LIBRE DE GLUTEN — 1 de Mayo 449 BIS, E3200
--     Concordia, Entre Ríos, Argentina
update places
set city = 'Concordia', country = 'Argentina'
where id = 'c236debc-2090-463f-bad3-9551e6de9357'
  and city = 'Salto' and country = 'Uruguay';

-- 15. Lo de Pauli Gluten Free — Damián P. Garat 405, E3200 Concordia,
--     Entre Ríos, Argentina
update places
set city = 'Concordia', country = 'Argentina'
where id = 'd7e973e5-f038-4983-8016-d72ec9369617'
  and city = 'Salto' and country = 'Uruguay';

-- Verification query — run after the updates above, expect 0 rows:
-- select id, name, city, country from places
-- where id in (
--   '29e8f921-b428-4e49-b7ed-5be86650b62e', '37c91881-c4d8-4890-ac48-d1f1b0d7c010',
--   '19b937f3-92c9-4abf-8dce-0833e032cf6f', '5553bbc1-9596-412a-9176-3beff6fb5416',
--   'e24385bb-01bf-43d9-a678-e72cd6903acb', '4d9e7129-9091-4577-9729-51248b5aadec',
--   'd4378fc5-dc47-4528-be22-a88d0a839793', '88bb052a-f719-4170-9a30-faeecef4c937',
--   '95028e87-1725-417d-bd45-4ede4131f182', 'f73250fb-21b3-4cea-9f88-a2a1f6354092',
--   'e5b20b64-b5bd-44e2-b2d7-9c049c81c0fe', '102f1557-9d12-494d-bd4a-b4395c006b6d',
--   'e499828c-2b87-46a0-8b21-7ce5084f2989', 'c236debc-2090-463f-bad3-9551e6de9357',
--   'd7e973e5-f038-4983-8016-d72ec9369617'
-- ) and country = 'Uruguay';
