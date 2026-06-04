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
