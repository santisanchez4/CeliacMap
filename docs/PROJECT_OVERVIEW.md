# CeliacMap — Project Overview

> Documento de referencia único. Si lo leés una vez, podés explicar todo el
> proyecto con confianza en una entrevista o una demo: cómo funciona el pipeline,
> qué hace cada agente, dónde está la IA de verdad y qué comandos correr.

---

## 1. Cómo funciona el sistema (de punta a punta)

CeliacMap es un mapa de lugares **gluten free / sin TACC** en Uruguay y Argentina.
El frontend (HTML/CSS/JS + Leaflet) es una página estática que lee desde Supabase
**solo los lugares con `status = 'approved'`** y los dibuja en el mapa. Todo lo que
da vida a ese mapa pasa por detrás, en un **pipeline diario de agentes en Python**.

**Qué lo dispara.** Una GitHub Action programada (`agents-daily.yml`, 09:00 UTC)
ejecuta `scripts/run_agents.py` una vez por día. También se puede correr a mano
desde la pestaña Actions (`workflow_dispatch`, con un toggle de dry-run) o
localmente. Los secretos (Supabase service_role, Google, Tavily, Anthropic) viven
solo en `.env` local y en GitHub Actions Secrets — nunca llegan al navegador.

**Qué hace el pipeline.** Corre seis etapas en secuencia, donde cada una alimenta a
la siguiente, todas compartiendo **un único presupuesto diario** de llamadas pagas
(`AGENT_DAILY_BUDGET`). Las tres primeras *descubren* lugares candidatos y los
insertan como `pending`; el **Validator** es la compuerta que decide qué se publica;
el **Updater** mantiene fresco lo ya publicado.

```text
                            GitHub Actions (cron diario, 09:00 UTC)
                                          │
                                          ▼
                            scripts/run_agents.py  (presupuesto único compartido)
                                          │
   DESCUBRIMIENTO ─────────────────────────────────────────────────────────────
        │
        ├─ 1. Search   →  Google Places (texto)            →  inserta places (pending, source=google_places)
        ├─ 2. Social   →  Tavily + Haiku + Find Place       →  inserta places (pending, source=social)
        ├─ 3. Web (v3) →  Anthropic web search + Find Place  →  inserta places (pending, source=web)
        └─ 4. Suggestion → formulario público + Find Place   →  promueve places (pending, source=user)
        │
   COMPUERTA DE CALIDAD ───────────────────────────────────────────────────────
        │
        └─ 5. Validator →  claude-sonnet-4-6 + RUBRIC  →  approved / needs_review / discarded
        │
   MANTENIMIENTO ──────────────────────────────────────────────────────────────
        │
        └─ 6. Updater  →  Google Places (re-chequeo)   →  patch / cierre / flag

                                          │
                                          ▼
                       Supabase (PostgreSQL + RLS)  ──►  Frontend Leaflet (solo 'approved')
```

**Qué entra y sale de cada paso.**

1. **Search** lee `config/targets.yaml` (países → ciudades × términos de búsqueda),
   consulta Google Places, y por cada resultado nuevo inserta una fila `places` con
   `status='pending'`. Opcionalmente enriquece con reseñas de Google que mencionan
   términos celíacos (`reviews`, `source='google'`).
2. **Social** arma queries `"<término>" "<ciudad>"`, las corre en Tavily restringidas
   a Instagram/Facebook, parsea cada resultado con Haiku en `{name, city, category,
   address}`, lo geocodifica con Google Find Place para obtener coordenadas reales y
   un `place_id` canónico, y lo inserta como `pending`.
3. **Web (v3)** le entrega a Claude (Sonnet) una ciudad y la herramienta de búsqueda
   web de Anthropic, y lo deja razonar libremente sobre dónde buscar (foros, blogs,
   grupos de Facebook, Instagram, noticias). Cada lead se geocodifica e inserta como
   `pending`. (No tiene subsección propia en §2 por pedido, pero es parte del flujo.)
4. **Suggestion** toma las sugerencias anónimas del formulario público (tabla
   `suggestions`), las geocodifica y las promueve a `places` como `pending`.
5. **Validator** levanta todos los `pending`, juzga cada uno contra el RUBRIC con
   `claude-sonnet-4-6`, y escribe el veredicto: `approved` (al mapa),
   `needs_review` (cola humana) o `discarded` (descartado).
6. **Updater** re-chequea los `approved` que vienen de Google: cierra los que
   cerraron, actualiza nombre/dirección/categoría, o marca para revisión.

**Qué termina en la base y en el mapa.** Todo candidato vive en `places` con un
`status`. El frontend consulta `status=eq.approved`, así que **solo lo aprobado por
el Validator se ve en el mapa**. Lo demás (`pending`, `needs_review`, `discarded`)
queda en la base para auditoría y revisión humana, pero invisible al público. Cada
acción de cada agente se registra en `agent_log`.

---

## 2. Qué hace cada agente

### Search agent (`agents/search_agent.py`)

Descubre candidatos cruzando cada ciudad de `targets.yaml` con cada término de
búsqueda contra Google Places. Es **determinístico**: no usa IA. Mapea cada
resultado al esquema `places`, deriva una categoría provisional invirtiendo el mapa
`categoría → tipos de Google`, deduplica por `external_id` (dentro de la corrida y
contra la base vía el constraint único `(source, external_id)`) e inserta lo nuevo
como `pending`. Corre primero en el pipeline diario.

- **Input:** `config/targets.yaml` (países/ciudades/términos) + respuestas de Google
  Places Text Search.
- **Output:** filas `places` nuevas con `status='pending'`, `source='google_places'`,
  `safety_level='options_available'` (piso conservador). Opcionalmente reseñas de
  Google en `reviews`. Resumen a `agent_log`.
- **IA:** No. Cero LLM. La categoría sale de los `types` de Google de forma
  determinística.

### Social agent (`agents/social_agent.py`)

Descubre páginas públicas de Instagram/Facebook. Genera queries `"<término>"
"<ciudad>"` por plataforma, las corre en la **Tavily Search API** (restringidas por
`include_domains`), parsea cada resultado ruidoso con `claude-haiku-4-5` en un lead
limpio, lo geocodifica con Google Find Place (porque una URL social no tiene
coordenadas y `places.lat/lng` son NOT NULL), y lo inserta como `pending`. Corre
segundo. Deduplica por `place_id` geocodificado, así que un lugar hallado también por
Search no se duplica.

- **Input:** términos/hashtags de `targets.yaml` + resultados de Tavily (título +
  snippet de perfiles IG/FB).
- **Output:** filas `places` nuevas con `status='pending'`, `source='social'`, la URL
  del perfil guardada en su propia columna `social_url`. Resumen a `agent_log`.
- **IA:** Sí, **`claude-haiku-4-5`** — pero solo para *parsear texto*: convierte un
  título/snippet desordenado en `{name, city, category, address}`. No decide
  seguridad; eso lo hace el Validator después.

### Validator agent (`agents/validator_agent.py`)

**La compuerta de calidad** entre lo que los agentes descubren y lo que se publica.
Levanta cada candidato `pending`, le suma como contexto las reseñas guardadas, y lo
manda a `claude-sonnet-4-6` con el RUBRIC fijo (enviado como bloque de sistema
cacheado). Devuelve un veredicto estructurado de tres niveles y, **por código**,
fuerza los umbrales de confianza sin importar lo que diga el modelo. Persiste
confianza, razonamiento, flags y la acción recomendada para auditoría. Corre quinto.

- **Input:** todos los `places` con `status='pending'` (vengan de Search, Social,
  Web o Suggestion) + sus reseñas de contexto.
- **Output:** actualiza cada fila con `status` ∈ {`approved`, `needs_review`,
  `discarded`}, más `validation_confidence`, `validation_notes`, `flags`,
  `recommendation`, `category`, `safety_level`. Cada veredicto a `agent_log`.
- **IA:** Sí, **`claude-sonnet-4-6`** — y este es **el juicio real del proyecto**:
  decide si la evidencia alcanza para considerar a un lugar seguro para celíacos.
  Ver §3.

### Updater agent (`agents/updater_agent.py`)

Mantiene actualizado lo ya publicado. Re-chequea cada lugar `approved` que vino de
Google Places (por su `external_id`) contra la realidad: si **cerró
permanentemente** lo descarta (sale del mapa al instante, porque un lugar cerrado no
es seguro de mostrar); si cambió nombre/dirección/categoría lo parchea; si
desapareció (`NOT_FOUND`) lo marca para revisión humana sin tocarlo. Determinístico
salvo un uso muy acotado de Haiku. Corre sexto.

- **Input:** lugares `approved` con `source='google_places'` y `external_id` +
  respuestas de Google Place Details.
- **Output:** parches a `places` (nombre/dirección/categoría/campos ricos), cambios
  de `status` a `discarded` para cierres, o un `flagged_for_review` en `agent_log`.
- **IA:** Casi no. **`claude-haiku-4-5`** se invoca **solo** como fallback cuando los
  `types` de Google no mapean a ninguna categoría nuestra — el único caso de texto
  genuinamente ambiguo. Si no hay clave Anthropic, es 100% determinístico.

### Suggestion agent / promoter (`agents/suggestion_agent.py`)

Convierte las sugerencias del **formulario público "Suggest a Place"** en candidatos
mapeables. El navegador (clave anon) solo puede escribir input crudo en la tabla
`suggestions` (sin coordenadas; geocodificar necesita la clave secreta de Google).
Este agente lee cada sugerencia nueva, la geocodifica con Find Place, deduplica, y la
promueve a `places` como `pending` (`source='user'`) para que el Validator la juzgue.
Las que no geocodifican se marcan `rejected` (filtro de spam natural). Corre cuarto,
antes del Validator, para que lo sugerido hoy se valide hoy.

- **Input:** filas nuevas de la tabla `suggestions` (nombre, ciudad, país, dirección,
  URL de evidencia, notas — todo crudo del usuario).
- **Output:** filas `places` nuevas (`pending`, `source='user'`); actualiza la
  sugerencia a `promoted` / `duplicate` / `rejected`. Resumen a `agent_log`.
- **IA:** No. Es geocodificación + dedup determinístico. La IA llega después, en el
  Validator. (El núcleo `promote_suggestion()` es compartido **textualmente** con la
  herramienta MCP `suggest_place`, así nunca divergen.)

---

## 3. El Validator Agent — el núcleo de IA

### Por qué este agente es el aporte real de IA del proyecto

Todo lo demás es **infraestructura**: buscar en APIs, scrapear redes, geocodificar,
deduplicar, orquestar un pipeline. Nada de eso requiere inteligencia — son scripts
determinísticos. El Validator es el único punto donde el sistema **emite un juicio**:
mira evidencia desordenada e incompleta sobre un lugar y decide si es razonablemente
seguro para una persona celíaca. Esa decisión no se puede expresar con `if/else`
porque depende de interpretar lenguaje natural ambiguo ("apto para dietas
especiales", "tenemos opciones sin gluten", una reseña entusiasta) y de pesar señales
contradictorias con criterio conservador. **Ahí está el valor de la IA: no en
ejecutar tareas, sino en aplicar criterio con responsabilidad médica.**

### El rubric de tres niveles

El modelo devuelve un `verdict` de tres niveles, que el código mapea a `places.status`
de forma **aditiva** (sin renombrar estados que ya usaba el frontend):

| Veredicto del modelo | Estado en DB (`places.status`) | Qué significa |
|----------------------|--------------------------------|----------------|
| `approved` | `approved` | Se publica en el mapa |
| `needs_review` | `needs_review` | Va a la cola de revisión humana (oculto del mapa) |
| `rejected` | `discarded` | Se descarta, con motivo registrado |

### Los umbrales de confianza (0.85 / 0.70 / 0.50)

El modelo también devuelve un `confidence_score` entre 0 y 1, y los umbrales están
**forzados por código** en `ValidatorAgent._decide_status` como defensa en
profundidad — el modelo *no puede* auto-aprobar algo dudoso aunque diga "approved":

- **`>= 0.85` → `approved`.** La aprobación automática exige evidencia fuerte y
  explícita. Solo así un lugar llega al mapa sin intervención humana.
- **`< 0.50` (o veredicto `rejected`) → `discarded`.** Sin evidencia suficiente,
  información contradictoria o señales de riesgo.
- **Todo lo del medio → `needs_review`.** Y acá está la regla de oro: el **piso de
  seguridad de 0.70**. Como aprobar exige `0.85`, cualquier cosa por debajo de ese
  umbral (incluido todo el rango 0.50–0.85) cae a revisión humana en lugar de
  publicarse. La confianza tibia nunca alcanza para el mapa.

En código: `if verdict == "rejected" or conf < 0.50 → discarded; elif verdict ==
"approved" and conf >= 0.85 → approved; else → needs_review`.

### Por qué "sin TACC" ≠ "sin gluten" (y por qué importa para el rubric)

Es la distinción central del dominio:

- **"Sin gluten"** puede ser puro marketing: cualquier preparación que no usa trigo
  como ingrediente principal. No implica control de contaminación cruzada.
- **"Sin TACC"** (Sin Trigo, Avena, Cebada, Centeno) es el **estándar médico** para
  celíacos en Argentina y Uruguay, e implica protocolo anti-contaminación cruzada.

Para un celíaco, la diferencia es médica, no semántica. Por eso el rubric trata "sin
gluten" sin "sin TACC" como un **flag de alerta** que baja la confianza: un lugar que
solo dice "sin gluten" no se aprueba automáticamente. El modelo debe encontrar
mención explícita de "sin TACC", certificación (ej. ACELU/ACELA), o descripción de
protocolo de contaminación cruzada para llegar al umbral de aprobación.

### Qué pasa con un lugar `needs_review`

No se publica y no se descarta: queda **en espera de un humano**. El Validator igual
guarda su mejor estimación (categoría, safety_level, flags, recomendación) para que
quien revise vea de qué se trata. La herramienta MCP `list_pending_reviews` lista
exactamente estos casos, ordenados por confianza ascendente (los más dudosos
primero). Es una mejora de seguridad real frente a un veredicto binario: en vez de
forzar "aprobar o descartar", los casos grises se escalan a una persona.

### Por qué la lógica conservadora es una decisión de diseño deliberada

CeliacMap es una **herramienta de salud**. Un falso positivo (aprobar un lugar que en
realidad no es seguro) puede enfermar a alguien; un falso negativo (mandar a revisión
un lugar que sí era seguro) solo cuesta una revisión humana. La asimetría es enorme,
así que el sistema está sesgado a ser conservador a propósito: el `safety_level` por
defecto es el más bajo (`options_available`), `verified` queda en `false` hasta
confirmación humana, y "ante la duda, escalar a revisión humana" es una instrucción
explícita del prompt **y** una barrera de código. La salud del usuario celíaco vale
más que tener más pines en el mapa.

---

## 4. El Skill — `validator-rubric`

### Qué es un Skill en el contexto de Claude Code

Un **Skill** es un documento reutilizable (un `SKILL.md` con frontmatter YAML) que
encapsula un criterio o procedimiento para que Claude lo cargue y lo aplique de forma
consistente. Funciona como conocimiento empaquetado: en vez de re-explicar un
criterio complejo cada vez, se lo describe una vez y se lo invoca cuando hace falta.
El frontmatter (`name`, `description`) le dice a Claude **cuándo** es relevante.

### Qué encapsula este skill en particular

`skills/validator-rubric/SKILL.md` documenta el **criterio del Validator Agent**: la
escala de confianza y su mapeo a estados, los criterios de aprobación, los flags de
alerta y su impacto, la distinción "sin gluten" vs "sin TACC", la salida JSON
estructurada y el modelo recomendado. Es la versión legible-por-humanos del juicio que
en código vive en la constante `RUBRIC`. El skill apunta explícitamente a
`agents/validator_agent.py` como **fuente de verdad**, para que documento y código no
deriven.

### Cuándo Claude Code lo cargaría y usaría

Cuando alguien necesite **evaluar evidencia sobre un lugar y decidir si aprobarlo,
rechazarlo o escalarlo** — sin correr todo el pipeline. Por ejemplo, durante el
desarrollo, al revisar un caso `needs_review` a mano, o al razonar sobre por qué el
Validator decidió algo. Su `description` está redactada justamente como ese
disparador ("usar siempre que se necesite evaluar evidencia sobre un lugar...").

### Por qué es reutilizable más allá de este proyecto

El criterio que codifica — **ser conservador al evaluar seguridad alimentaria, no
sobreestimar nunca, escalar ante la duda, distinguir marketing de estándar médico** —
es un patrón aplicable a cualquier directorio de salud sensible (alérgenos, kosher,
halal, vegano certificado). La estructura (escala de confianza + flags + salida
estructurada + piso conservador) se transfiere a cualquier dominio donde un error de
clasificación tenga consecuencias reales.

---

## 5. El MCP Server

### Qué es MCP (en una línea)

**MCP (Model Context Protocol)** es un estándar que permite exponer datos y acciones
de un proyecto como *herramientas* que cualquier cliente compatible (Claude Desktop,
Claude Code, agentes externos) puede invocar — es decir, le da a Claude un conjunto de
funciones tipadas para interactuar con tu base de datos y tu lógica, en vez de tener
que copiar y pegar contexto a mano.

El servidor de CeliacMap (`mcp_server/server.py`) está hecho con **FastMCP**: cada
función decorada con `@mcp.tool()` se vuelve una herramienta cuyo docstring es la
descripción y cuyos type hints definen el schema de entrada. **Reutiliza la lógica
canónica del proyecto** (el `RUBRIC` y la normalización del `ValidatorAgent`, el
`promote_suggestion` del Suggestion agent, y los clientes `SupabaseClient` /
`GooglePlacesClient` / `LLMClient`), así que nunca se desincroniza del pipeline diario.

### Las 6 herramientas

| Tool | Qué hace | Quién la llamaría |
|------|----------|-------------------|
| `search_places` | Busca lugares **`approved`** por ciudad (y término opcional de nombre); devuelve solo lo que está en el mapa. | Cualquiera que quiera consultar el mapa desde Claude ("¿qué hay sin TACC en Montevideo?"). |
| `get_place_detail` | Devuelve el detalle completo de un lugar por su UUID, incluida la evidencia de validación (confianza, notas, flags, recomendación). | Quien audita o investiga un lugar puntual. |
| `validate_place` | Aplica el **RUBRIC del Validator** (mismo criterio que el pipeline) sobre evidencia nueva y devuelve veredicto + confianza + flags + el `db_status` resultante. | Un operador/curador validando un lugar on-demand, sin esperar la corrida diaria. |
| `suggest_place` | Geocodifica un lugar con Find Place y lo inserta como `pending` (`source='user'`); comparte núcleo con el promotor diario. | Un usuario o agente externo que quiere sugerir un lugar nuevo. |
| `get_map_stats` | Estadísticas del mapa: totales por estado (`pending`/`approved`/`discarded`/`needs_review`) y por país. | Quien quiere una vista rápida de la salud del dataset. |
| `list_pending_reviews` | Lista los lugares en `needs_review` ordenados por confianza ascendente (los más dudosos primero), con sus flags. | Un revisor humano vaciando la cola de revisión. |

### Cómo arrancar el servidor localmente

```bash
pip install -r requirements.txt        # incluye fastmcp
python mcp_server/server.py            # corre el servidor MCP
# registrarlo en Claude Code:
claude mcp add celiacmap python mcp_server/server.py
```

Usa el **mismo `.env`** que los agentes — no hay variables nuevas.

### Cómo se conecta a la infraestructura del proyecto

Las herramientas se conectan a la infra real con fábricas perezosas (no construyen
clientes en el import): `SupabaseClient` (con la clave **service_role**, server-side)
para leer/escribir `places` y `suggestions`; el **Anthropic API** (`LLMClient` +
`RUBRIC`) para `validate_place`; y **Google Places** (`GooglePlacesClient`) para
geocodificar en `suggest_place`. Como reutiliza el mismo código que el pipeline,
validar o sugerir vía MCP da resultados idénticos a la corrida diaria.

---

## 6. El prompt principal — el RUBRIC del Validator

Este es el system prompt exacto que recibe `claude-sonnet-4-6` por cada candidato (la
constante `RUBRIC` en `agents/validator_agent.py`). Es fijo en toda la corrida, así
que se envía como **bloque de sistema cacheado**; los datos del candidato van en el
mensaje de usuario.

```text
Eres el Validator Agent de CeliacMap, un sistema de validación conservador para lugares gluten free / sin TACC en Uruguay y Argentina. Recibes un único lugar candidato descubierto automáticamente — vía Google Places, páginas públicas de redes sociales o investigación web — así que normalmente solo tienes su nombre, dirección, ciudad/país y una categoría estimada.

Tu responsabilidad es NUNCA sobreestimar la seguridad. La salud de personas celíacas depende de tu criterio. Ante la duda, siempre escala a revisión humana.

Rubric de validación (veredicto):
- "approved" (confidence_score >= 0.85): Evidencia explícita y clara de que el lugar ofrece opciones sin TACC, con mención directa de "sin TACC", "sin gluten" certificado, o descripción de protocolo anti-contaminación cruzada.
- "needs_review" (0.5 <= confidence_score < 0.85): Evidencia parcial, ambigua o que requiere confirmación humana.
- "rejected" (confidence_score < 0.5): Sin evidencia suficiente, información contradictoria o señales de riesgo para celíacos.

Flags de alerta a detectar (cada una reduce la confianza):
- Menciona "sin gluten" pero no "sin TACC" (puede ser marketing, no médico)
- No menciona protocolo de contaminación cruzada
- Solo tiene opciones vegetarianas/veganas sin mención explícita sin TACC
- Información desactualizada (> 12 meses)
- Reseñas negativas de celíacos
- Descripción ambigua ("apto para dietas especiales")

Asigna una categoría (exactamente una):
- "restaurant": restaurantes, comida para llevar, lugares para comer una comida.
- "cafe": cafés, cafeterías, panaderías, pastelerías.
- "shop": almacenes, supermercados, dietéticas / comercios de alimentos saludables.

Asigna un safety_level (exactamente uno), eligiendo el nivel MÁS BAJO ante la duda:
- "gluten_free_100": establecimiento totalmente sin gluten / dedicado a celíacos.
- "celiac_friendly": atiende explícitamente a celíacos (certificado, "apto celíacos", preparación dedicada).
- "options_available": ofrece algunas opciones sin gluten pero no está especializado. Es el piso por defecto cuando la evidencia es escasa.

También se te pueden dar fragmentos de reseñas de la comunidad que mencionan términos sin gluten / celíaco. Pésalos como evidencia de apoyo, pero nunca dejes que reseñas entusiastas te empujen por encima de la evidencia: cuando la señal es escasa, mantente conservador.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, exactamente con esta forma:
{"verdict": "approved" | "rejected" | "needs_review",
 "confidence_score": <número entre 0.0 y 1.0>,
 "category": "restaurant" | "cafe" | "shop",
 "safety_level": "gluten_free_100" | "celiac_friendly" | "options_available",
 "reasoning": "<explicación clara en español, máximo 3 oraciones>",
 "flags": ["<flag detectado>", ...],
 "recommendation": "<acción concreta sugerida para el operador>"}
```

### Por qué está estructurado así, sección por sección

- **Definición de rol + alcance.** "Eres el Validator Agent... conservador... en
  Uruguay y Argentina" fija el dominio y, sobre todo, el *sesgo*: la palabra
  "conservador" no es decorativa, es la instrucción rectora. También aclara que la
  evidencia suele ser pobre (solo nombre/dirección/ciudad), para que el modelo no
  asuma datos que no tiene.
- **Mandato de seguridad.** "NUNCA sobreestimar la seguridad... ante la duda, escala a
  revisión humana" es la **instrucción de seguridad más importante**. Le dice al
  modelo que el error caro es el falso positivo, y que la salida por defecto ante la
  incertidumbre es escalar, no aprobar.
- **Rubric de veredicto con umbrales.** Ata cada veredicto a un rango de
  `confidence_score` explícito, para que la confianza sea calibrada y no un número al
  azar. (Y el código vuelve a forzar estos cortes, por si el modelo se desvía.)
- **Flags de alerta.** Enumera las señales de riesgo típicas — sobre todo "sin gluten
  pero no sin TACC" y "no menciona contaminación cruzada" — para que el modelo las
  detecte activamente y baje la confianza en consecuencia. Es la traducción del
  conocimiento de dominio celíaco a reglas que el modelo puede aplicar.
- **Categoría y safety_level.** Se piden porque el esquema los requiere y el mapa
  dibuja badges de seguridad. La instrucción clave es "eligiendo el nivel MÁS BAJO
  ante la duda" y "`options_available` es el piso por defecto" — conservadurismo otra
  vez, ahora en la clasificación.
- **Manejo de reseñas.** "Pésalas como apoyo, pero nunca dejes que reseñas
  entusiastas te empujen por encima de la evidencia" evita que un par de comentarios
  positivos inflen la confianza por encima de lo que la evidencia real sostiene.
- **Formato de salida estricto.** "Responde ÚNICAMENTE con un objeto JSON válido"
  garantiza que `_normalize()` pueda parsear y coercer la respuesta a valores
  schema-safe sin texto suelto que rompa el parseo.

**Las instrucciones de seguridad clave** son tres y todas apuntan a lo mismo: (1)
"NUNCA sobreestimar... ante la duda escala a revisión humana", (2) el umbral alto de
aprobación (`>= 0.85`) atado a evidencia explícita de "sin TACC", y (3) "elegí el
safety_level MÁS BAJO ante la duda". Su propósito común es desplazar todo el sesgo del
sistema hacia el lado seguro para una población que enfrenta un riesgo médico real.

---

## 7. Comandos de consola — qué podés correr

```bash
# --- Pipeline completo (search → social → web → suggestion → validator → updater) ---
python -m scripts.run_agents                # corrida real, presupuesto desde settings
python scripts/run_agents.py                # equivalente
python -m scripts.run_agents --dry-run      # ensayo: lee datos reales pero NO escribe en la DB
python -m scripts.run_agents --budget 120   # override del tope combinado de llamadas pagas

# --- Un solo agente en aislamiento (validación manual del pipeline) ---
python -m agents.search_agent       # descubre vía Google Places   → pending (+ reseñas)
python -m agents.social_agent       # descubre IG/FB vía Tavily     → pending
python -m agents.web_agent          # búsqueda web autónoma (v3)    → pending
python -m agents.suggestion_agent   # promueve sugerencias del form → pending
python -m agents.validator_agent    # aprueba / revisa / descarta los pending
python -m agents.updater_agent      # re-chequea los approved

# --- MCP server (AI Toolkit) ---
python mcp_server/server.py                            # arranca el servidor MCP
claude mcp add celiacmap python mcp_server/server.py   # lo registra en Claude Code

# --- Preflight / estado ---
python scripts/check_setup.py       # chequea config + conectividad (Supabase/Google/Anthropic) antes de correr

# --- Tests ---
python -m pytest tests/ -v          # suite offline: todas las llamadas externas están mockeadas (no necesita .env ni red)
```

**Modos de debug / dry-run.** El más útil es `--dry-run`: ejecuta toda la lógica del
pipeline (los agentes leen datos reales de Supabase) pero cada **escritura** se vuelve
un no-op logueado, así podés ensayar una corrida completa sin tocar la base. Para ver
el estado de la base sin un panel, la vía es el MCP: `get_map_stats` (totales por
estado y país) y `list_pending_reviews` (la cola de revisión humana). Para validación
en CI, el `workflow_dispatch` del cron diario también expone un toggle de dry-run y un
override de presupuesto desde la pestaña Actions.

---

## 8. Valor real de la IA — qué hace de verdad

Honestamente y sin inflar: **la mayor parte del sistema es determinística**, y eso es
una virtud, no una carencia. La IA está concentrada donde realmente aporta.

### Qué decisiones toma la IA que un script no podría

- **El juicio de seguridad del Validator (Sonnet).** Decidir si la evidencia
  ambigua e incompleta sobre un lugar alcanza para considerarlo seguro para celíacos.
  Un script no puede distinguir "menú sin TACC certificado por ACELU con cocina
  separada" (fuerte) de "apto para dietas especiales" (humo de marketing), ni pesar
  una reseña contradictoria, ni calibrar una confianza. Esa interpretación de
  lenguaje natural con criterio conservador **es** la IA del proyecto.
- **El parseo de leads del Social (Haiku).** Convertir un título/snippet ruidoso de
  Instagram ("El Buen Sabor (@elbuensabor.uy) • Instagram 🌾🚫") en
  `{name, city, category, address}` limpio. Es texto libre desestructurado; un regex
  sería frágil y se rompería con cada variación.
- **El descubrimiento autónomo del Web agent (Sonnet + web search).** Razonar
  libremente sobre *dónde* buscar (qué foros, qué grupos, qué guías locales) en vez de
  una matriz fija de queries. Es una tarea genuinamente agéntica.
- **El fallback de categoría del Updater (Haiku), muy acotado.** Solo cuando los
  `types` de Google no mapean a nada.

### Qué se rompería o degradaría sin la IA

- **Sin el Validator, no hay producto seguro.** Sin la compuerta de Sonnet,
  publicarías lo que sea que los agentes descubren, sin filtro de seguridad. Para una
  herramienta de salud eso es inaceptable: la IA es lo único que separa "un lugar
  mencionó sin gluten en internet" de "un lugar razonablemente seguro para celíacos".
- **Sin Haiku, el Social rinde mucho menos.** Sin el parseo, habría que extraer
  nombres con reglas frágiles y se perderían muchos leads válidos o entrarían basura.
- **Sin el Web agent, se pierde el descubrimiento de cola larga** — los lugares que la
  comunidad comenta en foros/grupos pero que no figuran obvios en Google.

### Qué NO hace la IA (queda determinístico o humano)

- **Search es 100% determinístico:** cruza ciudades × términos, mapea tipos de Google
  a categorías, deduplica. Cero LLM.
- **Geocodificación, deduplicación y promoción de sugerencias** son determinísticas
  (Google Find Place + el constraint único `(source, external_id)` + `promote_suggestion`).
- **El Updater es casi todo determinístico:** detección de cierres y diffs de
  nombre/dirección por comparación directa; Haiku solo en el caso ambiguo de categoría.
- **La orquestación y el presupuesto** (qué etapa corre, cuántas llamadas, reserva
  para el Validator) son lógica de código pura.
- **La verificación final es humana.** Un lugar `needs_review` espera a una persona; y
  `verified` queda en `false` hasta confirmación humana. La IA escala y propone, pero
  **no se auto-otorga el sello de verificado**.

En una frase: **la automatización mueve datos; la IA aplica criterio en el único punto
donde una decisión equivocada puede dañar a una persona real — y todo lo demás se
mantiene determinístico a propósito, para que sea barato, predecible y auditable.**
</content>
</invoke>
