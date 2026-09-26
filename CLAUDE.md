# CLAUDE.md

> **Size budget.** This file is loaded into every session and must stay under 50,000 characters
> (`tests/test_claude_md_size.py` fails above that). Long-form decisions, the build-phase history and the full
> detail of every risk live in [`docs/DECISIONS.md`](docs/DECISIONS.md); this file keeps the contracts, the
> standing rules and an index that links there. See **Documentation Rules**.

## Project Context

This project is a web portfolio focused on the celiac community. The main idea is to present a digital platform where people can find gluten-free / sin TACC places, visualize an interactive map proposal, suggest new locations, leave reviews, and see a future evolution powered by artificial intelligence or agents.

The project must look professional, clear, modern, and presentable as both an academic and personal portfolio.

> The public site no longer presents the project as academic (2026-09-24); the academic framing above is historical
> context for the repo, not copy for the page.

## Main Goal

Create a high-quality landing page that communicates:

- The problem the celiac community faces when looking for safe places.
- The proposed solution.
- The main features.
- The value for users.
- The future vision of the product.
- The growth roadmap.

## Architecture

> **Status:** CeliacMap evolved from a static landing page into a functional product. The landing (HTML/CSS/JS) is
> the frontend shell; Supabase, Python agents and Edge Functions are the backend, data and agent layers. This
> supersedes the original "no backend / no real AI" scope. Full original text (Overview block, schema refinements,
> model rationale): [Architecture — texto completo](docs/DECISIONS.md#architecture--texto-completo-movido-de-claudemd).

```txt
FRONTEND    HTML/CSS/JS + Leaflet. Anon key, read-only: only `status = 'approved'` places.
DATABASE    Supabase (PostgreSQL + REST + Auth). Core: places, reviews, agent_log. Intake: suggestions, place_reports,
            place_votes. Server-only: place_evidence, outreach_messages, chat_usage (db/schema.sql).
AGENTS      Python, one file per agent in agents/, all feeding the same Validator gate:
  search      Google Places (data-driven by config/targets.yaml), dedup by external_id, inserts `pending`.
  social      Tavily (public IG/FB pages) -> claude-haiku-4-5 parse -> Google Find Place geocode; source "social".
  web (v3)    Anthropic web search (WEB_SEARCH_MODEL), opt-in per city (`web: true`, off since Phase 11).
  validator   claude-sonnet-4-6; the only quality gate: approved / needs_review / rejected (rubric below).
  updater     periodic deterministic diff of approved places (closures, moves, category changes).
  also        suggestion promoter, outreach (+ reply handler), review handler (community reports), admin_notify.
AUTOMATION  GitHub Actions (.github/workflows/): monthly pipeline plus the jobs listed under File Structure.
SCOPE       Phase 1: Uruguay and Argentina; add entries to targets.yaml to scale to Latin America.
```

**Schema refinements**
- `places.status` (`pending` | `approved` | `discarded` | `needs_review`, plus `outreach_confirmed`) is the spine of the
  agent flow; the frontend shows only `approved`. Verdicts map additively (`rejected` -> `discarded`). `source` +
  `external_id` (Google `place_id`) are unique together and drive dedup.
- `reviews` is **server-only** since 2026-09 (Google ToS). `suggestions` / `place_reports` carry three optional unverified
  kitchen declarations; `places` deliberately does not (ADR-007). The only public read of `place_reports` is the view
  `community_opinions` (ADR-008). RLS on every table: anon may only `SELECT` approved places; agents use `service_role`.

**AI models.** Validator `claude-sonnet-4-6` (structured JSON verdict, code-enforced 0.85 / 0.7 / 0.5 gates); Search and
Updater deterministic first; Social and Web `claude-haiku-4-5` (extract and discover, never judge safety;
`WEB_SEARCH_MODEL` upgrades Web); chatbot `claude-haiku-4-5`. Anthropic only, behind `agents/clients/llm.py`. Deferred:
escalate candidates below ~0.7 confidence to `claude-opus-4-8`.

**Phase 1 scope.** Auth deferred (anonymous forms, votes, reports). No hand-made seed places: a place is never added
without a real business behind it (the 13 invented "sample" places were removed 2026-09-25).

### Key risks to keep in mind

The long risks are summarized (the three short ones are verbatim); the full text of each, with its measurements and history, is in
[Key risks — detalle completo](docs/DECISIONS.md#key-risks-to-keep-in-mind--detalle-completo-movido-de-claudemd).

- **Secrets boundary:** never ship the `service_role` key or any API key to the
  browser — only the anon key, made safe by correct RLS.
- **Google Places** requires billing enabled; cap calls per run. Caching/storage
  ToS handling (specifically for reviews) is resolved — see **Google Places
  reviews — ToS-driven access restriction + 30-day expiration** in the
  Decisions Log.
- **Health-sensitive false approvals:** `verified` stays `false` until confirmed;
  `status` + `agent_log` act as a human review queue; surface a UI disclaimer that
  `safety_level` is a community/AI estimate, not a medical guarantee.
- **Search stamped city/country from the query, not the result (fixed 2026-08-08; hardened 09-01 and 09-25).** Country now
  comes from the result's own address; non-UY/AR results are dropped (`to_candidate()`, `is_foreign_address()`). Not
  retroactive. Limits: a bare-city domestic address reads as foreign; a province-only address takes the query country
  (`Río Negro`). [→](docs/DECISIONS.md#risk--search-agent-stamped-citycountry-from-the-query-target)
- **`resolve_location()` can return the wrong business (fixed 2026-09-24).** A Find Place match whose name differs is
  dropped (`names_match()`) and falls to the address-only geocode. Limit: a name that *contains* the searched word still
  passes ("Serendipia" / "Serendipia - CEA"); the Validator is the backstop. Do not delete the víaSana row (legitimate).
  [→](docs/DECISIONS.md#risk--resolve_location-can-return-the-wrong-business)
- **`VALIDATOR_RESERVE=80` was sized for the daily cadence (decided 2026-08-20).** A monthly run leaves 70–150 `pending`.
  Mitigation: `validator-midmonth.yml` (15th, 150 per run); the reserve and `AGENT_DAILY_BUDGET` stay unchanged.
  [→](docs/DECISIONS.md#risk--validator_reserve-was-sized-for-the-old-daily-cadence)
- **`validation_notes` is invisible to the Validator and overwritten on each run (open).** Evidence goes in
  `place_evidence`; sending an evidenced place back through `pending` destroys it. Deferred fix: a `curator_notes` column.
  [→](docs/DECISIONS.md#risk--validation_notes-is-invisible-to-the-validator-and-overwritten)
- **A redactor failure after a successful insert 500s the chat turn, and a retry can duplicate the row (open, parked).**
  Bounded harm. Pending fix: on write success + redactor error, return 200 with a canned acknowledgment and the real
  `action`. [→](docs/DECISIONS.md#risk--a-redactor-failure-after-a-successful-insert-can-duplicate-a-report)

## The Core Prompt — Validator Rubric

> **Por qué este prompt es el corazón del proyecto:** CeliacMap es una herramienta
> de salud — la usan personas celíacas para quienes el gluten es un peligro real,
> no una preferencia. Este rubric es la **única compuerta de calidad** entre lo que
> los agentes descubren automáticamente y lo que se publica en el mapa, y es lo que
> obliga al modelo a ser conservador cuando la evidencia es débil. Por eso **no debe
> perderse ni modificarse sin una consideración cuidadosa**: cambiarlo cambia
> directamente qué lugares se aprueban para una comunidad sensible a la salud.

This is the exact system prompt sent to `claude-sonnet-4-6` for every pending
candidate (the `RUBRIC` constant in `agents/validator_agent.py`). It is fixed
across all candidates in a run, so it is sent as a **cached system block**; the
per-candidate data goes in the user message. The model must reply with only the
structured JSON verdict `{verdict, confidence_score, category, safety_level,
reasoning, flags, recommendation}`, which `_normalize()` then coerces into
schema-safe values. The **same `RUBRIC`** is reused on-demand by the MCP server's
`validate_place` tool, so batch and on-demand validation share one source of truth.

**Three-tier verdict + code-enforced gates (adopted Jun 2026).** The verdict is
`approved` / `needs_review` / `rejected`, mapped to `places.status` **additively**:
`approved`→`approved`, `rejected`→`discarded`, `needs_review`→`needs_review` (a
human-review tier held back from the map). `ValidatorAgent._decide_status` enforces
the gates as defense in depth regardless of the model's stated verdict:
auto-approval requires `confidence_score >= 0.85`; `< 0.5` (or an explicit
`rejected`) discards; everything between — and the `< 0.7` safety floor — becomes
`needs_review`. `confidence_score` persists to `validation_confidence`, `reasoning`
to `validation_notes`, and `flags` / `recommendation` to their own columns.
`category` + `safety_level` are retained in the output (the schema requires them and
the map renders safety badges).

**Full rubric (Spanish — as it exists in code):**

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
- "gluten_free_100": establecimiento donde se cocinan y venden ÚNICAMENTE productos aptos para celíacos (cocina exclusiva / dedicada). Un local que cocina con gluten pero ofrece menú, preparación aparte o cocina separada para celíacos NO es "gluten_free_100".
- "celiac_friendly": atiende explícitamente a celíacos (certificado, "apto celíacos", preparación dedicada).
- "options_available": ofrece algunas opciones sin gluten pero no está especializado. Es el piso por defecto cuando la evidencia es escasa.

También se te pueden dar fragmentos de reseñas de la comunidad que mencionan términos sin gluten / celíaco. Pésalos como evidencia de apoyo, pero nunca dejes que reseñas entusiastas te empujen por encima de la evidencia: cuando la señal es escasa, mantente conservador.

Si el mensaje incluye "declaraciones_comunidad" (un bloque aparte de las reseñas), son afirmaciones de personas sobre la cocina del lugar (si es exclusivamente sin gluten, cómo preparan lo apto para celíacos). NO están verificadas: úsalas para orientar la revisión, pero por sí solas NO justifican "approved" ni "gluten_free_100". Si una declaración indica que el local también cocina con gluten, el nivel no puede ser "gluten_free_100". Si ese bloque es la única evidencia de que la cocina es exclusiva, el safety_level no puede ser "gluten_free_100": como máximo "celiac_friendly". Estas declaraciones no cambian cómo pesas las reseñas ni el resto de la evidencia: sin ese bloque, evalúa exactamente como siempre.

Si el mensaje incluye "ubicacion_geocode", significa que solo se geocodificó la dirección de texto del candidato: NO hay una ficha de Google Places que confirme que el negocio existe y opera en ese lugar (sin reseñas de Google, sin verificación de existencia). Tratá esto como evidencia debilitada — NO asignes "approved" salvo que el resto de la evidencia (mención explícita de "sin TACC", reseñas claras de la comunidad) sea fuerte por sí sola. Ante la duda, "needs_review".

Si el mensaje incluye "evidencia_descubrimiento", son textos tomados de fuentes públicas (publicaciones o perfiles de redes sociales, páginas web) o aportados por personas o por el administrador, con su URL cuando existe. Son la evidencia principal para distinguir un espacio 100% sin gluten de un lugar con opciones: úsalos. No están verificados: una fuente aislada no alcanza para "approved" si el resto de la evidencia la contradice, y lo que aporta una persona pesa como las declaraciones_comunidad.

Basá el veredicto y el safety_level SOLO en la evidencia que viene en este mensaje. No uses lo que creas saber del negocio por tu cuenta, ni tomes el nombre o una parte del nombre como evidencia: que el nombre diga "sin gluten" no prueba que la cocina sea exclusiva, y que no lo diga no prueba lo contrario. No menciones en reasoning, flags ni recommendation datos de salud de ninguna persona (por ejemplo, si el dueño o la dueña es celíaco/a).

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, exactamente con esta forma:
{"verdict": "approved" | "rejected" | "needs_review",
 "confidence_score": <número entre 0.0 y 1.0>,
 "category": "restaurant" | "cafe" | "shop",
 "safety_level": "gluten_free_100" | "celiac_friendly" | "options_available",
 "reasoning": "<explicación clara en español, máximo 3 oraciones>",
 "flags": ["<flag detectado>", ...],
 "recommendation": "<acción concreta sugerida para el operador>"}
```

> ⚠️ **Do not lose or change this prompt without careful consideration.** It is the
> quality gate for a health-sensitive use case. Any edit to the wording, the
> categories, the safety levels, the confidence gates, or the "be conservative when
> unsure" rule directly affects which places are approved for celiac users — treat
> changes as a deliberate design decision, test them, and record them in this
> Decisions Log. (The Jun 2026 move from the `approve`/`discard` rubric to this
> three-tier rubric is recorded under **AI Toolkit** in the Decisions Log; the
> later `ubicacion_geocode` paragraph — cautioning against `approved` for a
> candidate resolved only by geocoding its address — is recorded under
> **Geocode-gate — address fallback** there and in prompts.md §24. The 2026-09-24
> kitchen change — `gluten_free_100` defined as "only celiac-safe products are
> cooked and sold" plus the `declaraciones_comunidad` paragraph, measured in four
> real-model A/B iterations — is recorded under **Kitchen information as review
> evidence** there, in ADR-007 and in prompts.md §31.)

## The Chatbot System Prompts — Router + Redactor

The chatbot (Edge Function `chat`, `claude-haiku-4-5`) makes two calls per turn: an intent **router** (JSON) and a
**redactor** (text grounded only in the `<datos>` it is given). Its two system prompts are a health gate on the same level
as the `RUBRIC`: closed scope of four topics, never name a place that is not in `<datos>`, no medical advice, resistance to
"ignore your instructions". **The source of truth is `supabase/functions/chat/prompts.ts` (`ROUTER_PROMPT`,
`RESPONDER_PROMPT`).** Copies: `prompts.md` §27 and `docs/architecture/ADR-006-chatbot-rag.md` ("Los prompts del
chatbot"); `tests/test_chat_prompts_sync.py` fails if either drifts and `python scripts/sync_chat_prompts.py` rewrites
them. The full text used to be inlined here (removed 2026-09-26); the prose that came with it is in
[docs/DECISIONS.md](docs/DECISIONS.md#the-chatbot-system-prompts--router--redactor).

> ⚠️ **Do not change these prompts without the battery.** Any edit to the scope, the constraints or the sources list is a
> deliberate design decision: run the jailbreak battery (`db/checks/chat_jailbreak_battery.py`, ADR-006 Fase E), measure
> against the real model, record it in `docs/DECISIONS.md` and `prompts.md`, and remember that changing a chatbot prompt
> restarts the soft-launch count.

## Technical Scope

Hand-written HTML/CSS plus a light `js/main.js`; no frameworks or libraries without a clear reason (Leaflet and the
Supabase REST access are the approved exceptions); semantic, responsive, accessible code. A backend (Supabase), a real map
(Leaflet) and real AI (Python agents on the Claude API) are now in scope; **authentication remains deferred**. Original
text: [Technical Scope (texto anterior)](docs/DECISIONS.md#technical-scope-texto-anterior).

## File Structure

```txt
/
├── index.html · css/styles.css · assets/{images,icons}/ (favicons only)
├── js/         main.js (i18n, nav) · config.js (public keys) · map.js · suggest.js + kitchen.js (Form A) · report.js
│               (Form B) · ranking.js · opinions.js · chat.js (widget -> the `chat` function)
├── agents/     base.py · {search,social,web,validator,updater,suggestion,outreach}_agent.py · outreach_reply_handler.py ·
│               review_handler.py · manual_overrides.py · admin_notify.py · clients/ (supabase, google_places, tavily,
│               llm, resend, website_scraper)
├── mcp_server/ server.py (6 tools over Supabase + the RUBRIC) · skills/validator-rubric/SKILL.md (academic deliverable)
├── supabase/functions/  outreach-reply/ · place-report-created/ · chat/ (index.ts, prompts.ts, index.test.ts) — Deno/TS
├── config/     settings.py (env-driven) · targets.yaml (countries, cities, search terms, `web: true` opt-in)
├── scripts/    run_agents.py (CI: search -> social -> web -> suggestion -> validator -> updater -> outreach -> review_sweep)
│               plus admin tools (review_queue, moderate_opinions, cap_unsupported_100, revalidate_low_confidence,
│               admin_digest), purge_chat_logs, sync_chat_prompts, check_setup, gen_favicons, gen_cursors
├── db/         schema.sql · seed.sql (ranking votes only) · migrations/ · fixes/ (one-off production SQL) · checks/
├── docs/       DECISIONS.md (decisions log + detail) · architecture/ (ADR-001…008, C4-diagrams.md) · plans/ · superpowers/
├── tests/      offline Python tests + frontend_*.test.js; guards: test_rubric_docs_sync, test_chat_prompts_sync, test_claude_md_size
├── .github/workflows/  monthly pipeline, mid-month Validator, weekly suggestions, admin digest, Pages deploy, dispatch handlers
└── requirements.txt · .env.example · README.md · CLAUDE.md · prompts.md · .gitignore
```

Previous, longer tree: [File Structure (texto anterior)](docs/DECISIONS.md#file-structure-texto-anterior).

## Development Rules

- Before modifying files, briefly explain the plan.
- Create or modify only the necessary files.
- Do not over-engineer the solution.
- Use clear names for classes, files, and sections.
- Use semantic HTML: `header`, `main`, `section`, `article`, `footer`, etc.
- Keep CSS organized by sections with clear comments.
- Design mobile-first and ensure full responsiveness across desktop, tablet, and mobile.
- Care about contrast, readability, and accessibility.
- Avoid unnecessary comments in the code.
- If there are multiple options, choose the simplest, most maintainable, and most appropriate one for the project.

## Design Guidelines

The design must convey:

- Health
- Trust
- Safety
- Community
- Clarity
- Modernity

### Color Palette and Typography (current — editorial redesign)

- **Greens:** deep `#1a3a2a` / `#2d6a4f`, soft `#52b788` / `#b7e4c7`. **Backgrounds:** warm off-white `#fdfaf5` (base) and
  `#f8f4ee` (alternating).
- **Text:** `#26352b` (warm green-charcoal) and `#5e6358` (muted). **Borders:** `#e7ded0`. Green-first accents (no amber);
  gold `#bfa06a` only for star ratings.
- **Type:** Playfair Display for headings, hero, brand, stats and pull-quotes; DM Sans for body, navigation, buttons and captions.
- Rationale: [Editorial redesign](docs/DECISIONS.md#editorial-redesign-visual--content). The original palette (`#2E7D32` / `#F59E0B` / Inter) is in
  [Design Guidelines (texto anterior)](docs/DECISIONS.md#design-guidelines-texto-anterior).

Avoid a cluttered or confusing design. The page must feel like a real product proposal.

## Suggested Sections

Landing order: Hero · Problem · Solution · Features · Interactive Map (+ community ranking) · Suggest a Place · Reviews /
community voice · AI & Agents · About · Call to Action · Footer. (Roadmap removed 2026-09-01.) Original list:
[Suggested Sections (texto anterior)](docs/DECISIONS.md#suggested-sections-texto-anterior).

## Documentation Rules

- **New decisions go to [`docs/DECISIONS.md`](docs/DECISIONS.md)**: a new `###` entry at the end of its "Decisions Log"
  (a new build phase goes in "Build status (phases)"). Never write long-form rationale, run logs or measurements here.
- **`CLAUDE.md` only receives** (a) one index line in "Decisions Log (índice)" — title, date, one sentence, anchor link —
  and (b) a new line in "Reglas vigentes" when the decision creates a permanent rule.
- **Size budget:** `tests/test_claude_md_size.py` fails above 50,000 characters. Once the index passes ~40 entries, group
  the old entries of one theme into a single line; if a change would still cross the budget, move the detail to
  `docs/DECISIONS.md` and shorten index lines.
- `README.md`: update when features, structure, deploy or project information change. `prompts.md`: add every important
  prompt used during development, with a brief description. When a doc mirrors code (the `RUBRIC`, the chatbot prompts),
  edit the code first and re-sync the copies; the sync tests are the gate.
- Do not wait to be asked: keep the docs in sync when a section or feature is added, the structure changes, a deploy URL
  appears, a decision is made or the status changes. Previous wording:
  [Documentation Rules (texto anterior)](docs/DECISIONS.md#documentation-rules-texto-anterior).

## Git Rules

- Use clear and descriptive commit messages.
- Do not commit unnecessary system or editor files.
- Keep the repository clean.
- If a slash command is created, it must be committed within the project.

## Skills
- skills/prompt-engineer/SKILL.md — load when writing,
  improving, or debugging any prompt for an LLM
- .claude/skills/frontend-design/, .claude/skills/web-design-guidelines/,
  .claude/skills/ui-ux-pro-max/ — third-party design-review skills (not
  authored in this repo); load when reviewing or improving the frontend's
  visual design. See **Frontend design audit** in the Decisions Log for
  provenance and what was applied.

## Quality Criteria

The result must be presentable as:

- An academic project.
- A personal portfolio piece.
- An initial foundation for a future real web application.

The priority is quality, visual clarity, good structure, and clear communication of the idea.

## Reglas vigentes

Standing rules taken from the Decisions Log; the incident and reasoning behind each is in the entry named in brackets in
[docs/DECISIONS.md](docs/DECISIONS.md).

**Validator, overrides and labels**
- **Manual overrides are never silent** [Manual Validator overrides]. Record them in `places.validation_notes` under a
  header (`OVERRIDE MANUAL` / `APROBACIÓN MANUAL` / `CORRECCIÓN MANUAL`): who, what direct knowledge, what the Validator
  had said. Never inflate or deflate `validation_confidence`; leave `verified` alone unless a human vouches for it.
- **`DATA_CORRECTION_PHRASES`** (`agents/manual_overrides.py`): a `CORRECCIÓN MANUAL` header that only corrects data
  ("país/ciudad corregidos", "ciudad corregida", "lugar de ejemplo del seed", "no es un comercio", "fuera del alcance
  geográfico") does not protect a place; each header line is judged on its own; `OVERRIDE` / `APROBACIÓN MANUAL` always
  protect. In fix scripts, a data-only note uses one of those phrases and a safety decision goes on its own line.
- **100% label** [Manual Validator overrides; Kitchen information]: `gluten_free_100` means only celiac-safe products are
  cooked and sold. Cooking everything but offering a celiac menu, separate prep or a separate kitchen is
  `options_available`; one shared kitchen is not 100% by default. An **owner-is-celiac** claim raises confidence but is
  evidence for human review, never automatic: only the admin upgrades to 100%. Kitchen declarations are unverified, live
  only on `suggestions` / `place_reports` (never `places`), and `owner_celiac` never reaches the model.
- **No third-party health data in public columns** (`places.*`, `validation_notes`, flags, opinions): `places` is public.
- **Evidence, not action** [Community reports; ranking; outreach]: reports, votes, outreach replies and the chatbot never
  change `places.status` on their own; only the Validator, the admin (with a transparent note) or the documented report
  rules do.
- **Evidence the Validator must weigh goes in `place_evidence`**, not `validation_notes` (invisible to it, overwritten).
  To bring back a `discarded` / `needs_review` place with real evidence, approve it with a manual override; do not send it
  through `pending`.
- **Never add a place without a real business behind it.** Fix bad rows with `status='discarded'` plus a
  `CORRECCIÓN MANUAL` header, not `DELETE` (auditable; a delete cascades to reviews and outreach rows). Before geocoding a manual place from the cadastre, run Find Place on name + city.
- **CABA is `Buenos Aires`** in `city` everywhere; the frontend and the chatbot filter by it.
- **Country comes from the result's own address, never from the query target.** Discovery agents share
  `resolve_location()` and `insert_place_candidate()` (UY+AR bounding box; out-of-scope rows are never inserted).

**Production and security**
- **Secrets boundary:** only the anon key reaches the browser. Server-only tables (`agent_log`, `reviews`, `place_evidence`,
  `chat_usage`, `outreach_messages`) get no anon grant. Google Places reviews are purged after 30 days. The legacy Places API **and** the Geocoding API must both be enabled in
  GCP and allowed in the `GOOGLE_MAPS_API_KEY` restrictions.
- **Show the literal SQL/command and wait for an explicit "dale" before writing to production or any external service**; verify
  read-only afterwards. Live tests: fixed session token, cleanup SQL shown first, guard `DELETE`s that must match 0 rows,
  revert against the baseline counts.
- **`revoke all` before the minimal `grant`** on every new public object (Supabase grants everything by default). A view
  runs with its owner's rights: its `WHERE` is the only barrier.
- **Smoke-test a new PostgREST filter live (read-only) before relying on it** (a jsonb `cs.` filter needs
  `json.dumps([x])`, not a Python list).
- **Edge Functions: `verify_jwt` OFF** (dashboard toggle; the CLI `--no-verify-jwt` flag is unreliable). After each deploy
  confirm `verify_jwt=false` and that the downloaded source equals `HEAD`. GitHub Pages does not deploy Supabase functions;
  deploy `chat` separately. One root `deno.lock` is the standard.
- **Supabase CLI** is `node_modules/.bin/supabase` (already linked); `db query --linked` runs SQL against production.
- **`db/schema.sql`:** unique constraints used by `ON CONFLICT` are full, not partial; a superseded intermediate
  `CHECK`-widening block is deleted, not kept (replaying it on current data fails); `sync_place_vote_count` stays
  `SECURITY DEFINER`.

**Prompts and chatbot**
- **The `RUBRIC` and the chatbot prompts are health gates.** Source of truth in code (`agents/validator_agent.py`,
  `supabase/functions/chat/prompts.ts`); copies guarded by `test_rubric_docs_sync.py` / `test_chat_prompts_sync.py`. Any
  change is deliberate, measured (real-model A/B, jailbreak battery) and recorded in `docs/DECISIONS.md` + `prompts.md`.
- **Do not forward `limite_medico` to the redactor** (audit-only flag; a test pins it). The medical hard line stays: no
  gluten figures, no severity or urgency judgments; `guardCeliaquiaReply` is the deterministic net.

**Frontend**
- **Any new link that dispatches `celiacmap:open-place` must be exempted in `js/map.js`'s outside-click handler**
  (`.chat-place-link`, `.review-place`, …); `tests/frontend_explorer.test.js` covers it.
- **Verify `hidden` toggles and marker clicks in a real browser, with a real click**: DOM emulation cannot see
  `display:flex` beating `hidden`, or a click on a node that was just detached.
- **Two public safety labels only** ("Espacio 100% sin gluten" / "Tiene opciones sin TACC"); `safetyGroup()` in
  `js/map.js` is the single rule and an unknown level falls to "options", never to 100%. The CARTO/OSM attribution on the
  map is a free-tier condition and is never removed.

## Decisions Log (índice)

One line per entry: title (date) — one sentence, linking to its anchor in `docs/DECISIONS.md`, where the full text lives
("s/f" = the entry states no date).

- **Chatbot — named place retrieval (2026-09-23)** — search by business name, accent/typo tolerant (chat v14). [→](docs/DECISIONS.md#chatbot--named-place-retrieval-2026-09-23)
- **Base landing decisions (s/f)** — ES/EN toggle, fonts, CSS-only mockup, SVG icons, favicons; unheaded, at the end of the entry above. [→](docs/DECISIONS.md#chatbot--named-place-retrieval-2026-09-23)
- **Editorial redesign (s/f)** — warm editorial look, green-first palette. [→](docs/DECISIONS.md#editorial-redesign-visual--content)
- **Product evolution (s/f)** — landing to product: Leaflet, Supabase, agents; CARTO key; full unique constraint. [→](docs/DECISIONS.md#product-evolution-landing--functional-product)
- **Social agent (Jan 2026)** — Find Place geocode, dedup by `place_id`, Tavily over Google CSE. [→](docs/DECISIONS.md#social-agent-design-decisions)
- **Web agent v3 (Jun 2026)** — autonomous web search on haiku; real `place_id` + Validator as guards. [→](docs/DECISIONS.md#web-discovery-agent-v3-design-decisions)
- **AI Toolkit (Jun 2026)** — three-tier rubric, code gates 0.85/0.7/0.5, MCP server. [→](docs/DECISIONS.md#ai-toolkit-prompts--skill--mcp-server-design-decisions)
- **Suggest-a-Place form (Jun 2026)** — anon INSERT-only `suggestions`, promoted by an agent. [→](docs/DECISIONS.md#suggest-a-place-public-form-design-decisions)
- **Outreach agent, Etapa 1 (2026-08 → 09-16)** — emails to `needs_review`, live mode, opt-out, scraper; cron wiring fixed. [→](docs/DECISIONS.md#outreach-agent-design-decisions)
- **Outreach reply webhook (2026-08)** — Edge Function → dispatch → Python re-evaluation, RUBRIC unmodified. [→](docs/DECISIONS.md#outreach-reply-webhook-etapa-2-design-decisions)
- **Community reports (2026-08-18)** — report = evidence, not action; webhook + monthly sweep; `deno.lock`. [→](docs/DECISIONS.md#community-reports-place_reports-design-decisions)
- **Frontend design audit (s/f)** — compliance pass with three design skills. [→](docs/DECISIONS.md#frontend-design-audit-frontend-design--web-design-guidelines--ui-ux-pro-max)
- **Map drag cursor (s/f)** — thin-line hand as a PNG (SVG cursors flicker). [→](docs/DECISIONS.md#map-drag-cursor-cm-mapleaflet-grab)
- **Geocode-gate address fallback (2026-09-01)** — Find Place, then Geocoding API; `address_only` = weaker evidence. [→](docs/DECISIONS.md#geocode-gate--address-fallback-resolve_location)
- **Manual Validator overrides (2026-09-01 → 09-25)** — never silent; four precedents; data-correction phrases; the 100% labeling rule. [→](docs/DECISIONS.md#manual-validator-overrides--allowed-but-never-silent)
- **`#suggest` card titles and copy (2026-09-24)** — titles and intros for both form cards. [→](docs/DECISIONS.md#suggest-section--card-titles-and-copy-2026-09-24)
- **Audit — evidence for the Validator (2026-09-24)** — `place_evidence`, unsupported-100% cap, report thresholds, admin tools. [→](docs/DECISIONS.md#audit-2026-09-24--evidence-for-the-validator--100-only-with-explicit-evidence)
- **Audit data-quality pass (2026-09-25)** — 42 rows fixed (seed, country/city, non-businesses, Chile); debt listed. [→](docs/DECISIONS.md#audit-data-quality-pass-2026-09-25--fictional-seed-places-wrong-countrycity-non-business-rows)
- **Kitchen information (2026-09-24)** — three unverified kitchen questions, two code caps, RUBRIC change (ADR-007). [→](docs/DECISIONS.md#kitchen-information-as-review-evidence-2026-09-24)
- **Form B collects reviews, not kitchen data (2026-09-24)** — kitchen is asked only when adding a business. [→](docs/DECISIONS.md#form-b-collects-reviews-not-kitchen-data-2026-09-24)
- **Community opinions (2026-09-24)** — approved positive opinions via a public view (ADR-008). [→](docs/DECISIONS.md#community-opinions-on-the-public-site-2026-09-24)
- **Retroactive re-validation (2026-09-06)** — 173 approvals re-judged: 138 `needs_review`, 35 discarded. [→](docs/DECISIONS.md#retroactive-re-validation-of-pre-three-tier-rubric-approvals-2026-09-06)
- **Validator: parametric knowledge (2026-09-06)** — Enharinate approved on the model's own knowledge; audit signal open. [→](docs/DECISIONS.md#validator--parametric-knowledge-vs-provided-evidence-2026-09-06)
- **Validator: name-substring heuristic (2026-09-07)** — Serendipia-cea false positive; audit signal open. [→](docs/DECISIONS.md#validator--interpretación-heurística-de-un-substring-del-nombre-sin-verificar-su-significado-real-2026-09-07)
- **`needs_review` queue with no way out (2026-09-06)** — 71 places without contact stuck; ideas, none decided. [→](docs/DECISIONS.md#cola-de-needs_review-sin-salida-automática--71-lugares-huérfanos-de-contacto-2026-09-06)
- **Brazil out-of-scope places (2026-09-01)** — 6 Curitiba-area places via the ambiguous "Paraná"; three-layer fix. [→](docs/DECISIONS.md#brazil-out-of-scope-places--curitiba-cluster-2026-09-01)
- **Geographic scope guard (2026-09-01)** — UY+AR bounding box in `insert_place_candidate()`. [→](docs/DECISIONS.md#geographic-scope-guard--insert_place_candidate-bounding-box-2026-09-01)
- **Roadmap and GitHub links removed (2026-09-01)** — public-site content. [→](docs/DECISIONS.md#public-site--roadmap-section--github-links-removed-2026-09-01)
- **Community ranking seed (2026-09-02)** — Marce Cakes city fix; JANA duplicate is data debt. [→](docs/DECISIONS.md#community-ranking-seed--data-quality-findings-adr-005-fase-d-2026-09-02)
- **Google Places reviews, ToS (2026-09-05)** — server-only, purged after 30 days, re-fetched. [→](docs/DECISIONS.md#google-places-reviews--tos-driven-access-restriction--30-day-expiration-2026-09-05)
- **Chatbot Fase C (2026-09-19)** — real `place_reports` / `suggestions` writes; four gaps, review findings. [→](docs/DECISIONS.md#chatbot-fase-c--módulo-2-reportarrecomendar--módulo-4-confirmar-design-decisions)
- **Chatbot Fase D (2026-09-19)** — `js/chat.js` widget decisions and findings. [→](docs/DECISIONS.md#chatbot-fase-d--widget-flotante-jschatjs-design-decisions)
- **Chatbot Fase E (2026-09-20)** — no gluten figures, `cortesia`, deterministic guard (v11). [→](docs/DECISIONS.md#chatbot-fase-e--revisión-de-prompts-f4-cifra-de-tolerancia--f3-falsos-positivos-de-cortesía)
- **Jailbreak battery on chat v18 (2026-09-25)** — 0 breaks; scope decline now refers to a professional (v19). [→](docs/DECISIONS.md#chatbot-jailbreak-battery-re-run-on-chat-v18-2026-09-25)
- **Map explorer simplification (2026-09-20)** — Top 3 only, two safety labels, hero before map. [→](docs/DECISIONS.md#map-explorer--results-list-and-chat-prompts-removed-2026-09-20)
- **Build status (phases)** — per-phase history; one line each below. [→](docs/DECISIONS.md#build-status-phases)
- **GitHub Pages deploy (s/f)** — Actions deploy, no build, relative paths; the ADR/C4 pointer bullets close it. [→](docs/DECISIONS.md#github-pages-deploy-decision)

### Build status — one line per phase

Detail of every phase, with its verification notes: [Build status (phases)](docs/DECISIONS.md#build-status-phases).

- ✅ 1–2 Landing page + editorial redesign
- ✅ 3 Supabase backend (schema, RLS, seed)
- ✅ 4 Leaflet map + agent foundation
- ✅ 5 Search agent
- ✅ 6 Validator agent
- ✅ 7 Updater agent + pipeline orchestrator
- ✅ 8 GitHub Actions cron (monthly)
- ✅ 9 GitHub Pages deploy
- ✅ 10 Social agent + Google review enrichment (Tavily)
- ✅ 11 Web agent v3 — ⚠️ disabled in the pipeline (a live run timed out CI)
- ✅ 12 AI Toolkit + three-tier rubric
- ✅ 13 Suggest-a-Place form
- 🚧 14 Outreach agent: schema only
- 🚧 15 Outreach agent: `outreach_send`
- 🚧 16 Outreach agent: `contact_email` website scraper
- ✅ 17 Outreach Etapa 2 reply webhook (verified live)
- 🚧 18 ADR-003 opt-out + `OUTREACH_LIVE_MODE` (1 real send 2026-09-01; cron wiring fixed 09-16, not re-verified)
- ✅ 19 Community reports (`place_reports`), live
- ✅ 20 Geocode-gate address fallback
- ✅ 21 Community ranking (ADR-005), live
- ✅ 22 Chatbot Fase C: reportar / confirmar writes
- ✅ 23 Chatbot Fase D: floating widget
- ✅ 24 Chatbot Fase E: jailbreak battery, F3/F4, guard (chat v11)
- ✅ 25 Kitchen information (2026-09-24)
- ✅ 26 Community opinions (2026-09-24)
- **Open:** chatbot soft-launch with organic traffic (Fase F: ADR-006 closure, C4, README); F4 Option 1 prompt
  reformulation (non-blocking); live confirmation of a real outreach reply and opt-out.

**ADRs:** `docs/architecture/ADR-001…008` (the file names give the topic) and `C4-diagrams.md` (Mermaid `flowchart`, not C4
syntax, which overlaps text on GitHub). Pointer bullets for the first six are at the end of the "GitHub Pages deploy" entry.
