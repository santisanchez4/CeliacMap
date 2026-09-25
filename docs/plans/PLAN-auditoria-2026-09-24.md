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

## Estado (2026-09-24)

Implementado en la rama `claude/celiacmap-audit-agents-chatbot-0ohie6`. DNS revisado y migración aplicada el 2026-09-25; el resto **sin desplegar**: pasos 1, 2a, 2b (script),
3, 4, 5, 6, 7, 8 y 9, y el control de nombre (H6). Falta, en este orden: revisar los MX del dominio, aplicar
`db/migrations/2026-09-24-audit-plan.sql`, el A/B contra el modelo real (RUBRIC y prompts del chat), mergear y
desplegar `chat`, y correr `scripts/cap_unsupported_100.py` en modo prueba antes de `--apply`. El web agent sigue
apagado.

**2026-09-25 — limpieza de datos aplicada** (`db/fixes/2026-09-25-seed-and-data-quality.sql`, 42 filas, 8/8
verificaciones): los 13 lugares de ejemplo del seed (inventados, estaban en el mapa público) pasaron a `discarded`;
23 lugares argentinos con `country='Uruguay'` corregidos; ExpoCelíaca, Celi events y Asociación Celíaca Argentina
descartados (no son comercios); 5 ciudades mal cargadas. Los 100% aprobados pasaron de 313 a **306**, que es la
base del paso 2b. **Deuda conocida:** las 12 filas `discarded` con país equivocado no se corrigieron (no son
públicas; cada ciudad exige investigación). Detalle en CLAUDE.md → "Audit data-quality pass 2026-09-25".

**2026-09-25 — paso 2b, cambio de enfoque:** `cap_unsupported_100.py` ganó `--flag-only`: para los mismos lugares solo
agrega la marca `100% pendiente de confirmación del administrador` (nivel, status, confianza y notas intactos, un
`agent_log` por corrida). Motivo: `place_evidence` está vacía para lugares viejos y las reseñas de Google se borran a
los 30 días, así que bajar el nivel de 277 de 313 de golpe confundía "sin evidencia guardada" con "sin respaldo".
`review_queue.py` suma `--offset` (junto a `--limit` y `--city`) y `--discard` ahora también quita la marca, para que un
lugar decidido salga de `--pending-100`. Dry run de `--flag-only` sobre producción antes de la limpieza: 277 a marcar.
`--flag-only --apply` **todavía no se corrió**: es decisión del admin. Dry run tras la limpieza y la regla de marcas: de
306 lugares 100% aprobados, 12 protegidos por decisión manual + 23 con evidencia explícita + **271 a marcar** (víaSana
incluida).

**2026-09-25 — cierre de la pasada de datos:** (1) `resolve_location` ya no toma como buena una dirección de Find Place
fuera de Uruguay/Argentina (`GooglePlacesClient.is_foreign_address`): el país caía al de la búsqueda (caso *Goût Gluten
Free*, Vitacura); ahora cae al geocode de solo dirección. Las 2 filas chilenas de `needs_review` se corrigieron con
`db/fixes/2026-09-25-chile-out-of-scope.sql` (precedente Brasil). (2) Regla de marcas: un encabezado `CORRECCIÓN MANUAL` que
es solo una corrección de datos (`DATA_CORRECTION_PHRASES` en `agents/manual_overrides.py`) ya no cuenta como decisión de
seguridad; los 12 lugares 100% con decisión manual real siguen protegidos. (3) Deuda conocida: las 12 filas descartadas con
país equivocado y el parser que devuelve la ciudad `Departamento de X` (4 filas, no públicas).

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
| H8 | Un solo reporte negativo anónimo saca un lugar del mapa | Decidido: aviso con 1, salida con el umbral | `review_handler.py`, `js/map.js` |

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

### H8 — Un reporte negativo anónimo saca un lugar del mapa

La prueba en vivo del 2026-08-18 bajó la confianza de 0,95 a 0,52 y pasó el lugar a `needs_review` con un solo reporte.
Sin cuentas, cualquiera puede ocultar un lugar competidor. **Decidido el 2026-09-24** (ver el paso 7): con un reporte,
el lugar queda en el mapa con un pin de aviso; a partir del umbral de reportes en 30 días, sale del mapa.

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
- **El nombre no cuenta ni a favor ni en contra.** Los Leños, Dalbertt y San Felipa son 100% y su nombre no lo dice:
  llegan a 100% por lo que dicen su bio de Instagram, sus reseñas, un blog o un foro (evidencia del paso 1), o por
  confirmación del admin. Un "Sin Gluten X" sin esa evidencia queda en "opciones" con el flag de pendiente.
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

### Paso 7 — Reportes negativos: aviso en el mapa y salida por umbral (H8, decidido 2026-09-24)

**Regla del dueño:**

- **1 reporte negativo** en los últimos 30 días: el lugar **sigue en el mapa** con un pin distinto (rojo/ámbar) y el
  aviso "Reportado por la comunidad — consultá en el lugar antes de ir".
- **Con 3 reportes distintos** en 30 días (`REPORTS_TO_HIDE = 3`, confirmado): pasa a `needs_review` y sale del mapa
  hasta que el admin lo revise. Queda como constante para poder cambiarlo sin tocar la lógica.
- Si pasan 30 días sin reportes nuevos, el aviso se apaga solo. El admin también puede apagarlo antes.

**Cambios:**

- **Esquema:** `places.community_warning_at timestamptz` (null = sin aviso). Es público, pero no es un dato de salud de
  nadie: solo dice que hubo un reporte. **El texto del reporte nunca se publica** (no está verificado y puede ser
  difamatorio). `place_reports.reporter_token text`, generado en el navegador como el `voter_token` del ranking, para
  contar reportes "distintos". Es una defensa débil (se borra con el localStorage), igual que en los votos: lo
  complementa el umbral + la revisión del admin.
- **`review_handler.py`:** deja de mover el lugar con cada reporte. Cuenta los reportes negativos distintos de los
  últimos 30 días del lugar: con 1, marca `community_warning_at` y **no** cambia `status`; con el umbral, `status =
  'needs_review'` con una nota antepuesta (se aplica el paso 3). La re-evaluación de Sonnet se mantiene como evidencia
  para el admin (flags + recomendación), pero no decide la salida del mapa.
- **Excepción por contaminación (confirmada):** si el reporte describe contaminación o síntomas y la re-evaluación del
  Validator lo considera creíble (veredicto `rejected`, o `needs_review` con un flag de contaminación), el lugar sale del
  mapa con el primer reporte. Para que esto sea verificable, la re-evaluación devuelve un campo booleano
  `reporte_contaminacion_creible` (cambio al prompt del reporte, no al RUBRIC general), y el código decide con ese campo,
  no con el texto libre.
- **Frontend (`js/map.js`, `css/styles.css`):** clase de marcador `cm-marker--warning`, badge y texto en la ficha,
  entrada en la leyenda, ES + EN. `community_warning_at` va en el `select` del mapa y del ranking. Un lugar con aviso
  no debería aparecer en el Top 3.
- **Chatbot:** agregar `community_warning` a los campos que ve el redactor, con una instrucción: "si viene, avisá que
  la comunidad lo reportó recientemente y que conviene consultar en el lugar". Cambia el prompt, así que reinicia el
  soft-launch (conviene hacerlo junto con el paso 4).
- **`scripts/review_queue.py` (paso 6):** `--warnings` lista los avisos activos con el texto de los reportes (solo
  para el admin), y `--clear-warning ID`.
- **Tests:** 1 reporte → aviso y status sin cambios; N reportes del mismo token cuentan como 1; umbral → `needs_review`;
  aviso vencido → no se muestra; el texto del reporte nunca aparece en el `select` público.

**Otras decisiones abiertas:**

1. **H6:** implementar el control de nombre en `resolve_location`. No tiene que ver con que el nombre diga "sin
   gluten": es comprobar que el negocio que devuelve Google es el que buscamos (ver la respuesta en el chat del
   2026-09-24). Propuesta: coincidencia de palabras entre el nombre buscado y el devuelto ≥ 0,5; si no alcanza, se
   usa solo la dirección.
2. **Web agent:** reactivarlo después del paso 1, con límites de latencia.

### Paso 8 — Que "¿Conocés un lugar? Agregalo" recorra el mismo camino que la carga manual

**El caso que hay que reproducir:** Bienestar Gluten Free (Fray Bentos) no tenía ficha de Google. El admin conocía el
negocio y su dirección: se geocodificó solo la dirección, se cargó el lugar y el admin lo aprobó con una nota de override.

**Qué pasa hoy con el formulario** (`agents/suggestion_agent.py` → `resolve_location`):

| Situación | Hoy | Problema |
|-----------|-----|----------|
| El negocio tiene ficha en Google | Find Place → `pending` → Validator | Funciona |
| No tiene ficha, la dirección se geocodifica | `address_only` → `pending` → Validator → casi siempre `needs_review` | Queda invisible y nadie lo revisa (H7) |
| Find Place devuelve **otro** negocio | Se carga el negocio equivocado (caso víaSana) | H6 |
| La dirección no se geocodifica ("JC 23", Lo de Flor) | `suggestions.status='rejected'`, sin aviso | Se pierde en silencio |
| La descripción y el link que escribió la persona | `notes` va a `validation_notes` (el Validator no lo lee y lo pisa); el link va a `social_url` (no lo lee) | H1 |
| Tiempos | El promotor corre **una vez por mes** | Una sugerencia puede tardar hasta 30 días en llegar al Validator |

**Cambios** (se apoyan en los pasos 1, 6 y H6):

1. **Control de nombre (H6):** si Find Place devuelve un negocio con otro nombre, se ignora y se usa solo la dirección.
   Es exactamente lo que se hizo a mano con Bienestar.
2. **Dirección que no se geocodifica → cola del admin, no rechazo.** Nuevo estado `suggestions.status='needs_location'`.
   El admin la ve en `review_queue.py --suggestions`, corrige la dirección o carga las coordenadas a mano (como con Lo de
   Flor o con el catastro de Ta Bacana), y la promueve con un comando.
3. **Lo que escribió la persona llega al Validator:** `notes` y `evidence_url` se guardan en `places.evidence` (paso 1)
   como `{source:'user'}`. Siguen siendo evidencia de la comunidad, no verificada: el tope A (una sugerencia nunca sale
   como 100% sin el admin) se mantiene.
4. **La aprobación final de un lugar sin ficha de Google la da el admin, con un comando.**
   `review_queue.py --suggestions` muestra juntos la sugerencia, las declaraciones de cocina, el link, el veredicto del
   Validator y un link a Google Maps de las coordenadas. `--approve ID --level 100|options` escribe la nota
   `APROBACIÓN MANUAL`, igual que con Bienestar. **No se publica solo:** un formulario anónimo no tiene el conocimiento
   directo que tenía el admin, y sin revisión cualquiera podría cargar un lugar falso con etiqueta de 100%.
5. **Más rápido:** un workflow semanal liviano (`suggestions-weekly.yml`) que corre solo el promotor + el Validator
   sobre las sugerencias nuevas. Necesita el secreto de Google además de Supabase y Anthropic, y tiene un tope de
   llamadas bajo.
6. **Aviso al visitante:** el mensaje de éxito del formulario ya dice que la sugerencia se revisa antes de publicarse.
   Agregar el plazo esperado ("en general, en una semana").

**Tests:** una sugerencia con Find Place equivocado termina en `address_only`; una dirección que no se geocodifica
queda en `needs_location` (no en `rejected`); `notes` y `evidence_url` aparecen en el prompt del Validator; `--approve`
escribe la nota de override sin tocar `validation_confidence`.

### Paso 9 — Avisos por email al admin (santiagosanchez@celiacmap.org)

**Objetivo:** enterarse de todo lo que hace la gente y de lo que dejan los agentes para revisar, sin entrar a Supabase.
Se envía con Resend (ya configurado, dominio `celiacmap.org` verificado) al buzón de Zoho.

**Dos canales**, para no llenar el buzón:

| Canal | Cuándo | Qué incluye |
|-------|--------|-------------|
| **Aviso inmediato** (un email por evento) | Solo lo urgente | Reporte negativo (sobre todo si describe contaminación o síntomas); lugar que salió del mapa por reportes (paso 7); respuesta de un comercio al outreach |
| **Resumen diario** (un email, solo si hay algo) | Todos los días, ~08:45 (Uruguay) | Todo lo demás, agrupado |

**Contenido del resumen diario** (últimas 24 h, más lo que sigue pendiente):

- Formulario "Agregalo" y chatbot: sugerencias nuevas, con nombre, ciudad, dirección, nota, link y respuestas de cocina.
- Sugerencias sin ubicar (`needs_location`, paso 8).
- Recomendaciones positivas esperando moderación (`moderate_opinions.py`), con el texto completo y el aviso ⚠ del paso 5.
- Reportes negativos del día y avisos activos en el mapa.
- Resultado del Validator: nuevos `needs_review` y nuevos "100% pendiente de confirmación".
- Errores de los agentes (filas `agent_log` con `status='error'`) y el resumen del pipeline si corrió.
- Chatbot: **solo conteos** (turnos, turnos marcados, disparos del guardián de celiaquía). El texto de los turnos no va
  por email: la retención de 30 días del chatbot no alcanza a un buzón externo.
- Cada ítem trae el comando para resolverlo (`review_queue.py --approve …`, `moderate_opinions.py --approve …`) y el link
  al lugar en el mapa.

**Implementación:**

- `scripts/admin_digest.py`: consulta con service_role, arma el email en texto plano + HTML simple y lo envía con
  `ResendClient`. `--dry-run` imprime el email sin enviarlo. No envía nada si no hay novedades.
- `.github/workflows/admin-digest.yml`: cron diario `45 11 * * *` (UTC) + `workflow_dispatch`. Secretos que ya existen
  (`SUPABASE_*`, `RESEND_API_KEY`) más `ADMIN_EMAIL` (nuevo).
- Aviso inmediato: una Edge Function `notify-admin`, disparada por un Database Webhook en `INSERT` de `place_reports`
  (tipo `negative`), con el mismo secreto compartido que `place-report-created`. La salida del mapa y la respuesta de un
  comercio se avisan desde el código Python que ya maneja esos eventos (`review_handler.py`,
  `outreach_reply_handler.py`), con un `notify_admin()` común.
- Remitente: `avisos@celiacmap.org`. Asunto con prefijo fijo (`[CeliacMap] Resumen del día`, `[CeliacMap] URGENTE: …`)
  para armar un filtro en Zoho.
- Anti-flood: el aviso inmediato tiene un tope por hora. Si se supera, el resto va al resumen diario. Así un bot que
  llena el formulario no inunda el buzón.
- Privacidad: el email lleva el dato "dueño celíaco" de una sugerencia porque es para la revisión del admin, pero nunca
  va a un canal público. No lleva el texto de los turnos del chatbot.

**DNS revisado el 2026-09-25 (captura de Cloudflare):**

- MX de `celiacmap.org` → solo Zoho (`mx`, `mx2`, `mx3.zoho.com`). No hay conflicto: el buzón del admin recibe bien.
- Resend **recibe** en `reply.celiacmap.org` (MX → `inbound-smtp.sa-east-1.amazonaws.com`) y **envía** con
  `celiacmap.org` y `reply.celiacmap.org` (DKIM `resend._domainkey` en los dos, SPF y MX de rebote en `send.*`).
- SPF raíz `include:zohomail.com`: correcto. Resend no lo necesita, porque su SPF va en `send.celiacmap.org`
  (dominio de rebote) y alinea con DMARC en modo relajado. DKIM de Zoho (`zmail._domainkey`) presente.
- **Error encontrado:** `agents-monthly.yml` tenía `OUTREACH_INBOUND_DOMAIN: celiacmap.org`, así que el Reply-To
  de cada email de outreach era `outreach+<id>@celiacmap.org`, que va a **Zoho** y no a Resend: una respuesta de
  un comercio nunca llegaba al webhook. Corregido a `reply.celiacmap.org` (el webhook ya acepta cualquier
  dominio). La respuesta que pudiera haber mandado Niter (2026-09-01) habría ido a Zoho.
- Sin identificar: `rsend.reply` CNAME → `send.forge.rmta.net` (no es un registro de Resend ni de Zoho).
- Pendiente opcional: DMARC está en `p=none`; con Zoho y Resend firmando DKIM se puede pasar a `p=quarantine`
  más adelante.

**Antes de implementar — verificar el DNS del correo** (hecho, ver arriba). En agosto se configuró Resend para **recibir** mail en
`celiacmap.org` (las respuestas al outreach llegan a `outreach+<id>@celiacmap.org`), y el buzón de Zoho usa el mismo
dominio. Si los dos tienen registros MX en `celiacmap.org`, el mail entrante se reparte entre Resend y Zoho según la
prioridad, y se pierden las respuestas al outreach o los emails del buzón. Hay que mirar los MX en el panel del DNS. Si
están los dos, mover la recepción de Resend a un subdominio (por ejemplo `respuestas.celiacmap.org`) y cambiar
`OUTREACH_INBOUND_DOMAIN`. El envío (SPF/DKIM) no tiene conflicto; el SPF tiene que incluir a los dos
(`include:zoho.com` y el de Resend).

**Tests:** el resumen agrupa bien y no se envía vacío; `--dry-run` no llama a Resend; el texto del chatbot nunca aparece;
el tope por hora desvía al resumen.

---

## Verificación de cada paso

- Python: `pytest -q`. Deno: `deno test supabase/functions/chat/`. Frontend: los tests de `tests/frontend_*`.
- Pasos 1 y 2: A/B contra el modelo real con N ≥ 16 casos. Compuerta: **0 lugares con 100% sin señal explícita** y sin
  regresiones en el caso de "evidencia fuerte sin declaraciones" (el caso que la iteración de cocina casi rompe).
- Paso 4: batería de jailbreak completa (37 turnos) más turnos "solo 100%" en vivo, revirtiendo contra la línea base.
- Cada cambio al RUBRIC o a los prompts del chat se registra en el Decisions Log, prompts.md y las copias sincronizadas.
