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
