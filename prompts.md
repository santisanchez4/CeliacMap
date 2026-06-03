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
