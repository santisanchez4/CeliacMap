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
