# CeliacMap

A digital platform that helps the celiac / "sin TACC" community find safe,
gluten-free places — on a real interactive map, kept fresh by AI agents.

## Goal

Help people with celiac disease or gluten intolerance find trusted, verified
places nearby, starting in Uruguay and Argentina and scaling across Latin America.

## Status

🚧 Evolving from a portfolio landing page into a functional product.

- ✅ Landing page (single page, fully responsive, bilingual ES/EN).
- ✅ Supabase backend (`places` / `reviews` / `agent_log`, RLS, manual UY/AR seed).
- ✅ Live Leaflet map backed by Supabase (reads approved places, category filters).
- ✅ **Search agent** — discovers places via Google Places, inserts candidates as
  `pending`.
- ✅ **Validator agent** — Claude `claude-sonnet-4-6` approves or discards each
  pending candidate (structured verdict + confidence/notes).
- ✅ **Updater agent** — re-checks approved places via Google Places; closes /
  updates / flags. Deterministic, with a narrow Haiku fallback.
- ✅ **Pipeline orchestrator** (`scripts/run_agents.py`) — runs all three agents
  under one combined daily budget, with a `--dry-run` mode.
- ✅ **GitHub Actions daily cron** — runs the pipeline once per day (manual
  `workflow_dispatch` with a dry-run toggle for validation).

See [`CLAUDE.md`](CLAUDE.md) → **Architecture** for the full technical design.

## Tech Stack

**Frontend**
- HTML5 (semantic), CSS3 (mobile-first, custom properties, no frameworks)
- JavaScript (vanilla — nav, language toggle, scroll reveal, map)
- [Leaflet.js](https://leafletjs.com/) — interactive map
- Google Fonts — [Playfair Display](https://fonts.google.com/specimen/Playfair+Display)
  + [DM Sans](https://fonts.google.com/specimen/DM+Sans)

**Backend / Database**
- [Supabase](https://supabase.com/) — PostgreSQL + REST API + Row Level Security
  (the browser reads only approved data via the public anon key)

**Agents**
- Python 3.14
- [Anthropic API](https://docs.anthropic.com/) (`claude-sonnet-4-6`) — Validator
- [Google Places API](https://developers.google.com/maps/documentation/places/web-service) — Search
- Key libraries: `supabase` (supabase-py), `anthropic`, `googlemaps`,
  `python-dotenv`, `PyYAML`

**Automation (upcoming)**
- [GitHub Actions](https://docs.github.com/actions) — daily cron job

## Architecture

CeliacMap has three layers:

1. **Frontend** — static site + Leaflet map that reads **approved** places from
   Supabase and filters them by category (Restaurants, Cafés, Shops).
2. **Database** — Supabase Postgres (`places`, `reviews`, `agent_log`) with RLS so
   the browser can only read approved data.
3. **Agents** — a daily Python pipeline: **Search** finds candidates via Google
   Places (status `pending`) → **Validator** uses Claude to approve/discard →
   **Updater** keeps published places current. Orchestrated by GitHub Actions.

Full details, schema, and design decisions: [`CLAUDE.md`](CLAUDE.md#architecture).

## Design

Editorial, minimal and warm — closer to a high-end health/lifestyle brand than a
corporate SaaS page. Refined green palette (deep `#1a3a2a` / `#2d6a4f`, soft
`#52b788` / `#b7e4c7`) on warm off-white backgrounds (`#fdfaf5` / `#f8f4ee`),
serif display headings over a clean sans body, and generous spacing.

## Features

- 12 sections: Hero, Problem, Solution, Features, Interactive Map, Suggest a Place,
  Reviews, AI & Agents, Roadmap, About, Call to Action, Footer.
- Bilingual interface: Spanish (default, "sin TACC") with a client-side ES/EN
  toggle (remembered via `localStorage`).
- Conceptual interactive map built entirely with HTML/CSS (no map library).
- Accessible: semantic landmarks, skip link, focus styles, reduced-motion support.

## Project Structure

```txt
/
├── index.html                  # frontend shell + Leaflet map
├── css/styles.css
├── js/
│   ├── main.js                 # i18n, nav, reveal
│   ├── config.js               # Supabase URL + anon key (public)
│   └── map.js                  # Leaflet + Supabase data + filters
├── assets/{images,icons}/
├── agents/                     # Python agents
│   ├── base.py                 # shared base + agent_log helper
│   ├── search_agent.py         # ✅ Google Places → pending candidates
│   ├── validator_agent.py      # 🚧 Claude approves/discards pending
│   └── clients/                # supabase_client / google_places / llm wrappers
├── config/
│   ├── settings.py             # env-driven config (python-dotenv)
│   └── targets.yaml            # countries/cities + search terms
├── scripts/
│   └── check_setup.py          # connectivity / config preflight
├── db/
│   ├── schema.sql              # tables, constraints, indexes, RLS, triggers
│   └── seed.sql                # manual seed (UY/AR)
├── requirements.txt
├── .env.example
└── README.md  CLAUDE.md  prompts.md  .gitignore
```

> Note: the Updater agent, `scripts/run_agents.py` orchestration, and the
> `.github/workflows/` daily cron are part of the approved architecture and are
> still upcoming — see `CLAUDE.md` → **Build status**.

## How to Run

### Frontend

Open `index.html` in your browser — no build step. The map reads public,
read-only data from Supabase using the anon key in `js/config.js`.

### Agents (Python)

```bash
cp .env.example .env             # fill in Supabase service_role + API keys
pip install -r requirements.txt
python scripts/check_setup.py    # preflight: config + connectivity

# Run the full pipeline (search → validator → updater) under one daily budget:
python -m scripts.run_agents --dry-run   # rehearse: no database writes
python -m scripts.run_agents             # real run

# …or run any stage on its own:
python -m agents.search_agent    # discover candidates  → pending
python -m agents.validator_agent # approve / discard pending
python -m agents.updater_agent   # re-check approved places
```

In production the pipeline runs automatically once per day via the
`Agents — daily pipeline` GitHub Actions workflow
([`.github/workflows/agents-daily.yml`](.github/workflows/agents-daily.yml)); it
can also be triggered manually (with a dry-run toggle) from the Actions tab.

Secrets (Supabase `service_role`, Google Places, Anthropic) live only in `.env`
locally and in GitHub Actions Secrets — never in the frontend.

## Live Demo

Coming soon.

## Repository

Coming soon.

## Author

Santiago Sanchez — [\[LinkedIn\]](https://www.linkedin.com/in/santisanchez4/) - [\[gitHub\]](https://github.com/santisanchez4/CeliacMap)