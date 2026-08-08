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
- Web agent (v3, autonomous):
    Uses the Anthropic web search tool (claude-sonnet-4-6 + server-side
    web_search / web_fetch). Given a single city/country (data-driven via
    config/targets.yaml, opt-in per city with web: true), the model reasons
    freely about how to find gluten-free / sin TACC places — forums, blogs,
    Facebook groups, Instagram, news — instead of a fixed query matrix. Each
    lead is geocoded via Google Find Place (real coords + canonical place_id),
    deduplicated across sources, and inserted with status "pending",
    source "web" (originating URL kept in social_url).
- Validator agent:
    Uses the Anthropic Claude API (claude-sonnet-4-6).
    Analyzes each pending candidate, verifies category, safety level
    and legitimacy, and approves or discards before publishing.
- Updater agent:
    Periodically reviews already published (approved) places.
    Detects closures, relocations or category/menu changes and
    updates Supabase accordingly. Deterministic diff (no LLM by default).

AUTOMATION
- GitHub Actions cron job (free tier): runs all agents once per month.
- Manual workflow_dispatch is used to validate the pipeline before
  enabling the monthly cron.

GEOGRAPHIC SCOPE
- Phase 1: Uruguay and Argentina.
- Designed to scale to all of Latin America (add entries in targets.yaml).
```

### Schema refinements (beyond the original spec)

- **`places.status`** (`pending` | `approved` | `discarded` | `needs_review`) is the
  spine of the agent flow: Search inserts `pending`, Validator sets `approved` /
  `discarded` (= verdict `rejected`) / `needs_review` (the human-review queue), and
  the frontend shows **only `approved`** places. `needs_review` was added when the
  three-tier rubric was adopted (see **AI Toolkit** in the Decisions Log).
- **`places.source` / `external_id`** record provenance and enable deduplication
  (unique on `(source, external_id)`); `external_id` stores the Google `place_id`.
- **`places.validation_confidence` / `validation_notes`** persist the Validator's
  `confidence_score` / `reasoning` for auditing and future escalation; **`flags`**
  (jsonb) and **`recommendation`** (text) persist the rest of the three-tier verdict.
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
  structured JSON verdict `{verdict, confidence_score, category, safety_level,
  reasoning, flags, recommendation}` (three-tier `approved`/`needs_review`/`rejected`
  with code-enforced 0.85/0.7/0.5 gates — see the Core Prompt section).
- **Search / Updater → deterministic first**, with `claude-haiku-4-5` used only
  where free-text interpretation is genuinely needed (ambiguous category,
  "no longer offers GF" signals). Keeps CI fast and cheap.
- **Social → `claude-haiku-4-5`.** Parsing a noisy social-media search-result
  title/snippet into a clean `{name, city, category, address}` lead is exactly the
  cheap, high-volume free-text task Haiku is suited to; the heavier Validator gate
  (Sonnet) still judges every social candidate afterwards.
- **Web (v3) → `claude-haiku-4-5`** with the Anthropic web search tool. The agent
  only **discovers and extracts** candidates (it writes its own queries, reads
  forums/blogs/IG/FB, and pulls names + evidence + a source URL) — it makes **no**
  safety judgment, so Haiku is sufficient and materially cheaper for a recurring
  daily batch (changed Jun 2026 from `claude-sonnet-4-6`). Quality is upgradeable
  to `claude-sonnet-4-6` / `claude-opus-4-8` via the `WEB_SEARCH_MODEL` env var
  (one-line flip, no code change) if discovery quality proves weak. The **Sonnet**
  Validator still gates every web candidate, and every lead must geocode to a real
  Google `place_id`, so a hallucinated place is dropped before it can be published.
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

> ⚠️ **Do not lose or change this prompt without careful consideration.** It is the
> quality gate for a health-sensitive use case. Any edit to the wording, the
> categories, the safety levels, the confidence gates, or the "be conservative when
> unsure" rule directly affects which places are approved for celiac users — treat
> changes as a deliberate design decision, test them, and record them in this
> Decisions Log. (The Jun 2026 move from the `approve`/`discard` rubric to this
> three-tier rubric is recorded under **AI Toolkit** in the Decisions Log.)

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
│   ├── social_agent.py
│   ├── web_agent.py
│   ├── validator_agent.py
│   ├── updater_agent.py
│   ├── outreach_agent.py       # Etapa 1: outreach_send
│   ├── outreach_reply_handler.py  # Etapa 2: reply re-evaluation (repository_dispatch only)
│   └── clients/{supabase_client,google_places,tavily_client,llm,
│       resend_client,website_scraper}.py
├── mcp_server/                 # AI toolkit — MCP server
│   ├── server.py               # 6 tools over Supabase + the Validator rubric
│   └── README.md
├── skills/                     # AI toolkit — reusable skills
│   └── validator-rubric/SKILL.md
├── supabase/functions/
│   └── outreach-reply/         # Edge Function: Etapa 2 webhook receiver (Deno/TS)
│       ├── index.ts
│       └── index.test.ts
├── config/
│   ├── settings.py             # env-driven config (python-dotenv)
│   └── targets.yaml            # countries/cities + search terms
├── scripts/
│   ├── run_agents.py           # CI entrypoint: search → social → web → validator → updater
│   └── check_setup.py
├── db/
│   ├── schema.sql              # tables, constraints, indexes, RLS, triggers
│   └── seed.sql                # manual seed (UY/AR)
├── tests/                      # offline unit tests (external calls mocked)
├── .github/workflows/{agents-monthly,deploy-pages,outreach-reply}.yml
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

### Web discovery agent (v3) design decisions

The discovery lineage is now **v1 (Google Places tags) → v2 (Tavily social) →
v3 (autonomous web search)**. v3 (`agents/web_agent.py`) does not replace v1/v2;
it adds a smarter third funnel that feeds the **same unchanged Validator gate**.

- **No predefined tags — the model reasons freely.** Instead of a fixed query
  matrix, the Web agent hands Claude the Anthropic **server-side web search +
  web fetch tools** (`web_search_20260209` / `web_fetch_20260209`, wrapped by
  `LLMClient.research_with_web_search`) and a single city/country, and lets it
  decide what to search and which pages to read (forums, blogs, FB groups, IG,
  news). This stays on the first-party Anthropic API the project already uses —
  no new provider.
- **Coordinates — geocode, don't relax NOT NULL.** Same problem and solution as
  the Social agent: a web mention has no coordinates, so each lead is resolved via
  **Google Find Place** (`name + city`, biased to the city center) to obtain real
  coordinates + a canonical Google `place_id`. Unresolvable leads are skipped and
  logged (`web_unresolved`).
- **Dedup — across sources via the geocoded `place_id`.** Web stores the Google
  `place_id` as `external_id`, so the `(source, external_id)` unique constraint
  dedups within web runs, and `place_exists_by_external_id` dedups against places
  already found by Search/Social (same `place_id`, different `source`). The source
  URL is preserved in the `social_url` column (shared with the Social agent; the
  Validator overwrites `validation_notes`, so the URL lives apart from it).
- **Hallucination guard (health-sensitive).** A web agent can invent a
  plausible-sounding place. Two backstops: (a) every lead must geocode to a real
  Google `place_id` or it is dropped, and (b) the Sonnet Validator still judges it
  against the health-sensitive rubric; `verified` stays `false`. The research
  rubric also explicitly forbids fabricating a name or URL.
- **Rollout — opt-in per city.** A city is researched only when flagged
  `web: true` in `targets.yaml`; v3 starts with **Montevideo + Buenos Aires** and
  expands after verification. Bounded by `MAX_WEB_CITIES_PER_RUN` and
  `MAX_WEB_SEARCHES_PER_CITY`, and by a `WEB_MAX` slice of the shared
  `AGENT_DAILY_BUDGET` that never eats the Validator's reserve.
- **Schema gap fixed.** `social_url` was used by the Social agent in code but was
  missing from `db/schema.sql`; it is now added there (idempotently) since v3
  reuses it. `places.source` and `agent_log.agent` CHECKs gained `'web'`.
- **Model — `claude-haiku-4-5`** (changed Jun 2026 from `claude-sonnet-4-6`; the
  agent only discovers/extracts, the Sonnet Validator still judges safety — see the
  Web bullet under **AI model decisions**); `WEB_SEARCH_MODEL` allows a one-line
  upgrade back to `claude-sonnet-4-6` / `claude-opus-4-8`.

### AI Toolkit (prompts + Skill + MCP server) design decisions

An academic "Toolkit de IA" deliverable, integrated Jun 2026 from a set of incoming
files. The central decision was to **adopt the toolkit's richer Validator rubric**
as canonical rather than adapt the toolkit to the old rubric.

- **Three-tier rubric adopted (deliberate health-gate change).** The Validator
  verdict moved from `approve`/`discard` to `approved`/`needs_review`/`rejected`
  with `confidence_score`, `flags`, `recommendation` and explicit 0.85 / 0.7 / 0.5
  confidence gates. This is a deliberate change to the single health-sensitive
  quality gate — the new `needs_review` tier is a safety improvement (low-confidence
  candidates are escalated to a human instead of being forced to a binary verdict),
  and the gates are **code-enforced** in `ValidatorAgent._decide_status` as defense
  in depth (the model cannot auto-approve below 0.85). The full rubric text lives in
  the Core Prompt section and in `agents/validator_agent.py`.
- **Additive status mapping — keep the frontend alive.** Rather than rename the
  load-bearing published-state contract (`js/map.js` queries `status=eq.approved`),
  the verdict maps onto the existing `places.status` additively: `rejected` reuses
  `discarded`, and only `needs_review` is a new status value. RLS, the seed, and the
  map query are untouched. (Alternative considered and rejected: literal column /
  status renames to `active` / `confidence_score`, which would have broken the
  frontend, RLS and every agent/test referencing `approved`/`discarded`.)
- **`category` + `safety_level` retained.** The toolkit rubric dropped them, but the
  schema requires them (`NOT NULL`) and the map renders safety badges, so the
  adopted prompt still requests both.
- **MCP server reuses canonical logic — no second copy.** `mcp_server/server.py`
  imports the `RUBRIC` + `ValidatorAgent` normalization and the `agents/clients/*`,
  so the on-demand `validate_place` tool is identical to the daily pipeline and uses
  the **real** schema (the incoming `server.py` had assumed a divergent schema —
  `type`/`confidence_score`/`status='active'`/`source='mcp_suggestion'` — that would
  have failed against the live DB; corrected during integration).
- **`suggest_place` geocodes (like Social/Web).** A suggestion has no coordinates,
  but `places.lat/lng` are `NOT NULL`; the tool resolves the lead via Google Find
  Place and inserts `source='user'`, `status='pending'` for the daily Validator to
  judge. Unresolvable suggestions are rejected, never inserted unmappable.
- **Dependency — `fastmcp` (`>=3,<4`).** The only new dependency; verified to
  coexist with the deliberate `supabase<2.26` / `anthropic<1` pins. Lives in the
  single `requirements.txt` (the daily CI job installs it too — harmless).
- **Skill is a documentation artifact** at repo root `skills/validator-rubric/`
  (per the academic spec), not a harness-invocable `.claude/skills/` skill; it points
  to `agents/validator_agent.py` as the source of truth to prevent drift.

### Suggest-a-Place public form design decisions

The public "Suggest a Place" form (community Phase 2) lets anyone submit a
gluten-free / sin TACC place that isn't on the map yet. Auth stays deferred, so it
is anonymous. The central constraint: `places.lat/lng` are `NOT NULL` and geocoding
needs the **secret Google key**, so the browser can neither geocode nor (per the
secrets boundary) write to `places` — and RLS only lets the anon key `SELECT`
approved rows.

- **Intake table, not a direct `places` write or an Edge Function.** The browser
  writes RAW input (no coordinates) into a new **`suggestions`** table the anon key
  may only `INSERT` into; the daily pipeline's new **Suggestion promoter**
  (`agents/suggestion_agent.py`) geocodes each via Google Find Place, dedups, and
  promotes it into `places` as `source='user'`, `status='pending'` for the unchanged
  Validator gate. Chosen over (a) a Supabase Edge Function (adds a new Deno/TS server
  surface) and (b) a map-pin direct insert (loses the canonical Google `place_id`
  used for cross-source dedup and lets browser-precision coords into `places`). This
  keeps `places` always-mappable (honoring the documented NOT-NULL stance shared with
  Social/Web/MCP), adds **no new server tech**, and keeps every secret server-side.
  Trade-off: a suggestion appears only after the next daily run — consistent with the
  MCP `suggest_place` tool's own "próximo pipeline diario" contract.
- **Shared promotion core — no third copy.** The geocode→dedup→insert logic lives in
  `promote_suggestion()` (in `agents/suggestion_agent.py`), reused **verbatim** by
  both the daily `SuggestionAgent` and the MCP `suggest_place` tool (which was
  refactored to call it), mirroring how the MCP `validate_place` reuses the canonical
  `RUBRIC`. One source of truth → the on-demand tool and the batch never diverge.
- **RLS — INSERT-only, state forced.** `grant insert` to anon (no SELECT/UPDATE/
  DELETE), plus a `with check (status='new' and promoted_place_id is null)` policy
  and per-column length `CHECK`s, so the public can submit but cannot read back,
  mutate, pre-promote, or abuse the table as free storage. `suggestions.status`
  (`new`/`promoted`/`duplicate`/`rejected`) is the **promoter's** processing state,
  distinct from `places.status`.
- **Spam — layered, no new dependency.** Honeypot field + min-fill-time + per-browser
  `localStorage` cooldown (client), length-bounded RLS (server), and two strong
  backstops already in the pipeline: the **geocode-gate** drops anything that isn't a
  real Google place (→ `rejected`), and the **Validator** health-rubric gates the
  rest. A CAPTCHA (Turnstile/hCaptcha) is deliberately deferred until real abuse
  appears, to avoid a new third-party script.
- **Validation timing — daily pipeline, not on submit.** The form does only client
  validation (required fields, URL format, length); promotion + Validator judgment
  happen in the daily run. Immediate validation would require the very server surface
  the intake-table design avoids.
- **`places` unchanged.** `source='user'` was already allowed by its CHECK; the
  promoter inserts via the existing always-mappable `insert_place_candidate` path.
  Only `agent_log.agent` gained `'suggestion'` (idempotent widener).

### Outreach agent design decisions

`agents/outreach_agent.py` implements only **Etapa 1 (`outreach_send`)** of
`docs/plans/PLAN-outreach-agent.md` — drafting and sending a confirmation
email to businesses stuck in `needs_review`. Etapa 2
(`outreach_reply_handler`, a webhook that re-evaluates the reply through the
Validator) is not yet built.

- **Sandbox sender means a fixed test recipient, not per-business email
  (superseded by `OUTREACH_LIVE_MODE` — see below).** Google Places Details
  never returns a business email address (confirmed while building this
  agent — only `phone`/`website` exist, already persisted), and separately
  Resend's shared sandbox sender (`onboarding@resend.dev`) can only deliver
  to the Resend account's own verified email until a custom domain is
  verified. Every outreach email originally went to a fixed
  `OUTREACH_TEST_RECIPIENT` env var regardless of mode — selection, drafting,
  budget, `outreach_messages`, and `places.outreach_status` all still operate
  on the real `needs_review` candidate; only the physical send destination
  was the test inbox.
- **`OUTREACH_LIVE_MODE` — the ADR-003 final switch to real per-business
  delivery.** A new `Settings.outreach_live_mode` (bool, default `false`)
  routes real sends to `place["contact_email"]` instead of
  `OUTREACH_TEST_RECIPIENT` when `true` — there is deliberately **no shared
  code path / silent fallback** between the two modes. In live mode,
  `_select_candidates()` additionally requires `contact_email` to be present
  (a candidate with no scraped email is simply not eligible), and as
  defense-in-depth a candidate that somehow reaches the send step in live
  mode without `contact_email` is skipped and logged
  (`outreach_send_missing_contact_email`) rather than silently falling back
  to the test recipient. `outreach_reply_handler.py` needed no change (it has
  no recipient logic). Shipping this capability did **not** flip it on by
  itself — `OUTREACH_LIVE_MODE=true` is a separate, deliberate operational
  step (a GitHub Secret), per ADR-003's own framing. See
  `docs/architecture/ADR-003-outreach-real-send-conditions.md`: all three of
  its conditions (verified domain, opt-out mechanism, bounded initial volume)
  are met and the secret is now set to `true` and wired into
  `.github/workflows/agents-monthly.yml`'s `env:` block, so **the next
  monthly cron run sends real email to real businesses** — this has not yet
  been verified live end-to-end (the standalone verification called for in
  Phase 15/16 below still applies, now for live mode specifically).
- **Opt-out mechanism (ADR-003 condition 2).** Every Etapa 1 email appends a
  fixed, literal (non-AI-generated) `OPT_OUT_FOOTER` telling the business how
  to decline further contact. `places.outreach_opt_out` (bool) is excluded
  from candidate selection everywhere — both
  `SupabaseClient.fetch_needs_review_for_outreach` (SQL filter) and
  `OutreachAgent._select_candidates` (Python, defense in depth) — regardless
  of `outreach_status`, so an opted-out business is never recontacted even if
  it later re-enters `needs_review`. Detection itself lives in Etapa 2's
  reply handler (see **Outreach reply webhook (Etapa 2) design decisions**
  below for the classifier). Opt-out never touches `places.status` — a
  business declining contact isn't evidence about GF safety, only about
  contact preference.
- **Sender identity — configurable via settings, defaults to
  `outreach@celiacmap.org`.** The `from` address changed from Resend's shared
  sandbox sender (`onboarding@resend.dev`) to a project-owned address, read
  from `Settings.outreach_sender_email` / env `OUTREACH_SENDER_EMAIL`
  (following the settings-over-hardcoding convention used for every other
  configurable value) rather than hardcoded in `resend_client.py`; the
  `ResendClient.send` default (`SANDBOX_FROM`) stays as the wrapper's generic
  fallback for callers that don't pass one, but `OutreachAgent` always does.
  Sending from `outreach@celiacmap.org` requires that domain to be verified
  with Resend — purely a sender-identity change, orthogonal to the recipient
  (the fixed `OUTREACH_TEST_RECIPIENT` by default, or the real
  `contact_email` when `OUTREACH_LIVE_MODE` is enabled; domain verification
  itself was ADR-003's first condition, now met — see the
  `OUTREACH_LIVE_MODE` bullet above).
- **Selection — phone or website present, oldest first, not yet contacted.**
  `SupabaseClient.fetch_needs_review_for_outreach` filters
  `status='needs_review'` and `outreach_status='not_sent'`, ordered oldest
  first; the agent then keeps only rows with a `phone` or `website` on file
  (a place with neither is unlikely to be reachable at all), in Python rather
  than a Supabase `OR` filter string (no precedent for `.or_()` anywhere in
  `supabase_client.py`, and `needs_review` volume has historically been small).
- **Failure leaves the place retryable, no new status value.** If drafting
  (Haiku) or sending (Resend) fails, nothing is written — `outreach_status`
  stays `'not_sent'`, so the place is naturally retried on a later run. No
  `'failed'` status was added; this mirrors how Social/Search swallow
  per-item errors and let the next run retry.
- **`agent_log.agent='outreach'` CHECK widening — applied and verified.**
  Was flagged here as a pending gap; closed in a later session (see the
  Phase 15 entry below) — `agent_log` now shows `agent='outreach'` rows.
- **Model — `claude-haiku-4-5`**, same choice and rationale as the Social
  agent's lead-parsing call: drafting a short templated email from
  `{name, category, city}` is a cheap, low-judgment text task; the Validator
  (Sonnet) still makes every safety judgment when Etapa 2 re-evaluates a reply.
- **`contact_email` discovery — deterministic website scrape, not another LLM
  call.** `agents/clients/website_scraper.py` (`WebsiteScraperClient`) fetches
  a candidate's own (non-social) website home page with a 5s timeout and
  looks for a `mailto:` link, falling back to a generic email regex over the
  visible text — zero AI calls, zero API cost. It deliberately never raises
  (unlike `TavilySearchClient.search` / `ResendClient.send`, which raise and
  let the calling agent's per-item `try/except` handle it): this is a pure
  enrichment step, so a dead site, timeout, or bad cert must degrade to "no
  email found," not abort the run. Filters out `facebook.com` /
  `instagram.com` / `wa.me` / `whatsapp.com` / `beacons.ai` / `linktr.ee`
  links before attempting anything — confirmed against real data that 40 of
  the 68 `needs_review` places with a website on file are exactly these
  profile pages, not a business's own site. `OutreachAgent._scrape_missing_emails`
  runs before `_select_candidates`, persists `places.contact_email` (or
  `null`) and always stamps `contact_email_checked_at` so the same site isn't
  re-scraped every run, and is capped by a new `max_email_scrapes_per_run`
  setting (default 30, env `MAX_EMAIL_SCRAPES_PER_RUN`) mirroring every other
  agent's per-run limit — the Web agent's lack of one already caused a real CI
  timeout (Phase 11), and each scrape can legitimately take up to 5s. The
  scraped email is now consumed directly by the send step when
  `OUTREACH_LIVE_MODE` is enabled (see the bullet above); previously it was
  stored only for future use.
- **Scraper false-positive fix, found via manual review before flipping live
  mode.** Reviewing the first 3 real `OUTREACH_LIVE_MODE` candidates surfaced
  two classes of bad `contact_email` matches: image-filename lookalikes that
  match `EMAIL_RE`'s shape but are asset filenames (e.g. `nuvempago@2x.png`),
  and platform/infrastructure domains (`wixpress.com`, `sentry.io`,
  `sentry-cdn.com`, `godaddy.com`, `squarespace.com`) picked up from a site
  builder's own scripts rather than the business. Fixed by rejecting both
  patterns and switching `EMAIL_RE.search` to `finditer` so a rejected
  candidate doesn't stop the scan before a real email further down the page;
  domain rejection matches on proper suffix, not substring (avoids
  false-rejecting lookalikes like `wearewixpress.com`). The two affected
  places' `contact_email` / `contact_email_checked_at` were cleared so the
  scraper retries them; a duplicate listing found in the same review (two
  "Il Porto" entries sharing a phone/`contact_email`) was resolved via
  `outreach_opt_out=true` on one, not a scraper change. 7 new tests.

### Outreach reply webhook (Etapa 2) design decisions

`docs/plans/PLAN-outreach-agent.md`'s Etapa 2 (`outreach_reply_handler`) —
re-evaluating a place after a business replies to the Etapa 1 email — spans
three systems: `supabase/functions/outreach-reply/index.ts` (a Deno/TS
Supabase Edge Function, the webhook receiver), `.github/workflows/outreach-reply.yml`
(GitHub Actions, `repository_dispatch`-triggered), and
`agents/outreach_reply_handler.py` (Python, the actual re-evaluation).

- **Split across languages by design, not accident.** The webhook receiver
  must be a Supabase Edge Function (Deno/TS) — but the actual LLM
  re-evaluation must reuse `RUBRIC` / `ValidatorAgent._normalize` from
  `agents/validator_agent.py` **unmodified**, per this project's standing
  rule that the health-sensitive rubric has exactly one source of truth (see
  the Core Prompt section). Those two constraints only reconcile one way:
  the Edge Function does webhook mechanics only (verify the signature,
  resolve `place_id`, fetch the reply body, persist it, flip
  `outreach_status`); it fires a GitHub `repository_dispatch` event
  (`outreach_reply_received`, `client_payload: {place_id}`) to
  `santisanchez4/CeliacMap`, and `.github/workflows/outreach-reply.yml` runs
  `python -m agents.outreach_reply_handler --place-id <id>` — the only place
  the LLM is actually called. This mirrors how every other agent in this
  repo already only executes via GitHub Actions; there is no persistent
  Python server anywhere in this project. The alternative (porting the
  rubric + confidence gates into TypeScript so the Edge Function could
  respond in one hop) was rejected — it would create a second,
  separately-maintained copy of the one quality gate a health-sensitive
  product depends on.
- **Reply-to encodes the place_id — no separate lookup table.**
  `ResendClient.send` gains an optional `reply_to`; `OutreachAgent` builds
  `outreach+<place_id>@<OUTREACH_INBOUND_DOMAIN>` (the account's
  auto-assigned `*.resend.app` inbound address — confirmed via Resend's docs
  that any plus-addressed variant reaches the webhook, no custom domain
  needed) per send. The reply's `to` header carries this straight back, so
  the Edge Function matches a reply to its place with a regex, no state to
  keep in sync. Degrades gracefully (no Reply-To header at all) when
  `OUTREACH_INBOUND_DOMAIN` is unset.
- **Signature verification is manual Svix HMAC, not the `resend`/`svix`
  npm package's convenience method.** `resend.webhooks.verify()`, assumed
  from Resend's docs while researching this feature, turned out not to
  exist in the actually-installed `resend@4.8.0` — confirmed the hard way
  when `deno check` also caught a second, unrelated wrong assumption in the
  same file (`emails.receiving.get()`, fixed to the SDK's own
  `resend.get<T>('/emails/receiving/{id}')`). Rather than chase the SDK's
  exact (and evidently unstable/undocumented-in-package) surface for the one
  security-critical check, it implements the documented Svix algorithm
  directly against Web Crypto (`svix-id`.`svix-timestamp`.`<raw body>`,
  HMAC-SHA256 with the base64-decoded `whsec_...` secret, constant-time
  compare, ±5 min timestamp tolerance) — one less external dependency to
  drift out from under this file. `deno check` passes and `deno test`
  passes 6/6 (place_id extraction only); the signature algorithm itself
  still needs a live webhook test with a real Resend-signed request before
  it's trusted in production — type-checking proves the code compiles, not
  that the crypto matches Resend's actual signing.
- **Status remap sits on top of the unmodified `_decide_status` output — all
  three of its outcomes are allowed through, not just two.**
  `docs/plans/PLAN-outreach-agent.md` and ADR-002 name two outcomes
  (`outreach_confirmed` / `needs_review`), but reusing `_decide_status`
  unmodified also yields `discarded` if the business's own reply is itself
  disqualifying. Decided (during planning) to allow it: more conservative,
  matches ADR-001's "never overestimate safety" ethos, and needs zero
  special-casing of already-battle-tested logic.
  ```
  verdict (from _decide_status, unchanged) -> db status
    approved      -> outreach_confirmed   (never approved directly — ADR-002)
    needs_review  -> needs_review          (unchanged)
    discarded     -> discarded             (unchanged — ADR-001's own gate)
  ```
- **Idempotency — a full unique constraint on `(place_id, external_id)`,
  same "full, not partial" precedent as `places_source_external_id_key`.**
  Resend redelivers a webhook on any non-2xx response; the Edge Function
  stores Resend's `email_id` as `outreach_messages.external_id` so a
  redelivery can't double-insert the same reply. A `23505` unique-violation
  on insert is treated as success (already recorded), not an error. A place
  already in a resolved status (`approved`/`discarded`) when a reply arrives
  is also short-circuited (200, no dispatch) — a duplicate/late reply must
  not re-trigger a stale re-evaluation; `outreach_confirmed` is still
  actionable, since a later reply in the same thread should be able to
  update it further.
- **Response codes are deliberate.** 401 = bad signature (no writes, no
  dispatch). 200 = verified but not actionable — wrong event type, no
  `place_id` match, unknown place, or already-resolved place — logged, not
  retried, since redelivery wouldn't change the outcome. 500 = verified and
  actionable but a step failed (content fetch / Supabase write / GitHub
  dispatch) — retryable, so Resend's automatic redelivery can recover from a
  transient failure.
- **Opt-out classification runs before the RUBRIC re-evaluation, as a cheap
  Haiku pre-check (ADR-003 condition 2).** `agents/outreach_reply_handler.py`
  classifies every received reply with a small fixed rubric
  (`OPT_OUT_RUBRIC`) before the full Sonnet re-evaluation: if the business is
  explicitly asking not to be contacted again, `handle()` sets
  `places.outreach_opt_out = true`, logs
  `outreach_reply_opt_out_detected`, and returns without ever calling the
  Sonnet `RUBRIC` — saving that cost and correctly treating "stop contacting
  us" as contact preference, not GF-safety evidence (`places.status` is
  untouched). **Fails closed toward "not opt-out"** on any classifier error
  (a missed opt-out just falls through to the existing, already-conservative
  Sonnet path; a false positive would permanently block a legitimate
  business, since there's no unset path for `outreach_opt_out` in this
  design) — the inverse of the health-rubric's own "escalate when unsure"
  bias, deliberately, because the two failure directions have opposite
  costs. Full text and a worked example: prompts.md §21.
- **Two distinct secret stores, on purpose.** `RESEND_WEBHOOK_SECRET` and
  `GITHUB_DISPATCH_TOKEN` (a fine-grained PAT scoped to this repo only) are
  Supabase Edge Function secrets (`supabase secrets set`) — they're only
  ever needed inside the Edge Function, never in `.env` or GitHub Actions
  secrets. `.github/workflows/outreach-reply.yml` reuses the same three
  GitHub Actions secrets `agents-monthly.yml` already has
  (`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`/`ANTHROPIC_API_KEY`) — no new
  ones needed there, since the Python side never calls Resend or GitHub
  itself.

### Community reports (`place_reports`) design decisions

Proposed (not yet built) in
`docs/architecture/ADR-004-community-reports-evidence-not-direct-action.md`
(Estado: Propuesto) and `docs/plans/PLAN-community-reviews.md`. Lets anyone
recommend or report on a place **already published** on the map — distinct
from `suggestions`, which is for places not yet published. Same governing
principle as Outreach (ADR-002): a report never modifies `places` directly,
only reinjects evidence into the same Validator rubric.

- **Reuses Etapa 2's exact pattern; one real difference.** The planned
  `agents/review_handler.py` reuses `RUBRIC` / `ValidatorAgent._normalize`
  unmodified, same reuse discipline as `outreach_reply_handler.py` — but
  with **no status remapping**: since the place being reported on is
  already `approved` (unlike outreach's `needs_review` starting point), the
  Validator's own verdict (approved/needs_review/discarded) is trusted
  directly instead of being funneled through a distinct
  `outreach_confirmed`-style intermediate state.
- **Trigger — a Supabase Database Webhook, not a Resend webhook.** `INSERT`
  on `place_reports` (`report_type='negative'` + place `approved`) fires a
  Database Webhook → a new Edge Function (`place-report-created`) →
  `repository_dispatch` → a new workflow → `review_handler.py`, mirroring
  outreach's Etapa 2 chain exactly except for the trigger source.
- **Database Webhooks don't auto-retry — a monthly sweep is the
  mitigation.** Confirmed (official docs + a GitHub discussion with no
  maintainer reply) that, unlike the Resend webhook redelivery outreach's
  Etapa 2 relies on, Supabase Database Webhooks do **not** retry on a
  non-2xx response or a timeout. `ReviewHandler.sweep()` — planned as an
  8th pipeline stage in `scripts/run_agents.py`, budgeted like every other
  agent (`MAX_REVIEW_SWEEP_PER_RUN`) — re-drives anything left stuck in
  `place_reports.status` `new`/`dispatched`. An atomic claim
  (`claim_place_report`, CAS on `status`, new state `processing`) is the
  single guard that makes the real-time path and the monthly sweep safe to
  race against each other — whichever reaches the claim first does the
  work; the other is a no-op.
- **`suggestions.origin` added for the report form's no-match fallback.** A
  report typed against the autocomplete with no match routes into the
  existing `suggestions` pipeline instead of a dead end in `place_reports`
  (which has nothing to auto-re-evaluate without a `place_id`). `origin`
  (`'community'` default, `'business'` reserved unused) distinguishes
  writers; `js/suggest.js` now sends `origin: 'community'` explicitly
  rather than relying on the column default silently.
- **Schema-migration lesson (applies beyond this feature).** Preparing this
  schema surfaced a real bug already living in `db/schema.sql`: a chain of
  `do $$ ... drop/add constraint ... check(...) ... end $$;` blocks that
  incrementally *widen* a CHECK is only safe to apply **one block at a
  time, as each ships** — replaying the whole file fresh once real
  production data has accumulated past an early, narrower block makes that
  block fail outright (`ALTER TABLE ... ADD CONSTRAINT` validates against
  every existing row at the moment it runs, not just the file's final
  state). Found in `places_status_check` (a stale 4-value block predating
  `outreach_confirmed`, which real rows already use) and confirmed the same
  latent bug in `agent_log_agent_check`'s 4-block chain via a **read-only**
  `supabase db query --linked` check against production (19
  `agent='outreach'` rows, 6 `agent='outreach_reply'` rows would have broken
  it). Both collapsed to one final block each. Going forward, a superseded
  intermediate widening step should be deleted, not kept as history, once
  superseded.
- **Tooling correction — the Supabase CLI is installed.** `node_modules/.bin/supabase`
  (npm `devDependency`, v2.111.0), not on the system `PATH` — already
  linked and authenticated to the real `celiacmap` project. `supabase db
  query --linked --file <path>` can execute SQL directly against
  production; `supabase db query --linked "<sql>"` was used read-only to
  verify the bug above. Corrects an earlier claim made in this same session
  that no CLI was available — worth remembering so future sessions don't
  re-discover it the hard way.

### Frontend design audit (frontend-design + web-design-guidelines + ui-ux-pro-max)

Three third-party Claude Code skills were installed as **project skills** under
`.claude/skills/` (not committed to `skills/`, which is the academic AI-toolkit
deliverable — see **AI Toolkit** above) and used for a targeted design-review
pass over the existing editorial redesign, not a rebuild:

- **`frontend-design`** (`anthropics/skills`) — aesthetic-distinctiveness review.
- **`web-design-guidelines`** (`vercel-labs/agent-skills`) — fetches the live
  Vercel Web Interface Guidelines at review time and checks compliance.
- **`ui-ux-pro-max`** (`nextlevelbuilder/ui-ux-pro-max-skill`) — searchable
  UI/UX rule database (styles, palettes, typography, touch/a11y rules) via a
  bundled Python CLI (`scripts/search.py`); ~1.8 MB, not just a `SKILL.md`.

**Findings applied to `index.html` / `css/styles.css` / `js/main.js`:**
- Touch targets under the 44×44px guideline (`.chip`, `.nav-toggle`,
  `.map-search-clear`, `.place-panel-close`) — fixed via invisible hit-area
  expansion (`::before` insets) where enlarging the visible control would hurt
  the compact editorial look, and a direct size bump for `.place-panel-close`
  (a corner control with room to grow).
- Missing `.chip:hover` state, missing `overscroll-behavior: contain` and
  `env(safe-area-inset-bottom)` on the mobile place-panel bottom sheet, missing
  `touch-action: manipulation` / `-webkit-tap-highlight-color`, missing
  `text-wrap: balance` on headings, missing `preconnect` for the `unpkg.com`
  Leaflet CDN.
- Literal `...` and straight quotes in the ES review pull-quotes and map
  search placeholder — the EN dictionary in `main.js` already used curly
  quotes/ellipsis; ES (the source-of-truth markup) did not.
- `.step-line .step-num` was declared in HTML but never styled — the two
  numbered-step sequences ("La solución" and "Sumá un lugar") rendered
  identically. Gave the second one a smaller circular badge treatment (reusing
  the existing `.card-icon` visual language) so repeating the 01/02/03 device
  twice doesn't read as one decorative habit.
- **One deliberate aesthetic risk, per `frontend-design`'s "spend your
  boldness in one place":** replaced the `.ai-orb` — a generic glowing-circle
  "AI" cliché — with a small radar/pin-constellation motif (`.ai-radar`,
  reusing the same brand pin SVG used in the header/hero/footer, with a
  pulsing scan ring), grounded in what the AI section actually describes
  (agents discovering and validating pins on a map) instead of an abstract
  orb. Scoped to one section; the rest of the established palette/typography
  (documented under **Editorial redesign** above) was intentionally left
  untouched — this was a compliance-and-polish pass, not a new design system.
- Verified live in Chrome against the real Supabase-backed map (place markers,
  the place-detail panel with real data, filter-chip hover, reveal timing) with
  zero console errors; the harness's window-resize tool would not reliably
  force a mobile viewport for screenshotting, so the safe-area / bottom-sheet
  CSS was verified by inspection rather than a mobile screenshot.

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
- ✅ **Phase 8 — GitHub Actions scheduled cron.** `.github/workflows/agents-monthly.yml`
  runs the pipeline on a schedule (09:00 UTC) and on manual `workflow_dispatch`
  (with a `dry_run` toggle and optional `budget` override). Secrets come from
  GitHub Actions Secrets; `.env.example` documents every variable. CI actions are
  pinned to Node 24 majors (`checkout@v5`, `setup-python@v6`). _(Schedule switched
  from daily to **monthly** — `0 9 1 * *`, the 1st of each month — and the workflow
  renamed `agents-daily.yml` → `agents-monthly.yml`, Jun 2026.)_
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
- ✅ **Phase 11 — Web discovery agent (v3, autonomous).** `agents/web_agent.py`
  gives Claude (`claude-sonnet-4-6`) the Anthropic server-side web search tool and
  a single city, letting it reason freely about where to find gluten-free / sin
  TACC places (forums, blogs, FB groups, Instagram, news) instead of a fixed query
  matrix. Leads are geocoded via Google Find Place, deduplicated across sources,
  and inserted as `pending` with `source='web'`. The pipeline now runs
  **search → social → web → validator → updater** under the shared budget. New env
  vars: `WEB_SEARCH_MODEL`, `MAX_WEB_CITIES_PER_RUN`, `MAX_WEB_SEARCHES_PER_CITY`.
  Rollout is opt-in per city via `web: true` (Montevideo + Buenos Aires to start).
  Design rationale: **Web discovery agent (v3) design decisions** above. Code
  complete with 16 offline tests; first live standalone run on Montevideo is the
  next verification step before enabling it in the full daily pipeline.
  - **⚠️ Disabled in the daily pipeline (Jun 2026).** A live daily run with
    `web: true` on Montevideo + Buenos Aires **timed out the 30-min CI job**: each
    city's autonomous web search took ~10–16 min, and Montevideo's final turn
    exhausted its continuation budget while still searching, returning empty
    (non-JSON) output (`JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
    from `LLMClient.research_with_web_search`). The `web: true` flags were commented
    out in `config/targets.yaml`, so the daily pipeline runs
    **search → social → suggestion → validator → updater** reliably. Re-enabling the
    Web agent requires fixing (a) per-city latency / continuation budget and
    (b) the empty-final-text → JSON parse path, then a standalone verification —
    exactly the gate this phase already called for.
- ✅ **Phase 12 — AI Toolkit (prompts + Skill + MCP server) & three-tier rubric.**
  Added an academic "Toolkit de IA": documented prompts (`prompts.md` §12–13), a
  reusable Skill (`skills/validator-rubric/SKILL.md`), and an MCP server
  (`mcp_server/server.py` + `README.md`) exposing 6 tools (`search_places`,
  `get_place_detail`, `validate_place`, `suggest_place`, `get_map_stats`,
  `list_pending_reviews`) over Supabase + the canonical Validator rubric. The
  Validator rubric was **deliberately changed** from `approve`/`discard` to a
  three-tier `approved`/`needs_review`/`rejected` verdict with `confidence_score`,
  `flags`, `recommendation` and code-enforced 0.85/0.7/0.5 gates (see **AI Toolkit**
  in the Decisions Log and the Core Prompt section). Schema gained the
  `needs_review` status plus `flags`/`recommendation` columns (idempotent). New
  dependency: `fastmcp`. The MCP `validate_place` tool and the daily Validator share
  one `RUBRIC`. Full offline suite green (122 tests). The MCP server imports
  cleanly; a first live `validate_place` / `suggest_place` smoke test against
  Supabase is the next verification step.
- ✅ **Phase 13 — Suggest-a-Place public form (community Phase 2).** A real form in
  the `#suggest` section of `index.html` (+ `js/suggest.js`, bilingual via the
  existing `data-i18n` system) lets anyone submit a place anonymously. The browser
  writes raw input into a new anon-INSERT-only **`suggestions`** table; the daily
  pipeline's new **Suggestion promoter** (`agents/suggestion_agent.py`) geocodes via
  Google Find Place, dedups, and promotes each into `places` as `pending`
  (`source='user'`) for the Validator. The pipeline now runs
  **search → social → web → suggestion → validator → updater** under the shared
  budget. Spam defenses: honeypot + min-fill-time + cooldown (client), INSERT-only
  length-bounded RLS (server), and the geocode + Validator gates as backstops. The
  MCP `suggest_place` tool was refactored to share `promote_suggestion`. New env var:
  `MAX_SUGGESTIONS_PER_RUN`. Schema gained the `suggestions` table + RLS and
  `agent_log.agent='suggestion'` (idempotent). Full offline suite green (133 tests,
  +11). Design rationale: **Suggest-a-Place public form design decisions** above.
  Next verification: apply `db/schema.sql`, submit a test suggestion from the form
  (expect `201` + a `new` row), then a live pipeline run promoting it to `pending`.
- 🚧 **Phase 14 — Outreach Agent (schema only).** `db/schema.sql` gained
  `places.outreach_status` (`not_sent`/`sent`/`replied`/`no_response`, default
  `not_sent`), `places.outreach_channel` (`email`/`whatsapp`, nullable), a new
  `places.status` value `outreach_confirmed` (widened `places_status_check`,
  additive per ADR-002 — never reached by auto-approval), and a new
  `outreach_messages` table (full send/reply audit thread, RLS-locked like
  `agent_log`: service_role only, no anon/authenticated access). Design
  rationale: `docs/plans/PLAN-outreach-agent.md` and
  `docs/architecture/ADR-002-outreach-evidence-not-autoapproval.md`. Schema-only
  step — `agents/outreach_agent.py`, the `agent_log.agent='outreach'` CHECK
  widening, and a `contact_email` source are still unscoped (plan's "Fase 0").
  Not applied to the live database yet; `db/schema.sql` is the proposal,
  applied manually in the Supabase SQL Editor per this project's established
  migration workflow.
- 🚧 **Phase 15 — Outreach Agent (`outreach_send` implemented).**
  `agents/outreach_agent.py` (`OutreachAgent`) and `agents/clients/resend_client.py`
  (thin Resend wrapper, mirrors `tavily_client.py`'s style) are code-complete
  and wired into `scripts/run_agents.py` as the pipeline's 7th stage
  (**search → social → web → suggestion → validator → updater → outreach**),
  sharing the combined `AGENT_DAILY_BUDGET` via the same `budget.allow(cap)`
  pattern as the Validator/Updater. Selects the oldest `needs_review` places
  with `phone`/`website` on file and `outreach_status='not_sent'`, drafts a
  confirmation email with `claude-haiku-4-5`, and sends it via Resend — to a
  fixed `OUTREACH_TEST_RECIPIENT` for now (sandbox constraint, see **Outreach
  agent design decisions** above). New env vars: `RESEND_API_KEY`,
  `OUTREACH_TEST_RECIPIENT`, `OUTREACH_MONTHLY_LIMIT` (default 20). New
  dependency: `resend>=2,<3`. Full offline suite green (144 tests, +9), plus a
  fully-mocked `run_pipeline()` smoke test confirming the new stage threads
  through the budget/summary/dry-run machinery correctly with zero real
  network calls. The `agent_log.agent='outreach'` CHECK-widening addendum
  proposed alongside Phase 14 has been applied and verified live — a
  Supabase query confirms `agent_log` rows with `agent='outreach'`,
  `status='success'` (actions `outreach_sent`, `outreach_run_complete`).
  **Still required before this is live:** set `RESEND_API_KEY` /
  `OUTREACH_TEST_RECIPIENT` in `.env` / GitHub Secrets. Next verification: a
  standalone `python -m agents.outreach_agent` run against a real
  `needs_review` row, confirming the test inbox receives the email and
  `outreach_messages` / `places.outreach_status` update accordingly.
  **Etapa 2 (`outreach_reply_handler`, the reply webhook) is not built** —
  out of scope for this phase.
- 🚧 **Phase 16 — Outreach Agent (`contact_email` website scraper).**
  `agents/clients/website_scraper.py` (`WebsiteScraperClient`) is a
  deterministic, zero-API-cost scraper that fetches a candidate's own
  (non-social) website home page and looks for a `mailto:` link or a visible
  email address, filtering out `facebook.com` / `instagram.com` / `wa.me` /
  `whatsapp.com` / `beacons.ai` / `linktr.ee` first (confirmed live: 40 of
  the 68 `needs_review` places with a website on file are exactly these
  profile pages). `OutreachAgent._scrape_missing_emails` runs as the first
  step of `run()`, before `_select_candidates`, for eligible places
  (non-social website, `contact_email_checked_at` still null), persists
  `places.contact_email` (or `null`) and always stamps
  `contact_email_checked_at`, and is capped by a new
  `max_email_scrapes_per_run` setting (default 30, env
  `MAX_EMAIL_SCRAPES_PER_RUN`) — see **Outreach agent design decisions**
  above for the full rationale. New dependency: `requests>=2.34,<3` (was
  already a transitive dependency; now pinned directly since CeliacMap's own
  code imports it). Full offline suite green (169 tests, +25), including the
  repo's first transport-level HTTP mock (`tests/test_website_scraper.py`).
  `places.contact_email` / `contact_email_checked_at` were added to
  `db/schema.sql` in a prior session; whether that migration has been
  applied to the live database is the remaining gate before this can run for
  real. Next verification: apply the migration if not already live, then a
  standalone `python -m agents.outreach_agent` run confirming `contact_email`
  / `contact_email_checked_at` populate for real `needs_review` places and
  aren't re-scraped on a second run.
- ✅ **Phase 17 — Outreach Agent Etapa 2 (reply webhook, verified live end
  to end).** `supabase/functions/outreach-reply/index.ts`
  (this repo's first Edge Function), `.github/workflows/outreach-reply.yml`,
  and `agents/outreach_reply_handler.py` implement the full reply flow —
  webhook receipt → Python re-evaluation reusing `RUBRIC` /
  `ValidatorAgent._normalize` unmodified → `outreach_confirmed` /
  `needs_review` / `discarded`. See **Outreach reply webhook (Etapa 2)
  design decisions** above for the full architecture and every design
  choice. `agents/outreach_agent.py` and `agents/clients/resend_client.py`
  gained `reply_to` support (`OUTREACH_INBOUND_DOMAIN` setting). Schema
  additions proposed in `db/schema.sql` (not yet applied):
  `outreach_messages.external_id` + a unique `(place_id, external_id)`
  constraint, and `agent_log.agent` widened for `'outreach_reply'`. Full
  offline suite green (183 tests, +14). Deno was installed and
  `deno check` run for real against the Edge Function (not just the
  editor's Node-based TS server, which can't resolve `npm:` specifiers or
  the `Deno` global) — it caught a genuine bug: `resend@4.8.0`'s typed SDK
  has no `emails.receiving` namespace at all (an assumption from Resend's
  docs alone, not the installed package), fixed by calling the SDK's own
  public low-level `resend.get<T>('/emails/receiving/{id}')` instead, the
  same method every typed resource in the SDK is itself built on. Also
  restructured `Deno.serve(...)` behind an `import.meta.main` guard
  (`export function handleRequest`) after `deno test` revealed the webhook
  handler was starting a live HTTP server as an import side-effect merely by
  importing the file for its pure `extractPlaceId` helper. `deno check`
  passes clean on both `index.ts` and `index.test.ts`; `deno test` passes
  6/6.

  **Verified live with real data.** The Edge Function is deployed and
  working (Resend shows a `200 OK` / Success delivery). A full cycle was
  confirmed end to end: `outreach_send` → a real business-style reply →
  Resend's `email.received` webhook → the Edge Function (signature
  verified, reply persisted, `outreach_status` flipped) →
  `repository_dispatch` → `agents/outreach_reply_handler.py` →
  re-evaluation through the unmodified `RUBRIC` → result: `needs_review`
  maintained at confidence `0.72` — correctly held below the `0.85`
  auto-confirm threshold, since the reply was an uncorroborated business
  self-report with no external evidence. ADR-002 behaving exactly as
  designed: the reply strengthened the evidence but did not fast-track
  approval.

  **Operational note — Edge Function JWT verification.** The dashboard's
  "Verify JWT with legacy secret" toggle must stay **OFF** for this
  function (Resend's webhook calls have no Supabase auth JWT). The
  Supabase CLI's `--no-verify-jwt` deploy flag did not apply reliably (a
  known Supabase CLI issue) — resolved by disabling the toggle manually in
  the Supabase dashboard instead of via deploy flags.

- 🚧 **Phase 18 — ADR-003 accepted: opt-out detection + `OUTREACH_LIVE_MODE`
  (all three conditions met, real send not yet verified live).** Closes the
  gap Phase 15/16 left open (sandbox-only sending) by implementing every
  condition `docs/architecture/ADR-003-outreach-real-send-conditions.md`
  requires before contacting real businesses:
  1. **Domain verified** — `celiacmap.org` verified with Resend (DKIM, SPF,
     send + receive MX) on 2026-08-04.
  2. **Opt-out mechanism** — a fixed, non-AI-generated footer on every
     outreach email plus a Haiku pre-check in
     `agents/outreach_reply_handler.py` that sets
     `places.outreach_opt_out = true` and excludes the place from all future
     selection, fail-closed toward "not opt-out" on classifier error. See the
     new bullets under **Outreach agent design decisions** and **Outreach
     reply webhook (Etapa 2) design decisions** above, and prompts.md §21.
  3. **Bounded volume** — `OUTREACH_MONTHLY_LIMIT=3` (not the code default of
     20) in `agents-monthly.yml`.

  The actual send-routing switch is `Settings.outreach_live_mode`
  (`OUTREACH_LIVE_MODE`, default `false`): when `true`,
  `agents/outreach_agent.py` sends to `place["contact_email"]` instead of
  `OUTREACH_TEST_RECIPIENT`, with no shared code path between the two modes
  and a defense-in-depth skip (`outreach_send_missing_contact_email`) if a
  live-mode candidate somehow has no `contact_email`. See the
  `OUTREACH_LIVE_MODE` bullet under **Outreach agent design decisions** above.

  Along the way, manually reviewing the first 3 real live-mode candidates
  before activating surfaced and fixed a `website_scraper.py` false-positive
  bug (image-filename and platform-domain emails — see the updated
  `contact_email` bullet above) and one duplicate listing (resolved via
  `outreach_opt_out=true`).

  **CI wiring completed this session:** `OUTREACH_LIVE_MODE` is now a GitHub
  Secret (set to `true`) and forwarded into `agents-monthly.yml`'s `env:`
  block for the `run-agents` job, alongside `RESEND_API_KEY` /
  `OUTREACH_TEST_RECIPIENT`. This means **the next monthly cron run (1st of
  the month) will send real outreach email to a real business**, not the
  test recipient. Full offline suite green (202 tests). **Not yet verified
  live:** a real send to a `contact_email` recipient with live mode on has
  not been observed end-to-end (bounce/delivery, opt-out reply, and a normal
  reply all still need a live confirmation) — the standalone verification
  called for in Phase 15/16 now applies specifically to live mode.
- 🚧 **Phase 19 — Community reports (`place_reports`), schema prepared.**
  `db/schema.sql` gained the `place_reports` table (`report_type`
  positive/negative, nullable `place_id` + `place_name_text` fallback, and a
  processing-state `status` including `processing` for the claim-based
  idempotency guard — see **Community reports (`place_reports`) design
  decisions** above), `suggestions.origin`, RLS for both, and a widened
  `agent_log.agent` CHECK for `'review_handler'`. `js/suggest.js` sends
  `origin: 'community'` explicitly. Design rationale:
  `docs/architecture/ADR-004-community-reports-evidence-not-direct-action.md`
  (Propuesto) and `docs/plans/PLAN-community-reviews.md`. Along the way, a
  real bug already living in `db/schema.sql` was found and fixed — duplicate/
  superseded `CHECK`-widening blocks unsafe to replay against current
  production data (see the schema-migration lesson above) — unrelated to
  this feature but blocking a first full fresh apply of the file.
  Re-validated with `pglast` (a local Postgres-parser syntax check) after
  every edit: 0 errors, 64 statements. **Applied live to Supabase** (pasted
  manually into the SQL Editor, ran to `success`) and verified read-only
  via `supabase db query --linked`: `place_reports` exists,
  `suggestions.origin` defaults to `'community'`, and both fixed
  constraints (`places_status_check` with its 5 values,
  `agent_log_agent_check` with its 10) hold exactly as written — no data
  was harmed by the earlier duplicate-CHECK bug, since it was caught before
  this apply. Still unbuilt: Fase 2 (`agents/review_handler.py`, the
  `place-report-created` Edge Function, its workflow) and Fase 3 (the
  frontend report form) — see the plan's remaining phases.

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

- Three-tier validation rubric: see
  docs/architecture/ADR-001-three-tier-validation-rubric.md
- C4 diagrams in Mermaid `flowchart` instead of `C4Context`/
  `C4Container`: GitHub's native renderer shows overlapping text
  with the dedicated C4 syntax; `flowchart` with subgraphs
  preserves the same semantic levels (context and containers) and
  renders reliably with no additional installation required. See
  docs/architecture/C4-diagrams.md.
- Outreach Agent: respuesta del comercio como evidencia adicional,
  no aprobación automática — ver
  docs/architecture/ADR-002-outreach-evidence-not-autoapproval.md
- Outreach Agent: condiciones para habilitar envío real a comercios
  (dominio verificado, opt-out, volumen acotado) — ver
  docs/architecture/ADR-003-outreach-real-send-conditions.md
- C4 diagrams actualizados (post Entregable 2) para reflejar el
  Outreach Agent (Etapa 1 y 2): Nivel 1 agrega Resend como sistema
  externo (envío + webhook de respuesta); Nivel 2 agrega el
  contenedor Edge Function (`supabase/functions/outreach-reply/`) y
  la cadena `Resend → Edge Function → GitHub Actions
  (repository_dispatch) → outreach_reply_handler.py`, y el pipeline
  pasa a listar sus 7 etapas reales en orden (`search → social → web
  → suggestion → validator → updater → outreach`) más el Reply
  Handler on-demand. Ver docs/architecture/C4-diagrams.md.