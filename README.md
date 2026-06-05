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
- ✅ **Validator agent** — Claude `claude-sonnet-4-6` approves or discards each
  pending candidate (structured verdict + confidence/notes), using stored review
  snippets as extra context.
- ✅ **Updater agent** — re-checks approved places via Google Places; closes /
  updates / flags. Deterministic, with a narrow Haiku fallback.
- ✅ **Pipeline orchestrator** (`scripts/run_agents.py`) — runs all five agents
  (search → social → web → validator → updater) under one combined daily budget,
  with a `--dry-run` mode.
- ✅ **GitHub Actions daily cron** — runs the pipeline once per day (manual
  `workflow_dispatch` with a dry-run toggle for validation).
- ✅ **Deployed to GitHub Pages** — the frontend ships automatically from `main`
  via GitHub Actions ([live demo](https://santisanchez4.github.io/CeliacMap/)).

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
  `tavily-python`, `python-dotenv`, `PyYAML`

**Automation**
- [GitHub Actions](https://docs.github.com/actions) — daily agent cron + Pages deploy

## Architecture

CeliacMap has three layers:

1. **Frontend** — static site + Leaflet map that reads **approved** places from
   Supabase and filters them by category (Restaurants, Cafés, Shops).
2. **Database** — Supabase Postgres (`places`, `reviews`, `agent_log`) with RLS so
   the browser can only read approved data.
3. **Agents** — a daily Python pipeline: **Search** finds candidates via Google
   Places (status `pending`, plus GF review enrichment) → **Social** discovers
   Instagram / Facebook pages via the Tavily Search API → **Web** (v3) uses the
   Anthropic web search tool to discover places from forums/blogs/social → **Validator**
   uses Claude to approve/discard → **Updater** keeps published places current.
   Orchestrated by GitHub Actions.

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
verdict `{verdict, category, safety_level, confidence, reason}`.

**Full rubric (English — as it exists in code):**

```text
You are the Validator for CeliacMap, a curated directory of gluten-free / "sin TACC" (celiac-safe) places in Latin America. You receive a single candidate place that was discovered automatically — via Google Places, public social-media pages, or web research — so you usually only have its name, address, city/country and a guessed category. Decide whether it belongs in the directory, then classify it.

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
Sos el Validador de CeliacMap, un directorio curado de lugares sin gluten / "sin TACC" (seguros para celíacos) en América Latina. Recibís un único lugar candidato que fue descubierto automáticamente —mediante Google Places, páginas públicas de redes sociales o investigación web— así que normalmente solo tenés su nombre, dirección, ciudad/país y una categoría estimada. Decidí si pertenece al directorio y luego clasificalo.

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
> affects which places are approved for celiac users.

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
│   ├── search_agent.py         # Google Places → pending candidates (+ reviews)
│   ├── social_agent.py         # Tavily search → Haiku parse → geocode → pending
│   ├── web_agent.py            # Anthropic web search → geocode → pending (v3)
│   ├── validator_agent.py      # Claude approves/discards pending
│   ├── updater_agent.py        # re-checks approved places
│   └── clients/                # supabase / google_places / tavily_client / llm
├── config/
│   ├── settings.py             # env-driven config (python-dotenv)
│   └── targets.yaml            # countries/cities + search/social terms
├── scripts/
│   ├── check_setup.py          # connectivity / config preflight
│   └── run_agents.py           # pipeline: search → social → web → validator → updater
├── db/
│   ├── schema.sql              # tables, constraints, indexes, RLS, triggers
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

## Live Demo

**https://santisanchez4.github.io/CeliacMap/**

Deployed from `main` via GitHub Actions
([`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml)) on
every push that touches the frontend.

## Repository

**https://github.com/santisanchez4/CeliacMap**

## Author

Santiago Sanchez — [\[LinkedIn\]](https://www.linkedin.com/in/santisanchez4/) - [\[gitHub\]](https://github.com/santisanchez4/CeliacMap)