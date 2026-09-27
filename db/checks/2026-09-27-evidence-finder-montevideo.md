# Evidence finder — the 13 Montevideo places of the admin queue (2026-09-27), aggregate numbers

Live run over the queue places of Montevideo (`--city Montevideo --max-searches 30`), sources frozen; then replayed on the frozen sources with the
attribution fix (`docs/DECISIONS.md`, follow-up of "Evidence finder for the admin-pending 100% queue"). Nothing was written to the database.
The reports (quotes, URLs, place ids) are git-ignored in `db/checks/evidence-proposals/`.

| | 100 | 100 · verificar en la fuente | options | insuficiente | Tavily searches | Haiku tokens in / out |
|---|---|---|---|---|---|---|
| Live run | 3 | 0 | 3 | 7 | 26 | 10 444 / 1 865 (~US$0.020) |
| Replay with the fix (same sources) | 2 | 0 | 4 (1 with "posible 100") | 7 | 0 | 8 324 / 1 274 (~US$0.015) |

- Insuficientes by what the place has: website 2 · red social 1 · nada 4 (unchanged by the fix).
- All 13 Validator notes rest on the place's name alone (no reviews, no stored evidence).
- **What the run found:** one of the three 100s (Un Lugar Sin Gluten) was proposed from a sentence that belongs to another restaurant of the guide it came from.
  After the fix it is options with a "posible 100" backed by its own sentence. The other two 100s (Milena Gluten Free, RecoBeco Gluten Free) rest on
  quotes verified on the businesses' own websites and did not change.
- The earlier 10-place pilot replayed on its own frozen sources: Matilde and Apto unchanged; two flips (Pagana, @TACCTOMDP) caused by the model's variance between runs.
- Tests: Python 695 → 712.
