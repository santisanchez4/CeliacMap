# Re-validación retroactiva — APPLY

- Fecha: 2026-09-06
- Umbral: validation_confidence < 0.7  (status='approved', NOT NULL)
- Lugares bajo el umbral: 176
- Excluidos (override manual / ya re-validados): 3
- Lugares re-evaluados: 173

## Excluidos del barrido

Filas con una decisión humana deliberada que el modelo no puede reproducir:
  - Los Leños (Montevideo) — confidence 0.5, marcador `override`
  - Dalbertt (Montevideo) — confidence 0.5, marcador `override`
  - Bienestar Gluten Free (Fray Bentos) — confidence 0.52, marcador `override`

## Distribución proyectada

| Resultado | Lugares | % |
|---|---:|---:|
| approved -> approved (se mantienen en el mapa) | 0 | 0% |
| approved -> needs_review (salen del mapa, cola humana) | 138 | 79% |
| approved -> discarded (salen del mapa) | 35 | 20% |
| errores | 0 | — |

**1 forzado(s) a needs_review** (override manual del veredicto del modelo): Enharinate Mendoza (modelo dijo approved)

## Costo real (medido)

- Llamadas a claude-sonnet-4-6: 173
- Tokens input (sin cache): 13,018
- Tokens cache-read: 178,192
- Tokens cache-write: 1,036
- Tokens output: 50,876
- **Costo total: $0.8595 USD**

## Tiempo

- Duración: 1414 s  (23.6 min)
- Promedio por lugar: 8.2 s

## Ejemplos: approved -> needs_review  (138)

  - El Faro Bistro Mendoza (Mendoza) — approved @ 0.35 -> needs_review @ 0.50 (verdict=needs_review, reseñas=0)
      No se encontró evidencia explícita de opciones sin TACC, certificación celíaca o protocolo anti-contaminación cruzada para El Faro Bistro Mendoza. La fuente es Google Places pero no se aportaron reseñas, descripción del negocio ni ningún...
      flags: Sin mención de sin TACC ni sin gluten; Sin descripción de protocolo de contaminación cruzada; Sin reseñas de celíacos disponibles; Dirección atípica para un restaurante (piso 14) — posible error o negocio no convencional
  - Rayuela - Resto kids (Gualeguaychú) — approved @ 0.35 -> needs_review @ 0.50 (verdict=needs_review, reseñas=0)
      El lugar fue descubierto vía Google Places pero no se cuenta con evidencia explícita de menciones a 'sin TACC', 'sin gluten' o protocolos anti-contaminación cruzada. El nombre 'Resto kids' sugiere orientación familiar/infantil, lo que po...
      flags: No menciona protocolo de contaminación cruzada; Sin mención explícita de sin TACC o sin gluten; Descripción ambigua - solo se conoce nombre y dirección
  - Con el Cuchillo entre los Dientes (Gualeguaychú) — approved @ 0.40 -> needs_review @ 0.50 (verdict=needs_review, reseñas=0)
      El lugar fue identificado vía Google Places pero no se dispone de evidencia explícita de opciones sin TACC, certificación celíaca ni descripción de protocolos anti-contaminación cruzada. El nombre evocador y la categoría estimada no apor...
      flags: Sin mención de sin TACC ni sin gluten; Sin información sobre protocolo de contaminación cruzada; Evidencia insuficiente para determinar seguridad celíaca
  - Charola (La Plata) — approved @ 0.40 -> needs_review @ 0.50 (verdict=needs_review, reseñas=0)
      El candidato proviene de Google Places pero no se cuenta con evidencia explícita de opciones sin TACC, certificación o protocolo anti-contaminación cruzada. El nombre 'Charola' no permite inferir especialización celíaca y no se dispone d...
      flags: Sin mención de 'sin TACC' o 'sin gluten'; Sin información sobre protocolo de contaminación cruzada; Descripción ausente o ambigua; Sin reseñas de celíacos disponibles
  - Panadería Intuitiva - Brecha. (Montevideo) — approved @ 0.45 -> needs_review @ 0.55 (verdict=needs_review, reseñas=0)
      El nombre 'Panadería Intuitiva - Brecha' sugiere un establecimiento de panadería/cafetería con enfoque en alimentación consciente o alternativa, lo que puede incluir opciones sin TACC, pero no hay evidencia explícita de certificación sin...
      flags: Sin mención explícita de 'sin TACC' o 'sin gluten'; Sin información sobre protocolo de contaminación cruzada; Descripción ambigua basada solo en nombre del local; Panadería convencional implica alto riesgo de contaminación cruzada por defecto
  - La Sin Rival (Montevideo) — approved @ 0.45 -> needs_review @ 0.52 (verdict=needs_review, reseñas=0)
      El nombre 'La Sin Rival' no proporciona indicios claros de oferta sin TACC o sin gluten, y la fuente Google Places no aporta reseñas ni descripción del menú que confirmen opciones celíacas. Sin evidencia explícita de protocolo anti-conta...
      flags: Sin mención explícita de 'sin TACC' o 'sin gluten'; Sin descripción de protocolo anti-contaminación cruzada; Sin reseñas de celíacos disponibles; Información insuficiente para determinar especialización
  - ine Boutique de cosas ricas (Montevideo) — approved @ 0.45 -> needs_review @ 0.50 (verdict=needs_review, reseñas=0)
      El nombre 'Boutique de cosas ricas' sugiere una cafetería o pastelería artesanal, pero no hay evidencia explícita de opciones sin TACC, certificación celíaca ni protocolo de contaminación cruzada disponible en los datos del candidato. La...
      flags: No menciona 'sin TACC' ni 'sin gluten'; No menciona protocolo de contaminación cruzada; Descripción ambigua o ausente; Sin reseñas de celíacos disponibles
  - Let It V (Buenos Aires) — approved @ 0.45 -> needs_review @ 0.62 (verdict=needs_review, reseñas=0)
      Let It V parece ser una tienda vegana/vegetariana ubicada en Av. Corrientes, Buenos Aires, lo cual es consistente con una dietética o local de productos naturales que podría ofrecer opciones sin TACC. Sin embargo, la orientación vegana n...
      flags: Solo menciona perfil vegano/vegetariano sin mención explícita sin TACC; Descripción ambigua - apto para dietas especiales sin especificar celíacos; Sin evidencia de protocolo de contaminación cruzada; Fuente google_places sin reseñas de celíacos confirmadas
  - Nona (Montevideo) — approved @ 0.45 -> needs_review @ 0.50 (verdict=needs_review, reseñas=0)
      El lugar fue descubierto vía redes sociales sin evidencia explícita de menciones 'sin TACC', certificación o protocolo anti-contaminación cruzada. La información disponible es insuficiente para confirmar que el establecimiento atiende de...
      flags: sin mención explícita de sin TACC; sin información sobre protocolo de contaminación cruzada; fuente solo social sin ficha verificada; información insuficiente para evaluar seguridad celíaca
  - Comer en Compañía (Buenos Aires) — approved @ 0.45 -> needs_review @ 0.52 (verdict=needs_review, reseñas=0)
      El lugar fue descubierto a través de Google Places pero no se cuenta con evidencia explícita de menciones de 'sin TACC', 'sin gluten' certificado ni descripción de protocolo anti-contaminación cruzada. El nombre no sugiere especializació...
      flags: Sin mención explícita de sin TACC; Sin información sobre protocolo de contaminación cruzada; Evidencia insuficiente para confirmar apto celíacos; Descripción ambigua o ausente

## Ejemplos: approved -> discarded  (35)

  - Sushi 2x1 (Montevideo) — approved @ 0.35 -> discarded @ 0.15 (verdict=rejected, reseñas=0)
      No se encontró ninguna evidencia explícita de opciones sin TACC, sin gluten o protocolos para celíacos en este restaurante de sushi. Los restaurantes de sushi representan un riesgo alto para celíacos por el uso habitual de salsa de soja ...
      flags: sin mención de sin TACC; sin mención de protocolo anti-contaminación cruzada; categoría de alto riesgo para celíacos (sushi/salsa de soja); fuente social sin evidencia explícita; descripción ambigua o ausente
  - Pasteles Maria (Punta del Este) — approved @ 0.35 -> discarded @ 0.35 (verdict=needs_review, reseñas=0)
      No se encontró evidencia explícita de opciones sin TACC, certificación celíaca ni mención de protocolo anti-contaminación cruzada para Pasteles Maria. La fuente es social y la dirección usa un código plus, lo que sugiere geocodificación ...
      flags: sin mención de sin TACC ni sin gluten; sin información sobre protocolo de contaminación cruzada; dirección geocodificada sin ficha verificada (ubicacion_geocode implícito); categoría café/pastelería de alto riesgo sin evidencia de adaptación celíaca; información insuficiente para evaluación
  - Prosciutto e Provolone (Buenos Aires) — approved @ 0.35 -> discarded @ 0.15 (verdict=rejected, reseñas=0)
      No se encontró evidencia alguna de opciones sin TACC, sin gluten o protocolos para celíacos en este lugar. El nombre 'Prosciutto e Provolone' sugiere un restaurante de estilo italiano con embutidos y quesos, sin indicación de especializa...
      flags: sin evidencia de opciones sin TACC o sin gluten; sin mención de protocolo anti-contaminación cruzada; inconsistencia geográfica: dirección en Argentina pero país indicado como Uruguay; fuente social sin contenido validable proporcionado; nombre del establecimiento sugiere productos con potencial alto contenido de gluten
  - Serrano Café (Colonia del Sacramento) — approved @ 0.35 -> discarded @ 0.35 (verdict=needs_review, reseñas=0)
      No se encontró evidencia explícita de opciones sin TACC, certificación celíaca ni mención de protocolos anti-contaminación cruzada para Serrano Café. La fuente es Google Places pero no se dispone de descripción del negocio, reseñas de ce...
      flags: Sin mención de 'sin TACC' ni 'sin gluten'; Sin descripción de protocolo anti-contaminación cruzada; Sin reseñas de celíacos disponibles; Evidencia insuficiente para categoría cafe (alto riesgo de contaminación cruzada por defecto)
  - Pizzería Popular (Buenos Aires) — approved @ 0.45 -> discarded @ 0.10 (verdict=rejected, reseñas=0)
      No se encontró ninguna evidencia explícita de opciones sin TACC, sin gluten o protocolos para celíacos en la información disponible sobre este establecimiento. El nombre 'Pizzería Popular' sugiere un local de pizza convencional, lo que i...
      flags: Sin mención de 'sin TACC' o 'sin gluten'; Sin mención de protocolo anti-contaminación cruzada; Categoría de alto riesgo para celíacos (pizzería convencional); Sin reseñas de la comunidad celíaca
  - Panaderia y bizcocheria PUNTO DULCE (Montevideo) — approved @ 0.45 -> discarded @ 0.10 (verdict=rejected, reseñas=0)
      No se encontró ninguna evidencia explícita de opciones sin TACC o sin gluten para este establecimiento. Las panaderías y bizchoerías tradicionales representan un alto riesgo de contaminación cruzada para celíacos por el uso intensivo de ...
      flags: Sin mención de sin TACC ni sin gluten; No menciona protocolo de contaminación cruzada; Categoría de alto riesgo para celíacos (panadería/bizcochería tradicional); Sin evidencia de opciones dedicadas para celíacos
  - Confitería La Ideal (Buenos Aires) — approved @ 0.45 -> discarded @ 0.08 (verdict=rejected, reseñas=0)
      Confitería La Ideal es una confitería tradicional porteña histórica sin ninguna evidencia encontrada de opciones sin TACC, certificación celíaca ni protocolos de contaminación cruzada. Su oferta clásica de facturas, medialunas y pasteler...
      flags: Sin mención de sin TACC ni sin gluten; Sin protocolo de contaminación cruzada documentado; Establecimiento tradicional con oferta masiva de gluten (facturas, medialunas, pastelería); Sin certificación celíaca conocida; Alto riesgo de contaminación cruzada por naturaleza del negocio
  - il Toscano (Mar del Plata) — approved @ 0.45 -> discarded @ 0.35 (verdict=needs_review, reseñas=0)
      No se encontró evidencia explícita de que Il Toscano ofrezca opciones sin TACC o sin gluten certificadas para celíacos. El nombre sugiere una cafetería o panadería de estilo italiano, categoría que típicamente maneja harinas de trigo con...
      flags: sin mención de sin TACC ni sin gluten; sin información sobre protocolo de contaminación cruzada; categoría café/panadería implica alto uso de gluten; evidencia insuficiente para validar
  - 𝙿𝙸𝚉𝚉𝙴𝚁Í𝙰 POPULAR – ʀɪɴᴄᴏ́ɴ ɴᴜᴇsᴛʀᴏ (Gualeguaychú) — approved @ 0.45 -> discarded @ 0.10 (verdict=rejected, reseñas=0)
      El lugar es una pizzería sin ninguna mención explícita de opciones sin TACC, sin gluten o protocolos para celíacos. Las pizzerías convencionales representan un alto riesgo de contaminación cruzada con gluten. No existe evidencia alguna e...
      flags: Sin mención de 'sin TACC' o 'sin gluten'; Sin mención de protocolo anti-contaminación cruzada; Categoría de alto riesgo: pizzería convencional; Sin evidencia de especialización en dietas sin gluten
  - Sapori D' Italia pizza restaurant (Artigas) — approved @ 0.45 -> discarded @ 0.10 (verdict=rejected, reseñas=0)
      No existe evidencia de que Sapori D'Italia ofrezca opciones sin TACC o sin gluten; es una pizzería convencional donde el gluten es ingrediente central de su propuesta gastronómica. Sin mención de protocolo anti-contaminación cruzada ni c...
      flags: Sin mención de 'sin TACC' o 'sin gluten'; Sin protocolo de contaminación cruzada declarado; Pizzería convencional: gluten como ingrediente principal; Sin reseñas ni evidencia de la comunidad celíaca
