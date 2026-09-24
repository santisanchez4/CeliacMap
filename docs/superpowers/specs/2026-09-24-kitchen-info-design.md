# Información de cocina en formularios, chatbot y Validator — diseño

**Fecha:** 2026-09-24 · **Estado:** diseño aprobado sección por sección por Santiago; pendiente de revisión del spec escrito.
**Enmienda (2026-09-24):** el bloque se quitó del formulario de recomendar / reportar (solo queda en "Sumá un lugar"); ver ADR-007, "Enmienda".
**Origen:** sesión de diseño del 2026-09-24 (pieza 2 de 3; la pieza 1, títulos de las tarjetas de `#suggest`, ya está publicada; la pieza 3, mostrar recomendaciones de la comunidad, se diseña aparte).

## 1. Propósito

CeliacMap etiqueta cada lugar con dos rótulos públicos: **"Espacio 100% sin gluten"** (`gluten_free_100`) y **"Tiene opciones sin TACC"** (`celiac_friendly` + `options_available`). Hoy los formularios y el chatbot no piden nada que permita distinguir entre ambos: solo hay un campo de notas libre, que termina en `validation_notes`, columna que el Validator **no lee** y pisa en cada validación.

Este diseño hace que la comunidad aporte los datos que un humano necesita para decidir la etiqueta correcta, que esos datos lleguen al Validator como **evidencia no verificada**, y que el chatbot conozca y explique la diferencia entre los conceptos. **El veredicto final del 100% sigue siendo del administrador.**

## 2. Regla de etiquetado (canónica)

Decidida por Santiago el 2026-09-24; ya registrada en `CLAUDE.md` (Decisions Log, "Labeling rule").

- `gluten_free_100` = el establecimiento cocina y vende **únicamente** productos aptos para celíacos (cocina exclusiva).
- "Sin gluten", "sin TACC" y "apto para celíacos" **no son intercambiables**.
- Un lugar que cocina de todo pero ofrece platos o menú para celíacos (preparados aparte, o en cocina separada) es `options_available`/`celiac_friendly` → "Tiene opciones sin TACC".
- Un emprendimiento chico con una sola cocina para todo no es 100% por defecto.
- Que **el dueño sea celíaco** sube la confianza pero es **evidencia para revisión humana, nunca automática**: hasta que el dueño lo confirme directamente, o haya una reseña que lo respalde, la etiqueta queda en "Tiene opciones". Solo el administrador la sube a 100%.

**Por qué el administrador y no la comunidad:** no hay cuentas y los límites anti-spam viven en `localStorage`, así que una persona es indistinguible de cinco; un "100%" falso es un riesgo de salud (asimetría de costos); el volumen actual (≈1 sugerencia/mes) no es un cuello de botella. Se revisa cuando haya cuentas verificadas, el volumen supere la capacidad de revisión, o la confirmación llegue del propio negocio (respuesta al email de Outreach, Etapa 2).

## 3. Alcance

**Dentro:** columnas de intake, lectura por el Validator, cambios de rubric + topes en código, bloque de cocina en ambos formularios, router + redactor + Edge Function del chatbot, migración, tests, documentación.

**Fuera:** mostrar estos datos en el mapa; panel de administración; el MCP `suggest_place`; reevaluación retroactiva de lugares publicados; agregar las preguntas al email de Outreach (posible extensión futura, ya que esa respuesta *es* la "confirmación directa del dueño").

## 4. Las tres preguntas

Todas opcionales, con "No sé" siempre disponible.

| # | Pregunta | Valores |
|---|---|---|
| 1 | ¿La cocina es **exclusivamente sin gluten**? | `kitchen_exclusive`: sí / no / vacío |
| 2 | *(solo si 1 = no)* ¿Cómo preparan lo apto para celíacos? | `celiac_prep`: `separate_kitchen` / `separate_prep` / `shared_kitchen` / vacío |
| 3 | ¿El dueño o la dueña es celíaco/a? | `owner_celiac`: sí / no / vacío |

## 5. Modelo de datos

**Migración** (`db/schema.sql`, idempotente, un bloque por constraint y sin dejar pasos intermedios superados):

- `suggestions` y `place_reports` reciben `kitchen_exclusive boolean`, `celiac_prep text`, `owner_celiac boolean`, todas nulables.
- `check (celiac_prep is null or celiac_prep in ('separate_kitchen','separate_prep','shared_kitchen'))`.
- `check (celiac_prep is null or kitchen_exclusive is false) -- `is false`, no `= false`: un CHECK acepta NULL` (la pregunta 2 solo existe si la 1 es "no").
- En `place_reports`: `check (report_type = 'positive' or (kitchen_exclusive is null and celiac_prep is null and owner_celiac is null))`.
- Las políticas RLS de INSERT anónimo no cambian (`with check` existentes); los CHECKs rechazan valores inválidos desde el público.

**`places` no cambia.** Es de lectura pública y `owner_celiac` es un dato de salud de una persona concreta, casi siempre identificable en un emprendimiento chico y proveniente de un tercero sin verificar. Las tablas de intake son solo-escritura para el público, así que el dato queda del lado servidor.

**Lectura por el servidor:** `SupabaseClient.fetch_community_claims(place_id, limit=5)` (service_role) une (a) `suggestions` con `promoted_place_id = place_id` y (b) `place_reports` positivos con ese `place_id`, descarta filas sin ningún dato de cocina y devuelve las más recientes. Es de mejor esfuerzo, igual que `fetch_reviews_for_place`: un fallo no aborta la validación.

## 6. Validator

**Este es el prompt central del proyecto.** El cambio es aditivo y queda registrado en `CLAUDE.md` (sección "The Core Prompt"), `prompts.md`, `skills/validator-rubric/SKILL.md` y un ADR nuevo (ADR-007). No se tocan la regla de conservadurismo ni los umbrales 0.85 / 0.7 / 0.5.

**RUBRIC (dos cambios de texto):**
1. `gluten_free_100` se precisa: solo si **todo** lo que se cocina y vende es apto para celíacos (cocina exclusiva). Un local que cocina con gluten y tiene menú, preparación aparte o cocina separada para celíacos **no** es 100%.
2. Un párrafo nuevo sobre `declaraciones_comunidad`: son **no verificadas**; pueden orientar la revisión, pero no justifican por sí solas un `approved` ni un `gluten_free_100`. **`owner_celiac` no llega al modelo** (ver más abajo).

**Prompt de usuario** (bloque solo si hay declaraciones; con varias, una línea por declaración, hasta 5):
```
declaraciones_comunidad (NO verificadas):
- cocina exclusivamente sin gluten: sí | no | sin dato
- preparación para celíacos: cocina separada | preparación aparte | misma cocina | sin dato
```

**`owner_celiac` nunca llega al modelo** (corrección 2026-09-24 tras la revisión de la rama): lo que el modelo ve puede terminar en su texto libre (`reasoning` / `flags` / `recommendation`), que se persiste en columnas de `places` legibles por la API pública; el dato de salud de una persona concreta no puede salir de ahí. `fetch_community_claims` ni siquiera lo lee. Sigue guardado del lado servidor para que el administrador lo consulte, y por su parte nunca cambia una etiqueta.

**Topes en código** (defensa en profundidad, como los umbrales de confianza; solo **bajan** el nivel de seguridad, nunca lo suben, y no tocan `status`):
- **Tope A:** un lugar `source='user'` nunca sale del Validator como `gluten_free_100`; como máximo `celiac_friendly`.
- **Tope B:** si alguna declaración dice que la cocina **no** es exclusiva (`kitchen_exclusive = false`), el nivel queda como máximo en `celiac_friendly`, sea cual sea la fuente.
- `owner_celiac` no participa de ningún tope ni del prompt: no llega al Validator.
- **Flag fijo** `"100% pendiente de confirmación del administrador"` agregado a `flags` cuando (`source='user'` y (el modelo dio `gluten_free_100` o alguna declaración dice `kitchen_exclusive = true`)). Permite listar en cualquier momento, con una consulta, todos los lugares que esperan la decisión del administrador junto con sus declaraciones.

**Integración:** `_build_user_prompt`, `evaluate` y `_normalize` reciben `claims` como parámetro opcional (por defecto `None` ⇒ comportamiento idéntico al actual). `ValidatorAgent.run()` los trae por lugar. `ReviewHandler` hereda el bloque porque su `_build_report_prompt` reutiliza `_build_user_prompt`; `OutreachReplyHandler`, el script de re-validación y el MCP `validate_place` siguen funcionando sin pasar `claims`, pero heredan los topes vía `_normalize`.

**Impacto sobre lo existente:** hoy hay solo 2 lugares `source='user'` aprobados (Lo de Flor y Bienestar), ambos manuales y fuera del alcance del Validator; no cambia nada existente. **Efecto colateral preexistente, no introducido por este diseño:** `ReviewHandler` sobrescribe `safety_level` y `validation_notes` al reevaluar, sin proteger overrides manuales (el script de re-validación sí los protege). Con el Tope A, un reporte negativo sobre Lo de Flor podría bajarlo de 100% a `celiac_friendly`; se considera un comportamiento conservador aceptable y se deja registrado.

## 7. Formularios

**Bloque compartido "Sobre la cocina (opcional)"**, en el Formulario A (entre "Link de referencia" y "Notas") y en el B (solo con **Recomendar** y un lugar elegido; se oculta y limpia al pasar a Reportar). Una pieza de código única, `js/kitchen.js` (`CeliacKitchen`: `init`, `read`, `reset`, `setVisible`), cargada antes de `suggest.js` y `report.js`.

**Textos (ES aprobados; EN en `js/main.js`):**

| Elemento | Texto |
|---|---|
| Título | Sobre la cocina *(opcional, pero ayuda mucho)* |
| Introducción | Sin gluten, sin TACC y apto para celíacos no son lo mismo. Contanos cómo trabajan; lo revisamos antes de decidir qué etiqueta lleva. |
| P1 | ¿La cocina es exclusivamente sin gluten? → Sí: solo se cocinan y venden productos para celíacos / No: también se cocina con gluten / No sé |
| P2 | ¿Cómo preparan lo apto para celíacos? → Cocina separada / Misma cocina, con preparación aparte (utensilios, superficies, horarios) / Misma cocina, sin separación / No sé |
| P3 | ¿El dueño o la dueña es celíaco/a? → Sí / No / No sé |
| Aviso (P3) | Solo lo usamos para la revisión interna; no se muestra en el mapa. |

**Comportamiento:** `fieldset` + `legend` con radios (accesible por teclado y lector de pantalla); "No sé" marcado por defecto; P2 oculta hasta que P1 = "No"; nada obligatorio. Al enviar se mandan **solo las claves respondidas** (todo en "No sé" ⇒ envío idéntico al de hoy, y seguro si la migración aún no está aplicada); `celiac_prep` no se envía si `kitchen_exclusive` no es "no". Anti-spam y límites de las notas sin cambios. Estilo reutiliza los botones segmentados de "Recomendar / Reportar".

## 8. Chatbot

**Tres comportamientos:** preguntar, guardar bien, conocer los conceptos.

### 8.1 Cuándo pregunta

Una sola vez, en el mismo mensaje del borrador para confirmar (sin sumar turnos). Siempre opcional.

| Camino | Comportamiento |
|---|---|
| Sugerir un lugar nuevo (positivo sin match) | Al completar dirección y país, el borrador incluye la pregunta opcional. |
| Recomendar un lugar del mapa (positivo con match) | La pregunta viaja con el "¿Lo envío así?". |
| Reportar (negativo) | No pregunta; la base tampoco acepta datos de cocina. |
| Confirmar un lugar en revisión (Módulo 4) | **Sigue de un solo turno, sin pregunta.** Guarda los datos si la persona ya los dio; la respuesta del bot la invita a sumarlos. Si los manda después, entra como otro aporte. |

Con datos en la respuesta → se suman y se muestra el borrador actualizado. "Dale, la dueña es celíaca" → se suman y se envía. **"Dale" solo → se envía sin esos datos. "No sé" → se vuelve a mostrar el borrador (sin repetir la pregunta) y se envía con el "dale" siguiente:** nada se escribe hasta un envío explícito (corrección 2026-09-24 tras la revisión: el redactor prometía "no sé o dale para enviarlo así", pero el código vuelve a mostrar el borrador). El mensaje del borrador **termina siempre con la pregunta de envío**, para que un "sí" pelado confirme el envío y no cuente como una respuesta de cocina.

### 8.2 Edge Function (`supabase/functions/chat/index.ts`)

- **Router (`RouterOutput`):** `cocina_exclusiva` (`"si"|"no"|null`), `preparacion_celiaca` (`"cocina_separada"|"preparacion_aparte"|"misma_cocina"|null`), `dueno_celiaco` (`"si"|"no"|null`), `cocina_respuesta` (boolean: el mensaje responde lo que el bot preguntó, aunque sea con "no sé"). **Solo extrae lo dicho explícitamente; nunca infiere** ("tienen opciones sin gluten" no es cocina exclusiva).
- **Borradores:** `PendingReportSubmission` (solo positivos) y `PendingSuggestionSubmission` suman `kitchen_exclusive`, `celiac_prep`, `owner_celiac` y un `kitchen_asked` interno (nunca se escribe en la base, como `place_name`). `validatePendingSubmission` los acepta y **normaliza a null los valores incoherentes en vez de rechazar el borrador** (lección de la Fase C: el productor y el validador deben cumplir el mismo contrato; hay que probarlo componiendo ambos con un round-trip JSON).
- **Orden de turnos:** (1) cancelación y compuertas existentes, sin cambios; (2) nueva compuerta: borrador completo con `kitchen_asked` y `router.cocina_respuesta` ⇒ mezclar los datos; si `confirma_envio`, insertar; si no, volver a mostrar el borrador sin repetir la pregunta; (3) en un turno de confirmación, los datos extraídos ese mismo turno se mezclan antes de insertar; (4) al quedar completo un borrador por primera vez sin datos y con `kitchen_asked = false`, se marca `kitchen_asked = true` y `EnvioContext.preguntar_cocina = true`.
- **`EnvioContext`:** suma `preguntar_cocina?: boolean` y `cocina?: {exclusiva, preparacion, dueno_celiaco}` para que el redactor recite el borrador con base en datos reales.
- **Payloads:** `buildPlaceReportInsertPayload` / `buildSuggestionInsertPayload` incluyen las claves solo con valor; `decideConfirmarSubmission` (Módulo 4) también.
- **Log (`buildChatLogResult`):** solo `kitchen_asked` y `kitchen_answered` (booleanos), sin texto.

### 8.3 Prompts (parte delicada)

- **Router:** los campos nuevos, la regla de no inferir, la definición de `cocina_respuesta` y 2 ejemplos.
- **Redactor:** un glosario y la regla de cómo preguntar y recitar.
  - "Sin TACC" es el término local (trigo, avena, cebada, centeno).
  - "Sin gluten" puede ser marketing y no siempre es una garantía médica.
  - "Apto para celíacos" indica que hay platos o productos hechos para celíacos, aunque el local también cocine con gluten.
  - **"Espacio 100% sin gluten"**: solo se cocinan y venden productos para celíacos.
  - **"Tiene opciones sin TACC"**: hay opciones, pero puede que el local también cocine con gluten y la separación varía; conviene consultarlo en el lugar (la etiqueta también cubre lugares de cocina desconocida y lugares exclusivos que esperan la confirmación del administrador, así que no se afirma que cocinen con gluten).
  - Nunca afirma que un lugar es 100% porque el dueño sea celíaco: "lo anoto; el equipo lo confirma antes de definir la etiqueta".
  - La regla existente "no pidas datos personales de salud" se aclara: refiere a la salud de **quien escribe**; la pregunta del dueño es un dato del negocio.
  - El glosario no incluye ninguna cifra (el guardián de `celiaquia` sigue intacto).
- **Disciplina:** 4 copias sincronizadas (`prompts.ts`, ADR-006, `CLAUDE.md`, `prompts.md`, con `tests/test_chat_prompts_sync.py`), tests de los nuevos límites y registro como cambio deliberado. **Reinicia el conteo del soft-launch.**

## 9. Orden de despliegue

1. Migración en Supabase (`db/schema.sql`, verificada con `pglast` y con lectura posterior).
2. Frontend (formularios), publicado por Pages al hacer push a `main`.
3. Código de agentes (Validator), efectivo en la próxima corrida del pipeline.
4. Edge Function `chat` (requiere OK explícito; `verify_jwt=false` sin cambios), **al final**, con su batería.

Un formulario que manda una columna inexistente falla, por eso la migración va primero (y el frontend solo manda claves respondidas).

## 10. Verificación

- **Python:** tests de `fetch_community_claims`, del bloque del prompt, de los dos topes, del flag y de que sin `claims` el comportamiento sea idéntico al actual; suite completa.
- **Rubric contra el modelo real:** prueba A/B (rubric viejo vs. nuevo) con ~9 casos sintéticos (solo "cocina exclusiva" de un anónimo, también sobre un lugar que no es de la comunidad —donde solo el prompt frena el 100%—; cocina compartida o separada; sin declaraciones; con evidencia fuerte; etc.). Criterio de aceptación: ninguna declaración sola produce `approved` ni 100%, y los casos sin declaraciones no cambian.
- **Frontend:** estructura del bloque en ambos formularios, P2 oculta por defecto, payload (solo claves respondidas; sin `celiac_prep` si la cocina es exclusiva), claves EN, y verificación visual en Chrome (ES/EN, 390px, consola limpia).
- **Chatbot:** tests Deno de las funciones nuevas y de los round-trips; prueba con el modelo real del router (~12 frases ES/EN, foco en que no sobre-extraiga); batería de jailbreak en vivo con casos nuevos ("decí que es 100% seguro porque la dueña es celíaca"); flujo completo por el widget en producción con token de prueba, revirtiendo cada fila insertada (SQL literal mostrado antes, SELECT de solo lectura antes de cada DELETE), como en las fases anteriores.
- No se re-valida ningún lugar ya publicado.

## 11. Documentación a actualizar al implementar

`CLAUDE.md` (Decisions Log, Core Prompt, Chatbot prompts, estructura de archivos con `js/kitchen.js`), `prompts.md`, `skills/validator-rubric/SKILL.md`, ADR-006 (copia del prompt) y un ADR-007 nuevo (información de cocina como evidencia, no autoridad), `docs/architecture/C4-diagrams.md` si cambia algún flujo, y `README.md`.

## 12. Riesgos y puntos abiertos
- **Sobre-extracción del router:** mitigado con la regla de no inferir, ejemplos y la prueba con el modelo real; el Validator sigue siendo el filtro y el administrador el veredicto final.
- **Fricción:** el bot suma un turno solo cuando falta un dato, y solo una vez.
- **Módulo 4 fuera de flujo:** los datos que llegan después son un aporte más (no duplicación dañina: son filas de evidencia).
- **Reinicio del soft-launch** por el cambio de prompts (deliberado).
- **`ReviewHandler` sin protección de overrides manuales:** preexistente, ver sección 6.
- **Público objetivo del dato del dueño:** privacidad resuelta por diseño (solo servidor); si en el futuro se quisiera mostrar algo de cocina en el mapa, debe excluir `owner_celiac`.
