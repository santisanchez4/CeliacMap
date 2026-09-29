# `owner_celiac`: conteo y plan para eliminarlo

> Borrador del 2026-09-29. **No se ejecutó nada**: el conteo es un `SELECT` de solo lectura y el resto es una propuesta.

## Por qué sacarlo

La pregunta “¿El dueño o la dueña es celíaco/a?” junta un **dato de salud de una tercera persona**, identificable (el
dueño o la dueña de un negocio con nombre y dirección), que lo aporta alguien que no es esa persona y sin su
consentimiento. La Ley 18.331 (art. 18) y la Ley 25.326 (art. 7) exigen, para los datos sensibles, el consentimiento
expreso y escrito del titular. Además, el dato ya no cambia nada en el sistema: el Validator no lo lee
(`SupabaseClient._CLAIM_FACTS`), ningún tope del código lo usa y la regla del 100% dice que solo el admin sube un lugar a
100%. Hoy lo único que hace es aparecerle al admin en `review_queue` y en el mail diario.

## Conteo en producción (2026-09-29, solo lectura)

```sql
select 'suggestions' as tabla,
       count(*) filter (where owner_celiac is not null) as con_dato,
       count(*) filter (where owner_celiac) as si,
       count(*) filter (where owner_celiac = false) as no,
       count(*) as total
from public.suggestions
union all
select 'place_reports', count(*) filter (where owner_celiac is not null),
       count(*) filter (where owner_celiac), count(*) filter (where owner_celiac = false), count(*)
from public.place_reports;
```

| Tabla | Con dato | Sí | No | Total de filas |
|---|---|---|---|---|
| `suggestions` | **0** | 0 | 0 | 2 |
| `place_reports` | **0** | 0 | 0 | 2 |

También se revisaron los textos libres: 0 notas de sugerencias y 0 descripciones de reportes mencionan “dueño” o
“dueña” (`~* 'due[ñn]'`). `place_evidence` tiene 0 filas. **No hay nada guardado para borrar**, y como el mail diario
solo muestra el dato cuando existe, tampoco salió en ningún mail.

## Dónde aparece (código, prompts y tests)

**Formulario (Form A)**
- `index.html:620-628`: la pregunta 3 del bloque de cocina (`sg-kq3`, radios `sg-kitchen-owner`) y la nota
  `kitchen.ownerNote`.
- `js/main.js:209, 212` (y sus equivalentes en español): claves i18n `kitchen.q3` y `kitchen.ownerNote`.
- `js/kitchen.js:45, 60-62`: `reset()` y `read()` (`out.owner_celiac`).

**Chat (Edge Function `chat`)**
- `supabase/functions/chat/index.ts`: tipos (`:88`, `:112`, `:249`, `:885`, `:1051`, `:1089`, `:1372`),
  `NO_KITCHEN_FACTS` (`:1053`), `SparseKitchen`/`toSparse` (`:1055-1062`), `normalizeKitchenFacts` (`:1068-1080`),
  la extracción del router `dueno_celiaco` → `owner_celiac` (`:1097`, `:1312`), `mergeKitchenFacts` (`:1104-1117`),
  `withConfirmFacts` (`:1151-1160`), `cocinaContext` (`:1168`, lo que ve el redactor) y `moduloCuatroEnvioExtras`
  (`:1180`). Los reportes ya lo descartan (`mergeKitchenFacts` y `buildPlaceReportInsertPayload`); las **sugerencias
  del chat sí lo guardan**, y también las opiniones positivas del módulo 4.
- `supabase/functions/chat/prompts.ts` (**prompts: health gate**):
  - `ROUTER_PROMPT` regla 9 (`:69-83`: “La dueña / el dueño es celíaco/a → dueno_celiaco”), regla 10 (`:84-87`), el
    campo `dueno_celiaco` del esquema de salida (`:209`) y de cada `Salida:` de los ejemplos (`:116-190`), y el ejemplo
    de `:158-160`.
  - `RESPONDER_PROMPT` regla 3 (`:301`: la pregunta de cocina incluye al dueño), regla 5 (`:332`), la constraint de
    `:357-360` (“Preguntar si el dueño… es un dato del negocio”) y el ejemplo de `:536-548` (el bloque `<envio>` de `:546` trae `dueno_celiaco`).
  - Se conserva, sin cambios, la constraint de `:361-364` (“NUNCA digas… 100% porque el dueño sea celíaco”): protege
    contra lo que la persona escriba en texto libre.
- Copias sincronizadas: `prompts.md` §27 y `docs/architecture/ADR-006-chatbot-rag.md` (`scripts/sync_chat_prompts.py`).

**Validator y agentes**
- `agents/validator_agent.py:144` (RUBRIC): “No menciones… datos de salud de ninguna persona (por ejemplo, si el dueño o
  la dueña es celíaco/a)”. **Se conserva**: cubre el texto libre de reseñas y evidencia, no la columna. No hay que
  tocar el RUBRIC.
- `agents/validator_agent.py:247, 387` y `agents/clients/supabase_client.py:265, 574`: comentarios que explican por qué
  la columna no se lee. Se actualizan cuando la columna ya no existe.

**Herramientas del admin**
- `scripts/admin_digest.py:11, 56-59` (mail diario) y `scripts/review_queue.py:95, 117` (“solo para vos”).
- `scripts/review_queue.py:430` (aviso de no escribir datos de salud en la nota pública): **se conserva**.

**Base**
- `db/schema.sql:410-427` (columnas y comentario), `:466` (el `CHECK place_reports_kitchen_positive_only_check` la
  nombra) y `:477` (comentario de la vista).

**Tests**
- `tests/frontend_kitchen.test.js:69, 87, 137, 176`
- `supabase/functions/chat/kitchen.test.ts` (unas 30 aserciones; por ejemplo `:63`, `:100-102`, `:126`, `:235`,
  `:257-263`, `:378`, `:417`)
- `tests/test_admin_notify.py:95, 106` · `tests/test_review_queue.py:41, 72` · `tests/test_schema_kitchen_checks.py:38`
- `tests/test_supabase_client.py:299-357` y `tests/test_validator_agent.py:347-368, 472`: prueban que la columna
  **nunca** se lee. Se pueden quedar como guardas (con dicts de prueba siguen pasando) o simplificarse.
- No se tocan: `tests/test_evidence_finder.py`, `test_evidence_acceptance.py`, `test_review_queue_proposals.py` y
  `test_validator_agent.py:686-688`. Esos tests prueban que la frase “la dueña es celíaca” en **texto libre** no llegue
  a una nota pública, y eso sigue haciendo falta.

**Docs** (históricos, se actualizan con una entrada nueva y no se reescriben): `CLAUDE.md` (regla “100% label”:
“An owner-is-celiac claim…”), ADR-007, ADR-008, `docs/superpowers/specs|plans/2026-09-24-kitchen-info*`,
`skills/validator-rubric/SKILL.md:101`, `db/checks/*` (corridas viejas, no se tocan).

## Plan propuesto

### Etapa 1 — dejar de juntarlo sin tocar los prompts (se puede hacer ya)

1. **Formulario:** sacar la pregunta 3 y su nota de `index.html`, las claves i18n de `js/main.js` y la rama `owner` de
   `js/kitchen.js`. Test: `frontend_kitchen.test.js` pasa a afirmar que `owner_celiac` **nunca** está en el cuerpo
   enviado.
2. **Admin:** sacar la línea de `admin_digest.py` y de `review_queue.py`, con sus tests.
3. **Chat, solo código:** `normalizeKitchenFacts` ignora `owner_celiac` y `buildSuggestionInsertPayload` nunca lo
   escribe. El router puede seguir devolviendo `dueno_celiaco`, pero el código lo tira: no llega a la base, a
   `<envio>` ni al redactor. Test: `kitchen.test.ts` afirma que ningún payload lo trae. Esto no cambia los prompts,
   pero sí cambia lo que recibe el redactor (`cocinaContext` deja de traer `dueno_celiaco`). Hay que correr los tests
   offline y una prueba en vivo de una sugerencia con cocina antes de dar por bueno el deploy.
4. Deploy: primero el frontend (Pages) y `chat`, verificando `verify_jwt=false` y que la fuente sea igual a `HEAD`.

Límite de la etapa 1: el redactor **sigue preguntando** por el dueño (lo dice su prompt), aunque la respuesta ya no se
guarde. La respuesta sí queda en la conversación que ve Anthropic, y en `agent_log` durante 30 días si el turno se marca.

### Etapa 2 — sacar la pregunta de los prompts (en la próxima tanda de prompts)

Cambios en `ROUTER_PROMPT` (regla 9, regla 10, el campo `dueno_celiaco` y el ejemplo) y en `RESPONDER_PROMPT` (reglas 3
y 5, la constraint de `:357-360` y el ejemplo de Pan Justo). Después, borrar `dueno_celiaco` del tipo y del parser del
router.

**Recomendación: sumarlo a la próxima tanda de prompts, no hacer una tanda aparte.** Ya hay cambios de prompt en
espera: reemplazar el ejemplo de Bienestar, el glosario de “sin gluten”, la contradicción entre 2c y los ejemplos
(búsqueda por región) y la reformulación F4 opción 1. Cada tanda exige A/B contra el modelo real, la batería de
jailbreak y reiniciar la cuenta del soft-launch, así que juntar todo cuesta una sola vez. Mientras tanto, la etapa 1 ya
corta el guardado, y el riesgo que queda (una pregunta que se sigue haciendo y una respuesta que se descarta) es bajo:
hay 0 filas en cinco días. Si la tanda se atrasa mucho, se puede hacer una tanda mínima solo con este cambio.

Qué medir en esa tanda: que el redactor ya no pregunte por el dueño (0 de N en los casos de cocina de
`db/checks/chat_kitchen_live.py`), que la extracción de `cocina_exclusiva` y `preparacion_celiaca` no empeore
(`chat_kitchen_router_check.py`) y que la batería siga en 0 quiebres.

### Etapa 3 — base de datos (después de las etapas 1 y 2, con “dale”)

El orden importa: si la columna desaparece mientras alguien tiene la página vieja en caché, PostgREST rechaza el
`INSERT` que la trae y **se pierde la sugerencia entera**. Por eso la columna se borra al menos una semana después de la
etapa 1.

SQL propuesto (**no ejecutado**; se muestra literal y espera “dale”, como pide la regla de producción):

```sql
-- 0) Verificación previa: tiene que dar 0 y 0.
select (select count(*) from public.suggestions   where owner_celiac is not null) as sug,
       (select count(*) from public.place_reports where owner_celiac is not null) as rep;

begin;
-- 1) Borrar lo guardado (hoy 0 filas; queda por si aparece algo entre el conteo y la migración).
update public.suggestions   set owner_celiac = null where owner_celiac is not null;
update public.place_reports set owner_celiac = null where owner_celiac is not null;

-- 2) El CHECK de reportes nombra la columna: se recrea sin ella.
alter table public.place_reports drop constraint if exists place_reports_kitchen_positive_only_check;
alter table public.place_reports add constraint place_reports_kitchen_positive_only_check
  check (report_type = 'positive' or (kitchen_exclusive is null and celiac_prep is null));

-- 3) Sacar las columnas.
alter table public.suggestions   drop column if exists owner_celiac;
alter table public.place_reports drop column if exists owner_celiac;
commit;

-- 4) Verificación posterior (solo lectura): tiene que dar 0 filas.
select table_name, column_name from information_schema.columns
where table_schema = 'public' and column_name = 'owner_celiac';
```

Además: actualizar `db/schema.sql` (el bloque `KITCHEN-DECLARATIONS` y los comentarios), guardar la migración en
`db/migrations/`, ajustar `test_schema_kitchen_checks.py` y buscar mails del diario que traigan “dueño/a celíaco/a” en
el buzón (hoy no debería haber ninguno).

### Etapa 4 — documentación

Una entrada nueva en `docs/DECISIONS.md` (“owner_celiac eliminado, 2026-MM-DD”), una línea en el índice de `CLAUDE.md`,
el cambio de la regla “100% label” (sacar “An owner-is-celiac claim…” y dejar “los datos de salud de terceros no se
juntan”), una adenda en ADR-007 y la tanda de prompts registrada en `prompts.md`.
