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
    with status "pending". Deterministic (no LLM by default).
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
  seed / agent / user reviews. `rating` is constrained to 1–5.
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
- 🚧 **Phase 6 — Validator agent (in progress).** `agents/validator_agent.py`
  built; pending a live validation run over the 80 candidates.
- 🔜 **Phase 7+ — Updater agent, `scripts/run_agents.py` orchestration, and the
  GitHub Actions daily cron.**