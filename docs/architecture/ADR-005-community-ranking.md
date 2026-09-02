# ADR-005: Ranking comunitario de lugares — voto como orden, no como autoridad de seguridad

**Estado:** Aceptado

## Contexto

El mapa muestra hoy todos los lugares `approved` sin ninguna jerarquía
entre ellos: un lugar recién descubierto por un agente y uno que toda la
comunidad celíaca conoce y frecuenta se ven exactamente igual. No existe
ninguna forma de que la comunidad exprese "este lugar es de los mejores"
ni de que un usuario nuevo vea, de un vistazo, adónde va la gente.

El mensaje que originó este ADR propone un **ranking de lugares más
votados / recomendados por la comunidad**, filtrable por país
(Uruguay / Argentina), ubicado junto al mapa.

**Estado actual de la infraestructura (investigación previa, verificada
en producción read-only):**

- **No existe ninguna tabla de votos / likes.** `db/schema.sql` tiene
  `places`, `reviews`, `agent_log`, `suggestions`, `place_reports`,
  `outreach_messages` — nada más.
- **`place_reports` (ADR-004) no sirve como fuente de voto tal cual
  está.** Su `report_type` distingue `positive`/`negative`, pero un
  reporte `positive` **exige `description`** (`CHECK` 5–2000 caracteres):
  no hay camino para un "me gusta" sin texto. En producción `place_reports`
  tiene **1 sola fila** (el reporte negativo de prueba de la verificación
  de ADR-004, ya `processed`) y **cero reportes positivos**. No hay datos
  de voto comunitario de ningún tipo.
- **`places.rating` / `places.user_ratings_total` son 100% de Google
  Places** (confirmado por el comentario del schema y por los datos:
  285 de 588 lugares `approved` tienen `rating`, **todos**
  `source='google_places'`; el resto —social / web / user / manual— no
  tiene). La tabla `reviews` son 281 filas `google` + 4 `seed`, **cero
  `user`**. Todo es display-only, ninguna señal viene de la comunidad
  logueada (no hay auth).
- **Lugares `approved`: 588 total → Argentina 396, Uruguay 192.**
- **Componentes de frontend reusables:** el toggle `.chip` de
  `.map-chips` (`aria-pressed`, patrón de toggle ya en `js/map.js`), el
  grid de 2 columnas `.features-layout` (`1.15fr 0.85fr` ≥900px, columna
  derecha `sticky`, apila abajo), el lenguaje visual `.pp-*` del
  place-panel, `.pp-footer` (ya tiene el link "Reportar un error"), el
  sistema `data-i18n`, y el patrón de `fetch` con la anon key de
  `js/map.js` / `js/report.js`.

El riesgo central es el mismo que resolvieron ADR-002 (respuesta de
outreach) y ADR-004 (reportes comunitarios): una fuente externa sin
verificar —acá, un voto anónimo sin auth— no puede tener autoridad
directa sobre la seguridad que se le comunica a una persona celíaca.

## Decisión propuesta

**Principio rector (igual que ADR-002 y ADR-004):** el voto de la
comunidad **no tiene ninguna autoridad sobre `places.status`**. El
ranking se construye **estrictamente encima** de lugares que el Validator
ya aprobó — ordena *entre* lugares ya seguros, nunca vuelve seguro a un
lugar que no lo es, nunca lo saca de `needs_review`.

### 1. Mecanismo de voto: tabla nueva `place_votes`, no reusar `place_reports` positivo (2a)

Un voto = un click, sin texto. Reusar el reporte `positive` de ADR-004
obligaría a escribir `description` (5–2000 caracteres) para cada voto —
fricción incompatible con el propósito. `place_votes` es la **tercera
tabla intake anon-INSERT-only** del proyecto, misma forma que
`suggestions` y `place_reports`:

```sql
create table public.place_votes (
  id          uuid primary key default gen_random_uuid(),
  place_id    uuid not null references public.places(id) on delete cascade,
  voter_token text not null check (char_length(voter_token) between 8 and 64),
  source      text not null default 'community'
                check (source in ('community', 'seed')),
  created_at  timestamptz not null default now(),
  constraint place_votes_place_voter_key unique (place_id, voter_token)
);
```

El reporte `positive` de ADR-004 **sigue sin cambios** como el canal
**cualitativo** (una recomendación con una historia, evidencia para
revisión manual). v1 los mantiene desacoplados; un futuro "al recomendar
también suma un voto" queda fuera de alcance.

**Lectura del ranking: columna denormalizada `places.vote_count`**
mantenida por un trigger `AFTER INSERT OR DELETE` sobre `place_votes`. El
frontend lee el ranking por el **mismo path anon que ya existe**:

```
GET {SUPABASE_URL}/rest/v1/places
    ?select=id,name,city,country,category,safety_level,vote_count
    &status=eq.approved
    &country=eq.Argentina
    &order=vote_count.desc
    &limit=12
```

Cero grants nuevos, cero vista / RPC nueva, y `place_votes` queda 100%
cerrado a lectura para el público (igual que `suggestions` /
`place_reports` / `agent_log`). Consistente con las otras columnas
denormalizadas de `places` (`rating`, `user_ratings_total`,
`outreach_status`).

**Alternativas descartadas:**

- **Reusar `place_reports` positivo:** habría que relajar su RLS
  (`char_length(description) between 5 and 2000`) y repurposear su
  máquina de estados `new/dispatched/processing/...`, que no tiene
  ningún sentido para un voto — y tocar el contrato de un ADR ya
  aceptado.
- **Reusar `reviews`:** forma equivocada (escala 1–5 + texto +
  `user_id` orientado a auth); un voto no es una reseña.
- **Exponer `place_votes` a `SELECT` anon:** filtra `voter_token`,
  permite enumerar / verificar tokens de otros.
- **Vista o RPC nueva para el agregado:** primera superficie de ese
  tipo en el proyecto, innecesaria si un `count` denormalizado en
  `places` alcanza.

### 2. Anti-abuso: en capas, sin dependencia nueva, mismo nivel de esfuerzo que `js/report.js` (2b)

1. **`voter_token`:** UUID aleatorio generado en el cliente, guardado en
   `localStorage`. El `unique (place_id, voter_token)` hace que un
   `23505` al insertar se trate como "ya votaste, gracias" (mismo patrón
   "éxito silencioso" que el honeypot de `report.js`). Server-enforced,
   sobrevive sesiones.
2. **Cliente:** el botón de voto se oculta / deshabilita para los
   `place_id` que ya están en el set local de votados; cooldown global
   corto en `localStorage` (~10 s) entre votos, para frenar clicks
   scripteados rápidos desde un mismo browser.
3. **RLS:** `grant insert` a `anon` únicamente (sin `SELECT` / `UPDATE` /
   `DELETE`), `with check (source = 'community' and char_length(voter_token)
   between 8 and 64)` — misma forma "estado forzado + largos acotados"
   que las políticas de `suggestions` / `place_reports`.
4. **Estructural (la defensa más fuerte):** el ranking se computa **solo
   sobre `status='approved'`** — la RLS del anon key ni siquiera **puede
   leer** lugares no aprobados, así que un bug en el query del frontend
   no puede filtrarlos. El ranking muestra el conteo de votos al lado de
   cada lugar (un lugar bombardeado es visible), y solo los ~12 primeros
   por país: inflar 3 votos entre 396 lugares no mueve un top-12.
   Santiago puede auditar `place_votes` por clustering de
   `voter_token` / `created_at` y borrar filas fraudulentas
   (service_role).

**El caso "el dueño vota por su propio lugar repetidamente":** el
`unique (place_id, voter_token)` + el dedup en cliente cubren el caso
honesto (doble click, entusiasmo); un dueño determinado que limpia
`localStorage` una y otra vez se detecta por la auditoría de clustering,
y su impacto está acotado — un top-12 visible con conteos, y ningún voto
puede volver "seguro" nada.

**Fuera de alcance de v1** (diferido hasta que aparezca abuso real, misma
decisión que ADR-004 tomó para el CAPTCHA):

- Rate limit por IP (requeriría una policy leyendo `request.headers` o
  una Edge Function).
- CAPTCHA / Turnstile / hCaptcha.
- Detección automática de fraude / patrones.
- Requerir un mínimo de interacción previa (abrir el panel del lugar,
  etc.) antes de habilitar el voto.

Sin detección automática de fraude en v1 es un trade-off explícito, mismo
espíritu que ADR-004 punto 5 ("sin techo de volumen todavía").

### 3. Relación con el status del Validator: el ranking opera EXCLUSIVAMENTE sobre `status='approved'` — principio duro, confirmado (2c)

- Un lugar en `needs_review` / `pending` / `discarded` /
  `outreach_confirmed` **nunca** aparece en el ranking ni puede rankear
  alto, **sin importar cuántos votos tenga**.
- La exclusión está garantizada a **nivel base de datos**, no solo en el
  query del frontend: el anon key **no puede leer** filas de `places`
  con `status != 'approved'` (política RLS `public read approved places`).
- Los votos **se siguen guardando** para un lugar que después baja a
  `needs_review` (la fila de `place_votes` queda; `vote_count` también).
  Si el lugar vuelve a `approved`, sus votos siguen ahí y vuelve a
  aparecer en el ranking donde le corresponda.
- **Corolario (mismo principio que ADR-002 / ADR-004):** los votos de la
  comunidad tienen **cero autoridad** sobre `places.status`. Un lugar con
  500 votos que el Validator manda a `needs_review` —por ejemplo tras un
  reporte negativo (ADR-004)— desaparece del ranking hasta que un humano
  lo re-apruebe. El voto ordena **entre** lugares ya seguros; nunca es
  evidencia de seguridad.

### 4. Filtro por país: dos pestañas (segmented control), no un `<select>`, sin vista combinada (2d)

- Solo 2 países (Uruguay / Argentina) → un toggle de 2 opciones es el
  patrón correcto; un `<select>` es overkill y agrega un click de
  apertura.
- **Reusa el componente `.chip` de `.map-chips`** (`aria-pressed`, mismo
  patrón de toggle que `js/map.js` ya usa para las categorías) — cero
  diseño nuevo.
- **Sin opción "Todos":** un top-12 mezclado estaría dominado por
  Argentina (396 vs 192 aprobados), y comparar un café de Montevideo con
  un restaurante de Palermo no le sirve a alguien que va a comer a una
  ciudad concreta.
- **Default: Argentina** (dataset más grande → la lista se ve poblada
  desde el arranque). Un click para cambiar a Uruguay. La elección se
  recuerda en `localStorage`, mismo criterio que el toggle de idioma.

### 5. Ubicación: sección nueva `#ranking` inmediatamente después de `#map` (2e)

**"Al lado del mapa" en sentido literal (dentro de `.map-wrap`) NO es
viable:** el mapa ya tiene un panel overlay (`.place-panel`) que se abre a
la derecha en desktop y como bottom-sheet en mobile — una columna de
ranking persistente ahí colisiona, y el mapa necesita el ancho para ser
útil.

**Sí es viable reusando componentes existentes**, como una sección nueva
`#ranking` justo después de `#map` (se lee como "acá está el mapa… y acá
los favoritos de la comunidad"), con el **mismo grid de 2 columnas de
`.features-layout`**:

- **Izquierda (ancha):** la lista rankeada. Cada fila reusa el lenguaje
  visual `.pp-*` / `.review` — nombre, ciudad, badge de seguridad
  (`.pp-badge--safe` / `--options`), conteo de votos, botón de voto.
- **Derecha (angosta, `sticky`):** el toggle de país (`.chip`) + una
  línea explicativa ("Los lugares donde la comunidad comió seguro. Votá
  los tuyos.").
- Debajo de 900px apila (toggle arriba, lista abajo) — gratis, por la
  regla responsive que `.features-layout` ya tiene.

Reusa: `.section` / `.section-head` / `.eyebrow`, `.features-layout`,
`.chip`, los badges `.pp-*`, el sistema `data-i18n`, y el mismo patrón de
`fetch` con anon key de `map.js` / `report.js`.

**Nuevo:** un archivo JS chico (`js/ranking.js`), un bloque CSS chico, y
el botón de voto (el único elemento de UI genuinamente nuevo — un estilo
de botón).

**Alternativa más liviana considerada:** una sola columna con el toggle
de país como una fila de `.chip` arriba de la lista, replicando el patrón
"chips arriba del contenido" del `#map` justo encima. Es un poco más
simple y más consistente con el mapa, pero se elige la de 2 columnas
porque es la que pide el mensaje, es viable con reuso puro, y la columna
derecha `sticky` mantiene el toggle visible mientras se scrollea la
lista.

**Puntos de entrada para votar en v1:** las filas del ranking **y** el
footer del `.place-panel` del mapa (`.pp-footer` ya existe, al lado del
link "Reportar un error"). Ambos son contenedores existentes; el panel es
el punto de mayor señal (el usuario ya miró el lugar antes de votar).

### 6. Datos de ejemplo: sí, sembrar con lugares reales ya aprobados, curados a mano, con conteos chicos y filas marcadas (2f)

Lanzar con un ranking vacío hace que la sección se vea rota, y hoy hay
**cero votos comunitarios**.

- Se siembra `place_votes` con **~8–15 lugares `approved`** que Santiago
  puede avalar personalmente, cruzados con el `rating` /
  `user_ratings_total` de Google (285 de 588 aprobados tienen ese dato)
  como **chequeo de sanidad de selección** — pero el `rating` de Google
  es *solo ayuda para elegir qué sembrar*, no el mecanismo del ranking.
- Cada fila sembrada: **`source='seed'`**, conteo modesto (dígitos
  simples a ~10–15) para que unos pocos votos reales de la comunidad
  muevan la aguja rápido y la siembra no domine para siempre.
- Es un **patrón ya establecido del proyecto**: `db/seed.sql` siembra el
  mapa mismo — "A small hand-curated set (~10–20 approved places) seeds
  the map so it is alive immediately; agents grow it over time". El
  ranking sembrado es el mismo criterio, un nivel más arriba.
- La copy de la sección lo enmarca como "Recomendados por la comunidad";
  este ADR y el PLAN de implementación registran que el set inicial es
  **sembrado de lugares reales curados, no orgánico**.

**Alternativas descartadas:**

- **Arrancar en cero y crecer orgánicamente:** sección muerta al lanzar;
  con tráfico bajo y sin auth podría quedar casi vacía mucho tiempo.
- **Derivar el ranking inicial de `rating * log(user_ratings_total)` de
  Google:** mezcla "ranking comunitario" con "rating de Google" y
  confunde el propósito. Sí se usa como criterio de selección de qué
  sembrar, y queda como posible **segunda clave de desempate** a futuro.

### Tamaño y orden del ranking mostrado

Top **~12 por país** por `vote_count desc`, desempate por `rating` de
Google (nulls al final) y luego `name`. Sin paginación / "ver más" en v1.

### Alcance del ADR

Este ADR fija la decisión de diseño. El **schema exacto** (constraints,
trigger `vote_count`, RLS completa), la implementación de `js/ranking.js`,
el bloque CSS, los tests y las fases de verificación se redactan en un
PLAN de implementación después de aceptar este ADR — mismo flujo que
ADR-004 → `docs/plans/PLAN-community-reviews.md`.

## Verificación

Implementado y verificado end-to-end en producción, 2026-09-02
(`docs/plans/PLAN-community-ranking.md`, Fases A–E):

- **Schema (Fase A, commits `df8376b` + `6af819d`).** `place_votes`
  (anon-INSERT-only, `unique (place_id, voter_token)`, `voter_token` CHECK
  8–64), `places.vote_count` denormalizado + índice, y el trigger
  `sync_place_vote_count` aplicados a producción y sincronizados en
  `db/schema.sql`. **Corrección durante la Fase B:** el trigger necesitaba
  `SECURITY DEFINER` — como `INVOKER` (default), un `INSERT` disparado por
  `anon` corría el `update places` como `anon` (sin policy de UPDATE) y
  Postgres filtraba el UPDATE a 0 filas en silencio, así que `vote_count`
  nunca se movía. Encontrado con datos de prueba en `BEGIN; … ROLLBACK;`,
  antes de tráfico real.
- **Trigger + RLS (Fase B, commit `7ffa728`).**
  `db/checks/2026-09-01-place-votes.sql` — 6 checks en `BEGIN; … ROLLBACK;`,
  todos PASS: `INSERT` bumpea, `DELETE` decrementa, `greatest()` clamp en 0,
  duplicado → `23505`, RLS rechaza voto sobre lugar no `approved` (`42501`),
  RLS permite voto sobre `approved` vía el path `anon`. **Contrato
  PostgREST** (smoke test real): el approach de dedup del ADR
  (`resolution=ignore-duplicates`) **no es usable** — exige `GRANT SELECT`
  sobre `place_votes`, que el diseño retiene; se usa `POST` plano y un
  `409/23505` se trata como éxito ("ya votaste").
- **Frontend (Fase C, commit `1904901`).** Sección `#ranking` después de
  `#map` (grid 2 columnas clonando `.features-layout`), `js/ranking.js`
  (fetch top-12 por país, render con `.pp-*`, tabs `.chip` con default
  Argentina recordado en `localStorage`, `voter_token` + set de votados +
  cooldown 10 s), botón de voto también en el `.pp-footer` del panel del
  mapa vía el evento `celiacmap:panel-open`. Sin link en la nav (v1).
  Verificado en Chrome contra la Supabase real: voto → `201` → conteo +1
  optimista → "✓ Votado"; `409` en un revoto; tabs AR/UY; toggle EN;
  0 errores de consola. Deployado a `celiacmap.org` (GitHub Pages).
- **Seed (Fase D, commit `95097e3`).** 15 lugares `approved` elegidos por
  criterio objetivo (`validation_confidence >= 0.85`, Google `rating >= 4.5`
  con `>= 30` reseñas, uno por ciudad, 9 provincias/metros argentinos +
  6 departamentos uruguayos), `source='seed'`, conteos 3–15
  quality-correlated. **124 filas** insertadas; los 15 `vote_count`
  coinciden exactamente con lo planeado (JANA=15 … Celisano=4) vía el
  trigger. De paso se corrigió el `city` de "Marce Cakes® Gluten Free"
  (`Paraná` → `Santa Fe`, residuo de la ambigüedad de "Paraná") y se
  registró el duplicado de "JANA GLUTEN FREE" como deuda de datos.
- **Fase E (visual + e2e en vivo).** Ambos tabs renderizan los 15 lugares
  reales en orden correcto; un voto de prueba contra un lugar seedeado
  (`voter_token` fijo) subió el conteo `3 → 4`, se borró después y el
  trigger de `DELETE` lo devolvió a `3`. Media queries mobile verificadas
  por inspección de stylesheet (limitación conocida del harness). Deploy de
  producción confirmado (`js/ranking.js` HTTP 200, sección + i18n en el HTML
  servido).

Costo total de infraestructura: **cero** — sin LLM, sin APIs pagas, sin
GitHub Actions, sin Edge Function. Un `INSERT` + un `UPDATE` de trigger por
voto.

## Consecuencias

**Positivas:**

- El mapa gana una capa de prueba social real: la persona celíaca ve qué
  recomiendan sus pares, no solo lo que encontraron los agentes.
- Respeta la columna vertebral del proyecto: el voto tiene cero autoridad
  sobre `status`; solo el rubric del Validator decide seguridad. El
  ranking se apoya estrictamente encima de lo ya aprobado.
- Superficie nueva mínima: una tabla intake (misma forma que
  `suggestions` / `place_reports`), una columna denormalizada + un
  trigger, un JS chico, y reuso de `.chip` + `.pp-*` + `.features-layout`.
- Costo casi nulo: pura base de datos, cero LLM, cero llamadas a APIs
  pagas — a diferencia de cada agente del pipeline.
- El frontend lee el ranking por el **mismo endpoint anon que ya usa el
  mapa**, sin ningún grant ni política RLS nueva de lectura.

**Negativas / trade-offs aceptados:**

- **Sin auth**, la integridad del voto se apoya en un token de
  `localStorage` + un `unique` constraint + auditoría manual. Un actor
  determinado puede inflar el conteo de un lugar limpiando storage o
  cambiando de browser. Mitigado por: transparencia (conteos visibles),
  auditoría de clustering `created_at` / `voter_token`, N chico mostrado,
  y —lo más importante— que inflar votos **no puede volver visible un
  lugar inseguro** (sigue gateado a `approved`). Rate-limit por IP y
  CAPTCHA quedan diferidos hasta que aparezca abuso real.
- El ranking inicial es **curado, no orgánico** — la sección no es un
  reflejo puro del sentimiento de la comunidad el día 1. Documentado,
  filas `source='seed'`, conteos chicos para que lo orgánico pese rápido.
- Un lugar que baja a `needs_review` (por ejemplo vía un reporte
  negativo, ADR-004) **desaparece del ranking aunque tenga muchos
  votos** — correcto por diseño, pero un lugar muy votado que desaparece
  sin explicación pública puede confundir a un usuario que vuelve.
- **Tabla nueva escribible por anon** = superficie de abuso nueva,
  contenida por la RLS INSERT-only + largos acotados + el `unique`
  constraint — misma contención que las otras dos tablas intake, pero es
  una superficie más.
- `place_votes` nunca se expone a lectura → un usuario no puede ver quién
  votó ni cuándo, solo el agregado. Aceptable: no se recolecta ningún
  dato personal y el `voter_token` es aleatorio.
- El `vote_count` denormalizado + trigger tiene que mantenerse
  consistente: borrar una fila fraudulenta requiere que el trigger cubra
  también `DELETE`, o un recálculo periódico.
- Es la primera vez que el proyecto muestra en la UI un dato agregado
  generado por acción directa de usuarios anónimos (los reportes de
  ADR-004 no son visibles públicamente; el conteo de votos sí). Sigue
  siendo solo sobre lugares que pasaron el Validator, pero amplía qué
  tipo de dato comunitario aparece en pantalla.
