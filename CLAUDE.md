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

## Technical Scope

- Use HTML and CSS as the main foundation.
- Keep the project simple and easy to run.
- Do not add frameworks or external libraries without a clear reason.
- A lightweight JavaScript file (`js/main.js`) is allowed for minor interactions such as smooth scrolling, mobile menu toggling, or simple animations — only if it adds real value.
- Do not add backend, database, or authentication unless explicitly requested.
- Do not implement real AI if there is no explicit decision to do so. AI must be presented as part of the roadmap or future vision.
- Prioritize clean, semantic, responsive, and accessible code.

## File Structure

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

> **Follow-up (out of scope here):** the English strings in `js/main.js` still
> hold the previous wording. The ES/EN toggle keeps working, but the EN
> dictionary should be updated to match the rewritten Spanish copy.