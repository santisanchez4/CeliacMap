# Auditoría de datos Google — CeliacMap

**Corte de datos:** 02-10-2026, 04:16:39 UTC (01:16:39 Uruguay). **Código inspeccionado:** base `1ce6658`.
**Alcance:** lectura de Supabase, código/SQL/historial documental y políticas oficiales. Sin escrituras a la base, llamadas pagas a Google, cambios de etiquetas ni ocultamiento de campos. Decisión de producto pendiente del responsable.

La auditoría **no bloquea el piloto PWA/APK**, por decisión de alcance del responsable; sí debe resolverse antes de publicación en tiendas. Esa prioridad no constituye una excepción contractual ni una confirmación de cumplimiento para demos. Play interno también requiere revisar las condiciones de su canal, aunque no sea un lanzamiento público.

## 1. Resultado ejecutivo

Hay **417 filas aprobadas**. De ellas, 374 tienen `source=google_places`, 25 `social`, 16 `manual` y 2 `user`. Todos los lugares tienen coordenadas; 226 tienen rating/cantidad de reseñas; 222 horarios; 223 teléfono; 73 sitio web.

El frontend muestra estos campos en la ficha asociada a Leaflet/CARTO. **`source` describe la entrada del lugar, no la procedencia de cada campo.** Hay coordenadas Google en filas sociales, comunitarias y manuales; hay correcciones humanas en filas `google_places`. Cambiar `source`, copiar un dato a mano o aprobar un negocio no cambia la licencia de origen.

No existe trazabilidad completa por columna ni timestamp de adquisición/expiración de cada dato Google. Por eso los conteos siguientes prueban **presencia y exposición**, no certifican que cada valor tenga origen/licencia independiente. Se identifican las cargas manuales conocidas y sus límites.

Hay tres caminos razonables para decidir después: datos propios con Leaflet, Google Maps con estrategia de datos autorizada, o investigar **Places UI Kit**, cuya excepción específica permite componentes Google junto a mapas no Google. Ninguno se aplica automáticamente en este PR.

## 2. Método y reproducibilidad

Se realizó una lectura REST `GET /rest/v1/places`, filtro `status=eq.approved`, orden estable por `id`, paginación de 500 y columnas explícitas. La credencial de servidor se usó solo para leer metadatos de procedencia; no se imprimieron claves ni el contenido de `validation_notes`. El único almacenamiento temporal auxiliar contiene campos de negocios y banderas de inspección, no las notas. No se incorporó un dump al repo.

Las cuentas se hicieron sobre valores no nulos y no vacíos (`''`, `[]`, `{}` excluidos). En las columnas relevadas, ambos conteos coinciden. Los 226 ratings son positivos y pueden renderizarse según la condición actual. Los conteos son una fotografía, no una consulta continua.

Consulta SQL equivalente para repetir el conteo con acceso autorizado, **solo SELECT**:

```sql
select source, count(*) as approved,
       count(rating) as rating,
       count(user_ratings_total) as user_ratings_total,
       count(*) filter (where opening_hours is not null
                          and opening_hours not in ('[]'::jsonb, '{}'::jsonb, 'null'::jsonb)) as opening_hours,
       count(nullif(btrim(phone), '')) as phone,
       count(nullif(btrim(website), '')) as website,
       count(lat) as lat, count(lng) as lng,
       count(nullif(btrim(social_url), '')) as social_url
from public.places
where status = 'approved'
group by source
order by source;
```

También se contrastaron las filas identificadas en los scripts `db/fixes/` con el corte leído y con las entradas de aplicación en [Decisions Log](../DECISIONS.md). Un script preparado no demuestra por sí solo que fue aplicado. Coincidencia del valor actual con un literal histórico tampoco prueba que no hubo una actualización posterior al mismo valor.

## 3. Presencia de campos y exposición

| Campo | Aprobados con dato / 417 | En `google_places` / 374 | En `manual` / 16 | En `social` / 25 | En `user` / 2 | Uso público actual |
|---|---:|---:|---:|---:|---:|---|
| `rating` | 226 | 224 | 2 | 0 | 0 | Estrellas/número de ficha; desempate del ranking y consulta del chat |
| `user_ratings_total` | 226 | 224 | 2 | 0 | 0 | Cantidad de reseñas junto al rating; contexto del chat |
| `opening_hours` | 222 | 221 | 1 | 0 | 0 | Horarios en ficha y contexto del chat |
| `phone` | 223 | 216 | 6 | 0 | 1 | Teléfono/enlace `tel:` y contexto del chat |
| `website` | 73 | 71 | 2 | 0 | 0 | Enlace de sitio en ficha y contexto del chat |
| `lat` | 417 | 374 | 16 | 25 | 2 | Posición de marcador y destino de «Cómo llegar»; datos del chat |
| `lng` | 417 | 374 | 16 | 25 | 2 | Igual que `lat`; no son coordenadas del usuario |
| `social_url` | 117 | 87 | 15 | 13 | 2 | Perfil/link de ficha; puede provenir del antiguo `website` Google |

`external_id` está presente en 414 aprobados; los tres sin ID son Ta Bacana, Caneladesayunos y Pastas Lo de Flor. No inferir «sin Google» de un ID nulo: Pastas Lo de Flor fue geocodificado mediante Google. `geocode_method` es nulo en 409, `address_only` en 5 y `find_place` en 3; nulo tampoco significa geocodificación independiente.

Evidencia de exposición: [`js/map.js`](../../js/map.js), `panelHtml` y selección de columnas; [`js/ranking.js`](../../js/ranking.js), query ordenada por voto/rating; [`supabase/functions/chat/index.ts`](../../supabase/functions/chat/index.ts), campos del catálogo. Que el chat reciba un campo no garantiza que lo verbalice en todos los turnos.

La ficha añade «Datos de Google» cuando `source=google_places`; para otros orígenes usa otra etiqueta. No encontré un componente oficial de atribución Google asociado a los ratings de todas las procedencias. La atribución CARTO/OSM de tiles no cubre la de Places; «Google data» condicionado a `source` no resuelve la mezcla por columna. El enlace «Cómo llegar» tampoco cambia quién renderiza el mapa de CeliacMap.

## 4. De dónde salen los campos

| Campo en `places` | Ruta de origen posible en el código | Matiz |
|---|---|---|
| `name`, `address`, `lat/lng`, `external_id` | Google Text Search / Find Place / Geocoding; también ingreso/corrección humana | `to_candidate()` copia geometría/identidad; `resolve_location()` se usa fuera de Search |
| `rating`, `user_ratings_total` | Google Search/Place Details y cargas SQL históricas | Copiarlos manualmente no los convierte en votos CeliacMap |
| `opening_hours` | `opening_hours.weekday_text` de Place Details; correcciones manuales | Se guarda la lista, no `open_now`; no hay expiración individual |
| `phone` | `formatted_phone_number`; teléfono aportado/corregido | Necesita procedencia de campo, no solo del lugar |
| `website` | `website` Google o enlace independiente | El extractor ahora separa perfiles sociales |
| `social_url` | Leads sociales, comunidad/admin o perfil que Google entrega como `website` | El campo tampoco prueba una fuente ajena a Google |
| `city`, `country`, `region` | Dirección/componentes Google, normalización y backfills | Transformar la dirección no elimina su procedencia |
| `category` | Tipos Google, reglas/LLM y correcciones manuales | Campo derivado, requiere análisis aparte del nombre de la columna |
| `safety_level`, `status`, avisos y votos | Evaluación CeliacMap, comunidad y decisiones del responsable | No son una certificación emitida por Google; evidencia externa puede intervenir en evaluación |

Rutas verificadas: [`GooglePlacesClient`](../../agents/clients/google_places.py), [`Search`](../../agents/search_agent.py), [`Updater`](../../agents/updater_agent.py), [`Social`](../../agents/social_agent.py), [`Suggestion`](../../agents/suggestion_agent.py). Se usa `googlemaps` con métodos Legacy: la política aplicable debe incluir Legacy, no solo la documentación de Places New.

El Updater procesa filas `source=google_places` con `external_id`. Actualiza datos enriquecidos cuando Google aporta un valor distinto; deja valores previos si Google no entrega un reemplazo. No implementa una purga por antigüedad de estos campos y `_build_patch` no renueva coordenadas. El cron mensual con cupo tampoco garantiza refrescar cada lugar antes de 30 días.

Los 16 manuales **no son refrescados por ese loop**, aunque tengan ID Google. El comentario de Dispensario que sugiere actualización solo por tener `external_id` es más amplio que el código real. `updated_at` es de la fila completa, no evidencia de cuándo se obtuvo o refrescó cada campo Google.

## 5. Qué se cargó a mano

### 5.1 Las 16 filas aprobadas con `source=manual`

| Lugares (lista completa de este origen) | Cantidad | Procedencia documentada de coordenadas / datos |
|---|---:|---|
| La Molienda: 18 de Julio, Ejido, Sarandí, Costa Urbana, Punta Carretas, ACJ (Colonia), Carrasco, Parque Rodó, Tres Cruces | 9 | Direcciones contrastadas con la cadena; coordenadas/place IDs vía Google Find Place, según SQL del 07-09 |
| Café Ramona - WTC | 1 | Insert manual; ficha Google revalidada, coordenadas y rating 4,0 / 2.356 reseñas |
| Serendipia Gluten Free (Montevideo) | 1 | Dirección confirmada por administrador; punto obtenido por Google Geocoding, según Decisions Log |
| Ta Bacana Resto Bar | 1 | Coordenadas por interpolación AGESIC/OSM; teléfono/perfil aportados por administrador; sin Place ID |
| Caneladesayunos | 1 | Coordenadas del catastro AGESIC/OSM; teléfono/perfil aportados por administrador; sin Place ID |
| Dispensario | 1 | Coordenadas Google; rating 4,8 / 47, horarios y otros datos copiados/contrastados con Google e Instagram |
| Rikuras Sin Gluten El Pinar | 1 | Google Find Place para ubicación; tarjeta del negocio como fuente de contactos |
| Piu Helados Prado | 1 | Google Find Place para ubicación; teléfono/perfil contrastados con información del negocio |

Fuentes: [manual Montevideo 07-09](../../db/fixes/2026-09-07-montevideo-manual-places.sql), [Ta Bacana/Canela](../../db/fixes/2026-09-22-fray-bentos-ta-bacana-canela.sql), [Dispensario](../../db/fixes/2026-09-24-fray-bentos-dispensario.sql), [nuevas sucursales](../../db/fixes/2026-09-27-new-branches.sql), [Decisions Log](../DECISIONS.md). La fuente catastral también tiene su licencia/atribución; «no Google» no equivale a libre de obligaciones.

### 5.2 Cargas/correcciones de campos fuera de `source=manual`

| Lugar | Campo(s) de los auditados escritos a mano | Evidencia y situación observada |
|---|---|---|
| Café Ramona - Centro | `phone` | SQL 07-09 fija teléfono; fila actual `google_places` |
| Casa & Dispensa | `phone`, `website`, `rating`, `user_ratings_total` | SQL 07-09; los valores actuales coinciden. Rating externo no se vuelve propio |
| La Commedia | `phone`, `rating`, `user_ratings_total` | SQL 07-09; los valores actuales coinciden |
| CROC Galletas Artesanales | `user_ratings_total` | SQL 07-09 fija 168; coincide. El rating no se escribe en ese UPDATE |
| Piu Helados Cordón | `phone` | SQL 27-09 fija contacto; origen de fila sigue `google_places` |
| Rikuras Sin Gluten (Malvín) | `website` | Corrección por tarjeta a `pidedirecto.uy` documentada; lectura actual volvió a `ambit.la`. No asumir que la corrección persiste |
| ChocAra MVD | `opening_hours` | Corrección 01-10 de horario dominical; además `social_url`. Coordenadas no cambiaron |
| Alimentos NutriCiencia SRL | `website`, `opening_hours` | Corrección 01-10 a HTTPS y horario continuo; coordenadas no cambiaron |
| Pastas Lo de Flor (`source=user`) | `lat/lng` y datos de negocio en insert asistido | Resolución manual de sugerencia, pero coordenadas de Google Geocoding; `external_id` nulo |

Fuentes: [SQL Montevideo](../../db/fixes/2026-09-07-montevideo-manual-places.sql), [Piu/sucursales](../../db/fixes/2026-09-27-new-branches.sql), [Rikuras Malvín](../../db/fixes/2026-09-27-rikuras-malvin-website.sql), [ChocAra/NutriCiencia](../../db/fixes/2026-10-01-chocara-nutriciencia-data.sql), [Lo de Flor](../../db/fixes/2026-09-24-fray-bentos-pastas-lo-de-flor.sql).

Esto identifica intervenciones verificables, **no un historial exhaustivo de cada edición remota**. Al menos cuatro ratings actuales aparecen escritos en scripts manuales (WTC, Dispensario, Casa & Dispensa y La Commedia), y cinco conteos al sumar CROC. No se puede restar esas filas del conjunto Google para obtener una cifra de datos propios. El origen independiente de otros teléfonos/webs requiere confirmación por campo; no se lo asigna por descarte.

### 5.3 Redes y aprobación de seguridad

El arreglo de perfiles aplicado el 01-10 movió/vació `website` en 190 filas de todos los estados: 188 trasladaron perfil a `social_url`, dos ya tenían un perfil. El corte histórico incluía 79 aprobados afectados; hoy se conservan 117 perfiles y 73 sitios entre aprobados. Esa corrección mejora la semántica, pero no cambia la procedencia de la URL. [Fix de perfiles](../../db/fixes/2026-10-01-social-profile-out-of-website.sql).

La confirmación manual de MOOY corrigió una nota y ratificó la decisión del responsable. No cambió rating, horarios, coordenadas o licencia. Tampoco `APROBACIÓN MANUAL` en cualquier otra fila acredita propiedad de todos los campos. No se publican aquí notas privadas ni detalles de salud de terceros.

## 6. Políticas oficiales consultadas el 02-10-2026

### 6.1 Contrato general y API específica

Los [términos generales de Google Maps Platform](https://cloud.google.com/maps-platform/terms), §§3.2.2 y 3.2.3, exigen atribución y limitan extracción, almacenamiento, caché y uso con mapas ajenos. Las excepciones se buscan en las condiciones específicas del servicio; no se presume autorización por usar una API paga o por ser persona física.

Las [condiciones específicas](https://cloud.google.com/maps-platform/terms/maps-service-terms), §14, nombran **Places API Legacy y New**: permiten uso sin mapa, prohíben usar ese contenido junto con un mapa no Google y permiten caché temporal de latitud/longitud hasta 30 días. No extienden ese permiso a todos los campos. §6 regula Geocoding; su excepción de almacenamiento más amplio exige aislamiento por usuario/finalidad y no habilita un catálogo compartido arbitrario. §15 permite **Places UI Kit con cualquier mapa**, con sus propias condiciones.

El [documento de políticas de Places New](https://developers.google.com/maps/documentation/places/web-service/policies) explica la excepción de caché para `place_id`, la atribución Google Maps y las atribuciones de terceros/fotos/reseñas. La conservación de IDs no autoriza conservar indefinidamente el resto del contenido. Se cita como guía de presentación; para el cliente Legacy del repo la referencia contractual principal es §14, que lo incluye expresamente.

La dirección de facturación define si aplican condiciones EEA diferentes; el responsable está en Uruguay, pero no se verificó su contrato/cuenta Google. Confirmarlo antes de elegir la solución. La lectura técnica no sustituye la revisión contractual del responsable.

### 6.2 Implicación concreta para CeliacMap

- El panel del lugar y sus marcadores se usan junto a Leaflet/CARTO. **Ocultar solo el rating, poner «Datos de Google» o enlazar a Google Maps no resuelve por sí solo el uso de coordenadas/datos Google en ese mapa.** Inferencia técnica sobre la implementación y las reglas anteriores.
- Migrar el fondo a Google Maps aborda la combinación de mapas; no autoriza automáticamente la base persistente, la redistribución REST, el caché PWA ni el uso en prompts.
- El catálogo aprobado es compartido por usuarios: no tratarlo como una caché individual de la excepción Geocoding. No hay evidencia de expiración por campo. `updated_at`, aprobación manual y un cron mensual no la demuestran.
- La purga interna de reviews a 30 días es una medida de retención, **no una autorización general para guardar reseñas Google durante 30 días**. Mantenerlas fuera del frontend reduce exposición, pero la licencia de su almacenamiento y uso como evidencia requiere revisión propia.
- Agregar o preservar atribución sigue siendo necesario, pero no reemplaza permisos de uso. Una etiqueta por `source` es insuficiente para reflejar mezclas de origen; no decidir ahora un cambio de etiquetas o datos.
- Los permisos para APIs no se extrapolan al sitio web de Google Maps. Copiar datos de la web o de un agregador a mano requiere analizar también sus condiciones; no elimina la procedencia.

### 6.3 Places UI Kit: alternativa que merece un prototipo

Google ofrece componentes de detalle/búsqueda que pueden usarse junto a mapas ajenos bajo la excepción específica. La [documentación de UI Kit](https://developers.google.com/maps/documentation/javascript/places-ui-kit/overview) distingue componentes Essentials y Pro, personalización, facturación por instanciación y elementos preview. [Guía de integración en cualquier mapa](https://developers.google.com/maps/architecture/places-ui-kit-getting-started).

Posible diseño futuro: catálogo propio y etiquetas CeliacMap separados de un componente oficial que obtiene el detalle Google al abrirlo. **No basta con añadir el widget para legitimar las coordenadas y el contenido Legacy ya guardados**; revisar también cómo se obtienen/mantienen los puntos. No extraer la respuesta del componente para volver a almacenarla o enviarla al modelo como si fuera un dato propio.

Antes de elegirlo: validar compatibilidad WebView, clave/restricciones, español/inglés, accesibilidad, privacidad del tercero, disponibilidad de los campos, estado GA/preview y costo de instanciaciones. El componente no debe sugerir que Google emite la etiqueta de seguridad alimentaria.

## 7. Opciones, costo y esfuerzo

USD sin impuestos. Esfuerzo estimado propio, jornadas de 6 horas; no es cotización ni incluye tiempos de respuesta de negocios/asesoría. Ninguna opción se implementa en esta auditoría.

| Opción | Qué cambiaría | Costo externo orientativo | Esfuerzo y límites |
|---|---|---|---|
| A. Mantener piloto actual, documentar y decidir después | Ninguna columna/UI cambia ahora | Consumo actual; no nuevo servicio por esta auditoría | Decisión ya tomada para piloto; no equivale a subsanar contrato ni habilita tiendas |
| B. Catálogo propio verificable + Leaflet/CARTO | Registrar procedencia por campo; reemplazar contenido Google con aportes independientes/licenciados; dejar IDs/referencias donde se permita | CARTO comercial gratis hasta 1M requests/mes; luego USD 500/mes o 5.000/año hasta 10M; geocoding alternativo y curación aparte | 4–8 días de mecanismo/prototipo + revisión individual del catálogo; no estimar 417 verificaciones como una tarea de código |
| C. Google Maps + estrategia de contenido autorizada | Adaptador de mapa; datos frescos, almacenamiento permitido y atribución; conservar etiquetas propias | Dynamic Maps JS: 10k eventos gratis/mes, luego USD 7/1.000 primer tramo; Places aparte. Maps SDK nativo base sin cargo, pero no sustituye la PWA | 5–10 días de mapa/UX más 3–6 de estrategia de datos; publicar en Google Maps no corrige todo lo persistido |
| D. Leaflet + Places UI Kit | Componente oficial para detalle externo; resolver aparte procedencia de pines/catálogo | Query: 10k gratis/mes y luego USD 1/1.000; Pro: 5k gratis y luego USD 5/1.000, primer tramo; tiles aparte | Spike 2–3 días; integración 3–6 y revisión de almacenamiento/puntos; revisar preview y clave móvil |
| E. Datos propios + enlaces externos, sin enriquecimiento Google embebido | Retirar campos externos solo por decisión posterior; abrir ficha Google afuera | Enlaces Maps URLs sin API key; datos/tiles propios siguen teniendo costo | 2–4 días UI/API más curación de coordenadas; ocultar campos sin sustituir puntos no alcanza |

Fuentes de tarifas: [CARTO Basemaps](https://carto.com/basemaps/), [Google SKU y cuotas mensuales](https://developers.google.com/maps/billing-and-pricing/pricing), [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started). Se agregan consumos de web y app por cuenta/SKU; no hay un nuevo cupo gratuito por cada frontend.

El cliente actual usa Legacy: Text Search tiene 5k gratis y luego USD 32/1.000; Details y Find Place, 5k y USD 17/1.000; Contact/Atmosphere pueden sumar cargos. No presupuestar una migración aplicando esas tarifas a Places New indiscriminadamente. [Precios oficiales](https://developers.google.com/maps/billing-and-pricing/pricing).

Ejemplos de cálculo, no pronóstico: 20k cargas mensuales de Dynamic Maps JS darían USD 70 de ese SKU; 12k consultas UI Kit Query darían USD 2 de ese SKU, sin contar tiles/otros componentes. Cambiar SDK para ahorrar en el mapa puede aumentar horas de implementación y dejar sin solución la PWA.

Cambiar CARTO por MapTiler u OSM conserva el problema del contenido Google sobre un mapa ajeno. Tampoco corresponde bajar masivamente tiles OSM para «evitar costos». La alternativa de datos propios exige geocodificación con derechos compatibles, atribución y presupuesto; no elegir proveedor ni vaciar campos en esta tarea.

## 8. Recomendación y decisión pendiente

Para el piloto, mantener lo acordado en [ADR-010](../architecture/ADR-010-mobile-strategy.md): paridad, sin cambios de datos a partir de esta auditoría. Antes de una publicación en tiendas, el responsable elige entre datos propios, Google Maps o una integración autorizada como UI Kit, y valida contrato/atribución/retención.

Preparación futura sugerida: distinguir dato de negocio propio, contenido Google y resultado editorial CeliacMap; guardar origen/URL/fecha/licencia a nivel de campo o grupo coherente; separar valores de terceros de overrides explícitos para que el Updater no los pise sin política. Eso es una propuesta, **no una migración autorizada ahora**.

Preguntas concretas para decidir: ¿conservar rating/horarios externos en la ficha?, ¿priorizar datos propios sobre cobertura inmediata?, ¿aceptar UI Kit o un cambio de mapa?, ¿qué presupuesto y tiempo de curación hay? El permiso de ubicación del piloto es independiente: coordenadas del dispositivo bajo demanda, nunca adjuntadas a backend/modelo.

**Resultado de la auditoría:** conteos reales y limitaciones de procedencia documentados; políticas/alternativas enlazadas; cero cambios en producción. La decisión queda con el responsable.
