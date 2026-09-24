# Auditoría 2026-09-24 — agentes, Validator y chatbot

**Objetivo del producto:** que el mapa de celiacmap.org distinga con claridad dos cosas:

- **"Espacio 100% sin gluten"** (`gluten_free_100`): solo se cocinan y venden productos aptos para celíacos.
- **"Tiene opciones sin TACC"** (`celiac_friendly` + `options_available`): hay opciones para celíacos, pero puede
  que el lugar también cocine con gluten.

**Fuentes de evidencia:** Google (Places + reseñas), redes (Social), la web (Web agent) y los aportes de quienes
usan el sitio (formularios + chatbot).

**Alcance:** revisé el código de `agents/` (Search, Social, Web, Suggestion, Validator, Updater, Review handler), el
`RUBRIC`, la Edge Function `chat` (router, redactor, búsqueda) y el frontend del mapa. **No revisé datos de
producción**: el entorno no tiene acceso de red a Supabase. Por eso cada cambio que depende de cuántos lugares
afecta empieza con una consulta de solo lectura (paso 0).

---

## Resumen

La arquitectura es sólida. Hay una sola compuerta de seguridad, con umbrales que aplica el código. Los aportes de la
comunidad cuentan como evidencia y nunca actúan solos. La etiqueta pública está unificada en dos niveles. Encontré
**tres huecos que afectan directamente la distinción entre 100% y opciones**, más otros menores:

| # | Hallazgo | Gravedad | Dónde |
|---|----------|----------|-------|
| H1 | La evidencia que juntan los agentes de descubrimiento **nunca llega al Validator** | Alta | `web_agent.py`, `social_agent.py`, `validator_agent.py::_build_user_prompt` |
| H2 | Un lugar de Search/Social/Web puede pasar a **100% automático solo por el nombre** | Alta | `validator_agent.py::_apply_kitchen_caps` (el tope A solo cubre `source='user'`) |
| H3 | Un **reporte negativo** borra las correcciones manuales del admin y puede **subir** el nivel | Alta | `review_handler.py::handle` |
| H4 | El chatbot **no puede filtrar por nivel** ("solo 100% sin gluten") | Media | `chat/index.ts::buildPlacesSearchUrl` + router |
| H5 | Una opinión aprobada puede decir "es 100% sin gluten" sobre un lugar marcado "opciones" | Media | `scripts/moderate_opinions.py`, `js/opinions.js` |
| H6 | `resolve_location` acepta el primer resultado de Find Place sin comparar el nombre | Media (ya conocido) | `agents/clients/google_places.py` |
| H7 | La cola `needs_review` (~480) y los "100% pendientes" no tienen herramienta de revisión | Media | falta un script |
| H8 | Un solo reporte negativo anónimo saca un lugar del mapa | Decisión del dueño | `review_handler.py` |

---

## Hallazgos en detalle

### H1 — El Validator juzga con nombre + dirección, aunque ya tengamos evidencia

`ValidatorAgent._build_user_prompt` le manda al modelo solo `name`, `address`, `city`, `country`,
`guessed_category`, `source`, las reseñas de Google (si hubo enriquecimiento) y las declaraciones de cocina. Se pierde:

- **Web agent:** el modelo de descubrimiento devuelve `evidence` ("por qué este lugar es relevante para sin
  gluten") y una `source_url`. La URL se guarda en `social_url`, pero **la `evidence` se descarta** al armar el
  candidato (`web_agent.py` ~l.245) y el Validator tampoco lee `social_url`.
- **Social agent:** el título y el snippet de Instagram/Facebook (donde suele decir "100% sin TACC",
  "cocina exclusiva") se usan para extraer el lead y **se descartan**.
- **Admin:** la evidencia manual en `validation_notes` es invisible para el Validator y cada validación la pisa
  (riesgo ya documentado en CLAUDE.md; el caso de los 16 lugares de Montevideo del 2026-09-07).

**Consecuencia para el objetivo:** justo la frase que separa "100%" de "opciones" (la bio de Instagram, el post del
blog) la vemos en el descubrimiento y la tiramos. El Validator termina en `needs_review` por falta de señal
(parte de los 480), o infiere el nivel por el nombre (H2).

### H2 — 100% automático solo por el nombre

`_apply_kitchen_caps` impide que un lugar `source='user'` salga del Validator como `gluten_free_100` (tope A), pero
**no aplica a `google_places` / `social` / `web`**. Para esas fuentes el modelo puede asignar 100% con un nombre como
"Sin Gluten X" o "Celíaco Y" como única señal. Es la misma clase de error que "Serendipia-cea"
(aprobado `gluten_free_100` por interpretar un sufijo) y "Enharinate Mendoza" (aprobado por conocimiento propio del
modelo). Hoy la regla de etiquetado del 2026-09-24 dice que solo el admin sube a 100% ante una afirmación de la
comunidad, pero una afirmación implícita en el nombre del negocio pasa sin ese control.

Un nombre "sin gluten" no prueba que la cocina sea exclusiva: hay muchos locales "Sin Gluten ..." que también venden
con gluten, o que son dietéticas con góndola mixta.

### H3 — Un reporte negativo pisa las correcciones manuales

`ReviewHandler.handle` llama a `update_place_validation` con `notes`, `safety_level`, `category` y `confidence`
nuevos. Para un lugar con override manual (Los Leños y Dalbertt → 100%, Pastas Lo de Flor, Dispensario, Ta Bacana,
Bienestar):

1. **Borra la nota `APROBACIÓN/CORRECCIÓN MANUAL`**, que es el único registro auditable del override.
2. **Recalcula `safety_level` desde cero** con la evidencia pública, así que un 100% puesto por el admin puede volver a
   "opciones" sin que nadie lo decida.
3. **Puede subir el nivel.** Un reporte *negativo* sobre un lugar de fuente no-`user` puede terminar con un
   `safety_level` más alto que el que tenía. Un reporte negativo nunca debería subir el nivel.

`scripts/revalidate_low_confidence.py` ya protege las filas con marcadores manuales; el review handler no.

### H4 — El chatbot no filtra por nivel

El router extrae `ciudad`, `pais`, `zona`, `category`, `texto_libre` y `lugar_nombre`, pero **no hay campo de
nivel**. "Quiero lugares 100% sin gluten en Córdoba" trae los 8 más votados sin filtrar. Si ninguno de esos 8 es 100%,
el bot responde que no encontró o lista lugares con opciones, aunque existan lugares 100% en la ciudad (fuera del top 8).
Es exactamente la pregunta que el producto quiere responder bien.

### H5 — Una opinión pública puede contradecir la etiqueta

"La voz de la comunidad" publica recomendaciones positivas aprobadas a mano. Si alguien escribe "es 100% sin gluten"
sobre un lugar marcado "Tiene opciones sin TACC", la tarjeta contradice el mapa. La moderación depende de que el admin
lo note.

### H6 — Find Place sin control de nombre (ya documentado, sigue abierto)

Caso "Bienestar → víaSana" y los 5 negocios equivocados de "Serendipia". Sigue pendiente. Afecta la distinción
porque la evidencia de un negocio puede terminar pegada a otro.

### H7 — Cola sin salida y 100% pendientes sin herramienta

El flag `100% pendiente de confirmación del administrador` existe, pero para verlo hay que escribir una consulta.
Tampoco hay forma práctica de revisar los ~480 `needs_review` por tandas. `moderate_opinions.py` es el patrón que
funciona (lista → `--approve` → dry-run por defecto).

### H8 — Un reporte negativo anónimo saca un lugar del mapa (decisión, no bug)

La prueba en vivo del 2026-08-18 bajó la confianza de 0,95 a 0,52 y pasó el lugar a `needs_review` con un solo reporte.
Por salud es conservador y correcto, pero sin cuentas cualquiera puede ocultar un lugar competidor. Lo dejo como
decisión: ver el paso 7.

---

## Qué quitaría y qué agregaría

**Quitaría:**

- **Nada del núcleo.** Mantendría los tres niveles internos (`celiac_friendly` sigue siendo útil para ordenar y para el
  admin) con las dos etiquetas públicas.
- **El Web agent en su forma actual** (sigue desactivado desde junio por timeout). No lo reactivaría hasta hacer el
  paso 1: sin eso, su valor diferencial (la evidencia textual) se pierde igual.
- **El envío real de outreach**, mientras no se re-verifique el cableado arreglado el 2026-09-16. No es parte de esta
  auditoría: lo menciono para que no quede como "ya andando".

**Agregaría:**

1. Una columna de **evidencia persistente que el Validator lee y nunca pisa** (paso 1).
2. **"100% requiere evidencia explícita o confirmación del admin"** para todas las fuentes (paso 2).
3. Un **filtro de nivel en el chatbot** (paso 4).
4. En la ficha del lugar, **una línea que explique la etiqueta** ("En este lugar solo se cocinan y venden productos sin
   gluten" / "Tiene opciones; preguntá en el lugar cómo las preparan"). Hoy el glosario vive solo en el chatbot.
5. Un **script de revisión de la cola** para `needs_review` y los 100% pendientes (paso 6).

---

## Plan

Orden pensado para que cada paso se pueda desplegar solo. Los pasos 1–3 tocan la compuerta de salud: van con A/B contra
el modelo real (como `db/checks/validator_kitchen_ab.py`) y con registro en el Decisions Log, prompts.md y la sección
Core Prompt.

### Paso 0 — Medir antes de tocar (solo lectura, ~1 h)

Con `supabase db query --linked`:

```sql
-- Cuántos 100% aprobados hay, por fuente, y cuántos tienen evidencia que no sea el nombre
select source, count(*) filter (where safety_level='gluten_free_100') as cien,
       count(*) filter (where safety_level='gluten_free_100'
                         and not exists (select 1 from reviews r where r.place_id=p.id)) as cien_sin_resenas,
       count(*) as total
from places p where status='approved' group by source;

-- 100% pendientes del admin
select id, name, city from places where flags ? '100% pendiente de confirmación del administrador';

-- Lugares con override manual (los que H3 puede pisar)
select id, name, safety_level from places
where validation_notes ~* '(APROBACI[OÓ]N|CORRECCI[OÓ]N|OVERRIDE) MANUAL';
```

El resultado define el tamaño del paso 2b.

### Paso 1 — Evidencia persistente para el Validator (H1)

- **Esquema:** `places.evidence jsonb` (lista de `{source, text, url, added_at}`), con `add column if not exists`. RLS
  sin cambios. Como `places` es de lectura pública, **nunca guardar ahí datos de salud de terceros** (misma regla que
  `owner_celiac`).
- **Social:** guardar el título + snippet (recortado a ~400 caracteres) como `{source:'social'}`.
- **Web:** guardar `lead["evidence"]` + `source_url`.
- **Admin:** los `db/fixes/*.sql` escriben ahí la evidencia manual en vez de (o además de) `validation_notes`.
- **Validator:** `_build_user_prompt` agrega un bloque `evidencia_descubrimiento` (máx. 5 items, recortados).
  `update_place_validation` no toca `evidence`.
- **RUBRIC:** un párrafo que diga que ese bloque es evidencia citada de fuentes públicas: sirve para decidir el nivel,
  pero **no es verificación**, y el `approved` sigue exigiendo la misma confianza. Además, agregar la línea que CLAUDE.md
  ya dejó escrita como mitigación pendiente: **"no emitas un veredicto a partir de conocimiento previo del negocio ni
  de la interpretación del nombre: toda evidencia citada debe estar en el mensaje"** (cierra Enharinate y Serendipia).
- **Tests:** el prompt incluye el bloque; `update_place_validation` no lo pisa; Social y Web lo guardan.
- **A/B:** candidatos reales `needs_review` con evidencia social, antes y después. Métrica: cuántos pasan de
  `needs_review` a un veredicto, y que **ninguno** pase a 100% sin una frase de exclusividad.

### Paso 2 — 100% solo con evidencia explícita (H2)

**2a (código, determinista):** extender el tope A a todas las fuentes, con una salida:

- Si el modelo dice `gluten_free_100`, el código lo mantiene **solo si** el mensaje (reseñas o `evidence`) contiene una
  señal de exclusividad: una lista fija y normalizada sin acentos, por ejemplo "100% sin gluten", "100% sin tacc",
  "todo sin gluten", "exclusivamente sin gluten", "cocina exclusiva", "libre de gluten 100". **El nombre del lugar
  no cuenta.**
- Si no hay señal, se baja a `celiac_friendly` y se agrega el flag `100% pendiente de confirmación del administrador`
  (el mismo que ya existe).
- Las fuentes `manual` no pasan por el Validator. Sus overrides se protegen en el paso 3.

**2b (datos, una sola vez):** con el conteo del paso 0, pasar los 100% aprobados que no tengan señal explícita a
`celiac_friendly` con el flag de pendiente y una nota `CORRECCIÓN RETROACTIVA`. Mismo patrón que
`revalidate_low_confidence.py`: dry-run por defecto, salteando las filas con override manual. **Esto cambia lo que ve la
gente en el mapa** (esos lugares pasan a "opciones"): hay que revisar el listado antes de aplicarlo.

### Paso 3 — El reporte negativo respeta al admin y nunca sube el nivel (H3)

En `ReviewHandler.handle`:

- `safety_level = min(nivel_actual, nivel_nuevo)` según el orden `options_available < celiac_friendly < gluten_free_100`.
- Si `validation_notes` tiene un marcador manual (reusar `PROTECTED_NOTE_MARKERS` de `revalidate_low_confidence.py`, movido a un
  módulo común), **no reescribir las notas: anteponer** `RE-EVALUACIÓN POR REPORTE <fecha>: …` y conservar el resto.
- Tests: un reporte negativo nunca sube el nivel; un lugar con override conserva su nota.

### Paso 4 — Filtro de nivel en el chatbot (H4)

- Router: campo `nivel: "100" | null`, que se llena **solo** si la persona pide explícitamente lugares 100% /
  exclusivos / dedicados. "Sin TACC" a secas **no** activa el filtro. Hay que agregar ejemplos, el `<output_format>`, el
  parser y los tests del enum.
- `buildPlacesSearchUrl`: `safety_level=eq.gluten_free_100` cuando `nivel="100"`.
- Redactor: si `<datos>` viene vacío con ese filtro, decir "no encontré lugares 100% sin gluten para esa búsqueda" y
  ofrecer buscar lugares con opciones (sin afirmar que no existen).
- **Cambia los prompts:** hay que sincronizar las 4 copias (`scripts/sync_chat_prompts.py`), correr
  `chat_prompt_ab.py` y la batería de jailbreak, y **reinicia el conteo del soft-launch**.

### Paso 5 — Coherencia de opiniones y etiqueta (H5 + explicación en la ficha)

- `moderate_opinions.py`: al listar pendientes, marcar ⚠ cuando el texto tenga una señal de exclusividad (la misma
  lista del paso 2) y el lugar no sea `gluten_free_100`. El admin decide si la aprueba, la edita o usa la opinión como
  evidencia para revisar el nivel.
- Ficha del lugar (`js/map.js`): debajo del badge, la línea explicativa de cada nivel (ES + EN), con el mismo texto que el
  glosario del chatbot.

### Paso 6 — Herramienta de revisión del admin (H7)

`scripts/review_queue.py` (service_role, dry-run por defecto), con el patrón de `moderate_opinions.py`:

- `--pending-100`: lista los lugares con el flag, con su `evidence`, sus reseñas, `social_url` y las declaraciones de
  cocina.
- `--needs-review --city X --limit 15`: tandas por ciudad, con la misma información.
- `--approve ID [--level 100|options]` / `--discard ID`: escriben la nota `APROBACIÓN MANUAL` según la regla de
  overrides (sin inflar la confianza, `verified` sin tocar).

### Paso 7 — Decisiones del dueño (no las implementaría sin una respuesta)

1. **H8:** ¿un reporte negativo anónimo debe seguir sacando el lugar del mapa de inmediato? Alternativa: se queda
   publicado con un aviso, y pasa a `needs_review` solo si llegan 2 reportes negativos distintos en 30 días o si el
   reporte menciona contaminación o síntomas.
2. **H6:** ¿implementamos ya el control de similitud de nombres en `resolve_location` (propuesta: coincidencia de
   tokens ≥ 0,5; si no alcanza, se usa solo la dirección)?
3. **Web agent:** ¿se reactiva después del paso 1, con límites de latencia?

---

## Verificación de cada paso

- Python: `pytest -q`. Deno: `deno test supabase/functions/chat/`. Frontend: los tests de `tests/frontend_*`.
- Pasos 1 y 2: A/B contra el modelo real con N ≥ 16 casos. Compuerta: **0 lugares con 100% sin señal explícita** y sin
  regresiones en el caso de "evidencia fuerte sin declaraciones" (el caso que la iteración de cocina casi rompe).
- Paso 4: batería de jailbreak completa (37 turnos) más turnos "solo 100%" en vivo, revirtiendo contra la línea base.
- Cada cambio al RUBRIC o a los prompts del chat se registra en el Decisions Log, prompts.md y las copias sincronizadas.
