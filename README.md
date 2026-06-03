# CeliacMap

A digital platform that helps the celiac / "sin TACC" community find safe,
gluten-free places — on a real interactive map, kept fresh by AI agents.

## Goal

Help people with celiac disease or gluten intolerance find trusted, verified
places nearby, starting in Uruguay and Argentina and scaling across Latin America.

## Status

🚧 Evolving from a portfolio landing page into a functional product.

- ✅ Landing page (single page, fully responsive, bilingual ES/EN).
- 🔜 Real Leaflet map backed by Supabase.
- 🔜 Python agents (Search, Validator, Updater) automated via GitHub Actions.

See [`CLAUDE.md`](CLAUDE.md) → **Architecture** for the full technical design.

## Tech Stack

**Frontend**
- HTML5 (semantic), CSS3 (mobile-first, custom properties, no frameworks)
- JavaScript (vanilla — nav, language toggle, scroll reveal, map)
- [Leaflet.js](https://leafletjs.com/) for the interactive map
- [Playfair Display](https://fonts.google.com/specimen/Playfair+Display) +
  [DM Sans](https://fonts.google.com/specimen/DM+Sans) via Google Fonts

**Backend & data**
- [Supabase](https://supabase.com/) (PostgreSQL + REST API + Auth), read via the
  public anon key with Row Level Security

**Agents & automation**
- Python agents: Search (Google Places API), Validator (Anthropic Claude —
  `claude-sonnet-4-6`), Updater
- [GitHub Actions](https://docs.github.com/actions) daily cron

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
├── agents/                     # Python agents (search, validator, updater)
│   └── clients/                # supabase / google places / llm wrappers
├── config/                     # settings.py + targets.yaml (geo scope)
├── scripts/                    # run_agents.py, load_seed.py
├── db/                         # schema.sql, seed.sql
├── .github/workflows/          # agents-daily.yml (cron)
├── requirements.txt
├── .env.example
└── README.md  CLAUDE.md  prompts.md  .gitignore
```

> Note: the `agents/`, `config/`, `scripts/`, `db/` and workflow files are part of
> the approved architecture and are being added incrementally — see `CLAUDE.md`.

## How to Run

### Frontend

Open `index.html` in your browser — no build step. The map reads public,
read-only data from Supabase using the anon key in `js/config.js`.

### Agents (Python)

```bash
cp .env.example .env          # fill in Supabase service_role + API keys
pip install -r requirements.txt
python scripts/run_agents.py  # runs search → validator → updater
```

Secrets (Supabase `service_role`, Google Places, Anthropic) live only in `.env`
locally and in GitHub Actions Secrets — never in the frontend. In production the
agents run automatically once per day via GitHub Actions.

## Live Demo

Coming soon.

## Repository

Coming soon.

## Author

Santiago Sanchez — [\[LinkedIn\]](https://www.linkedin.com/in/santisanchez4/) - [\[gitHub\]](https://github.com/santisanchez4/CeliacMap)