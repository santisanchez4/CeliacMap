# Prompts Log

A running log of the important prompts used during the development of CeliacMap,
with a brief description of what each one was used for.

---

## 1. Initial landing page development

**Prompt (summary):** "Read CLAUDE.md carefully. Plan the complete development of
the landing page described there, then build it."

**Used for:** Bootstrapping the entire project — defining the file structure,
color palette, typography, and the 12-section breakdown of the landing page, then
implementing `index.html`, `css/styles.css`, and `js/main.js`.

**Key decisions made during this prompt:**
- **Language:** Bilingual — Spanish (Argentina, "sin TACC") as the default copy in
  the HTML, with a client-side ES/EN toggle (no build step, no backend).
- **Typography:** Inter via Google Fonts CDN, with a system-font fallback stack.
- **Interactive Map:** A pure HTML/CSS conceptual mockup (no map library), to keep
  the project dependency-free and self-contained.
- **Icons:** Inline SVG (no icon library), themeable via `currentColor`.
- **No binary image assets:** all visuals built with CSS/SVG.

## 2. Editorial visual + content redesign

**Prompt (summary):** "Full visual and content redesign — refined deep/soft greens
on warm off-whites, Playfair Display + DM Sans, editorial/minimal aesthetic,
shorter and warmer copy. Keep structure, accessibility and the ES/EN toggle."

**Used for:** Reworking `index.html` and `css/styles.css` (and later the `js/main.js`
EN dictionary) into an editorial, lifestyle-brand look without changing the section
structure or order.

## 3. Architecture & product evolution

**Prompt (summary):** "Evolve CeliacMap from a landing page into a real functional
product. Document the approved architecture (Leaflet + Supabase + Python agents +
GitHub Actions cron), refine the schema, plan the build order, recommend AI APIs
per agent, and update CLAUDE.md / README.md."

**Used for:** Planning the product evolution and documenting it — added the
**## Architecture** section to `CLAUDE.md` and updated `README.md`'s scope, stack
and structure. No implementation code yet.

**Key decisions made during this prompt:**
- **Validator model:** `claude-sonnet-4-6`; tiered escalation to `claude-opus-4-8`
  for low-confidence cases noted as a future optimization.
- **Search / Updater:** deterministic first; `claude-haiku-4-5` only where free-text
  interpretation is needed.
- **Schema:** added `places.status` (pending/approved/discarded), provenance/dedup
  fields, and RLS so the anon key reads only approved places.
- **Phase 1 (revisitable):** auth deferred; small manual seed for Uruguay/Argentina.

## 4. Search agent (Phase 5)

**Prompt (summary):** "Proceed with Phase 5 — build `agents/search_agent.py`. Read
targets from `targets.yaml`, search the Google Places API per city + term,
deduplicate by `external_id`, insert new candidates as `status='pending'` into
Supabase, and log each run to `agent_log`."

**Used for:** Implementing the first agent — a deterministic (no-LLM) `SearchAgent`
that crosses every city in `config/targets.yaml` with every search term, maps each
Google Places result onto the `places` schema, assigns a provisional category from
the Google place types, deduplicates by `external_id`, and inserts pending
candidates for the Validator to judge.

**Key decisions made during this prompt:**
- **Deterministic search:** no LLM; category is derived by inverting the
  `categories` map in `targets.yaml` (google type → our category), defaulting to
  `restaurant` when no type matches.
- **Provisional fields at insert:** `safety_level` defaults to the most
  conservative `options_available`; the Validator sets the real category/safety.
- **Deduplication:** a per-run `seen` set on `external_id` plus the DB's unique
  `(source, external_id)` index (upsert ignores duplicates) for cross-run dedup.
- **Cost/quality guards:** permanently-closed and malformed results are skipped;
  results per query are capped by `MAX_SEARCH_RESULTS_PER_QUERY`. Per-query
  failures and a final run summary are written to `agent_log`.

**Input variables** (data-driven from `config/targets.yaml`):
- `{{country}}`: country block to search (e.g. `Uruguay`).
- `{{city}}`: city within that block (e.g. `Montevideo`).
- `{{search_terms}}`: GF / sin-TACC terms crossed with the city (e.g. `sin TACC`,
  `gluten free`, `celíaco`).
- `{{categories}}`: the google-type → CeliacMap category map used to classify
  each result.

**Worked example:**

For `targets.yaml` → `Uruguay` / `Montevideo` / term `"sin TACC"`, the agent runs
a Google Places Text Search for `"sin TACC Montevideo"`. A result such as:

```json
{ "name": "El Buen Sabor",
  "formatted_address": "Av. 18 de Julio 1234, Montevideo, Uruguay",
  "place_id": "ChIJ_xyz_buensabor",
  "types": ["restaurant", "food", "point_of_interest"],
  "geometry": { "location": { "lat": -34.9059, "lng": -56.1913 } } }
```

is mapped deterministically (no LLM) and inserted as a candidate:

```json
{ "name": "El Buen Sabor",
  "address": "Av. 18 de Julio 1234, Montevideo, Uruguay",
  "lat": -34.9059, "lng": -56.1913,
  "category": "restaurant",            // inverted from `types` via the categories map
  "country": "Uruguay", "city": "Montevideo",
  "source": "google_places", "external_id": "ChIJ_xyz_buensabor",
  "safety_level": "options_available", // conservative floor; the Validator sets the real one
  "status": "pending" }
```

Re-running on Montevideo will not insert a second row for the same `place_id` —
the `(source, external_id)` unique constraint dedups it.

## 5. Validator agent (Phase 6)

**Prompt (summary):** "Proceed with Phase 6 — build the Validator agent. Pull all
pending places from Supabase, send each to `claude-sonnet-4-6` with a structured
rubric, output JSON `{verdict, category, safety_level, confidence, reason}`, set
status to approved/discarded and save confidence/notes, and log each validation to
`agent_log`."

**Used for:** Implementing `agents/validator_agent.py` — the single quality gate
between Search's `pending` candidates and what the public map shows. It batches
pending places, judges each against a fixed rubric via the cached-system-prompt
`LLMClient`, and persists the verdict with `update_place_validation`.

**Key decisions made during this prompt:**
- **Model:** `claude-sonnet-4-6` (the `LLMClient` default), with the rubric sent as
  a cached system block reused across the batch.
- **Health-sensitive defaults:** the rubric instructs conservative `safety_level`
  (floor `options_available`); `verified` stays `false` pending human confirmation.
- **Defensive normalization:** `confidence` clamped to 0–1; `category` /
  `safety_level` validated against the schema's allowed sets, falling back to the
  candidate's existing values; only approvals overwrite category/safety.
- **Auditability:** every verdict (and a run summary) is logged to `agent_log`;
  per-candidate LLM and persistence failures are caught so one bad row never aborts
  the batch.

## 6. Updater agent + pipeline orchestrator (Phase 7)

**Prompt (summary):** "Proceed with Phase 7 — build the Updater agent. Pull all
approved places, re-check each via Google Places using `external_id`, detect
closures / name / category changes, update Supabase or flag for review, and log
each check. Keep LLM usage minimal — deterministic first, Haiku only for ambiguous
text signals. Cap daily API calls to stay within budget. Then build
`scripts/run_agents.py`: run search → validator → updater, enforce a combined
daily budget cap, log the full run summary to `agent_log`, and accept a
`--dry-run` flag for testing without writes."

**Used for:** Implementing `agents/updater_agent.py` — the third pipeline stage
(Search → Validator → **Updater**) that keeps already-approved places current —
plus `scripts/run_agents.py`, the CI entrypoint that runs the three agents in
sequence. Also added a generic `SupabaseClient.update_place(place_id, patch)`, a
`MAX_UPDATES_PER_RUN` cap, and an `AGENT_DAILY_BUDGET` setting in
`config/settings.py`.

**Key decisions made during this prompt:**
- **Deterministic-first diffs:** permanently-closed (`CLOSED_PERMANENTLY` /
  `permanently_closed`) → `discarded` (drops off the public map); name / address /
  category changes are patched in place; category is recomputed from Google `types`.
- **Haiku only for ambiguity:** `claude-haiku-4-5` is invoked **only** when the
  Google `types` map to none of our categories, and only if an Anthropic key is
  present — otherwise the agent is fully deterministic.
- **Flag, don't guess:** `NOT_FOUND` / non-OK details responses are logged as
  `flagged_for_review` and the row is left untouched (could be transient).
- **Budget + scope:** manual/seed places (no `external_id`) are skipped; re-checks
  per run are capped by `MAX_UPDATES_PER_RUN`. Every check and a run summary are
  written to `agent_log`.
- **Combined budget cap:** `run_agents.py` shares one `AGENT_DAILY_BUDGET` across
  the run — search consumes its query count, then the validator/updater per-run
  sizes are clamped to the remaining budget so the day's total paid calls stay
  bounded. A stage whose budget is exhausted is skipped (recorded in the summary).
- **`--dry-run`:** wraps the Supabase client so reads pass through (agents see real
  data) but every write becomes a logged no-op — the whole pipeline is exercised
  without persisting anything. A consolidated `pipeline_run_complete` summary is
  written to `agent_log` on real runs.

## 7. GitHub Actions daily cron (Phase 8)

**Prompt (summary):** "After confirming the real pipeline run, proceed with
Phase 8 — the GitHub Actions cron job."

**Used for:** Adding `.github/workflows/agents-daily.yml`, which runs
`python -m scripts.run_agents` on a daily schedule and on manual
`workflow_dispatch`. Also added the previously-missing `.env.example` (referenced
by `config/settings.py` and the file structure) documenting every variable.

**Key decisions made during this prompt:**
- **Schedule + manual:** `cron: "0 9 * * *"` (09:00 UTC, ~06:00 UY/AR) plus a
  `workflow_dispatch` with a `dry_run` toggle and optional `budget` override, so the
  pipeline can be validated manually before relying on the cron.
- **Secrets in CI:** Supabase / Google / Anthropic keys are read from GitHub Actions
  Secrets via job `env`; nothing is hard-coded. `AGENT_DAILY_BUDGET` is an optional
  repo variable that falls back to the in-code default.
- **Safety rails:** a `concurrency` group prevents overlapping runs (they share one
  daily budget and database), a 30-minute timeout caps runaway runs, and
  `permissions: contents: read` keeps the token least-privileged.

**Discovered during the live run (folded into Phase 7):** the `agent_log.agent`
CHECK constraint only allowed `search` / `validator` / `updater`, so the
orchestrator's `agent='pipeline'` summary insert was rejected. The constraint was
widened in `db/schema.sql` (idempotent migration) to also allow `pipeline`.

## 8. GitHub Pages deploy (Phase 9)

**Prompt (summary):** "Move to Phase 9 — deploy the frontend to GitHub Pages."

**Used for:** Adding `.github/workflows/deploy-pages.yml`, which stages only the
static frontend (`index.html` + `css/` + `js/` + `assets/`) into `_site/` and
publishes it to GitHub Pages on push to `main` (frontend paths) and on manual
dispatch. Also updated the README Live Demo / Repository links and the status
across docs.

**Key decisions made during this prompt:**
- **Deploy via GitHub Actions, not "deploy from branch"** — full control over what
  ships (frontend only; agents / `db/` / `config/` are never published). Requires
  the repo's Pages Source to be set to "GitHub Actions".
- **Node 24, no `configure-pages`** — the official starter's
  `actions/configure-pages@v5` still runs on Node 20 and only matters for SSG
  base-path detection. It was omitted so the workflow stays fully Node 24
  (`checkout@v5`, `upload-pages-artifact@v3`, `deploy-pages@v5`).
- **Subpath-safe** — the frontend uses relative + CDN paths only, so it works under
  the `/CeliacMap/` project-page subpath with no `<base>` tag or rewriting.

**Earlier in this prompt — CI Node runtime fix:** `agents-daily.yml` was bumped
from `actions/checkout@v4` / `setup-python@v5` (Node 20, deprecated) to
`checkout@v5` / `setup-python@v6` (Node 24). Commit `chore: update GitHub Actions
to Node.js 24`.

## 9. Social discovery agent + Google Reviews enrichment (Phase 10)

**Prompt (summary):** "Add a social media discovery agent. Index public Instagram /
Facebook pages via Google Custom Search (`site:instagram.com "sin TACC"
"Montevideo"`, etc.), parse each result with `claude-haiku-4-5` into
{name, city, category, address}, insert as `pending` with `source='social'`, and
log to `agent_log`. Add it to the daily pipeline after the Search agent. Also add
Google Reviews enrichment: when the Search agent finds a place, fetch its reviews,
keep snippets mentioning sin TACC / sin gluten / gluten free / libre de gluten /
celíaco / apto celíaco, store them in `reviews`, and pass them to the Validator as
context. Add the new env vars, keep the daily budget cap, log everything, add
tests, and update the docs. Plan first."

**Used for:** Implementing `agents/social_agent.py` and
`agents/clients/google_custom_search.py` (stdlib-only Custom Search client),
extending `GooglePlacesClient` (`find_place`, reviews fetch, `extract_gf_snippets`)
and `SupabaseClient` (`insert_review`, `fetch_reviews_for_place`,
`place_exists_by_external_id`), wiring review enrichment into the Search agent and
review context into the Validator, adding the **Social** stage to
`scripts/run_agents.py`, widening the schema CHECK constraints, and adding offline
tests (`tests/test_social_agent.py` plus search/validator additions).

**Key decisions made during this prompt:**
- **Coordinates via Find Place, not nullable columns:** social leads are geocoded
  (`name + city`) to real coordinates + a canonical `place_id`; unresolved leads
  are skipped, so `places.lat/lng` stay `NOT NULL` and the map only ever gets
  mappable rows.
- **Cross-source dedup on `place_id`:** social uses the geocoded Google `place_id`
  as `external_id` and an explicit existence check, so a place found by both Search
  and Social is inserted once; the profile URL is kept in `validation_notes`.
- **Shared budget + own cap:** the Social stage draws Custom Search + Find Place
  calls from the combined `AGENT_DAILY_BUDGET` and is also capped by
  `MAX_SOCIAL_QUERIES_PER_RUN` to stay under the Custom Search 100/day free tier;
  review enrichment is gated by `MAX_REVIEW_ENRICHMENTS_PER_RUN` (off by default).
- **Haiku for parsing, Sonnet still the gate:** Haiku turns noisy result snippets
  into structured leads; the Validator (Sonnet) judges every social candidate and
  now weighs stored review snippets without overstating safety.
- **Stdlib Custom Search client + idempotent schema migrations:** no new Python
  dependency; `places.source` gains `'social'`, `reviews.source` gains `'google'`,
  and `agent_log.agent` gains `'social'` via idempotent `DO` blocks.

**Input variables** (the per-result Haiku parse that turns one noisy Tavily
search result into a structured lead — used once per social result):
- `{{platform}}`: source platform (`instagram` | `facebook`).
- `{{result_title}}`: title of the Tavily search result.
- `{{result_link}}`: URL of the profile / post.
- `{{result_snippet}}`: snippet text returned by Tavily.

**Worked example:**

A Tavily result for query `"sin TACC" "Montevideo"` restricted to `instagram.com`:

```text
title:   El Buen Sabor (@elbuensabor.uy) • Instagram
link:    https://www.instagram.com/elbuensabor.uy/
snippet: Restaurante sin TACC en el Centro de Montevideo. Menú celíaco certificado 🌾🚫
```

`claude-haiku-4-5` parses it into a clean lead:

```json
{ "name": "El Buen Sabor", "city": "Montevideo", "category": "restaurant", "address": null }
```

The agent then geocodes `name + city` via Google Find Place (→ real coords +
canonical `place_id`), keeps the profile URL in `validation_notes`, and inserts
the lead as `pending`, `source='social'` for the Validator. A result Haiku cannot
confidently resolve to a name is dropped (`social_unresolved`).

## 10. Social agent search provider: Google Custom Search → Tavily

**Prompt:** "We are replacing Google Custom Search with Tavily API for the social
agent. Reasons: Google PSE no longer allows 'search the entire web' for new engines
(policy change Jan 2026); Tavily is designed for AI agents, cleaner results; free
tier 1000 searches/month. Changes: replace `agents/clients/google_custom_search.py`
with `agents/clients/tavily_client.py`, update `agents/social_agent.py`, add
`TAVILY_API_KEY` to `.env.example`, update `requirements.txt`
(`pip install tavily-python`), update tests. Present the plan first, then implement
on approval."

**Used for:** Migrating the Social agent's discovery backend off the (now
unworkable) Google Custom Search JSON API. Added `agents/clients/tavily_client.py`
(wraps `tavily-python`, normalizes results to the existing `{title, link, snippet}`
shape), reworked `SocialAgent._build_queries` to emit `"<term>" "<city>"` queries
with the platform applied via Tavily `include_domains` (Tavily ignores `site:`),
swapped the wiring in `scripts/run_agents.py` and `social_agent.main()`, replaced
the `GOOGLE_CUSTOM_SEARCH_API_KEY` / `GOOGLE_SEARCH_ENGINE_ID` settings with
`TAVILY_API_KEY` (config, `.env`, `.env.example`, CI workflow, `check_setup.py`),
added `tavily-python` to `requirements.txt`, and updated the offline tests
(`tests/test_social_agent.py`, all 82 passing).

**Key decisions made during this prompt:**
- **Why Tavily:** a Google Programmable Search Engine must "search the entire web"
  to discover arbitrary Instagram / Facebook pages, and Google removed that toggle
  for new engines in January 2026 — the old approach is dead, not merely
  misconfigured. Tavily is purpose-built for agents and has a 1000/month free tier.
- **`include_domains`, not `site:`:** Tavily does not honor Google's `site:`
  operator, so the platform restriction moves into Tavily's `include_domains`
  parameter; the per-platform query matrix (and thus the budget accounting) is
  unchanged.
- **Normalized result shape:** the new client returns `{title, link, snippet}` so
  the agent's parsing / geocoding / dedup logic was untouched.
- **Full cleanup:** the dead Custom Search env vars and the stdlib client were
  removed rather than left in place; `TAVILY_API_KEY` was also added to the daily
  CI workflow so the Social stage can finally run in CI.

## 11. Web search discovery agent (v3, autonomous)

**Prompt (summary):** "Design and build a v3 discovery agent using Anthropic's web
search tool. Instead of predefined tags, it receives a city/country, reasons freely
about how to find gluten-free / sin TACC places, uses web search to read forums,
blogs, Facebook groups and Instagram, extracts candidates with context, and passes
them to the existing Validator. This is the evolution v1 (Google Places tags) → v2
(Tavily social) → v3 (autonomous web search). Present the plan first; implement on
approval (schema → llm → agent → config → orchestrator → tests → docs). Roll out to
Montevideo + Buenos Aires only via a per-city `web: true` toggle, model
`claude-sonnet-4-6`, and make the small neutral provenance tweak to the Validator
rubric (proposing exact wording first)."

**Used for:** Adding `agents/web_agent.py` and the `LLMClient.research_with_web_search`
wrapper (Anthropic server-side `web_search_20260209` / `web_fetch_20260209`,
handling `pause_turn`), wiring the **web** stage into `scripts/run_agents.py`
(search → social → web → validator → updater under the shared `AGENT_DAILY_BUDGET`),
the per-city `web: true` opt-in in `targets.yaml`, new settings/env vars
(`WEB_SEARCH_MODEL`, `MAX_WEB_CITIES_PER_RUN`, `MAX_WEB_SEARCHES_PER_CITY`), the
idempotent schema migration (`places.source` / `agent_log.agent` gain `'web'`; the
`social_url` column — used in code but missing from `schema.sql` — is added), the
neutral provenance wording in the Validator rubric, and 16 offline tests
(`tests/test_web_agent.py`).

**The research rubric (system prompt) handed to the model per city:**

```text
You are the Web Researcher for CeliacMap, a curated directory of gluten-free / "sin TACC" (celiac-safe) places in Latin America. Given one city and country, use web search to find real, currently-operating places that serve or sell gluten-free / celiac-safe food: restaurants, cafes/bakeries, and shops (dietéticas, health-food stores, supermarkets with GF products).

Reason freely about how to find them. Do not rely on a single query — search the way a celiac local would: community blogs and forums, Facebook groups, Instagram posts and roundups, local news and "dónde comer sin TACC" guides, and celiac association listings. Prioritise places that are discussed by the community but may not be obvious on the map. Fetch pages when a snippet looks promising but incomplete.

For every place you are reasonably confident is real and gluten-free relevant, collect: name, category (restaurant | cafe | shop), address (or null), evidence (one sentence on why it is GF relevant), and source_url. Only include places physically in the requested city/country. Do NOT invent places — if you cannot find a real source, leave it out. Prefer fewer, well-supported places over many weak guesses.

Respond with ONLY a JSON object: {"places": [{name, category, address, evidence, source_url}]}.
```

**Input variables** (the only two inputs; the model writes its own search queries
from them — the system prompt above is fixed and the city/country are injected
into the user turn that starts the research):
- `{{city}}`: target city to research (e.g. `Montevideo`).
- `{{country}}`: country containing that city (e.g. `Uruguay`).

**Worked example:**

User turn: `Investiga: Montevideo, Uruguay`

After running `web_search` / `web_fetch` over community blogs, IG roundups, celiac
Facebook groups and the ACELU listings, the model replies with only:

```json
{
  "places": [
    {
      "name": "El Buen Sabor",
      "category": "restaurant",
      "address": "Av. 18 de Julio 1234, Montevideo",
      "evidence": "Recomendado en un grupo de Facebook celíaco de Montevideo como restaurante con menú sin TACC certificado y cocina separada.",
      "source_url": "https://www.facebook.com/groups/celiacosuy/posts/123456789"
    }
  ]
}
```

The agent geocodes `"El Buen Sabor Montevideo"` via Google Find Place (→ real
coords + canonical `place_id`), dedups across sources, and inserts it as `pending`,
`source='web'` (the `source_url` kept in `social_url`) for the Validator to judge.

**Key decisions made during this prompt:**
- **Reuse, don't reinvent:** v3 mirrors the Social agent's geocode-and-dedup spine
  (Google Find Place → real coords + canonical `place_id` → `place_exists_by_external_id`)
  so a place found by Search/Social/Web is one row, and feeds the **unchanged**
  Validator gate.
- **Model — `claude-sonnet-4-6`:** genuinely agentic (free reasoning + tool use),
  so a stronger model than the Social parse; Sonnet is the cost/quality balance for
  a daily batch, with `WEB_SEARCH_MODEL` allowing a one-line upgrade to Opus 4.8.
- **Hallucination guard (health-sensitive):** the rubric forbids fabricating a
  name/URL; every lead must geocode to a real Google `place_id` or it is dropped;
  the Validator still judges every candidate; `verified` stays `false`.
- **Opt-in rollout:** a `web: true` flag per city (Montevideo + Buenos Aires first)
  keeps cost bounded and lets the approach be verified before expanding.
- **Provenance tweak (proposed before changing):** the Validator rubric's "discovered
  via Google Places" clause became neutral — "via Google Places, public social-media
  pages, or web research" — kept in sync across `validator_agent.py`, `README.md`,
  and `CLAUDE.md`. No verdict/category/safety rule changed.

## 12. AI Toolkit — Validator rubric adoption (three-tier verdict)

**Prompt (summary):** "Integrate an academic 'Toolkit de IA' (documented prompts,
CLAUDE.md, a reusable Skill, an MCP server). Adopt the toolkit's richer Validator
rubric as canonical — three-tier verdict `approved`/`rejected`/`needs_review` with
`confidence_score`, `flags`, `recommendation` and explicit 0.85/0.7/0.5 gates —
replacing the previous `approve`/`discard` rubric. Keep the frontend alive with an
**additive** status mapping and keep `category`/`safety_level` in the output."

**Used for:** A deliberate change to the project's single health-sensitive quality
gate (`RUBRIC` in `agents/validator_agent.py`). The verdict now maps to
`places.status` additively — `approved`→`approved`, `rejected`→`discarded`,
`needs_review`→`needs_review` (a new human-review tier held back from the map) —
so `js/map.js`, RLS and the seed are untouched. `confidence_score` persists to
`validation_confidence`, `reasoning` to `validation_notes`, and `flags`/
`recommendation` to new columns. The same `RUBRIC` is reused on-demand by the MCP
server's `validate_place` tool, so batch and on-demand validation are identical.

**Key decisions made during this prompt:**
- **Confidence gates are code-enforced** (`ValidatorAgent._decide_status`), defense
  in depth: auto-approval requires `confidence_score >= 0.85`; `< 0.5` (or an
  explicit `rejected`) discards; everything between — and the `< 0.7` safety floor —
  is held as `needs_review`, regardless of the model's stated verdict.
- **`category` + `safety_level` retained** in the output (the toolkit rubric dropped
  them) because the schema requires them and the map renders safety badges.
- **Rubric language → Spanish**, matching the MCP `validate_place` prompt and this
  log, so the code prompt and the documented prompt are the same text.

**The adopted Validator system prompt (`RUBRIC`, as it exists in code):**

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

Si el mensaje incluye "ubicacion_geocode", significa que solo se geocodificó la dirección de texto del candidato: NO hay una ficha de Google Places que confirme que el negocio existe y opera en ese lugar (sin reseñas de Google, sin verificación de existencia). Tratá esto como evidencia debilitada — NO asignes "approved" salvo que el resto de la evidencia (mención explícita de "sin TACC", reseñas claras de la comunidad) sea fuerte por sí sola. Ante la duda, "needs_review".

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, exactamente con esta forma:
{"verdict": "approved" | "rejected" | "needs_review",
 "confidence_score": <número entre 0.0 y 1.0>,
 "category": "restaurant" | "cafe" | "shop",
 "safety_level": "gluten_free_100" | "celiac_friendly" | "options_available",
 "reasoning": "<explicación clara en español, máximo 3 oraciones>",
 "flags": ["<flag detectado>", ...],
 "recommendation": "<acción concreta sugerida para el operador>"}
```

> The `ubicacion_geocode` paragraph was added later (geocode-gate address
> fallback) — see **§24** for that deliberate rubric change.

**Input variables** (the `RUBRIC` above is the fixed, cached **system** block; the
per-candidate data is interpolated into the **user** message, same shape the MCP
`validate_place` tool builds — see §13):
- `{{name}}`: candidate place name.
- `{{address}}`: street address (or "desconocida").
- `{{city}}`: city.
- `{{country}}`: country (`Uruguay` | `Argentina`).
- `{{category}}`: provisional category from discovery (may be unknown).
- `{{evidence}}`: collected evidence — discovery snippet, Google description, and
  any stored gluten-free review snippets.

**Worked example:**

System = the full `RUBRIC` above (cached). User message:

```text
Valida el siguiente lugar:

Nombre: El Buen Sabor
Dirección: Av. 18 de Julio 1234, Montevideo
Ciudad: Montevideo, Uruguay
Categoría estimada: restaurant

Evidencia recopilada:
El local se promociona como "menú sin TACC certificado por ACELU", con cocina
dedicada y protocolo de contaminación cruzada. Reseña de Google (source=google):
"Soy celíaca y comí tranquila, tienen carta sin TACC separada."
```

The Validator replies with only the JSON verdict:

```json
{
  "verdict": "approved",
  "confidence_score": 0.9,
  "category": "restaurant",
  "safety_level": "celiac_friendly",
  "reasoning": "Evidencia explícita de menú sin TACC certificado por ACELU, cocina dedicada y protocolo de contaminación cruzada, respaldada por una reseña de una persona celíaca.",
  "flags": [],
  "recommendation": "Aprobar y publicar; reconfirmar la certificación ACELU en la próxima pasada del Updater."
}
```

`_decide_status` maps `confidence_score 0.9 >= 0.85` → `places.status = 'approved'`
(published on the map). Had the evidence only said "opciones sin gluten" with no
contaminación-cruzada mention, the score would fall below the `0.7` floor and the
same code would force `needs_review` instead — never auto-approve on weak signal.

## 13. AI Toolkit — MCP server `validate_place` tool

**Archivo:** `mcp_server/server.py` · **Modelo:** `claude-sonnet-4-6`
**Propósito:** Validación on-demand desde Claude Desktop / Claude Code / agentes
externos, usando exactamente el mismo rubric que el pipeline diario.

The tool imports the canonical `RUBRIC` (above) as the system prompt and runs the
candidate through `ValidatorAgent._normalize` (same gates), so there is **no second
copy** of the rubric to drift. The user message is built from the tool arguments:

```text
Valida el siguiente lugar:

Nombre: [name]
Dirección: [address]
Ciudad: [city]

Evidencia recopilada:
[evidence]
```

The tool returns `{verdict, confidence_score, category, safety_level, reasoning,
flags, recommendation, db_status}` — `db_status` is the status the candidate would
take in the database (`approved` / `needs_review` / `discarded`).

**Input variables** (the four tool arguments, interpolated into the user prompt
above):
- `{{name}}`: nombre del establecimiento.
- `{{address}}`: dirección completa.
- `{{city}}`: ciudad.
- `{{evidence}}`: texto con la evidencia recopilada (posts, sitio web, reseñas,
  descripción de Google Maps).

**Worked example:**

Tool call:

```python
validate_place(
    name="El Buen Sabor",
    address="Av. 18 de Julio 1234",
    city="Montevideo, Uruguay",
    evidence="El Instagram del local anuncia menú sin TACC certificado por ACELU y cocina separada; varias reseñas de celíacos positivas.",
)
```

builds the user prompt:

```text
Valida el siguiente lugar:

Nombre: El Buen Sabor
Dirección: Av. 18 de Julio 1234
Ciudad: Montevideo, Uruguay

Evidencia recopilada:
El Instagram del local anuncia menú sin TACC certificado por ACELU y cocina
separada; varias reseñas de celíacos positivas.
```

and returns:

```json
{
  "verdict": "approved",
  "confidence_score": 0.88,
  "category": "restaurant",
  "safety_level": "celiac_friendly",
  "reasoning": "Mención explícita de menú sin TACC certificado por ACELU y cocina separada, con reseñas positivas de personas celíacas.",
  "flags": [],
  "recommendation": "Publicar; verificar la vigencia de la certificación ACELU.",
  "db_status": "approved",
  "validated_at": "2026-06-19T12:00:00+00:00",
  "place_name": "El Buen Sabor"
}
```

## 14. Suggest-a-Place public form (community Phase 2)

**Prompt (summary):** "Build the 'Suggest a Place' feature — a public form (no
login) that lets users submit a gluten-free / sin TACC place that isn't on the map
yet. Plan it first (frontend form, backend/DB, validation timing, spam protection,
files) for approval, then implement."

**Used for:** Adding the first public **write** path to the product. The browser
writes raw input into a new anon-INSERT-only `suggestions` table; the daily
pipeline's **Suggestion promoter** (`agents/suggestion_agent.py`) geocodes via
Google Find Place, dedups, and promotes each into `places` as `pending`
(`source='user'`) for the unchanged Validator gate. New `js/suggest.js` submits via
the Supabase REST API with the public anon key.

**Key decisions made during this prompt** (full rationale in CLAUDE.md →
**Suggest-a-Place public form design decisions**):
- **Intake table + pipeline promotion**, chosen over a Supabase Edge Function or a
  map-pin direct `places` insert — no new server tech, keeps `places` always-mappable
  and every secret server-side.
- **Shared `promote_suggestion` core** reused by both the daily `SuggestionAgent` and
  the refactored MCP `suggest_place` tool (no second copy).
- **Spam:** honeypot + min-fill-time + cooldown (client), INSERT-only length-bounded
  RLS (server), geocode + Validator gates as backstops; CAPTCHA deferred.
- **Validation on the daily pipeline, not on submit** (the form does client-side
  validation only).

No new LLM prompt was introduced — promoted user suggestions are judged by the same
canonical Validator `RUBRIC` (§12) as every other pending candidate.

## 15. Switch web_agent to Haiku

- **Trigger:** reduce token cost for the discovery agent.
- **Change:** `web_search_model` → `claude-haiku-4-5` (was `claude-sonnet-4-6`).
- **Files:** `config/settings.py`, `agents/web_agent.py`, `.env.example`, `CLAUDE.md`.
- **Rationale:** the Web agent only discovers and extracts candidates — it makes no
  safety judgment, so Haiku is sufficient and materially cheaper. The Sonnet
  Validator still gates every web candidate downstream, and `WEB_SEARCH_MODEL`
  allows a one-line flip back to Sonnet/Opus if discovery quality proves weak.

## 16. Add prompt-engineer skill

- **Trigger:** professor recommended the Vercel skills format.
- **Created:** `skills/prompt-engineer/SKILL.md`.
- **Registered in:** `CLAUDE.md` under the `## Skills` section.
- **Format:** YAML frontmatter + Markdown (modern standard, replaces HTML-based
  skill conventions).

## 17. ADR Generator — Three-Tier Rubric Decision

**Name:** ADR Generator — Three-Tier Rubric Decision

**Trigger:** When a major architectural decision needs to be formalized into a
standalone ADR file for academic deliverables.

**Input variables:** None — the prompt embeds the full ADR content verbatim
(title, Estado, Contexto, Decisión, Consecuencias), derived from the three-tier
rubric decision already documented in `CLAUDE.md`'s Decisions Log (see §12 above).

**Worked example (the prompt used to generate
`docs/architecture/ADR-001-three-tier-validation-rubric.md`):**

```text
Create docs/architecture/ADR-001-three-tier-validation-rubric.md
with exactly this content (no changes, no additions):

# ADR-001: Rubric de validación de tres niveles en lugar de binario

**Estado:** Aceptado

## Contexto
El Validator Agent usa Claude (Sonnet) para juzgar si un lugar es
efectivamente "sin TACC" a partir de evidencia en lenguaje natural
(reseñas, redes sociales, descripciones). Al tratarse de información
de seguridad alimentaria para personas celíacas, un falso positivo
(aprobar un lugar que no es seguro) tiene consecuencias reales para
la salud del usuario — no es un error cosmético. Un rubric binario
(aprobado/rechazado) obliga al modelo a colapsar casos ambiguos
—evidencia parcial, desactualizada, o contradictoria— hacia uno de
los dos extremos, sin manera de señalar incertidumbre real.

## Decisión
Se implementó un rubric de tres niveles con umbrales de confianza
explícitos:
- `approved` (confianza ≥ 0.85)
- `needs_review` (confianza 0.50–0.85)
- `discarded` (confianza < 0.50)

Esto requirió una migración de schema en Supabase, agregando las
columnas `needs_review` (status), `flags` (jsonb) y `recommendation`
(text) a la tabla `places`.

## Consecuencias

**Positivas:**
- Los casos ambiguos quedan explícitamente marcados para revisión
  humana en vez de forzarse a un sí/no.
- El sistema nunca "sobreestima" seguridad — el default ante la duda
  es `needs_review`, no `approved`. Esto respeta el principio
  conservador central del proyecto: nunca afirmar que algo es seguro
  sin evidencia suficiente.
- Es la base técnica para una futura escalación por niveles (Sonnet
  → Opus para los casos de menor confianza).

**Negativas / trade-offs aceptados:**
- Más complejidad de estado que un booleano simple: hay que mantener
  una cola de `needs_review` y decidir quién la resuelve (por ahora,
  revisión manual).
- El pipeline es más lento de "cerrar" — no todo lugar candidato
  termina en un estado final inmediato.

Do not modify any other file.
```

**Used for:** Producing `docs/architecture/ADR-001-three-tier-validation-rubric.md`
verbatim from content already decided and documented in prose form in `CLAUDE.md`
(§12 in this log; **AI Toolkit** in the Decisions Log). No new decision was made —
the prompt only reformats an existing decision into the standalone ADR format
required by the academic deliverable, and `CLAUDE.md`'s Decisions Log was updated
with a one-line pointer to the new file.

## 18. C4 Diagram Renderer Fix — Mermaid flowchart vs C4Context

**Name:** C4 Diagram Renderer Fix — Mermaid flowchart vs C4Context

**Trigger:** When Mermaid's dedicated `C4Context`/`C4Container` syntax renders with
overlapping/broken text on GitHub's native Markdown viewer, requiring a fallback
diagram type that preserves the same C4 semantic levels (context and containers).

**Input variables:** None — the prompt supplies the full replacement content of
`docs/architecture/C4-diagrams.md` verbatim (both diagrams, in `flowchart TB` with
subgraphs), preserving the same nodes and relationships as the original
`C4Context`/`C4Container` version.

**Worked example (the prompt used to regenerate
`docs/architecture/C4-diagrams.md`):**

```text
Replace the full content of docs/architecture/C4-diagrams.md with
this exact content:

# Diagramas de Arquitectura C4 — CeliacMap

## Nivel 1 — Contexto del sistema

```mermaid
flowchart TB
    usuario["👤 Persona celíaca<br/><i>Busca lugares sin TACC<br/>confiables en Argentina y Uruguay</i>"]
    colaborador["👤 Colaborador de la comunidad<br/><i>Sugiere nuevos lugares<br/>vía formulario público</i>"]

    celiacmap["🗺️ <b>CeliacMap</b><br/><i>Plataforma web que identifica, valida<br/>y muestra lugares sin TACC confiables</i>"]

    anthropic[["Anthropic API<br/><i>Claude Haiku (descubrimiento)<br/>y Sonnet (juicio de seguridad)</i>"]]
    google[["Google Places API<br/><i>Búsqueda determinística<br/>de comercios</i>"]]
    tavily[["Tavily API<br/><i>Descubrimiento de menciones<br/>en redes sociales</i>"]]
    github_actions[["GitHub Actions<br/><i>Orquesta el pipeline<br/>de forma mensual</i>"]]

    usuario -->|"Consulta el mapa<br/>HTTPS"| celiacmap
    colaborador -->|"Sugiere un lugar<br/>HTTPS/Formulario"| celiacmap

    celiacmap -->|"Valida y clasifica<br/>candidatos"| anthropic
    celiacmap -->|"Busca comercios<br/>candidatos"| google
    celiacmap -->|"Busca menciones<br/>sociales"| tavily
    github_actions -->|"Ejecuta el pipeline<br/>mensualmente"| celiacmap

    style celiacmap fill:#1168bd,color:#fff
    style usuario fill:#08427b,color:#fff
    style colaborador fill:#08427b,color:#fff
    style anthropic fill:#999,color:#fff
    style google fill:#999,color:#fff
    style tavily fill:#999,color:#fff
    style github_actions fill:#999,color:#fff
```

## Nivel 2 — Contenedores

```mermaid
flowchart TB
    usuario["👤 Persona celíaca"]

    anthropic[["Anthropic API"]]
    google[["Google Places API"]]
    tavily[["Tavily API"]]

    subgraph celiacmap["CeliacMap [SYSTEM]"]
        frontend["<b>Frontend estático</b><br/><i>HTML/CSS/JS + Leaflet.js</i><br/>Mapa interactivo, servido por<br/>GitHub Pages, sin build step"]
        pipeline["<b>Pipeline de agentes</b><br/><i>Python</i><br/>Search, Social, Validator,<br/>Updater, Web y Suggestion Agents"]
        mcp["<b>MCP Server</b><br/><i>Python/FastMCP</i><br/>Expone 6 tools para interactuar<br/>con los datos validados"]
        db[("<b>Base de datos</b><br/><i>Supabase (PostgreSQL)</i><br/>Lugares validados, sugerencias,<br/>estado del rubric de 3 niveles")]
    end

    usuario -->|"Navega el mapa<br/>HTTPS"| frontend
    usuario -->|"Envía sugerencia<br/>Formulario"| frontend
    frontend -->|"Lee/escribe<br/>REST"| db

    pipeline -->|"Lee/escribe lugares<br/>y estado, REST"| db
    pipeline -->|"Descubre (Haiku) y<br/>valida (Sonnet), API"| anthropic
    pipeline -->|"Busca candidatos<br/>API"| google
    pipeline -->|"Busca menciones<br/>sociales, API"| tavily

    mcp -->|"Consulta datos<br/>validados, REST"| db

    style frontend fill:#1168bd,color:#fff
    style pipeline fill:#1168bd,color:#fff
    style mcp fill:#1168bd,color:#fff
    style db fill:#1168bd,color:#fff
    style usuario fill:#08427b,color:#fff
    style anthropic fill:#999,color:#fff
    style google fill:#999,color:#fff
    style tavily fill:#999,color:#fff
```

Do not modify any other file.
```

**Used for:** Fixing rendering of `docs/architecture/C4-diagrams.md` on GitHub's
native Markdown viewer. The original diagrams used Mermaid's `C4Context` and
`C4Container` grammar (§ prior version), which GitHub's Mermaid renderer displays
with overlapping/broken text. Replaced with plain `flowchart TB` + `subgraph`,
which every Mermaid renderer supports reliably, while keeping the same two C4
levels (Nivel 1 — Contexto del sistema, Nivel 2 — Contenedores), the same actors,
systems, external systems, and relationships — only the diagram grammar changed,
not the architectural content. `CLAUDE.md`'s Decisions Log was updated with a
one-line pointer explaining the renderer trade-off.

## 19. ADR + Plan Generator — Outreach Agent Design

**Name:** ADR + Plan Generator — Outreach Agent Design

**Trigger:** When a new architectural proposal (not yet implemented) needs to be
formalized into both a plan file and an ADR at the same time, because they
reference each other and were designed together in conversation.

**Input variables:** None — the prompt embeds the full content of both files
verbatim, derived from a design discussion covering two-stage architecture
(monthly batch send vs. event-driven webhook for replies), schema changes, and
the core trade-off decision (business self-report as additional evidence, not
auto-approval).

**Worked example (the prompt used to create `docs/plans/PLAN-outreach-agent.md`
and `docs/architecture/ADR-002-outreach-evidence-not-autoapproval.md` in a single
step):**

```text
Create the following 2 files with the exact content specified below.
Do not modify any other file.

=== FILE 1: docs/plans/PLAN-outreach-agent.md ===

# Plan — Outreach Agent (verificación directa con comercios)

**Estado:** Aprobado
**Aprobado por:** Santiago

## Objetivo
Cerrar el gap de los lugares en `needs_review` con evidencia insuficiente,
contactando directamente al comercio para confirmar si tiene opciones
sin TACC reales, en vez de dejarlos indefinidamente en la cola de
revisión humana — sin ceder el criterio conservador del Validator.

## Contexto
El Validator (ADR-001) frena en `needs_review` cuando la evidencia
online no alcanza el piso de confianza (0.85). Hoy esa cola crece cada
corrida y se resuelve solo manualmente. El Outreach Agent no reemplaza
ese juicio — le agrega una fuente de evidencia nueva (la respuesta
directa del comercio), que el Validator reevalúa junto con la
evidencia original (ver ADR-002 para la decisión de por qué esa
respuesta no aprueba directo).

## Diseño en dos etapas, con frecuencias distintas

### Etapa 1 — Envío (`outreach_send`)
- Corre **dentro del pipeline mensual existente**, como 7ma etapa,
  compartiendo el mismo presupuesto de agentes.
- Toma hasta `OUTREACH_MONTHLY_LIMIT` lugares en `needs_review` con
  contacto disponible (prioriza los más antiguos).
- Redacta el mensaje con Claude Haiku (mismo patrón que el Social
  agent), usando una plantilla base + el nombre/categoría del lugar.
- Envía por email (Fase 1) o WhatsApp (Fase 2, sujeto a verificación
  de Meta).
- Guarda el mensaje enviado en `outreach_messages` y actualiza
  `places.outreach_status = 'sent'`.

### Etapa 2 — Recepción e interpretación (`outreach_reply_handler`)
- **No es parte del cron mensual** — es un webhook, disparado solo
  cuando llega una respuesta real. No corre en loop, no consume nada
  si nadie responde.
- Cuando llega una respuesta, el Validator (Claude Sonnet) re-evalúa
  combinando la evidencia original con la respuesta del comercio.
- Resultado de la re-evaluación (ver ADR-002):
  - Confianza combinada alta → `places.status = 'outreach_confirmed'`
    (NO `approved` directo) — queda esperando aprobación humana final,
    con contexto ya resuelto.
  - Sigue ambiguo → vuelve a `needs_review`.
  - Sin respuesta tras el período definido en Fase 1 → permanece en
    `needs_review`, sin cambios.
- Ningún camino de outreach llega a `approved` sin aprobación humana
  explícita.

## Cambios de schema requeridos (ver ADR-002)
- `places.contact_email`, `places.contact_phone` (confirmar primero
  qué trae Google Places Details que hoy no se está persistiendo)
- `places.status`: agregar `outreach_confirmed` como valor válido del
  CHECK constraint existente (junto a pending/approved/needs_review/discarded)
- `places.outreach_status`: `not_sent` / `sent` / `replied` / `no_response`
- `places.outreach_channel`: `email` / `whatsapp`
- Tabla nueva `outreach_messages`: thread completo (mensaje enviado,
  respuesta recibida, timestamps) para auditoría

## Control de gasto
- `OUTREACH_MONTHLY_LIMIT` — techo explícito de mensajes por corrida,
  separado del presupuesto de descubrimiento/validación.
- Prioriza lugares con contacto ya disponible, para no gastar en
  intentos que van a fallar por falta de dato.

## Fases
1. **Fase 0 (ahora):** confirmar qué contacto ya trae Google Places
   Details hoy sin persistir — puede que la mitad del trabajo de
   datos ya esté a mitad de camino.
2. **Fase 1:** canal Email únicamente, envío + webhook de recepción.
   Define acá el período de espera y reintentos antes de considerar
   "sin respuesta".
3. **Fase 2:** canal WhatsApp, en paralelo iniciar verificación de
   negocio ante Meta (proceso externo, no depende de nosotros).

## Fuera de alcance por ahora
- Aprobación automática sin pasar por revisión humana final — la
  respuesta del comercio es evidencia adicional, nunca un atajo de
  confianza ciega (ver ADR-002).
- Reintentos automáticos si no hay respuesta (se define el número de
  intentos y espaciado en Fase 1).

=== FILE 2: docs/architecture/ADR-002-outreach-evidence-not-autoapproval.md ===

# ADR-002: Respuesta de outreach como evidencia adicional, no como aprobación directa

**Estado:** Aceptado

## Contexto
El Outreach Agent contacta directamente a comercios en `needs_review`
para pedir confirmación sobre opciones sin TACC. A diferencia de las
fuentes que el Validator ya evalúa (reseñas de terceros, redes
sociales, Google Places), la respuesta del comercio viene de una
fuente con incentivo económico directo en confirmar que es seguro —
aparecer en el mapa les da visibilidad — sin que eso implique
necesariamente que entienden protocolo de contaminación cruzada o que
la respuesta sea precisa. Auto-aprobar directo desde esa respuesta
introduciría un sesgo estructural nuevo que el rubric actual (ADR-001)
no está diseñado para pesar.

## Decisión
La respuesta del comercio se reinyecta como evidencia adicional al
mismo Validator, no como una vía de aprobación paralela. El resultado
de esa re-evaluación tiene tres salidas:
- Confianza combinada alta (evidencia online + respuesta) →
  `outreach_confirmed` (nuevo estado, NO `approved` directo) — queda
  esperando aprobación humana final, pero con contexto ya resuelto en
  vez de investigación desde cero.
- Sigue ambiguo incluso con la respuesta → vuelve a `needs_review`.
- Sin respuesta tras el período definido → permanece en `needs_review`,
  sin cambios.

Ningún camino de outreach llega a `approved` sin pasar por aprobación
humana explícita.

## Consecuencias

**Positivas:**
- Cierra el gap de evidencia insuficiente sin debilitar el estándar
  de seguridad del ADR-001.
- Reduce el costo de revisión humana: `outreach_confirmed` llega con
  contexto ya resuelto, en vez de requerir investigación desde cero
  como hoy en `needs_review`.
- Mantiene una única fuente de verdad para el criterio de seguridad
  (el Validator), en vez de crear una segunda vía de decisión.

**Negativas / trade-offs aceptados:**
- No resuelve `needs_review` de forma autónoma — sigue requiriendo
  una acción humana final, aunque más liviana.
- Depende de que el comercio responda; sin período de espera y
  reintentos definidos, algunos casos podrían quedar en un limbo de
  "esperando respuesta" indefinidamente (a definir en Fase 1 del plan
  de implementación).

Report back confirming both files were created and their line counts.
```

**Used for:** Documenting a proposed (not yet built) feature — the Outreach Agent
— before any code or schema changes are made, maintaining the same plan-first
discipline used throughout the project. Unlike ADR-001 (which documented an
existing production decision), ADR-002 documents a decision for a feature still
in design phase.

## 20. Outreach agent — `outreach_send` stage (Phase 15)

**Prompt (summary):** "Implement the `outreach_send` stage of the Outreach
Agent, per `PLAN-outreach-agent.md` and ADR-002. Provider is Resend (sandbox
`onboarding@resend.dev`), schema already migrated. Follow the existing agent
conventions (`social_agent.py` / `base.py`): a `BaseAgent` subclass, draft the
message with `claude-haiku-4-5`, respect a new `OUTREACH_MONTHLY_LIMIT`, and
prioritize the oldest `needs_review` places with `phone` or `website` on
file. Start with the design."

**Used for:** Implementing `agents/outreach_agent.py` and
`agents/clients/resend_client.py`, extending `SupabaseClient`
(`fetch_needs_review_for_outreach`, `insert_outreach_message`), adding the
**Outreach** stage to `scripts/run_agents.py` (7th, after Updater), the new
`RESEND_API_KEY` / `OUTREACH_TEST_RECIPIENT` / `OUTREACH_MONTHLY_LIMIT`
settings, and offline tests (`tests/test_outreach_agent.py`).

**Key decisions made during this prompt:**
- **Fixed test recipient, not per-business email:** Google Places has no email
  field (only `phone`/`website`, confirmed while building this), and Resend's
  sandbox sender can only deliver to the account's own verified email anyway —
  so every send currently targets a fixed `OUTREACH_TEST_RECIPIENT`, while
  selection/drafting/logging still operate on the real candidate.
- **No new `'failed'` status:** a drafting or send failure leaves
  `outreach_status` at `'not_sent'` (nothing is written), so the place is
  naturally retried next run — mirrors how Social/Search swallow per-item
  errors.
- **Haiku for drafting, same rubric-plus-JSON-contract pattern as Social's
  `PARSE_RUBRIC`:** a templated confirmation email from
  `{name, category, city}` is a cheap, low-judgment task; no safety judgment
  is made here (that remains the Sonnet Validator's job, for the
  not-yet-built Etapa 2 reply re-evaluation).

**Input variables** (one call per candidate place):
- `{{place_name}}`, `{{category}}`, `{{city}}` — drawn straight from the
  `places` row.

**The exact rubric (`OUTREACH_RUBRIC` in `agents/outreach_agent.py`):**

```text
Redactás un email breve y respetuoso en nombre de CeliacMap, un proyecto
comunitario que mapea lugares gluten free / sin TACC en Uruguay y Argentina,
dirigido a un comercio que aparece como candidato en el mapa pero todavía no
tiene evidencia suficiente confirmada.

Se te da el nombre del comercio, su categoría y su ciudad. El email debe:
- Presentar brevemente a CeliacMap (un mapa comunitario, no una entidad oficial).
- Pedir amablemente que confirmen si ofrecen opciones sin TACC y, si es
posible, que describan su protocolo de contaminación cruzada.
- Ser breve (2-3 párrafos cortos), cordial, sin sonar a spam ni a exigencia.
- Firmarse como "Equipo de CeliacMap".

Respondé ÚNICAMENTE con un objeto JSON válido, sin texto adicional, exactamente
con esta forma:
{"subject": "<asunto breve>", "body": "<cuerpo del email en texto plano>"}
```

**Worked example:**

For a `needs_review` place `{"name": "Café Aroma", "category": "cafe", "city":
"Montevideo"}`, Haiku returns:

```json
{"subject": "Confirmación sin TACC — Café Aroma",
 "body": "Hola,\n\nSomos el equipo de CeliacMap, un mapa comunitario de lugares gluten free / sin TACC en Uruguay y Argentina. Encontramos a Café Aroma como candidato, pero todavía no tenemos evidencia suficiente confirmada.\n\n¿Podrían confirmarnos si ofrecen opciones sin TACC y, de ser posible, contarnos brevemente cómo evitan la contaminación cruzada?\n\nSaludos,\nEquipo de CeliacMap"}
```

The agent sends this via Resend (to the fixed test recipient for now),
records it in `outreach_messages`, and flips that place's
`outreach_status` to `'sent'`.

## 21. Outreach reply handler — opt-out detection (ADR-003)

**Prompt (summary):** "Implement opt-out detection in the Outreach Agent,
per ADR-003 (not yet written as a file, but the design is settled). In
`outreach_agent.py`, the Haiku-drafted email must get a fixed, literal
(non-LLM) closing line telling the business how to opt out. In
`outreach_reply_handler.py`, before the full RUBRIC/Sonnet re-evaluation,
add a cheap Haiku pre-check classifying whether the reply is an opt-out
request. If yes: mark `places.outreach_opt_out = true`, log it, and skip
the full re-evaluation (saves the Sonnet cost). If no: continue the
existing flow unchanged. In `_select_candidates()` and
`fetch_needs_review_for_outreach`, always exclude
`outreach_opt_out = true` places, regardless of `outreach_status`. Start
with the design."

**Used for:** Implementing `OPT_OUT_FOOTER` + its append in `_draft()`
(`agents/outreach_agent.py`), `OPT_OUT_RUBRIC` + `_classify_opt_out()` +
its insertion into `handle()` (`agents/outreach_reply_handler.py`), the
`outreach_opt_out` exclusion filter in both
`SupabaseClient.fetch_needs_review_for_outreach` (SQL) and
`OutreachAgent._select_candidates` (Python, defense in depth), the
`places.outreach_opt_out` column (`db/schema.sql`, applied live to
Supabase), and offline tests (`tests/test_outreach_agent.py`,
`tests/test_outreach_reply_handler.py`).

**Key decisions made during this prompt:**
- **Classification fails closed, toward "not opt-out":** on any error
  (Haiku call fails, malformed JSON), `_classify_opt_out()` defaults to
  `is_opt_out=False` — never the reverse. A missed opt-out just falls
  through into the existing, already-conservative Sonnet re-evaluation
  (safe, known behavior); a false positive would permanently block a
  legitimate business, since `outreach_opt_out` has no unset path in this
  design. This needs its own `try/except`, separate from the full-eval's —
  reusing that one would incorrectly abort the real re-evaluation on a
  mere classification hiccup.
- **Footer appended after `_draft()`'s empty-check, not before:**
  appending first would make `body` always non-empty, silently defeating
  the existing guard that returns `None` on a degenerate Haiku draft.
- **Opt-out never touches `places.status`:** a business declining further
  contact isn't evidence about GF safety — only `outreach_opt_out`
  changes; the Validator-owned `status` stays whatever it was.

**Input variables** (one call per received reply):
- `{{reply_text}}` — the business's raw reply content, fetched via
  `fetch_latest_received_message`, passed as-is with no template wrapping.

**The exact rubric (`OPT_OUT_RUBRIC` in `agents/outreach_reply_handler.py`):**

```text
Analizás la respuesta de un comercio a un email de CeliacMap que le pedía
confirmar si ofrece opciones sin TACC. Tu única tarea es determinar si el
comercio está pidiendo explícitamente NO recibir más contactos de
CeliacMap — nada más. No evalúes si el lugar es seguro para celíacos.

Es un opt-out cuando el comercio pide explícitamente que no lo contacten
más, que lo den de baja, que dejen de escribirle, o rechaza ser contactado
nuevamente. NO es un opt-out una respuesta que simplemente no confirma
información sin TACC, ignora la pregunta, o es ambigua — ante la duda,
respondé false.

Respondé ÚNICAMENTE con un objeto JSON válido, sin texto adicional,
exactamente con esta forma:
{"is_opt_out": true | false, "reason": "<breve explicación en español>"}
```

**Worked example:**

For a received reply `"Por favor no nos contacten mas, no queremos
participar."`, Haiku returns:

```json
{"is_opt_out": true, "reason": "El comercio pide explícitamente no ser contactado nuevamente."}
```

`_classify_opt_out()` returns `{"is_opt_out": True, "reason": "..."}`;
`handle()` persists `places.outreach_opt_out = true` via `update_place`,
logs `outreach_reply_opt_out_detected`, and returns
`{"place_id": place_id, "opt_out": True}` — the RUBRIC/Sonnet call never
fires. A reply like `"Si, tenemos opciones sin TACC certificadas."` would
instead return `{"is_opt_out": false}`, and `handle()` continues into the
existing full re-evaluation unchanged.

## 22. `OUTREACH_LIVE_MODE` — final switch of ADR-003

- **Trigger:** ADR-003's three conditions (verified domain, opt-out
  mechanism, bounded volume) were all met; implement the actual code switch
  from the sandbox test recipient to real per-business delivery.
- **Change:** new `Settings.outreach_live_mode` (`OUTREACH_LIVE_MODE`,
  default `false`). When `true`, `OutreachAgent` sends to
  `place["contact_email"]` instead of `OUTREACH_TEST_RECIPIENT`, with no
  shared code path between the two modes; `_select_candidates()` additionally
  requires `contact_email` in live mode, and a candidate that reaches the
  send step without one is skipped and logged
  (`outreach_send_missing_contact_email`) rather than silently falling back
  to the test recipient.
- **Files:** `config/settings.py`, `agents/outreach_agent.py`,
  `.env.example`, `tests/test_outreach_agent.py`, `tests/test_settings.py`.
- **Rationale:** shipping the capability and flipping it on are kept
  separate — the default stays `false`, so `OUTREACH_LIVE_MODE=true` in
  `.env` / GitHub Secrets is a distinct, deliberate operational step, per
  ADR-003's own framing (accepting the ADR documents that its conditions are
  met; it doesn't itself activate sending).
- **Follow-up (same review pass):** manually reviewing the first 3 real
  live-mode candidates before activation surfaced a `website_scraper.py`
  false-positive bug (image-filename and platform-domain emails matching the
  regex) — fixed separately (`fix: reject false-positive emails from website
  scraper`) before enabling live mode for real. See CLAUDE.md's updated
  `contact_email` bullet under **Outreach agent design decisions**.
- **CI wiring (later session):** `OUTREACH_LIVE_MODE` added as a GitHub
  Secret and forwarded into `agents-monthly.yml`'s `env:` block — closing the
  gap where the secret existed but the workflow never passed it through to
  `scripts/run_agents.py`. See CLAUDE.md's Phase 18 build-status entry.

## 23. ADR-004 + PLAN-community-reviews.md — Community Reports Design

**Prompt (summary):** "Draft ADR-004 (reportes comunitarios como evidencia,
no acción directa — mismo patrón que ADR-002/outreach). Investigá cómo está
armado `outreach_reply_handler.py` + su Edge Function para reusar el mismo
patrón, ahora disparado por un `INSERT` en una tabla nueva `place_reports`
en vez de un webhook de email, y redactá
`docs/plans/PLAN-community-reviews.md` con schema, frontend, backend y
tests. Mostrame el plan para revisión antes de tocar código."

**Used for:** Documenting a proposed (not yet built) feature — community
"recommend / report" evidence on places already published on the map —
before any schema or code changes, same plan-first discipline used for
Outreach. Produced
`docs/architecture/ADR-004-community-reports-evidence-not-direct-action.md`
(Estado: Propuesto) and `docs/plans/PLAN-community-reviews.md`.

**Key decisions made across this multi-turn design session:**
- **Reused Etapa 2's exact pattern, one real difference in status
  mapping.** The planned `agents/review_handler.py` reuses `RUBRIC` /
  `ValidatorAgent._normalize` unmodified, same as `outreach_reply_handler.py`
  — but with **no remapping** to a distinct status (unlike outreach's
  `outreach_confirmed`): since the place is already `approved`, the
  Validator's own verdict (approved/needs_review/discarded) is trusted
  directly.
- **Fase 0 surfaced a real design gap before any code was written.**
  Investigating Supabase Database Webhooks (the planned trigger, replacing
  Resend's webhook) found they do **not** auto-retry on non-2xx/timeout,
  unlike Resend — invalidating the original "500 = retryable" assumption
  borrowed from `outreach-reply.ts`. Resolved by adding a monthly sweep
  stage (`ReviewHandler.sweep()`) to `scripts/run_agents.py` as a safety
  net, with an atomic claim (`claim_place_report`, CAS on
  `place_reports.status`) as the one guard making the real-time path and
  the sweep safe to race against each other — a report is never processed
  twice.
- **Schema prepared (Fase 1), not yet applied live:** `place_reports`
  table + `suggestions.origin` column drafted in `db/schema.sql`;
  `js/suggest.js` sends `origin: 'community'` explicitly.
- **Real production bug found and fixed while preparing this apply**
  (unrelated to the new feature, but blocking it): running `db/schema.sql`
  fresh end-to-end for the first time (previous migrations were always
  applied incrementally, one new block at a time) revealed that superseded
  `CHECK`-widening `do $$` blocks are **not** safe to leave in the file once
  real production data exists outside their (narrower) allowed set — an
  *earlier*, narrower block fails outright against current rows, even
  though a *later* block in the same file would have permitted them. Found
  via the file's own `places_status_check` (an old 4-value block predating
  `outreach_confirmed`, which real rows already use) and confirmed the same
  latent bug in `agent_log_agent_check`'s 4-block widening chain via a
  **read-only** `supabase db query --linked` check against production (19
  `agent='outreach'` rows, 6 `agent='outreach_reply'` rows). Both collapsed
  to a single final block each. General lesson: a chain of "widen in place"
  migration blocks is only safe to *incrementally* apply over time as each
  one ships — not to replay from scratch once real data has accumulated
  past the earliest ones.
- **Verification tooling discovered this session:** the Supabase CLI **is**
  installed (npm devDependency, `node_modules/.bin/supabase`, v2.111.0 —
  not on the system PATH, which is why it was initially missed) and already
  linked+authenticated to the real `celiacmap` project. `supabase db query
  --linked --file <path>` can execute SQL directly; `supabase db query
  --linked "<sql>"` was used read-only above to confirm the `agent_log` bug
  against real data. `pglast` (Python bindings to Postgres's real parser,
  `libpg_query`) was used as a local syntax check — installed and
  uninstalled per check, not a project dependency.

**Not yet done:** the SQL has not been applied to the live database; Fase 2
(backend: Edge Function, workflow, `agents/review_handler.py`) and Fase 3
(frontend form) are still unbuilt — see `docs/plans/PLAN-community-reviews.md`
for the full remaining plan.

---

## 24. Geocode-gate address fallback — deliberate RUBRIC change

**Prompt (summary):** "Implementar el fallback de geocodificación por
dirección (ya investigado y aprobado): un helper `resolve_location` centralizado
en `GooglePlacesClient` que, cuando Find Place por nombre no encuentra el
negocio, geocodifica la **dirección** vía la Geocoding API y acepta el candidato
con un marcador `geocode_method='address_only'`. Social, Web y el Suggestion
promoter usan el helper. El Validator recibe una línea de contexto extra y su
RUBRIC pide cautela para esos candidatos. Documentar el cambio de RUBRIC."

**Why:** Small gluten-free businesses that only exist on Instagram/Facebook have
no Google Place, so Find Place returned nothing and the candidate was rejected
before ever reaching the Validator (real case: "Bienestar Gluten Free", Fray
Bentos — a user suggestion auto-rejected 2026-06-10). The address fallback trades
a little precision for recall: a candidate whose *address* geocodes to a real
point in UY/AR now reaches the Validator, but **marked** as weaker evidence.

**The deliberate RUBRIC change (added to the `RUBRIC` constant in
`agents/validator_agent.py`, and to the verbatim copies in §12 above and
CLAUDE.md's Core Prompt section):**

```text
Si el mensaje incluye "ubicacion_geocode", significa que solo se geocodificó la
dirección de texto del candidato: NO hay una ficha de Google Places que confirme
que el negocio existe y opera en ese lugar (sin reseñas de Google, sin
verificación de existencia). Tratá esto como evidencia debilitada — NO asignes
"approved" salvo que el resto de la evidencia (mención explícita de "sin TACC",
reseñas claras de la comunidad) sea fuerte por sí sola. Ante la duda,
"needs_review".
```

`ValidatorAgent._build_user_prompt` appends the corresponding
`ubicacion_geocode: ...` line to the **user** message only when the candidate's
`places.geocode_method == 'address_only'` (absent for rows predating the column
and for the Search agent, which always resolves to a real Google Place). The
confidence gates in `_decide_status` are unchanged — the model is asked to be
conservative, not forced by code; the existing 0.85 auto-approval floor already
backstops it.

**Worked example.** Candidate: `Bienestar Gluten Free`, `Rivera 1967`, Fray
Bentos, `source='user'`, `geocode_method='address_only'`, no Google reviews. User
message carries the `ubicacion_geocode:` note. Expected verdict: `needs_review`
(the address is real, "sin TACC" is claimed in the user's notes, but nothing
external confirms the business operates there) — not `approved`.

**Full rationale + investigation:** CLAUDE.md Decisions Log,
"Geocode-gate — address fallback (`resolve_location`)".

---

## 25. Public site — remove Roadmap section & all GitHub links

**Prompt (paraphrased, owner's final decision):**

> "Two content changes to the public site. **(1)** Delete the Roadmap section
> entirely — the copy is stale (describes shipped work as 'future'). Remove the
> section, the nav link (desktop + mobile), any orphaned Roadmap i18n keys (EN
> dict too), and confirm no broken `#roadmap` anchors remain. **(2)** Remove
> every GitHub link from the public site — the GitHub button in the About author
> card (keep LinkedIn), the 'Ver en GitHub' button in the CTA band (keep
> 'Explorar el mapa', fix the centering for one button), any other
> `github.com/santisanchez4` reference, and orphaned 'Ver en GitHub' i18n keys.
> Verify with desktop + real-device-emulation mobile screenshots and 0 console
> errors. Show the full diff before committing. This is only about what the
> public site shows — we keep pushing to GitHub for version control."

**What was done.** Frontend-only edit — `index.html` (6 removals + the AI
eyebrow trimmed from "Visión futura · Roadmap" to "Visión futura"),
`js/main.js` (15 orphaned `nav.roadmap` / `roadmap.*` keys + `cta.secondary`
removed, `ai.eyebrow` EN trimmed), `css/styles.css` (dead `.timeline*` rules
removed). No CSS change was needed for the lone CTA button — `.cta-actions`
was already `justify-content: center`. Docs kept in sync: `README.md` section
count 12→11, this entry, and the CLAUDE.md Decisions Log entry **"Public site
— Roadmap section & GitHub links removed (2026-09-01)"** (full rationale +
scope note there). GitHub Actions / Pages / repo-URL mentions in `README.md`
were deliberately left — they document infrastructure, not the public site.

---

## 26. Community ranking (ADR-005) — research → ADR → phased build

**Prompt (paraphrased, across several turns):**

> "Investigate what infrastructure could be reused for a community ranking
> of the most-voted/recommended places, filtered by country, next to the
> map — research + ADR draft only, no code. … Accept the ADR, write a
> phased implementation plan (each phase its own commit). … Execute Fase A
> (schema), then B (DB/API checks), then C (frontend), then D (seed — I'll
> give you the list), then E (verification + README), then F (docs). Show
> me the diff / verification before each commit."

**What was built.** A "Los favoritos de la comunidad" section after
`#map`: top-12 `approved` places per country by a one-click anonymous
**vote**. Design principle (ADR-005, same as ADR-002/004): the vote
**orders** the ranking, it has **zero authority** over `places.status` —
only the Validator decides safety, and the ranking sits strictly on top of
already-approved places.

- **Research findings:** no votes/likes table existed; `place_reports`
  positive (ADR-004) requires a text `description` so it can't be a
  textless "upvote"; `places.rating` / `user_ratings_total` are 100% Google
  Places, not community. → new dedicated `place_votes` table.
- **Fase A** (`df8376b`) — `place_votes` (anon-INSERT-only,
  `unique (place_id, voter_token)`, token CHECK 8–64), denormalized
  `places.vote_count` + index, `sync_place_vote_count` trigger, RLS whose
  `with check` requires an `approved` target (subquery under the anon
  `places` RLS).
- **`6af819d`** — the trigger needed `SECURITY DEFINER`: as `INVOKER` an
  anon-fired `INSERT` ran `update places` as `anon` (no UPDATE policy) and
  Postgres silently filtered it to 0 rows, so `vote_count` never moved.
  Caught in Fase B with `BEGIN; … ROLLBACK;` test data before any real
  traffic.
- **Fase B** (`7ffa728`) — `db/checks/2026-09-01-place-votes.sql`
  (6 rollback'd checks, all PASS) + a real PostgREST smoke test. Key
  finding: the ADR's `resolution=ignore-duplicates` dedup **isn't usable**
  (PostgREST's upsert path needs a `SELECT` grant the design withholds);
  `ranking.js` uses a plain `POST` and treats a `409/23505` as success.
- **Fase C** (`1904901`) — `js/ranking.js` (fetch + render reusing
  `.pp-*`, `.chip` country tabs default Argentina remembered in
  `localStorage`, `voter_token` / voted-set / 10 s cooldown), `#ranking`
  section (2-col grid cloning `.features-layout`), a `.pp-vote` button in
  the map panel wired via a new `celiacmap:panel-open` event, zebra flip
  on the 4 sections below. No nav link (v1).
- **Fase D** (`95097e3`) — 15 objectively-selected real approved places
  (`validation_confidence >= 0.85`, Google `rating >= 4.5` with `>= 30`
  ratings, one per city, 9 AR provinces/metros + 6 UY departments), vote
  counts 3–15 quality-correlated → 124 seed rows via `generate_series`.
  Also fixed "Marce Cakes® Gluten Free" `city` (`Paraná` → `Santa Fe`) and
  flagged the "JANA GLUTEN FREE" duplicate as data debt.
- **Fase E + F** — end-to-end verification against the real seed (both tabs,
  vote → count bump → test vote deleted → trigger decrements), a
  `.rk-name { flex-basis: 100% }` polish so every row reads name /
  (city · badge) uniformly, README structure update, ADR-005 `## Verificación`
  section, CLAUDE.md Phase 21 + ADR pointer + C4 note, this entry, and
  `PLAN-community-ranking.md` → Completado.

**Full design + phase detail:** `docs/architecture/ADR-005-community-ranking.md`
and `docs/plans/PLAN-community-ranking.md`.
