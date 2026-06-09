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
- GitHub Actions cron job (free tier): runs all agents once per day.
- Manual workflow_dispatch is used to validate the pipeline before
  enabling the daily cron.

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
- **Web (v3) → `claude-sonnet-4-6`** with the Anthropic web search tool. Unlike
  the cheap Social parse, this is a genuinely agentic task — the model writes its
  own queries, reads forums/blogs/IG/FB, and extracts candidates with evidence.
  Sonnet 4.6 is the cost/quality balance for a recurring daily batch; upgradeable
  to `claude-opus-4-8` via the `WEB_SEARCH_MODEL` env var (one-line flip, no code
  change) if discovery quality proves weak. The Sonnet Validator still gates every
  web candidate, and every lead must geocode to a real Google `place_id`, so a
  hallucinated place is dropped before it can be published.
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
│   └── clients/{supabase_client,google_places,tavily_client,llm}.py
├── mcp_server/                 # AI toolkit — MCP server
│   ├── server.py               # 6 tools over Supabase + the Validator rubric
│   └── README.md
├── skills/                     # AI toolkit — reusable skills
│   └── validator-rubric/SKILL.md
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
├── .github/workflows/{agents-daily,deploy-pages}.yml
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
- **Model — `claude-sonnet-4-6`** (see the Web bullet under **AI model
  decisions**); `WEB_SEARCH_MODEL` allows a one-line upgrade to `claude-opus-4-8`.

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