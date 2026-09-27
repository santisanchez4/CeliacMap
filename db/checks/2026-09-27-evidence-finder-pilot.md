# Evidence finder — pilot of 10 places (2026-09-27), aggregate numbers

Design, findings and decisions: `docs/DECISIONS.md`, "Evidence finder for the admin-pending 100% queue". The reports themselves (quotes, URLs,
place ids) are third-party text and go stale: they live in `db/checks/evidence-proposals/`, git-ignored. Nothing was written to the database
in any run: only local reports. The same 10 places (10 cities: 3 with an own website, 3 with a social profile, 4 with no link; the three
categories) were used every time (`pick_pilot` is deterministic).

| Run | What it is | 100 | options | insuficiente | 100 · verificar en la fuente | Tavily searches | Haiku tokens in / out |
|---|---|---|---|---|---|---|---|
| 1 | live, first logic | 2 | 5 | 3 | (no labels yet) | 20 | not recorded |
| 2 | live, verification labels, vetoes with reason, discarded sources | 2 | 5 | 3 | 2 | 20 | 6 797 / 3 488 (~US$0.024) |
| 3 | live "capture" (same logic as 2) + freeze of what it retrieved | 2 | 6 | 2 | 2 | 20 | 7 936 / 4 154 (~US$0.029) |
| 3a | replay of 3 with name masking, code-level attribution, looser source filter | 3 | 4 | 3 | 2 | 0 | 12 949 / 4 481 (~US$0.035) |
| 3b | replay of 3 with identity words + neighbour veto (**final**) | 2 | 4 | 4 | 1 | 0 | 12 917 / 4 312 (~US$0.034) |

- Live runs differ from each other because Tavily's results and the model vary; only 3, 3a and 3b compare on identical sources.
- **Run 3a proposed one wrong 100** (Concepción sin TACC, from a reel of another business of the same city). Run 3b fixed it; the two
  remaining proposals of the 100 family were checked against the places' own data and are right.
- **Final proposals by place (run 3 → 3b):**

| Place | City | Run 3 | Final (3b) |
|---|---|---|---|
| Apto Libre de Gluten | San Nicolás de los Arroyos | 100 · verificar en la fuente | 100 · verificar en la fuente |
| Matilde Gluten Free | San Pedro | 100 · verificar en la fuente | **100** (two quotes verified on the page) |
| Vichenzo Sin Tacc Monserrat | Buenos Aires | options | options |
| Selkkis Gluten Free | Montevideo | options | options |
| Pagana Gluten Free | Ciudad de la Costa | options | options |
| Michela Sin Gluten Guaymallen | Mendoza | options | options |
| @TACCTOMDP | Mar del Plata | options | insuficiente |
| Concepción sin TACC | Concepción del Uruguay | options | insuficiente |
| Mesa Libre Gluten Free | Ituzaingó | insuficiente | insuficiente |
| Karina - Productos Para Celiacos | El Palomar | insuficiente | insuficiente |

- **Insuficientes by what the place has (final):** website 0 · red social 2 · nada 2. The rule for them is the owner's, after the full run.
- **Verification labels (run 2):** 6 citations verified on the page, 4 from social profiles (not verifiable), 0 snippet-only.
- **Tavily's usage endpoint** read 25 / 1000 before the first run and after the second (40 searches): it does not move; do not size a run from it. Total live searches of the pilot: 60.
- Tests: Python 535 → 695.
