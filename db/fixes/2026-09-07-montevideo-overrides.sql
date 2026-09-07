-- Manual Validator overrides — the 16 Montevideo places recovered/added on
-- 2026-09-07 (db/fixes/2026-09-07-montevideo-manual-places.sql + the Serendipia
-- changes) that a standalone `python -m agents.validator_agent` run then left in
-- needs_review, 16/16, confidence 0.50-0.72.
--
-- Why they all landed in needs_review: ValidatorAgent._build_user_prompt sends
-- the model ONLY name + address + city + country + guessed_category + source
-- (plus community review snippets, of which these have none). It does NOT include
-- places.validation_notes, so every piece of evidence gathered for these places
-- (findmeglutenfree / ACELU / viajosingluten / infonegocios / direct admin
-- confirmation) was invisible to the Validator, and update_place_validation then
-- OVERWROTE validation_notes with the model's fresh "no explicit sin-TACC signal"
-- reasoning. See CLAUDE.md "Key risks" — "validation_notes invisible para el
-- Validator". The manual evidence survives in
-- db/fixes/2026-09-07-montevideo-manual-places.sql (committed).
--
-- This is the documented manual-override path (CLAUDE.md "Manual Validator
-- overrides — allowed, but never silent"): a real evidence limitation of the
-- pipeline, not a real safety signal. Every row:
--   * validation_notes: OVERRIDE MANUAL header PREPENDED; the Validator's own
--     reasoning kept verbatim below it (|| validation_notes).
--   * validation_confidence: UNCHANGED (never inflated to match the decision).
--   * verified: UNCHANGED (stays false).
--
-- Groups:
--   A (6) + B (1)  -> approved @ gluten_free_100  (dedicated 100% GF businesses;
--                     Serendipia is address_only + admin-confirmed, Bienestar
--                     precedent)
--   C (La Molienda x9) -> approved @ options_available (general market with a
--                     curated ACELU-verified sin-TACC section, NOT a dedicated
--                     GF establishment)
--
-- Run: node_modules/.bin/supabase db query --linked --file <this file>
-- Idempotent: every statement guards on `and status = 'needs_review'`.

-- =====================================================================
-- GRUPO A — negocios 100% sin gluten / dedicados -> approved @ gluten_free_100
-- =====================================================================

-- La Panadería de Ramona (0c8ed54c) — conf 0.52
update public.places set
  status = 'approved',
  safety_level = 'gluten_free_100',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente. La Panadería de Ramona (San José 894) es la primera panadería del Uruguay con productos 100% para celíacos, HABILITADA POR ACELU (Asociación Celíaca del Uruguay); todo el local es sin gluten, sin riesgo de contaminación cruzada (infonegocios.biz, findmeglutenfree, viajosingluten). El Validator solo recibe nombre + dirección + categoría (sin reseñas, sin búsqueda web, sin acceso a validation_notes), por eso lo dejó en needs_review — es una limitación de evidencia del pipeline, no una señal de riesgo real. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.52): '
    || validation_notes
where id = '0c8ed54c-b0ef-430d-aa99-1a05da52be19' and status = 'needs_review';

-- La Commedia (7363c257) — conf 0.50
update public.places set
  status = 'approved',
  safety_level = 'gluten_free_100',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente. La Commedia (El Viejo Pancho 2414) es un restaurante italiano 100% sin gluten desde 1995: cocina totalmente dedicada, dueño celíaco, sin contaminación cruzada; reconocido como uno de los más celíaco-friendly de Montevideo (findmeglutenfree, wanderlog, viajosingluten). El Validator solo recibe nombre + dirección + categoría (sin reseñas, sin búsqueda web, sin acceso a validation_notes), por eso lo dejó en needs_review — es una limitación de evidencia del pipeline, no una señal de riesgo real. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.50): '
    || validation_notes
where id = '7363c257-9596-4aa1-a329-29d994d2eb65' and status = 'needs_review';

-- Casa & Dispensa (1e21c93a) — conf 0.50
update public.places set
  status = 'approved',
  safety_level = 'gluten_free_100',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente. Casa & Dispensa (Solano García 2496, Punta Carretas) es una pastelería boutique + café + mini-market 100% sin gluten: todo el local es sin gluten, sin riesgo de contaminación cruzada (findmeglutenfree; antes operaba como Goût Gluten Free). El Validator solo recibe nombre + dirección + categoría (sin reseñas, sin búsqueda web, sin acceso a validation_notes), por eso lo dejó en needs_review — es una limitación de evidencia del pipeline, no una señal de riesgo real. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.50): '
    || validation_notes
where id = '1e21c93a-0030-4c99-8ef1-eab8d487130f' and status = 'needs_review';

-- CROC Galletas Artesanales (8ffbc4ee) — conf 0.52
update public.places set
  status = 'approved',
  safety_level = 'gluten_free_100',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente. CROC (Andes 1206 = tramo renombrado José Germán Araujo 1206) es la panadería/rotisería de cocina inclusiva 100% sin gluten conocida como @crocpanaderiasingluten, operando dedicada desde 2016 (FB: Croc Productos Artesanales sin Gluten). El Validator solo recibe nombre + dirección + categoría (sin reseñas, sin búsqueda web, sin acceso a validation_notes), por eso lo dejó en needs_review — es una limitación de evidencia del pipeline, no una señal de riesgo real. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.52): '
    || validation_notes
where id = '8ffbc4ee-69f6-41e0-af31-2dc46be9ec79' and status = 'needs_review';

-- Café Ramona - Centro (03ea2fae) — conf 0.50
update public.places set
  status = 'approved',
  safety_level = 'gluten_free_100',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente. Café Ramona - Centro (San José 900) es un café/panadería de comida natural 100% sin gluten: panes, galletas, medialunas, pizzas y pastas 100% caseros sin gluten (viajosingluten, findmeglutenfree, sitiopatas.com.uy). El Validator solo recibe nombre + dirección + categoría (sin reseñas, sin búsqueda web, sin acceso a validation_notes), por eso lo dejó en needs_review — es una limitación de evidencia del pipeline, no una señal de riesgo real. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.50): '
    || validation_notes
where id = '03ea2fae-834c-48c0-9f7e-b43b089dc4b4' and status = 'needs_review';

-- Café Ramona - WTC (896d2aa6) — conf 0.52
update public.places set
  status = 'approved',
  safety_level = 'gluten_free_100',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente. Café Ramona - WTC (Av. Luis Alberto de Herrera 1196) es la sucursal WTC de Café Ramona, 100% sin gluten; findmeglutenfree la lista como Dedicated Gluten-Free Restaurant. El Validator solo recibe nombre + dirección + categoría (sin reseñas, sin búsqueda web, sin acceso a validation_notes), por eso lo dejó en needs_review — es una limitación de evidencia del pipeline, no una señal de riesgo real. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.52): '
    || validation_notes
where id = '896d2aa6-50b3-4398-8399-6ed933344c94' and status = 'needs_review';

-- =====================================================================
-- GRUPO B — address_only + dirección confirmada por el admin (patrón Bienestar)
-- =====================================================================

-- Serendipia Gluten Free (82fd31e9) — conf 0.72, geocode_method=address_only
update public.places set
  status = 'approved',
  safety_level = 'gluten_free_100',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente. Serendipia Gluten Free (@serendipia.glutenfree, Capitán Videla 3059) es un emprendimiento de alimentos artesanales 100% sin gluten con retiro por agenda (hasta 48 h) en Parque Batlle, verificado en Instagram. La dirección fue confirmada directamente por el administrador después de que el geocode automático fallara 4 veces con negocios equivocados (mismo criterio que Bienestar Gluten Free: address_only + conocimiento directo del admin). geocode_method=address_only y verified=false se mantienen: no hay ficha de Google que confirme la operación en el lugar. El Validator lo dejó en needs_review exactamente por esa limitación (address_only), no por una señal de riesgo. validation_confidence se mantiene sin cambios.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.72): '
    || validation_notes
where id = '82fd31e9-6a50-456d-aa74-8ba66a7508c5' and status = 'needs_review';

-- =====================================================================
-- GRUPO C — La Molienda x9 -> approved @ options_available
-- Mercado general con góndola curada sin-TACC (lamolienda.uy/celiaco, 422
-- productos, logo ACELU). NO es un local dedicado -> options_available, no
-- gluten_free_100. Nota idéntica en las 9 (texto provisto por el admin).
-- =====================================================================

-- La Molienda - 18 de Julio (16305a09) — conf 0.52
update public.places set
  status = 'approved',
  safety_level = 'options_available',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten_free_100). La Molienda es un supermercado/mercado general (huevos, salsa de soja, proteína, cosmética, etc.), no un local 100% dedicado a productos sin gluten. Tiene una categoría curada dedicada (lamolienda.uy/celiaco, 422 productos verificados) con el logo institucional de ACELU, en góndola separada del resto del local. Es exactamente el caso para el que existe options_available: fuente confiable con opciones reales verificadas, pero no todo el establecimiento es apto — el resto del local vende productos con gluten normalmente. El Validator solo recibe nombre+dirección+categoría, sin acceso a la web ni a esta evidencia, por eso lo dejó en needs_review. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.52): '
    || validation_notes
where id = '16305a09-8773-42ad-ae82-f849bdd44582' and status = 'needs_review';

-- La Molienda - Ejido (a2135458) — conf 0.50
update public.places set
  status = 'approved',
  safety_level = 'options_available',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten_free_100). La Molienda es un supermercado/mercado general (huevos, salsa de soja, proteína, cosmética, etc.), no un local 100% dedicado a productos sin gluten. Tiene una categoría curada dedicada (lamolienda.uy/celiaco, 422 productos verificados) con el logo institucional de ACELU, en góndola separada del resto del local. Es exactamente el caso para el que existe options_available: fuente confiable con opciones reales verificadas, pero no todo el establecimiento es apto — el resto del local vende productos con gluten normalmente. El Validator solo recibe nombre+dirección+categoría, sin acceso a la web ni a esta evidencia, por eso lo dejó en needs_review. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.50): '
    || validation_notes
where id = 'a2135458-3092-4398-9dae-8c79ab432e04' and status = 'needs_review';

-- La Molienda - Sarandí (c1199194) — conf 0.50
update public.places set
  status = 'approved',
  safety_level = 'options_available',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten_free_100). La Molienda es un supermercado/mercado general (huevos, salsa de soja, proteína, cosmética, etc.), no un local 100% dedicado a productos sin gluten. Tiene una categoría curada dedicada (lamolienda.uy/celiaco, 422 productos verificados) con el logo institucional de ACELU, en góndola separada del resto del local. Es exactamente el caso para el que existe options_available: fuente confiable con opciones reales verificadas, pero no todo el establecimiento es apto — el resto del local vende productos con gluten normalmente. El Validator solo recibe nombre+dirección+categoría, sin acceso a la web ni a esta evidencia, por eso lo dejó en needs_review. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.50): '
    || validation_notes
where id = 'c1199194-a936-4a31-95cc-2a430b226601' and status = 'needs_review';

-- La Molienda - Costa Urbana (59df8880) — conf 0.50
update public.places set
  status = 'approved',
  safety_level = 'options_available',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten_free_100). La Molienda es un supermercado/mercado general (huevos, salsa de soja, proteína, cosmética, etc.), no un local 100% dedicado a productos sin gluten. Tiene una categoría curada dedicada (lamolienda.uy/celiaco, 422 productos verificados) con el logo institucional de ACELU, en góndola separada del resto del local. Es exactamente el caso para el que existe options_available: fuente confiable con opciones reales verificadas, pero no todo el establecimiento es apto — el resto del local vende productos con gluten normalmente. El Validator solo recibe nombre+dirección+categoría, sin acceso a la web ni a esta evidencia, por eso lo dejó en needs_review. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.50): '
    || validation_notes
where id = '59df8880-41b2-4354-b183-ab7bc577178d' and status = 'needs_review';

-- La Molienda - Punta Carretas (3892f08f) — conf 0.52
update public.places set
  status = 'approved',
  safety_level = 'options_available',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten_free_100). La Molienda es un supermercado/mercado general (huevos, salsa de soja, proteína, cosmética, etc.), no un local 100% dedicado a productos sin gluten. Tiene una categoría curada dedicada (lamolienda.uy/celiaco, 422 productos verificados) con el logo institucional de ACELU, en góndola separada del resto del local. Es exactamente el caso para el que existe options_available: fuente confiable con opciones reales verificadas, pero no todo el establecimiento es apto — el resto del local vende productos con gluten normalmente. El Validator solo recibe nombre+dirección+categoría, sin acceso a la web ni a esta evidencia, por eso lo dejó en needs_review. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.52): '
    || validation_notes
where id = '3892f08f-eccf-499f-bd93-e0c199d7c92c' and status = 'needs_review';

-- La Molienda - ACJ (Colonia) (ab09d6d4) — conf 0.50
update public.places set
  status = 'approved',
  safety_level = 'options_available',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten_free_100). La Molienda es un supermercado/mercado general (huevos, salsa de soja, proteína, cosmética, etc.), no un local 100% dedicado a productos sin gluten. Tiene una categoría curada dedicada (lamolienda.uy/celiaco, 422 productos verificados) con el logo institucional de ACELU, en góndola separada del resto del local. Es exactamente el caso para el que existe options_available: fuente confiable con opciones reales verificadas, pero no todo el establecimiento es apto — el resto del local vende productos con gluten normalmente. El Validator solo recibe nombre+dirección+categoría, sin acceso a la web ni a esta evidencia, por eso lo dejó en needs_review. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.50): '
    || validation_notes
where id = 'ab09d6d4-e88a-40c0-9fb9-6f8550aff383' and status = 'needs_review';

-- La Molienda - Carrasco (9dd64b4e) — conf 0.55
update public.places set
  status = 'approved',
  safety_level = 'options_available',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten_free_100). La Molienda es un supermercado/mercado general (huevos, salsa de soja, proteína, cosmética, etc.), no un local 100% dedicado a productos sin gluten. Tiene una categoría curada dedicada (lamolienda.uy/celiaco, 422 productos verificados) con el logo institucional de ACELU, en góndola separada del resto del local. Es exactamente el caso para el que existe options_available: fuente confiable con opciones reales verificadas, pero no todo el establecimiento es apto — el resto del local vende productos con gluten normalmente. El Validator solo recibe nombre+dirección+categoría, sin acceso a la web ni a esta evidencia, por eso lo dejó en needs_review. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.55): '
    || validation_notes
where id = '9dd64b4e-3e13-4d2d-88ea-931219dc5c2b' and status = 'needs_review';

-- La Molienda - Parque Rodó (b41cc805) — conf 0.52
update public.places set
  status = 'approved',
  safety_level = 'options_available',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten_free_100). La Molienda es un supermercado/mercado general (huevos, salsa de soja, proteína, cosmética, etc.), no un local 100% dedicado a productos sin gluten. Tiene una categoría curada dedicada (lamolienda.uy/celiaco, 422 productos verificados) con el logo institucional de ACELU, en góndola separada del resto del local. Es exactamente el caso para el que existe options_available: fuente confiable con opciones reales verificadas, pero no todo el establecimiento es apto — el resto del local vende productos con gluten normalmente. El Validator solo recibe nombre+dirección+categoría, sin acceso a la web ni a esta evidencia, por eso lo dejó en needs_review. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.52): '
    || validation_notes
where id = 'b41cc805-f877-4b37-8a1e-5df0f27174df' and status = 'needs_review';

-- La Molienda - Tres Cruces (32dc14f4) — conf 0.52
update public.places set
  status = 'approved',
  safety_level = 'options_available',
  validation_notes =
    'OVERRIDE MANUAL (2026-09-07, Santiago Sánchez): aprobado manualmente como options_available (NO gluten_free_100). La Molienda es un supermercado/mercado general (huevos, salsa de soja, proteína, cosmética, etc.), no un local 100% dedicado a productos sin gluten. Tiene una categoría curada dedicada (lamolienda.uy/celiaco, 422 productos verificados) con el logo institucional de ACELU, en góndola separada del resto del local. Es exactamente el caso para el que existe options_available: fuente confiable con opciones reales verificadas, pero no todo el establecimiento es apto — el resto del local vende productos con gluten normalmente. El Validator solo recibe nombre+dirección+categoría, sin acceso a la web ni a esta evidencia, por eso lo dejó en needs_review. validation_confidence se mantiene sin cambios; verified sigue en false.'
    || E'\n\n--- Nota del Validator (needs_review, confidence 0.52): '
    || validation_notes
where id = '32dc14f4-ced7-4c36-8d6a-2942c64e0367' and status = 'needs_review';
