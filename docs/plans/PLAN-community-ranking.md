# Plan — Ranking comunitario de lugares (voto simple, filtrado por país)

**Estado:** Propuesto
**ADR relacionado:** `docs/architecture/ADR-005-community-ranking.md` (Aceptado)

## Objetivo

Darle a la comunidad celíaca una forma de un solo click de decir "este
lugar es de los mejores", y mostrar un ranking de los ~12 más votados por
país (Uruguay / Argentina) junto al mapa — **sin** que el voto tenga
ninguna autoridad sobre `places.status`. El ranking se construye
estrictamente encima de lugares que el Validator ya aprobó (ADR-005,
principio rector).

## Contexto

Hoy el mapa muestra todos los lugares `approved` sin jerarquía. No hay
ninguna tabla de votos / likes (`grep` de `db/schema.sql` lo confirma),
`place_reports` (ADR-004) no sirve como fuente de voto porque un reporte
`positive` exige `description` de 5–2000 caracteres, y `places.rating` /
`user_ratings_total` son 100% de Google Places (285 de 588 aprobados los
tienen, todos `source='google_places'`). En producción hay **cero votos
comunitarios de cualquier tipo**.

ADR-005 resolvió el diseño: una tabla intake nueva `place_votes`
(anon-INSERT-only, misma forma que `suggestions` / `place_reports`), un
contador denormalizado `places.vote_count` mantenido por trigger, lectura
del ranking por el mismo endpoint anon que ya usa el mapa, y anti-abuso en
capas sin dependencia nueva.

## Mecanismo actual reusado (investigación previa)

A diferencia de ADR-004 (que reusó toda la cadena webhook → Edge Function
→ `repository_dispatch` → agente Python + el `RUBRIC` del Validator), este
feature **no toca IA, ni agentes, ni el pipeline mensual, ni
`agent_log`**. Es puramente base de datos (una tabla + un trigger) +
frontend (un JS chico + una sección). Lo que se reusa:

Piezas concretas que se reusan **sin modificar**:

- **El patrón de tabla intake anon-INSERT-only** de `suggestions` /
  `place_reports`: `revoke all ... from anon`, `grant insert`, una única
  policy `for insert ... with check (<estado forzado> and <largos
  acotados>)`, sin policy de `SELECT` (server-only para lectura).
- **La RLS existente `public read approved places`** sobre `places`: el
  ranking se lee por `GET /rest/v1/places?...&status=eq.approved&...` con
  la anon key — sin ninguna policy nueva de lectura. El contador vive en
  `places.vote_count`, columna nueva pero de la misma tabla ya legible.
- **El patrón de columna denormalizada en `places`** (`rating`,
  `user_ratings_total`, `outreach_status`, `contact_email`): `vote_count`
  es una más, mantenida por trigger.
- **El trigger `set_updated_at` de `db/schema.sql`** como molde exacto de
  cómo se declara una función `plpgsql` + `drop trigger if exists` +
  `create trigger` idempotente.
- **El patrón de `fetch` con anon key** de `js/map.js` / `js/report.js`
  (`apikey` + `Authorization: Bearer`, `Prefer: return=minimal`).
- **El toggle `.chip` de `.map-chips`** (`js/map.js:438-451`): `.chip` /
  `.chip-active`, `aria-pressed`, un listener que limpia todos y activa
  el clickeado. Las pestañas de país lo copian tal cual.
- **El lenguaje visual `.pp-*` del place-panel** (`.pp-title`, `.pp-meta`,
  `.pp-badge--safe` / `--options`, `.pp-footer`): cada fila del ranking lo
  reusa en vez de un set de estilos nuevo.
- **El grid `.features-layout`** (2 columnas `1.15fr 0.85fr` ≥900px,
  columna derecha `sticky`, apila abajo): la sección `#ranking` lo reusa.
- **El patrón `MSG = {es:{...}, en:{...}}` + el evento `celiacmap:lang`**
  de `js/map.js` / `js/report.js` para el texto renderizado
  dinámicamente (el que no puede llevar `data-i18n`).
- **El `db/seed.sql`** (UUIDs fijos + `on conflict do nothing`) como
  molde del seed de la Fase D.
- **El `db/fixes/*.sql`** (scripts SQL fechados, corridos a mano en el
  SQL Editor) como molde de los checks de la Fase B/E.

**Diferencia clave con ADR-004:** ahí un evento externo disparaba una
re-evaluación asíncrona del Validator. Acá el "efecto" de un voto es
sincrónico y determinista: un `INSERT` en `place_votes` que un trigger
`AFTER` convierte en `places.vote_count = vote_count + 1`. Sin LLM, sin
GitHub Actions, sin webhook, sin Edge Function.

## Diseño

### Schema (`db/schema.sql`)

**Tabla nueva `place_votes`:**

```sql
create table if not exists public.place_votes (
  id          uuid primary key default gen_random_uuid(),
  place_id    uuid not null references public.places(id) on delete cascade,
  voter_token text not null check (char_length(voter_token) between 8 and 64),
  source      text not null default 'community'
                check (source in ('community', 'seed')),
  created_at  timestamptz not null default now(),
  constraint place_votes_place_voter_key unique (place_id, voter_token)
);

create index if not exists place_votes_place_id_idx on public.place_votes (place_id);
```

- `voter_token`: token aleatorio generado en el cliente (`crypto.randomUUID()`
  o fallback), no secreto — es solo la clave de dedup. Rango 8–64
  caracteres, reforzado también en la RLS.
- `unique (place_id, voter_token)`: constraint FULL (no parcial), mismo
  criterio que `places_source_external_id_key` / la de
  `outreach_messages` — PostgREST necesita el nombre de columnas simple
  para `on_conflict`.
- `source`: `'community'` (default, forzado por RLS) o `'seed'` (Fase D,
  solo vía service_role en el SQL Editor).
- `on delete cascade`: si un lugar se borra, sus votos se borran; el
  trigger de DELETE corre para cada uno pero el `update places` no
  matchea nada (el lugar ya no está) — no-op inofensivo.

**Columna denormalizada `places.vote_count`:**

```sql
alter table public.places add column if not exists vote_count integer not null default 0;
-- 588 filas: el índice es opcional a esta escala, pero barato y consistente
-- con el resto del schema (places_status_idx, places_country_city_idx, ...).
create index if not exists places_country_vote_count_idx
  on public.places (country, vote_count desc);
```

**Trigger que mantiene `vote_count` (molde: `set_updated_at`):**

```sql
create or replace function public.sync_place_vote_count()
returns trigger
language plpgsql
as $$
begin
  if (tg_op = 'INSERT') then
    update public.places set vote_count = vote_count + 1 where id = new.place_id;
    return new;
  elsif (tg_op = 'DELETE') then
    -- greatest(): nunca dejar vote_count negativo, aunque haya drift.
    update public.places set vote_count = greatest(vote_count - 1, 0) where id = old.place_id;
    return old;
  end if;
  return null;
end;
$$;

drop trigger if exists place_votes_sync_count on public.place_votes;
create trigger place_votes_sync_count
  after insert or delete on public.place_votes
  for each row execute function public.sync_place_vote_count();
```

**Snippet de reconciliación** (no corre solo — se corre a mano si
`vote_count` alguna vez se desincroniza, p. ej. tras un borrado masivo de
filas fraudulentas). Va documentado en `db/schema.sql` como comentario y
en `db/checks/`:

```sql
update public.places p
  set vote_count = coalesce(v.n, 0)
  from (select place_id, count(*) n from public.place_votes group by place_id) v
  where v.place_id = p.id;
update public.places
  set vote_count = 0
  where vote_count <> 0
    and id not in (select place_id from public.place_votes);
```

**RLS (mismo patrón que `suggestions` / `place_reports`):**

```sql
alter table public.place_votes enable row level security;
revoke all on public.place_votes from anon, authenticated;
grant insert on public.place_votes to anon, authenticated;

drop policy if exists "public can cast a vote" on public.place_votes;
create policy "public can cast a vote"
  on public.place_votes
  for insert
  to anon, authenticated
  with check (
    source = 'community'
    and char_length(voter_token) between 8 and 64
    and exists (
      select 1 from public.places p
      where p.id = place_votes.place_id
        and p.status = 'approved'
    )
  );
```

- **Sin policy de `SELECT`** para anon → `place_votes` es server-only para
  lectura, igual que `agent_log` / `outreach_messages`. El `voter_token`
  de nadie es visible; el conteo se lee vía `places.vote_count`.
- **`exists (... status='approved')` en el `with check`** — refinamiento
  respecto del sketch del ADR (que solo acotaba `source` + largo). El
  subquery corre como el rol `anon`, sujeto a la RLS de `places`, así que
  solo ve lugares aprobados: votar por un lugar `pending` / `needs_review`
  / `discarded` queda **rechazado a nivel base de datos**, no solo
  ocultado en el cliente. Alinea con el principio duro de ADR-005 punto
  3 ("el ranking opera EXCLUSIVAMENTE sobre `status='approved'`") y evita
  que alguien acumule votos sobre un lugar que todavía no es público.
  Trade-off menor aceptado: un lugar que baja temporalmente a
  `needs_review` no puede recibir votos en esa ventana (irrelevante — no
  aparece en el ranking igual).
- **Sin `agent_log` widening** — no hay agente. Sin etapa nueva en
  `scripts/run_agents.py`. Sin secreto nuevo.

### API — contrato de inserción de voto (sin código de servidor nuevo)

Igual que `place_reports`: `POST` directo a PostgREST con la anon key. La
única diferencia es el manejo del duplicado, que se resuelve del lado del
servidor con un header, **no** con un catch de `23505` en el cliente:

```
POST {SUPABASE_URL}/rest/v1/place_votes?on_conflict=place_id,voter_token
Headers:
  apikey: {ANON}
  Authorization: Bearer {ANON}
  Content-Type: application/json
  Prefer: return=minimal, resolution=ignore-duplicates
Body:
  { "place_id": "<uuid>", "voter_token": "<token>" }
```

- **`?on_conflict=place_id,voter_token` + `Prefer: resolution=ignore-duplicates`**
  → PostgREST hace `INSERT ... ON CONFLICT (place_id, voter_token) DO NOTHING`.
  Un voto repetido del mismo browser para el mismo lugar devuelve **200 /
  201 con cuerpo vacío**, sin error — el cliente no tiene que
  special-casear un 409. `DO NOTHING` no actualiza, así que el `grant
  insert` (sin `update`) alcanza.
- **Fallback documentado:** si esa versión de PostgREST no respeta
  `resolution=ignore-duplicates` como se espera, el cliente trata un
  `409` (código `23505`) como éxito silencioso — mismo espíritu que el
  honeypot de `report.js`. Se confirma cuál de los dos aplica en la Fase
  B (smoke test real).
- **`source` no se manda** — la RLS lo fuerza a `'community'` vía el
  default de columna + el `with check`.
- Un `POST` para un `place_id` no aprobado → la RLS lo rechaza con **403**
  (`new row violates row-level security policy`). El cliente lo trata como
  error genérico; por la UI no debería pasar nunca (el botón de voto solo
  se renderiza para lugares aprobados del ranking / del panel).

### Lectura del ranking (mismo endpoint que el mapa)

```
GET {SUPABASE_URL}/rest/v1/places
    ?select=id,name,city,country,category,safety_level,vote_count,rating
    &status=eq.approved
    &country=eq.Argentina
    &order=vote_count.desc,rating.desc.nullslast,name.asc
    &limit=12
```

- Desempate: `vote_count` desc → `rating` de Google desc (nulls al final,
  ADR-005 "desempate por rating de Google") → `name` asc.
- `country` es texto plano en `places`; en la práctica exactamente
  `'Uruguay'` / `'Argentina'` (los dos valores que la tabla `suggestions`
  restringe, y los únicos que usan los datos reales).
- Sin paginación / "ver más" en v1.

### Frontend

**`js/ranking.js`** (nuevo, ~180–220 líneas, convenciones de
`report.js` / `map.js`):

- IIFE `"use strict"`, `var cfg = window.CELIACMAP_CONFIG || {}`.
- Guard: `var section = document.getElementById("ranking"); if (!section) return;`
  — la página funciona sin esto (igual que map/suggest/report).
- **`voter_token`:** `localStorage["celiacmap-voter-token"]`; si no
  existe, se genera con `crypto.randomUUID()` (contexto seguro: HTTPS +
  localhost) o fallback `"v" + Date.now().toString(36) + Math.random()
  .toString(36).slice(2, 12)` (>8 chars). Se persiste. Todo en
  `try/catch` (localStorage puede tirar).
- **Set de votados:** `localStorage["celiacmap-voted"]` = array JSON de
  `place_id`. Un lugar ya en el set → su botón renderiza en estado
  "✓ Votado" deshabilitado.
- **Cooldown:** `localStorage["celiacmap-vote-last"]`; < ~10 s desde el
  último voto → el click muestra un inline "Esperá un momento" y no hace
  el `POST`. Mismo patrón que `COOLDOWN_MS` de `report.js` (que usa 60 s;
  acá 10 s porque un voto es más liviano que un reporte).
- **Pestañas de país (`.chip`):** dos botones
  `data-country="Argentina"` / `"Uruguay"`, patrón de toggle idéntico a
  `map.js:438-451` (`chip-active`, `aria-pressed`). Default **Argentina**;
  la elección se guarda en `localStorage["celiacmap-ranking-country"]` y
  se restaura al cargar (mismo criterio que el toggle de idioma).
- **Fetch + render:** al cargar y en cada cambio de pestaña, `GET` del
  top-12 (query de arriba) y render de la lista reusando `.pp-*`:
  cada fila = número de posición + `.pp-title` (nombre) + `.pp-meta`
  (ciudad) + badge `.pp-badge--safe` / `--options` (según `safety_level`,
  misma lógica que `map.js`) + conteo de votos + botón de voto.
- **Click de voto:** valida set-de-votados y cooldown → `POST` (contrato
  de arriba) → en éxito (200/201/o 409-como-éxito): agrega el `place_id`
  al set local, escribe `celiacmap-vote-last`, incrementa
  **optimísticamente** el conteo mostrado (solo si no estaba ya en el set
  — evita doble-conteo si el usuario ya votó desde el panel), pone el
  botón en "✓ Votado". En error real: inline "No se pudo votar".
- **Texto dinámico:** `MSG = {es:{...}, en:{...}}` propio (como
  `map.js` / `report.js`) + listener de `document.addEventListener(
  "celiacmap:lang", ...)` para re-renderizar en el toggle de idioma.
- **Voto desde el panel del mapa:** `js/ranking.js` engancha un listener
  **delegado** en `#place-panel` para clicks en `.pp-vote` — así toda la
  lógica de voto vive en un solo lugar y `js/map.js` solo agrega el
  markup del botón (ver abajo).

**`index.html` — sección `#ranking` nueva, después de `</section>` de
`#map` y antes de `#suggest`:**

```html
<section class="section" id="ranking">
  <div class="container">
    <header class="section-head reveal">
      <span class="eyebrow" data-i18n="ranking.eyebrow">Ranking</span>
      <h2 class="section-title" data-i18n="ranking.title">Los favoritos de la comunidad</h2>
      <p class="section-lead" data-i18n="ranking.lead">Los lugares donde la comunidad comió seguro. Votá los tuyos.</p>
    </header>
    <div class="ranking-layout">           <!-- reusa el grid de .features-layout -->
      <ol class="ranking-list reveal" id="ranking-list"><!-- js/ranking.js --></ol>
      <aside class="ranking-aside reveal">
        <div class="map-chips" role="group" aria-label="País del ranking">
          <button type="button" class="chip chip-active" data-country="Argentina" aria-pressed="true">Argentina</button>
          <button type="button" class="chip" data-country="Uruguay" aria-pressed="false">Uruguay</button>
        </div>
        <p class="ranking-note" data-i18n="ranking.note">Solo lugares ya verificados. El voto ordena, no aprueba.</p>
      </aside>
    </div>
    <p class="ranking-status" id="ranking-status" role="status" aria-live="polite" hidden></p>
  </div>
</section>
```

- **Zebra:** el orden actual alterna perfecto
  (`problem` plain → `solution` alt → `features` plain → `map` alt →
  `suggest` plain → `reviews` alt → `ai` plain → `about` alt → `cta`).
  Insertar `#ranking` como **plain** después de `map` (alt) obliga a
  invertir las 4 secciones de abajo para no romper la alternancia:
  `#suggest` plain→alt, `#reviews` alt→plain, `#ai` plain→alt, `#about`
  alt→plain. Son cambios de **una palabra** en el `class` de cada
  `<section>`, cero contenido, mismo tipo de ajuste que se hizo con
  `#about` al sacar el Roadmap. Va en el mismo commit de la Fase C,
  documentado.
- **Sin link en la nav** en v1 (la nav queda en 5 items; el ranking se
  descubre justo después del mapa). Agregarlo queda como opción futura.
- El `.reveal` va en el header y en los contenedores; las filas que
  renderiza `ranking.js` aparecen sin animación de reveal (el observer de
  `main.js` corre una sola vez sobre los nodos existentes) — igual que
  los markers del mapa.

**`js/map.js` — botón de voto en `.pp-footer` del panel:** el builder del
panel (`panelHtml()` / `showDetails()`) agrega, al lado del `.pp-report`
existente, un `<button type="button" class="pp-vote" data-place-id="{id}">`
(texto vía el `MSG` de map.js, es/en). No lleva lógica — `ranking.js` lo
maneja por delegación. Cambio mínimo y contenido.

**`js/main.js` — claves i18n EN nuevas:** `ranking.eyebrow`,
`ranking.title`, `ranking.lead`, `ranking.note` (van en el dict EN, el ES
vive en el markup como todo el resto). El texto dinámico de `ranking.js`
(botón votar / votado / "X votos" / vacío / error / cooldown) vive en el
`MSG` de `ranking.js`, no en `main.js` (mismo criterio que `map.js` /
`report.js`).

**`css/styles.css` — bloque nuevo `Ranking`:** `.ranking-layout` (clona
la regla de `.features-layout` — grid 1 col, 2 col `1.15fr 0.85fr`
≥900px, `.ranking-aside` `sticky`), `.ranking-list` / `.ranking-item`
(reusa tokens y el look de `.pp-*` / `.review`), `.rk-rank` (número de
posición), `.pp-vote` / `.ranking-item .rk-vote` (el único elemento de UI
nuevo — un botón chico, estados default / votado / disabled),
`.ranking-status`, `.ranking-note`. Sin sistema de diseño nuevo.

**`index.html` — orden de `<script>`:** agregar
`<script src="js/ranking.js"></script>` después de `js/report.js` (todos
al final del `<body>`, DOM listo).

### Datos de ejemplo (Fase D — bloqueada)

`db/seed.sql` gana un bloque al final (o un `db/seed-ranking.sql` nuevo —
se decide en la Fase D según prefiera Santiago):

```sql
-- Seed del ranking comunitario (ADR-005 punto 2f): votos iniciales para
-- ~8-15 lugares REALES ya approved que Santiago avala personalmente.
-- source='seed' para que sean transparentes y removibles cuando lo
-- orgánico domine. Conteos chicos (dígitos simples a ~15) a propósito.
-- Idempotente: on conflict (place_id, voter_token) do nothing.
-- LISTA A COMPLETAR CON INPUT DE SANTIAGO — no inventar.
insert into public.place_votes (place_id, voter_token, source) values
  -- ('<place_id real>', 'seed:<slug>:01', 'seed'),
  -- ('<place_id real>', 'seed:<slug>:02', 'seed'),
  -- ... (N filas por lugar = conteo inicial deseado para ese lugar)
on conflict (place_id, voter_token) do nothing;

-- Tras el seed: verificar que vote_count matchea el conteo real.
-- update ... (snippet de reconciliación de la sección Schema)
```

`voter_token` para filas seed: prefijo `'seed:'` + slug del lugar + índice
(p. ej. `'seed:sin-gluten-pocitos:03'`), siempre 8–64 chars.

## Control de gasto / alcance

- **Costo de infraestructura: cero.** Sin LLM, sin llamadas a APIs pagas,
  sin GitHub Actions, sin Edge Function. Solo un `INSERT` + un `UPDATE` de
  trigger por voto, y un `GET` de 12 filas por vista de ranking.
- **Sin techo de votos por lugar** en v1 (mismo trade-off explícito que
  ADR-004 punto 5). El `unique (place_id, voter_token)` limita a 1 voto
  por browser por lugar; un actor que limpia `localStorage` puede sumar
  más, acotado por la auditoría manual y por mostrar solo el top-12 con
  conteos visibles.
- **Sin rate limit por IP / CAPTCHA** en v1 — diferido hasta que aparezca
  abuso real (misma decisión que ADR-004 para el CAPTCHA).

## Fases

Cada fase = un commit separado, mismo patrón que la sesión de hoy. La
`Fase D` está **bloqueada** hasta que Santiago pase la lista de lugares.

### Fase A — Schema

- `db/schema.sql`: tabla `place_votes` (+ índice + `unique`), columna
  `places.vote_count` (+ índice), función `sync_place_vote_count()` +
  trigger `place_votes_sync_count` (after insert or delete), RLS
  (INSERT-only, `with check` con el `exists(status='approved')`), y el
  snippet de reconciliación como comentario.
- Aplicar el SQL en el **SQL Editor de Supabase** (mismo flujo manual que
  cada migración anterior del proyecto).
- Verificación read-only post-apply (`supabase db query --linked`): la
  tabla existe, la columna existe con default 0, el trigger existe, las
  588 filas de `places` tienen `vote_count = 0`.
- **Commit:** `feat(db): place_votes table + denormalized places.vote_count`

### Fase B — API / verificación de base de datos

- `db/checks/2026-XX-XX-place-votes.sql` (molde: `db/fixes/*.sql`) — un
  script que corre **dentro de `begin; ... rollback;`** en el SQL Editor
  (nada persiste) y verifica:
  1. `insert` de un voto para un lugar approved conocido → `places.vote_count`
     pasa de N a N+1.
  2. `insert` de un `(place_id, voter_token)` duplicado → `unique`
     violation (o `on conflict do nothing` → conteo sin cambios).
  3. `delete` del voto → `vote_count` vuelve a N.
  4. `greatest(vote_count-1, 0)`: forzar `vote_count=0` y borrar → no baja
     a -1.
  5. `set role anon; insert` para un `place_id` **no** approved → RLS lo
     rechaza (`with check`). `reset role`.
- **Smoke test del contrato PostgREST** (documentado en el propio script
  o en la sección Verificación): `curl` real con la anon key →
  (a) voto nuevo → 201; (b) `places.vote_count` subió (read-only check);
  (c) voto duplicado con `?on_conflict=...` + `Prefer:
  resolution=ignore-duplicates` → 200/201 sin error **o** 409/23505
  (documentar cuál aplica → define el manejo en `ranking.js`);
  (d) voto para un `place_id` no approved → 403. Borrar la fila de prueba
  al terminar (o usar un `place_id` de prueba y limpiar).
- **Commit:** `test(db): place_votes trigger + RLS + PostgREST contract checks`

### Fase C — Frontend

- `js/ranking.js` nuevo (fetch top-12 por país, render con `.pp-*`,
  pestañas `.chip`, `voter_token` + set-de-votados + cooldown en
  `localStorage`, `MSG` es/en + listener `celiacmap:lang`, listener
  delegado en `#place-panel` para `.pp-vote`).
- `index.html`: sección `#ranking` después de `#map`; **flip de zebra**
  de `#suggest` / `#reviews` / `#ai` / `#about` (cambio de una palabra en
  cada `class`); `<script src="js/ranking.js">` tras `js/report.js`;
  claves `data-i18n` nuevas en el markup ES.
- `js/map.js`: botón `.pp-vote` en el `.pp-footer` del panel (markup, sin
  lógica) + su texto en el `MSG` de map.js.
- `js/main.js`: claves EN nuevas (`ranking.eyebrow` / `.title` / `.lead`
  / `.note`).
- `css/styles.css`: bloque `Ranking` (`.ranking-layout` clonando
  `.features-layout`, `.ranking-list` / `.ranking-item`, `.rk-rank`,
  `.pp-vote` / `.rk-vote`, `.ranking-status`, `.ranking-note`).
- **Commit:** `feat(ranking): #ranking section + js/ranking.js + panel vote button`

### Fase D — Seed de datos  🚫 BLOQUEADA

- **BLOQUEADA hasta que Santiago pase la lista de 8–15 lugares reales**
  (`place_id` o nombre exacto + conteo de voto inicial deseado para cada
  uno). **No generar ni inventar la lista.**
- Una vez desbloqueada: bloque `insert into place_votes (... source='seed')`
  al final de `db/seed.sql` (o `db/seed-ranking.sql`), N filas por lugar
  = conteo deseado, `voter_token` `'seed:<slug>:<nn>'`, `on conflict do
  nothing`. Aplicar en el SQL Editor. Verificar `vote_count` vs conteo
  real con el snippet de reconciliación.
- **Commit:** `feat(db): seed community ranking with curated real places`

### Fase E — Tests + verificación

- **Python:** cero código Python nuevo → suite sin cambios (263 tests).
  Se anota explícitamente, no se agregan tests.
- **Verificación visual (Chrome, server local `python -m http.server`,
  no `file://`):** desktop — la sección `#ranking` aparece después del
  mapa; las pestañas AR/UY cambian la lista y se recuerdan en
  `localStorage`; el botón de voto pasa por default → "✓ Votado" →
  (segundo click) cooldown; el botón del `.pp-footer` del panel del mapa
  vota el mismo lugar sin doble-contar; el toggle EN renderiza todo el
  texto nuevo; **0 errores de consola**. Screenshots.
- **Mobile:** limitación conocida (el resize del harness no fuerza el
  viewport — documentado en "Frontend design audit" / Fase 19). Se
  verifica la regla de apilado de `.ranking-layout` y el wrap de
  `.map-chips` leyendo el stylesheet cargado + inspección de DOM.
- **End-to-end en vivo** contra el Supabase real: votar desde la UI →
  201 → la fila aparece en `place_votes` (`supabase db query --linked`,
  read-only) → `places.vote_count` incrementado por el trigger → recargar
  → el ranking re-ordena → el dedup local + el cooldown funcionan →
  **borrar la fila de voto de prueba** y confirmar que el trigger de
  DELETE decrementa `vote_count` (misma disciplina de "revertir la fila
  de prueba" que la verificación de ADR-004).
- `README.md`: subir el conteo de secciones (11 → 12), agregar el ranking
  a la lista de features y a la lista de secciones.
- **Commit:** `test(ranking): visual + live e2e verification; README sections`

### Fase F — Documentación y cierre

- `docs/architecture/ADR-005-community-ranking.md`: agregar una sección
  `## Verificación` con los resultados del e2e en vivo (mismo patrón que
  ADR-004).
- `CLAUDE.md`: subsección nueva en el Decisions Log ("Community ranking —
  `place_votes` / `places.vote_count`"), entrada en "Build status
  (phases)" (Phase 21), y el bullet-pointer en la lista de ADRs cerca del
  final.
- `docs/architecture/C4-diagrams.md`: nota menor en Nivel 2 — nuevo
  contenedor de frontend (`js/ranking.js`) + tabla `place_votes` +
  columna `places.vote_count`; no hay sistema externo ni agente nuevo.
- `prompts.md`: §26 (aceptación de ADR-005 + este plan + implementación).
- `PLAN-community-ranking.md`: `Estado` → `Completado`.
- **Commit:** `docs: close ADR-005 (community ranking) — verificación + Decisions Log`

## Tests a cubrir

**No hay runner de tests para SQL ni para JS en el proyecto** (toda la
suite Python mockea Supabase; `supabase/` no tiene config local). Por eso:

- **Trigger + RLS:** el script `db/checks/2026-XX-XX-place-votes.sql` de
  la Fase B, corrido en `begin; ... rollback;` — verificación manual
  reproducible y commiteada, no un test automatizado. Cubre: increment on
  insert, decrement on delete, `greatest()` underflow guard, `unique`
  violation, RLS `with check` rechaza lugar no-approved.
- **Contrato PostgREST:** `curl` documentado en la Fase B (201 / dedup /
  403).
- **Frontend:** sin test automatizado (mismo criterio que `js/suggest.js`
  / `js/report.js`) — verificación manual en Chrome (Fase E) + e2e en
  vivo con cleanup de la fila de prueba.
- **Python:** nada — no hay código Python en este feature.

## Fuera de alcance por ahora

- Techo de votos por lugar / rate limit por IP / CAPTCHA (ADR-005 punto
  2, diferido hasta que aparezca abuso real).
- Detección automática de fraude / clustering de `voter_token` (se hace a
  mano si hace falta).
- "Ver más" / paginación del ranking (solo top-12 por país en v1).
- Link en la nav a `#ranking`.
- Que un reporte `positive` de ADR-004 sume también un voto (ADR-005
  punto 1 los mantiene desacoplados en v1).
- Ranking combinado UY+AR, o sub-ranking por ciudad.
- Mostrar quién votó / cuándo (no se recolecta PII; `place_votes` no se
  expone a lectura).
- `rating` de Google como fuente del ranking (solo desempate y ayuda de
  selección del seed).

## TODO — deuda técnica detectada al implementar

_(a completar durante la implementación, mismo criterio que
PLAN-community-reviews.md)_
