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
  `pending`, and enriches them with gluten-free review snippets.
- ✅ **Social agent** — discovers public Instagram / Facebook pages via the Tavily
  Search API, parses each lead with `claude-haiku-4-5`, geocodes it via Google
  Find Place, and inserts candidates as `pending`. _(Live: a run inserted 30 social
  candidates; the Validator approved 23.)_
- ✅ **Web agent (v3, autonomous)** — hands `claude-sonnet-4-6` the Anthropic web
  search tool and a single city, letting it reason freely about where to find
  gluten-free / sin TACC places (forums, blogs, FB groups, Instagram, news) instead
  of a fixed query matrix; geocodes each lead, dedups across sources, inserts as
  `pending` (`source='web'`). Opt-in per city via `web: true` in `targets.yaml`
  (Montevideo + Buenos Aires to start).
- ✅ **Suggest a Place form** — a public form (no login) lets anyone submit a
  gluten-free / sin TACC place that isn't on the map yet. The browser writes raw
  input (no coordinates) into a `suggestions` table via the anon key (RLS:
  INSERT-only); the daily **Suggestion promoter** geocodes each via Google Find
  Place, dedups, and promotes it into `places` as `pending` (`source='user'`) for
  the Validator to judge. Honeypot + timing + cooldown guard against spam.
- ✅ **Validator agent** — Claude `claude-sonnet-4-6` approves or discards each
  pending candidate (structured verdict + confidence/notes), using stored review
  snippets as extra context.
- ✅ **Updater agent** — re-checks approved places via Google Places; closes /
  updates / flags. Deterministic, with a narrow Haiku fallback.
- ✅ **Pipeline orchestrator** (`scripts/run_agents.py`) — runs all six agents
  (search → social → web → suggestion → validator → updater) under one combined
  daily budget, with a `--dry-run` mode.
- ✅ **GitHub Actions daily cron** — runs the pipeline once per day (manual
  `workflow_dispatch` with a dry-run toggle for validation).
- ✅ **Deployed to GitHub Pages** — the frontend ships automatically from `main`
  via GitHub Actions ([live demo](https://santisanchez4.github.io/CeliacMap/)).
- ✅ **AI Toolkit** — documented prompts ([`prompts.md`](prompts.md)), a reusable
  Skill ([`skills/validator-rubric/SKILL.md`](skills/validator-rubric/SKILL.md)),
  and an **MCP server** ([`mcp_server/`](mcp_server/)) exposing 6 tools over Supabase
  + the Validator rubric for Claude Desktop / Claude Code / external agents.

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
- [Anthropic API](https://docs.anthropic.com/) (`claude-sonnet-4-6` Validator + Web,
  `claude-haiku-4-5` Social/Updater) — incl. the server-side **web search tool**
  (Web agent, v3)
- [Google Places API](https://developers.google.com/maps/documentation/places/web-service) — Search / Social / Web / Updater
- [Tavily Search API](https://tavily.com/) — Social agent (discovers public
  Instagram / Facebook pages)
- Key libraries: `supabase` (supabase-py), `anthropic`, `googlemaps`,
  `tavily-python`, `fastmcp` (MCP server), `python-dotenv`, `PyYAML`

**Automation**
- [GitHub Actions](https://docs.github.com/actions) — daily agent cron + Pages deploy

## Architecture

CeliacMap has three layers:

1. **Frontend** — static site + Leaflet map that reads **approved** places from
   Supabase and filters them by category (Restaurants, Cafés, Shops).
2. **Database** — Supabase Postgres (`places`, `reviews`, `agent_log`,
   `suggestions`) with RLS so the browser can only read approved data and submit
   suggestions (INSERT-only).
3. **Agents** — a daily Python pipeline: **Search** finds candidates via Google
   Places (status `pending`, plus GF review enrichment) → **Social** discovers
   Instagram / Facebook pages via the Tavily Search API → **Web** (v3) uses the
   Anthropic web search tool to discover places from forums/blogs/social →
   **Suggestion** promotes public form submissions into `pending` candidates →
   **Validator** uses Claude to approve/discard → **Updater** keeps published places
   current. Orchestrated by GitHub Actions.

Full details, schema, and design decisions: [`CLAUDE.md`](CLAUDE.md#architecture).

## The Core Prompt — Validator Rubric

> **Por qué este prompt es el corazón del proyecto:** CeliacMap es una herramienta
> de salud — la usan personas celíacas para quienes el gluten es un peligro real,
> no una preferencia. Este rubric es la **única compuerta de calidad** entre lo que
> los agentes descubren automáticamente y lo que se publica en el mapa, y obliga al
> modelo a ser conservador cuando la evidencia es débil. Por eso **no debe perderse
> ni modificarse sin una consideración cuidadosa**: cambiarlo cambia directamente
> qué lugares se aprueban para una comunidad sensible a la salud.

This is the exact system prompt sent to `claude-sonnet-4-6` for every pending
candidate (the `RUBRIC` constant in
[`agents/validator_agent.py`](agents/validator_agent.py)). It is fixed across all
candidates in a run, so it is sent as a **cached system block**; the per-candidate
data goes in the user message. The model must reply with only the structured JSON
verdict `{verdict, confidence_score, category, safety_level, reasoning, flags,
recommendation}`. The **same `RUBRIC`** is reused on-demand by the MCP server's
`validate_place` tool.

**Three-tier verdict + code-enforced gates.** The verdict is `approved` /
`needs_review` / `rejected`, mapped to `places.status` **additively**:
`approved`→`approved`, `rejected`→`discarded`, `needs_review`→`needs_review` (a
human-review tier held back from the map). `ValidatorAgent._decide_status` enforces
the gates regardless of the model's stated verdict: auto-approval requires
`confidence_score >= 0.85`; `< 0.5` (or `rejected`) discards; everything between —
and the `< 0.7` safety floor — becomes `needs_review`.

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
> unsure" rule directly affects which places are approved for celiac users. See
> [`skills/validator-rubric/SKILL.md`](skills/validator-rubric/SKILL.md) for the
> rubric documented as a reusable Skill.

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
│   ├── map.js                  # Leaflet + Supabase data + filters
│   └── suggest.js              # public "Suggest a Place" form → suggestions table
├── assets/{images,icons}/
├── agents/                     # Python agents
│   ├── base.py                 # shared base + agent_log helper
│   ├── search_agent.py         # Google Places → pending candidates (+ reviews)
│   ├── social_agent.py         # Tavily search → Haiku parse → geocode → pending
│   ├── web_agent.py            # Anthropic web search → geocode → pending (v3)
│   ├── suggestion_agent.py     # promotes public form suggestions → pending
│   ├── validator_agent.py      # Claude: approved / needs_review / rejected
│   ├── updater_agent.py        # re-checks approved places
│   └── clients/                # supabase / google_places / tavily_client / llm
├── mcp_server/                 # AI toolkit — MCP server (FastMCP, 6 tools)
│   ├── server.py
│   └── README.md
├── skills/                     # AI toolkit — reusable skills
│   └── validator-rubric/SKILL.md
├── config/
│   ├── settings.py             # env-driven config (python-dotenv)
│   └── targets.yaml            # countries/cities + search/social terms
├── scripts/
│   ├── check_setup.py          # connectivity / config preflight
│   └── run_agents.py           # pipeline: search → social → web → suggestion → validator → updater
├── db/
│   ├── schema.sql              # tables (+ suggestions), constraints, indexes, RLS, triggers
│   └── seed.sql                # manual seed (UY/AR)
├── tests/                      # offline unit tests (all external calls mocked)
├── .github/workflows/          # agents-daily cron + Pages deploy
├── requirements.txt
├── .env.example
└── README.md  CLAUDE.md  prompts.md  .gitignore
```

## How to Run

### Frontend

Open `index.html` in your browser — no build step. The map reads public,
read-only data from Supabase using the anon key in `js/config.js`.

### Agents (Python)

```bash
cp .env.example .env             # fill in Supabase service_role + API keys
pip install -r requirements.txt
python scripts/check_setup.py    # preflight: config + connectivity

# Run the full pipeline (search → social → web → validator → updater) under one budget:
python -m scripts.run_agents --dry-run   # rehearse: no database writes
python -m scripts.run_agents             # real run

# …or run any stage on its own:
python -m agents.search_agent    # discover candidates    → pending (+ reviews)
python -m agents.social_agent    # discover IG/FB pages   → pending
python -m agents.web_agent       # autonomous web search  → pending (v3)
python -m agents.validator_agent # approve / discard pending
python -m agents.updater_agent   # re-check approved places
```

### Tests

Unit tests cover the agents and config. They run fully offline — every external
call (Supabase, Google Places, Anthropic) is mocked, so no `.env` or network is
needed:

```bash
python -m pytest tests/ -v
```

In production the pipeline runs automatically once per day via the
`Agents — daily pipeline` GitHub Actions workflow
([`.github/workflows/agents-daily.yml`](.github/workflows/agents-daily.yml)); it
can also be triggered manually (with a dry-run toggle) from the Actions tab.

Secrets (Supabase `service_role`, Google Places, Tavily, Anthropic) live only in
`.env` locally and in GitHub Actions Secrets — never in the frontend.

### MCP server (AI Toolkit)

The MCP server exposes the database + the Validator rubric as tools for Claude
Desktop / Claude Code / external agents. It reuses the same `.env` (no new vars):

```bash
python mcp_server/server.py          # run the server
claude mcp add celiacmap python mcp_server/server.py   # register with Claude Code
```

See [`mcp_server/README.md`](mcp_server/README.md) for the tool list and the
Claude Desktop config.

## Live Demo

**https://santisanchez4.github.io/CeliacMap/**

Deployed from `main` via GitHub Actions
([`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml)) on
every push that touches the frontend.

## Repository

**https://github.com/santisanchez4/CeliacMap**

## Author

Santiago Sanchez — [\[LinkedIn\]](https://www.linkedin.com/in/santisanchez4/) - [\[gitHub\]](https://github.com/santisanchez4/CeliacMap)