# CLAUDE.md

## Project Context

This project is a web portfolio focused on the celiac community. The main idea is to present a digital platform where people can find gluten-free / sin TACC places, visualize an interactive map proposal, suggest new locations, leave reviews, and see a future evolution powered by artificial intelligence or agents.

The project must look professional, clear, modern, and presentable as both an academic and personal portfolio.

## Main Goal

Create a high-quality landing page that communicates:

- The problem the celiac community faces when looking for safe places.
- The proposed solution.
- The main features.
- The value for users.
- The future vision of the product.
- The growth roadmap.

## Architecture

> **Status:** CeliacMap is evolving from a static portfolio landing page into a
> real functional product. The landing page (HTML/CSS/JS) remains the frontend
> shell; the sections below define the backend, data, and agent layers being
> added. This supersedes the "no backend / no real AI" rules in the original
> Technical Scope (kept below for historical context).

### Overview

```txt
FRONTEND
- HTML/CSS/JS (current) + Leaflet.js for a real interactive map
- Filters by category (Restaurants, Cafés, Shops) connected to the DB
- Data loaded from Supabase via REST API (anon key, read-only)

DATABASE
- Supabase (PostgreSQL + REST API + Auth)
- Tables:
    places   (id, name, lat, lng, category, country, city,
              safety_level, verified, status, address, source,
              external_id, validation_confidence, validation_notes,
              created_at, updated_at)
    reviews  (id, place_id, text, rating, user_id, source, created_at)
    agent_log(id, agent, action, result, status, place_id, created_at)

AGENTS (Python)
- Search agent:
    Uses the Google Places API to find new gluten-free / sin TACC places.
    Searches by country and city (data-driven via config/targets.yaml).
    Deduplicates by external_id and proposes candidates to Supabase
    with status "pending". Deterministic (no LLM by default). Optionally
    enriches each new candidate with gluten-free review snippets pulled
    from the Google place details (stored in reviews, source "google").
- Social agent:
    Uses the Tavily Search API to index public Instagram / Facebook
    business pages ("sin TACC" "Montevideo" restricted to a platform domain via
    Tavily include_domains, data-driven via config/targets.yaml). Parses each
    result with claude-haiku-4-5 into {name, city, category, address}, geocodes
    the lead via Google Find Place to obtain real coordinates + a canonical
    place_id, deduplicates (within the run and against existing places sharing
    the place_id), and inserts candidates with status "pending", source "social".
- Validator agent:
    Uses the Anthropic Claude API (claude-sonnet-4-6).
    Analyzes each pending candidate, verifies category, safety level
    and legitimacy, and approves or discards before publishing.
- Updater agent:
    Periodically reviews already published (approved) places.
    Detects closures, relocations or category/menu changes and
    updates Supabase accordingly. Deterministic diff (no LLM by default).

AUTOMATION
- GitHub Actions cron job (free tier): runs all agents once per day.
- Manual workflow_dispatch is used to validate the pipeline before
  enabling the daily cron.

GEOGRAPHIC SCOPE
- Phase 1: Uruguay and Argentina.
- Designed to scale to all of Latin America (add entries in targets.yaml).
```

### Schema refinements (beyond the original spec)

- **`places.status`** (`pending` | `approved` | `discarded`) is the spine of the
  agent flow: Search inserts `pending`, Validator sets `approved`/`discarded`, and
  the frontend shows **only `approved`** places.
- **`places.source` / `external_id`** record provenance and enable deduplication
  (unique on `(source, external_id)`); `external_id` stores the Google `place_id`.
- **`places.validation_confidence` / `validation_notes`** persist the Validator's
  output for auditing and future escalation.
- **`reviews.user_id`** is **nullable** (auth deferred); **`source`** distinguishes
  seed / agent / user / **google** reviews (the last added for the Search agent's
  review enrichment). `rating` is constrained to 1–5.
- **`places.source`** allows `google_places` / `manual` / `user` / **`social`** —
  the last added for the Social agent. Social leads store the originating profile
  URL in `validation_notes` and use the geocoded Google `place_id` as `external_id`
  so a place found by both Search and Social is not duplicated.
- **`agent_log`** gains `agent`, `status`, `place_id` and a `jsonb result` for
  traceability; `timestamp` is named `created_at` for consistency.
- **Row Level Security (RLS)** is enabled on all tables: the public **anon** key may
  only `SELECT` `approved` places (and read reviews); it has **no** write access and
  **no** access to `agent_log`. Agents use the **service_role** key server-side only.

### AI model decisions

- **Validator → `claude-sonnet-4-6`.** Strong judgment at the one true quality
  gate, with the best cost/quality balance for a recurring daily batch. Emits a
  structured JSON verdict `{verdict, category, safety_level, confidence, reason}`.
- **Search / Updater → deterministic first**, with `claude-haiku-4-5` used only
  where free-text interpretation is genuinely needed (ambiguous category,
  "no longer offers GF" signals). Keeps CI fast and cheap.
- **Social → `claude-haiku-4-5`.** Parsing a noisy social-media search-result
  title/snippet into a clean `{name, city, category, address}` lead is exactly the
  cheap, high-volume free-text task Haiku is suited to; the heavier Validator gate
  (Sonnet) still judges every social candidate afterwards.
- **Provider strategy:** standardize on Anthropic behind a thin
  `agents/clients/llm.py` wrapper so OpenAI / DeepSeek can be swapped if cost
  demands, without touching agent logic.
- **Future optimization — tiered validation:** validate everything with Sonnet 4.6,
  then escalate only **low-confidence** candidates (e.g. `confidence < ~0.7`) to
  `claude-opus-4-8` for a second opinion. Best accuracy-per-dollar; deferred until
  logs show false approvals warrant it.

### Phase 1 scope decisions (revisitable)

- **Auth deferred.** Phase 1 is public read-only via the anon key; reviews are
  seed/agent-sourced and display-only. Supabase Auth + user-submitted reviews
  come in a later phase.
- **Manual seed.** A small hand-curated set (~10–20 approved places in UY/AR) seeds
  the map so it is alive immediately; agents grow it over time.

### Key risks to keep in mind

- **Secrets boundary:** never ship the `service_role` key or any API key to the
  browser — only the anon key, made safe by correct RLS.
- **Google Places** requires billing enabled and has caching/storage ToS limits;
  cap calls per run.
- **Health-sensitive false approvals:** `verified` stays `false` until confirmed;
  `status` + `agent_log` act as a human review queue; surface a UI disclaimer that
  `safety_level` is a community/AI estimate, not a medical guarantee.

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
structured JSON verdict `{verdict, category, safety_level, confidence, reason}`,
which `_normalize()` then coerces into schema-safe values.

**Full rubric (English — as it exists in code):**

```text
You are the Validator for CeliacMap, a curated directory of gluten-free / "sin TACC" (celiac-safe) places in Latin America. You receive a single candidate place that was discovered automatically via Google Places (so you only have its name, address, city/country and a guessed category). Decide whether it belongs in the directory, then classify it.

This data is used by people with celiac disease, for whom gluten is a health hazard. Never overstate how safe a place is. When unsure, be conservative.

Decide a verdict:
- "approve": the place plausibly serves or sells gluten-free / celiac-safe food (a restaurant, a cafe/bakery, or a shop with GF products). Names or addresses mentioning "sin TACC", "sin gluten", "gluten free", "celíaco/a", "apto celíacos" are strong positive signals.
- "discard": clearly not a food/place business, clearly unrelated to gluten-free needs, generic/ambiguous with no GF signal, or implausible as a directory entry.

Assign a category (exactly one):
- "restaurant": restaurants, takeaways, places to eat a meal.
- "cafe": cafes, coffee shops, bakeries, pastry shops.
- "shop": grocery stores, supermarkets, health-food / dietetica shops.

Assign a safety_level (exactly one), choosing the LOWER level whenever unsure:
- "gluten_free_100": a fully gluten-free / dedicated celiac establishment.
- "celiac_friendly": explicitly caters to celiacs (certified, "apto celíacos", dedicated preparation).
- "options_available": offers some gluten-free options but is not specialized. This is the default floor when evidence is thin.

You may also be given community review snippets that mention gluten-free / celiac terms. Weigh them as supporting evidence (they can raise confidence or sharpen the safety_level), but never let enthusiastic reviews push you above the evidence — when the signal is thin, stay conservative.

Respond with ONLY a JSON object, no prose, in exactly this shape:
{"verdict": "approve" | "discard",
 "category": "restaurant" | "cafe" | "shop",
 "safety_level": "gluten_free_100" | "celiac_friendly" | "options_available",
 "confidence": <number between 0 and 1>,
 "reason": "<one or two short sentences>"}
```

**Spanish translation (reference only — the code uses the English version above):**

```text
Sos el Validador de CeliacMap, un directorio curado de lugares sin gluten / "sin TACC" (seguros para celíacos) en América Latina. Recibís un único lugar candidato que fue descubierto automáticamente mediante Google Places (así que solo tenés su nombre, dirección, ciudad/país y una categoría estimada). Decidí si pertenece al directorio y luego clasificalo.

Estos datos los usan personas con enfermedad celíaca, para quienes el gluten es un peligro para la salud. Nunca exageres lo seguro que es un lugar. Ante la duda, sé conservador.

Decidí un veredicto:
- "approve" (aprobar): el lugar plausiblemente sirve o vende comida sin gluten / segura para celíacos (un restaurante, un café/panadería, o un comercio con productos sin gluten). Nombres o direcciones que mencionen "sin TACC", "sin gluten", "gluten free", "celíaco/a", "apto celíacos" son señales positivas fuertes.
- "discard" (descartar): claramente no es un negocio de comida/lugar, claramente no tiene relación con necesidades sin gluten, genérico/ambiguo sin ninguna señal sin gluten, o inverosímil como entrada del directorio.

Asigná una categoría (exactamente una):
- "restaurant": restaurantes, comida para llevar, lugares para comer una comida.
- "cafe": cafés, cafeterías, panaderías, pastelerías.
- "shop": almacenes, supermercados, dietéticas / comercios de alimentos saludables.

Asigná un nivel de seguridad (safety_level, exactamente uno), eligiendo el nivel MÁS BAJO ante la duda:
- "gluten_free_100": un establecimiento totalmente sin gluten / dedicado a celíacos.
- "celiac_friendly": atiende explícitamente a celíacos (certificado, "apto celíacos", preparación dedicada).
- "options_available": ofrece algunas opciones sin gluten pero no está especializado. Este es el piso por defecto cuando la evidencia es escasa.

También se te pueden dar fragmentos de reseñas de la comunidad que mencionan términos sin gluten / celíaco. Pesalos como evidencia de apoyo (pueden aumentar la confianza o afinar el safety_level), pero nunca dejes que reseñas entusiastas te empujen por encima de la evidencia: cuando la señal es escasa, mantenete conservador.

Respondé con SOLO un objeto JSON, sin prosa, exactamente con esta forma:
{"verdict": "approve" | "discard",
 "category": "restaurant" | "cafe" | "shop",
 "safety_level": "gluten_free_100" | "celiac_friendly" | "options_available",
 "confidence": <número entre 0 y 1>,
 "reason": "<una o dos oraciones breves>"}
```

> ⚠️ **Do not lose or change this prompt without careful consideration.** It is the
> quality gate for a health-sensitive use case. Any edit to the wording, the
> categories, the safety levels, or the "be conservative when unsure" rule directly
> affects which places are approved for celiac users — treat changes as a deliberate
> design decision, test them, and record them in this Decisions Log.

## Technical Scope

> **Note:** This section describes the original landing-page scope. As of the
> product evolution (see **## Architecture**), a backend (Supabase), a real map
> (Leaflet), and Python agents (real AI) are now explicitly in scope. The bullets
> below are retained as the frontend baseline and historical context.

- Use HTML and CSS as the main foundation.
- Keep the project simple and easy to run.
- Do not add frameworks or external libraries without a clear reason. *(Leaflet.js
  and the Supabase JS access are the approved, clearly-justified exceptions.)*
- A lightweight JavaScript file (`js/main.js`) is allowed for minor interactions such as smooth scrolling, mobile menu toggling, or simple animations — only if it adds real value.
- ~~Do not add backend, database, or authentication unless explicitly requested.~~
  Backend + database are now in scope (Supabase); authentication remains deferred
  to a later phase.
- ~~Do not implement real AI if there is no explicit decision to do so.~~ Real AI
  is now an explicit decision: Python agents use the Claude API (see Architecture).
- Prioritize clean, semantic, responsive, and accessible code.

## File Structure

Current (landing page):

```txt
/
├── index.html
├── README.md
├── CLAUDE.md
├── prompts.md
├── .gitignore
├── assets/
│   ├── images/
│   └── icons/
├── css/
│   └── styles.css
└── js/
    └── main.js
```

Target (functional product — see **## Architecture**):

```txt
/
├── index.html                  # frontend shell + real Leaflet map
├── css/styles.css
├── js/
│   ├── main.js                 # i18n, nav, reveal
│   ├── config.js               # Supabase URL + anon key (public)
│   └── map.js                  # Leaflet init, fetch approved places, filters
├── assets/{images,icons}/
├── agents/                     # Python agents
│   ├── base.py
│   ├── search_agent.py
│   ├── validator_agent.py
│   ├── updater_agent.py
│   └── clients/{supabase_client,google_places,llm}.py
├── config/
│   ├── settings.py             # env-driven config (python-dotenv)
│   └── targets.yaml            # countries/cities + search terms
├── scripts/
│   ├── run_agents.py           # CI entrypoint: search → validator → updater
│   └── load_seed.py
├── db/
│   ├── schema.sql              # tables, constraints, indexes, RLS, triggers
│   └── seed.sql                # manual seed (UY/AR)
├── .github/workflows/agents-daily.yml
├── requirements.txt
├── .env.example
├── README.md  CLAUDE.md  prompts.md  .gitignore
```

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

### Color Palette (orientative)

- **Primary green:** `#2E7D32` or similar — represents health, nature, safety.
- **Light background:** `#F9FAFB` or white — clean, breathable layout.
- **Accent:** a warm tone like `#F59E0B` or soft teal — for CTAs and highlights.
- **Text:** dark gray `#1F2937` for readability, never pure black.
- **Borders / subtle separators:** `#E5E7EB`.

### Typography

- Use a clean, modern sans-serif font (e.g. Inter, Poppins, or system fonts as fallback).
- Clear hierarchy: large hero title → section headings → body text → captions.

Avoid a cluttered or confusing design. The page must feel like a real product proposal.

## Suggested Sections

The landing page should include:

1. **Hero** — main presentation of the project.
2. **Problem** — what the celiac community faces today.
3. **Solution** — what this platform proposes.
4. **Features** — main functionalities of the platform.
5. **Interactive Map** — conceptual view of the map as the core feature.
6. **Suggest a Place** — how users can contribute new locations.
7. **Reviews** — user experiences and community feedback.
8. **AI & Agents** — future use of AI to find, validate, and update information.
9. **Roadmap** — product growth plan.
10. **About** — information about the project and its author.
11. **Call to Action** — invite users to explore or get involved.
12. **Footer** — links, credits, and repository.

## Documentation Rules

Keep the following files always updated as the project evolves:

- `README.md`: update when new features are added, structure changes,
  deploy is available, or any relevant project information changes.
- `prompts.md`: add every important prompt used during development,
  with a brief description of what it was used for.
- `CLAUDE.md`: update when new decisions are made, rules change,
  or the project scope evolves.

Claude Code must update these files automatically when:
- A new section or feature is added to the project.
- The file structure changes.
- A deploy or live demo URL becomes available.
- A relevant technical or design decision is made.
- The project status changes.

Do not wait to be asked. Keep documentation in sync with the code.

## Git Rules

- Use clear and descriptive commit messages.
- Do not commit unnecessary system or editor files.
- Keep the repository clean.
- If a slash command is created, it must be committed within the project.

## Quality Criteria

The result must be presentable as:

- An academic project.
- A personal portfolio piece.
- An initial foundation for a future real web application.

The priority is quality, visual clarity, good structure, and clear communication of the idea.

## Decisions Log

Key decisions made during development (keep this updated as the project evolves):

- **Language — Bilingual (ES default + EN toggle):** Spanish (Argentina, "sin
  TACC") is the default copy in `index.html`. A lightweight client-side toggle
  (`js/main.js`) swaps to English using an in-file dictionary, with the choice
  remembered in `localStorage`. Spanish lives in the markup so the page works
  fully without JavaScript. Implemented via `data-i18n` attributes on every
  translatable node.
- **Typography — Playfair Display + DM Sans (via Google Fonts):** Serif display
  font (Playfair Display) for headings, hero, brand, stat figures and review
  pull-quotes; DM Sans for body, navigation, buttons and captions. Both loaded
  from the Google Fonts CDN with system-font fallbacks. _(Superseded the original
  Inter choice in the editorial redesign.)_
- **Interactive Map — Pure HTML/CSS mockup:** The map section is a conceptual
  visual built with HTML and CSS only (no map library), keeping the project
  dependency-free and self-contained.
- **Icons — Inline SVG:** No icon library or font; icons are inline SVGs themeable
  via `currentColor`. `assets/icons/` is kept as a structural placeholder.
- **No binary image assets:** All visuals are built with CSS/SVG; `assets/images/`
  is kept as a placeholder via `.gitkeep`.

### Editorial redesign (visual + content)

A full visual and content redesign was applied to `index.html` and
`css/styles.css` only (file structure and section order unchanged):

- **Aesthetic — editorial / minimal / warm:** Inspired by high-end health and
  lifestyle brands. Generous spacing, serif display headings, sparse copy, and
  border-led cards with soft, warm-tinted shadows instead of heavy elevation.
- **Palette — refined greens on warm off-white:** Deep greens `#1a3a2a` /
  `#2d6a4f` and soft greens `#52b788` / `#b7e4c7`, on warm off-white backgrounds
  `#fdfaf5` (base) and `#f8f4ee` (alternating). Text is a warm green-charcoal
  `#26352b` with warm muted gray `#5e6358`; borders are warm `#e7ded0`. The old
  saturated green (`#2E7D32`) and amber accent (`#F59E0B`) were removed.
- **Accent — green-first:** CTAs and the map's "mid" safety level now use the
  green scale (no amber). A single muted gold `#bfa06a` is reserved purely for
  decorative star ratings, to keep the warm editorial tone.
- **CTA button inversion:** On the dark-green CTA band the primary button inverts
  to an off-white fill (`.cta .btn-accent`) so it stays legible.
- **Content — tighter, warmer copy:** Hero headline shortened to an emotional
  "Comer afuera, sin miedo."; section leads trimmed of filler so every word
  counts. Tone is warm and community-focused rather than corporate.

> **Resolved:** the English strings in `js/main.js` were updated to match the
> rewritten Spanish copy; every `data-i18n` key has a matching EN entry.

### Product evolution (landing → functional product)

- **Decision — evolve to a real product.** Add a Leaflet map, a Supabase backend,
  and three Python agents (Search, Validator, Updater) automated via GitHub Actions.
  Full design, refined schema, model choices, deferred-auth and seed decisions, and
  risks are documented in **## Architecture** above. Build order and verification
  live in the approved plan file.
- **Dedup key — full unique constraint, not a partial index.** The dedup key on
  `places (source, external_id)` was originally a **partial** unique index
  (`where external_id is not null`). PostgreSQL cannot use a partial index for
  `ON CONFLICT` inference unless the same `WHERE` predicate is supplied, and
  PostgREST / `supabase-py` only send the bare column list — so the Search agent's
  upsert failed with *"no unique or exclusion constraint matching the ON CONFLICT
  specification"*. Replaced it with a **full** unique constraint
  `places_source_external_id_key (source, external_id)` (idempotent `DO` block in
  `db/schema.sql` that drops the legacy partial index). Multiple manual rows with
  `external_id = NULL` remain allowed, because NULLs are treated as distinct in a
  multi-column unique key — so the partial predicate was never actually needed.

### Social agent design decisions

- **Coordinates — geocode, don't relax NOT NULL.** A social URL has no
  coordinates, but `places.lat/lng` are `NOT NULL` and the map needs them. Rather
  than make the columns nullable (which would admit un-mappable rows), the Social
  agent resolves each parsed lead via **Google Find Place** (`name + city`, biased
  to the city center) to obtain real coordinates and a canonical Google `place_id`.
  Leads that cannot be resolved are skipped and logged (`social_unresolved`).
- **Dedup — across sources via the geocoded `place_id`.** Social stores the Google
  `place_id` as `external_id`, so the `(source, external_id)` unique constraint
  dedups across social runs, and an explicit `place_exists_by_external_id` check
  dedups against places the Search agent already found (same `place_id`, different
  `source`). The profile URL is preserved in `validation_notes`.
- **Budget — shared cap plus its own per-run limit.** Social consumes its Tavily
  searches + Find Place geocodes from the combined `AGENT_DAILY_BUDGET`, and is
  independently bounded by `MAX_SOCIAL_QUERIES_PER_RUN` so it stays well under the
  Tavily 1000/month free tier.
- **Search provider — Tavily, not Google Custom Search (changed Jan 2026).** The
  Social agent originally used the Google Custom Search JSON API, but a Programmable
  Search Engine must be set to "search the entire web" to discover arbitrary
  Instagram / Facebook pages — and as of January 2026 Google no longer offers that
  toggle for new engines, making the approach unworkable. Switched to the **Tavily
  Search API** (`agents/clients/tavily_client.py`), which is purpose-built for AI
  agents (cleaner result text), has a 1000-searches/month free tier, and restricts
  domains via `include_domains` (Tavily does not honor Google's `site:` operator).
  This adds the `tavily-python` dependency — justified under "no libraries without a
  clear reason" since it replaces a now-dead provider for the core use case. New env
  var `TAVILY_API_KEY` replaces `GOOGLE_CUSTOM_SEARCH_API_KEY` + `GOOGLE_SEARCH_ENGINE_ID`.
- **Review enrichment — opt-in and best-effort.** The Search agent only enriches
  reviews when `MAX_REVIEW_ENRICHMENTS_PER_RUN > 0`; each enrichment is one extra
  Places details call, failures never abort the run, and only snippets matching a
  gluten-free / celiac keyword (accent-insensitive) are stored.

### Build status (phases)

- ✅ **Phase 1–2 — Landing page + editorial redesign.** Responsive bilingual
  single page.
- ✅ **Phase 3 — Supabase backend.** `db/schema.sql` (tables, constraints, RLS,
  triggers) + `db/seed.sql` (manual UY/AR seed).
- ✅ **Phase 4 — Live Leaflet map + agent foundation.** Map reads approved places
  from Supabase; `config/`, `agents/base.py`, `agents/clients/*`, and
  `scripts/check_setup.py` in place.
- ✅ **Phase 5 — Search agent.** `agents/search_agent.py` working end-to-end:
  a live run found and inserted **80 candidates** as `status='pending'`.
- ✅ **Phase 6 — Validator agent.** `agents/validator_agent.py` working end-to-end:
  a live run validated 35 pending candidates (33 approved, 2 discarded).
- ✅ **Phase 7 — Updater agent + pipeline orchestrator.** `agents/updater_agent.py`
  plus `scripts/run_agents.py` (search → validator → updater under one combined
  `AGENT_DAILY_BUDGET`, `--dry-run` for no-write rehearsals, consolidated
  `pipeline_run_complete` summary to `agent_log`). A live pipeline run completed
  with no errors (82/200 budget used). The `agent_log.agent` CHECK constraint was
  widened to allow `'pipeline'` so the orchestrator can persist its run summary.
- ✅ **Phase 8 — GitHub Actions daily cron.** `.github/workflows/agents-daily.yml`
  runs the pipeline once per day (09:00 UTC) and on manual `workflow_dispatch`
  (with a `dry_run` toggle and optional `budget` override). Secrets come from
  GitHub Actions Secrets; `.env.example` documents every variable. CI actions are
  pinned to Node 24 majors (`checkout@v5`, `setup-python@v6`).
- ✅ **Phase 9 — GitHub Pages deploy.** `.github/workflows/deploy-pages.yml`
  publishes only the static frontend (`index.html`, `css/`, `js/`, `assets/`) from
  `main` via `upload-pages-artifact@v3` + `deploy-pages@v5`. Live at
  **https://santisanchez4.github.io/CeliacMap/**. See the deploy decision below.
- ✅ **Phase 10 — Social discovery agent + Google Reviews enrichment.**
  `agents/social_agent.py` discovers public Instagram / Facebook pages via the
  Tavily Search API (`agents/clients/tavily_client.py`), parses each lead with
  `claude-haiku-4-5`, geocodes it via Google Find Place, and inserts `pending`
  candidates with `source='social'`. The Search agent now optionally enriches each
  new candidate with gluten-free review snippets (`reviews.source='google'`), which
  the Validator reads as extra context. The pipeline runs
  **search → social → validator → updater** under the shared `AGENT_DAILY_BUDGET`,
  with the Social stage additionally capped by `MAX_SOCIAL_QUERIES_PER_RUN`
  (Tavily free tier: 1000/month). New env vars: `TAVILY_API_KEY`,
  `MAX_SOCIAL_QUERIES_PER_RUN`, `MAX_REVIEW_ENRICHMENTS_PER_RUN`.
  - **Search-provider migration (Jan 2026):** the Social agent's discovery backend
    was migrated from Google Custom Search to Tavily after Google removed the
    "search the entire web" option for new Programmable Search Engines. See the
    *Search provider* bullet under **Social agent design decisions**.
  - **Live run verified.** An end-to-end run discovered 114 results across 16 Tavily
    queries, parsed 87 leads with Haiku, geocoded 67 via Find Place, and inserted
    **30 new `pending` candidates**; the Validator then approved 23 and discarded 7
    (0 errors). The map now shows social-sourced places.
  - **Geocoding depends on the legacy Places API.** `find_place` (via the
    `googlemaps` library) calls the **legacy** Places API, which must be both
    *enabled on the project* and *allowed in the API key's restrictions* (alongside
    Places API New). Google is sunsetting legacy APIs — a future migration to the
    Places API (New) `searchText` endpoint is the durable fix (deferred).

### GitHub Pages deploy decision

- **Method — GitHub Actions, not "deploy from branch."** Pages source is set to
  **GitHub Actions** so the workflow controls exactly what ships: only the static
  frontend is staged into `_site/` and uploaded; the Python agents, `db/`,
  `config/` and secrets-adjacent files are never published. Consistent with the
  repo's existing Actions-based automation.
- **No build step.** The site is hand-written static HTML/CSS/JS; the workflow just
  copies `index.html` + `css/` + `js/` + `assets/` and uploads the artifact.
- **Relative paths only.** The frontend references assets relatively (`css/...`,
  `js/...`) and via CDNs, so it works unchanged under the project-page subpath
  `/CeliacMap/` — no `<base>` tag or path rewriting needed.
- **`configure-pages` omitted on purpose.** The official starter includes
  `actions/configure-pages@v5`, but that action still runs on **Node 20** and is
  only needed for static-site-generator base-path detection (which a hand-written
  site doesn't need). Omitting it keeps the whole deploy workflow on **Node 24**
  (`checkout@v5`, `upload-pages-artifact@v3` (composite), `deploy-pages@v5`) with no
  deprecation warnings. It can be re-added if base-path injection is ever required.
- **Triggers.** Deploys on push to `main` limited to frontend paths (so backend-only
  commits don't redeploy), plus manual `workflow_dispatch`. A `pages` concurrency
  group serializes deploys.