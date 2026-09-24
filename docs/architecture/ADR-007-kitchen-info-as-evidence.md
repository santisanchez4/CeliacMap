# ADR-007: Información de cocina como evidencia para revisión, no como autoridad sobre la etiqueta

**Estado:** Aceptado (2026-09-24) — implementado y verificado en producción (ver **Verificación**).

**Spec:** `docs/superpowers/specs/2026-09-24-kitchen-info-design.md` · **Plan:** `docs/superpowers/plans/2026-09-24-kitchen-info.md`

## Contexto

CeliacMap muestra dos rótulos públicos: **"Espacio 100% sin gluten"** (`gluten_free_100`) y **"Tiene opciones sin
TACC"** (`celiac_friendly` + `options_available`). Para decidir cuál corresponde hay que saber *cómo cocina* el
lugar: si solo se cocinan y venden productos aptos para celíacos, si también se cocina con gluten y cómo se separa lo
apto (cocina separada, preparación aparte, misma cocina), y si el dueño es celíaco. "Sin gluten", "sin TACC" y "apto
para celíacos" **no son lo mismo**.

Hasta ahora ninguno de los canales de la comunidad (formulario "Sumá un lugar", formulario "Recomendar / reportar",
chatbot) pedía nada de eso: solo había un campo de notas libre. Y esas notas terminaban en `places.validation_notes`,
que el Validator **no lee** y pisa en cada validación (ver "`validation_notes` es invisible para el Validator" en
`CLAUDE.md`). No hay cuentas: cualquiera puede enviar cualquier cosa, y los límites anti-spam viven en `localStorage`.

La regla de etiquetado la fijó Santiago el 2026-09-24 (registrada en `CLAUDE.md`): `gluten_free_100` significa que se
cocinan y venden **únicamente** productos aptos para celíacos; un local que cocina con gluten pero tiene menú,
preparación aparte o cocina separada es "opciones"; una cocina única en un emprendimiento chico no es 100% por
defecto; y que el dueño sea celíaco sube la confianza pero **nunca cambia la etiqueta solo**: hasta que el dueño lo
confirme directamente o haya una reseña que lo respalde, queda en "Tiene opciones".

## Decisión

1. **Tres preguntas opcionales, siempre con "No sé"**: ¿la cocina es exclusivamente sin gluten? (`kitchen_exclusive`),
   si no lo es ¿cómo preparan lo apto? (`celiac_prep`: `separate_kitchen` | `separate_prep` | `shared_kitchen`), y ¿el
   dueño es celíaco? (`owner_celiac`). Se piden en los dos formularios (`js/kitchen.js`, un solo módulo compartido) y
   en el chatbot.
2. **Columnas solo en las tablas de intake** (`suggestions`, `place_reports`), con CHECKs que hacen respetar la
   coherencia (`celiac_prep` solo si la cocina no es exclusiva; ningún dato de cocina en un reporte negativo).
   **`places` no cambia.** `owner_celiac` es un dato de salud de una persona concreta, casi siempre identificable en un
   emprendimiento chico, y viene de un tercero sin verificar; `places` es de lectura pública, las tablas de intake son
   solo-escritura para el público. El dato queda del lado servidor.
3. **El Validator las lee como evidencia no verificada.** `SupabaseClient.fetch_community_claims` une la sugerencia que
   originó el lugar y sus reportes positivos; `ValidatorAgent._build_user_prompt` las incluye en un bloque rotulado
   `declaraciones_comunidad (NO verificadas)`; `ReviewHandler` lo hereda. El `RUBRIC` precisa `gluten_free_100` y agrega
   un párrafo que acota esas declaraciones **a su propio bloque** (no cambian cómo se pesan las reseñas).
   **`owner_celiac` nunca llega al modelo** (`fetch_community_claims` no lo lee; el bloque no lo muestra): lo que el
   modelo ve puede terminar en su texto libre (`reasoning`, `flags`, `recommendation`), que se persiste en columnas de
   `places` legibles por la API pública, y el dato de salud de una persona concreta no puede salir por ahí (hallazgo de
   la revisión de la rama, verificado). Queda guardado del lado servidor para el administrador.
4. **Dos topes en código, defensa en profundidad** (como los umbrales de confianza): solo **bajan** el nivel y nunca
   tocan el `status`. **A)** un lugar `source='user'` nunca sale del Validator como `gluten_free_100`. **B)** si alguna
   declaración dice que la cocina no es exclusiva, el nivel queda como máximo en `celiac_friendly`. `owner_celiac` no
   participa de ningún tope (ni del prompt). Cuando un lugar de la comunidad queda esperando el 100%, se agrega la bandera fija
   `100% pendiente de confirmación del administrador`, que permite listar con una consulta todo lo que espera decisión.
5. **El chatbot pregunta una sola vez**, junto con el borrador ("¿Lo envío así?"), de forma opcional y salteable
   (con "dale" se envía sin esos datos; con "no sé" se vuelve a mostrar el borrador sin repetir la pregunta; el mensaje
   termina siempre con la pregunta de envío, así un "sí" pelado confirma el envío y no cuenta como respuesta de cocina).
   El router extrae los datos **sin inferir** (`cocina_exclusiva`, `preparacion_celiaca`,
   `dueno_celiaco`, `cocina_respuesta`); el borrador arrastra los datos y un `kitchen_asked` interno (que nunca se
   escribe). El **Módulo 4 (confirmar) sigue de un solo turno y no pregunta**: guarda los datos si la persona ya los
   dio y la respuesta la invita a sumarlos. El redactor incorpora un glosario (sin cifras) y nunca promete un 100%
   porque el dueño sea celíaco.
6. **El veredicto final del 100% es del administrador.** Un aporte de la comunidad es evidencia, no autoridad.

## Alternativas descartadas

- **Un `jsonb` con los datos de cocina.** Menos migraciones, pero el público (anon) podría escribir cualquier cosa y la
  validación por CHECK sobre un jsonb es débil.
- **Solo texto en las notas con un formato fijo.** Sin migración, pero el Validator no lo ve y no se puede consultar:
  es exactamente el problema de partida.
- **Validar el 100% con la comunidad** (p. ej. "N aportes coinciden ⇒ 100%"). Sin cuentas, una persona es
  indistinguible de cinco; y el costo de un 100% falso es asimétrico (un problema de salud). El volumen actual
  (≈1 sugerencia/mes) tampoco es un cuello de botella. Se revisa cuando haya cuentas verificadas, el volumen supere la
  capacidad de revisión, o la confirmación llegue del propio negocio (respuesta al email de Outreach, Etapa 2).
- **Guardar los datos en `places`.** Habría expuesto `owner_celiac` por la API pública.

## Verificación

- **Base de datos:** `db/checks/2026-09-24-kitchen-columns.sql` (transacción con `rollback`: filas válidas, cada CHECK
  debe rechazar lo que corresponde, y `anon` sigue pudiendo insertar) — **todavía no se corrió en producción**. La
  revisión de la rama encontró que `celiac_prep is null or kitchen_exclusive = false` **acepta** un `kitchen_exclusive`
  NULL (un CHECK pasa con NULL; verificado en Postgres): se corrigió a `kitchen_exclusive is false` antes de aplicar la
  migración, con un test que lo fija (`tests/test_schema_kitchen_checks.py`) y un caso más en la verificación SQL.
- **Rubric contra el modelo real:** `db/checks/validator_kitchen_ab.py`, **cuatro iteraciones**
  (`db/checks/2026-09-24-validator-kitchen-ab-run*.md`). La primera redacción dejaba el veredicto correcto (nunca
  `approved`) pero el `safety_level` crudo seguía en 100% con solo "cocina exclusiva: sí"; el refuerzo inicial hizo que
  el modelo desconfiara también de las reseñas y dejara de aprobar un lugar con evidencia fuerte y sin declaraciones
  (regresión detectada gracias a un caso agregado a propósito). La redacción final acota la regla al bloque de
  declaraciones: ninguna declaración sola produce `approved` ni 100% (también sobre un lugar que **no** es de la
  comunidad, donde solo el prompt —no el Tope A— frena el 100%), y la evidencia fuerte sin declaraciones vuelve a
  `approved` 100%. Deriva aceptada (spec §10 pedía "sin cambio"): un lugar con solo el nombre "Sin Gluten" y sin
  ninguna evidencia ahora muestra `celiac_friendly` en vez de `gluten_free_100` como mejor estimación cruda (el
  veredicto sigue en `needs_review`, y esa fila no es pública) — es la dirección conservadora y sale de la definición
  nueva de 100% ("únicamente productos aptos").
- **Router:** `db/checks/chat_kitchen_router_check.py`, 19 casos × 8 muestras, todo verde (sin sobre-extracción; "no sé"
  nunca cae en `fuera_de_alcance`; una respuesta de cocina mezclada con "ignorá tus reglas" sí queda `fuera_de_alcance`
  —el prompt anterior la trataba como respuesta de cocina, 0/8—; "sí", "sí, mandalo", "ok" y "dale" confirman el envío sin guardar ningún dato — el
  prompt anterior ya los manejaba con la redacción nueva de la pregunta, así que la regla agregada es defensiva). **Redactor:** `db/checks/2026-09-24-chat-kitchen-responder-regression-run.md`, sin
  regresión en cifras ni urgencia y 0/40 falsos positivos del guardián.
- **Suites:** Python, Deno (`supabase/functions/chat/`) y frontend, todas verdes.
- **En producción (2026-09-24), en el orden fijado:** la migración se aplicó y `db/checks/2026-09-24-kitchen-columns.sql`
  corrió sin errores (seis columnas solo en las tablas de intake, `places` sin cambios, cinco CHECK); el frontend se
  publicó al mergear a `main`; `chat` se desplegó (v15 y luego v16), con el código descargado idéntico a `HEAD` y
  `verify_jwt` en `false`. Los escenarios en vivo y la batería de jailbreak de 37 turnos (**0 rupturas**) están en
  `db/checks/2026-09-24-chat-kitchen-live-run.md`. Hallazgos: tras un "no sé" el bot ofrecía reescribir el comentario
  en vez de volver a mostrar el borrador (corregido en v16; los datos ya iban bien); el Módulo 4 con datos de cocina no
  pudo ejercitarse en vivo por la ambigüedad de ruteo `reportar`/`confirmar` que ya existía (solo tests unitarios). Todas
  las filas de prueba se revirtieron contra la línea base.

## Consecuencias

- El cambio a los prompts **reinicia el conteo del soft-launch** del chatbot (deliberado).
- `ReviewHandler` sobrescribe `safety_level` y `validation_notes` al reevaluar y **no protege overrides manuales**
  (preexistente; el script de re-validación sí los protege). Con el Tope A, un reporte negativo sobre un lugar
  `source='user'` aprobado manualmente como 100% (p. ej. Pastas Lo de Flor) podría bajarlo a `celiac_friendly`; se acepta
  como comportamiento conservador y queda registrado.
- Mostrar estos datos en el mapa queda fuera de alcance; si se hiciera, debe excluir `owner_celiac`.
- Un lugar de la comunidad no llega solo a 100%: el administrador sube la etiqueta con un override manual documentado
  (`CLAUDE.md`, "Manual Validator overrides"), como se hizo con Los Leños, Dalbertt y Pastas Lo de Flor.
