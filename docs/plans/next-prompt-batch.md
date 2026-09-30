# Next chatbot prompt batch — queued changes

> One list of every change waiting for the next edit of `supabase/functions/chat/prompts.ts` (`ROUTER_PROMPT`,
> `RESPONDER_PROMPT`). Started 2026-09-29 (privacy phase 1) by collecting the items spread over `docs/DECISIONS.md`.
> Every item is applied together: one real-model A/B, one jailbreak battery (`db/checks/chat_jailbreak_battery.py`), one
> restart of the soft-launch count, recorded in `docs/DECISIONS.md` and `prompts.md` (CLAUDE.md, "Prompts and chatbot").
> When an item is done, strike it here and name the entry that records it.

## Privacy (2026-09-29, privacy phase 1)

1. **Stop asking whether the owner is celiac** (`docs/legal/owner-celiac-plan.md`, stage 2). The code already discards
   the answer (it never reaches a draft, a row or `<envio>`), but the prompts still ask for it: `ROUTER_PROMPT` rule 9
   (`dueno_celiaco`), rule 10, the `dueno_celiaco` field of `<output_format>` and of every example's `Salida:`, the "Pan
   Justo" example; `RESPONDER_PROMPT` rules 3 and 5 (the kitchen question and the invitation), the constraint "Preguntar
   si el dueño o la dueña… es un dato del negocio" and the Pan Justo examples (including the `<envio>` with
   `"dueno_celiaco": "si"`). **Keep** the constraint "NUNCA digas… 100% porque el dueño sea celíaco" (it covers free
   text). Afterwards remove `dueno_celiaco` from `RouterOutput`, `parseRouterOutput` and `kitchenFactsFromRouter`.
   Measure: the redactor never asks about the owner (`db/checks/chat_kitchen_live.py`), kitchen extraction does not get
   worse (`db/checks/chat_kitchen_router_check.py`).
2. **Tell the person a recommendation may be published as "Anónimo".** Módulo 4 (`decideConfirmarSubmission`) and
   the report flow store a positive report the admin could publish, and the chat never says so (form B does, under the
   name field). Until the notice exists, `scripts/moderate_opinions.py` never offers a recommendation without
   `reporter_token` (the chat never sends one). With the notice live, decide whether chat recommendations become
   publishable (and how to tell them apart then: a `reporter_token` minted by the chat, or an `origin` column).

3. **The chat no longer asks about the kitchen (code, 2026-09-30).** `preguntar_cocina` and `invitar_cocina` are never
   set and `kitchen_asked` is never kept, so the redactor's kitchen question (which still names the owner) never fires;
   facts a person volunteers are still kept, the owner's health still discarded. In this batch: **decide whether the chat
   asks about the kitchen again.** If not, remove the kitchen instructions from `RESPONDER_PROMPT` (rule 3's optional
   question, rule 5's invitation, the owner constraint, the Pan Justo examples) and the router's `cocina_respuesta` (rule
   10); if yes, bring them back without the owner question (item 1) and turn the code flags on again, with the kitchen
   A/B (`db/checks/chat_kitchen_live.py`). The kitchen question is then only in form A (“Agregalo”).
   Live finding (chat v24, 2026-09-30): with the flags off, the draft turn no longer asks, but when Módulo 4
   (`confirmar`) asks for more detail (`necesita_mas_detalle`), the redactor improvised kitchen-style examples ("¿es 100%
   sin gluten o tiene opciones sin TACC? ¿Cómo preparan lo apto para celíacos?"); the owner was not asked. Also, "quiero
   recomendar un lugar nuevo que no está en el mapa" was routed to `confirmar` (a place still being verified) and the
   address given there was lost once the draft started in `reportar`. Cover both in this batch.

## Earlier items (from `docs/DECISIONS.md`)

4. **Replace the Bienestar Gluten Free example** in the prompts (a partner since 2026-09-28; see "Sponsorships",
   pre-existing finding, `prompts.ts` lines ~467–474).
5. **Redactor glossary: Argentina's official term is now "sin gluten"** (Joint Resolution 32/2023; see "Sponsorships").
6. **The 2c-vs-examples contradiction** ("Por ahora no tengo lugares confirmados en…"; see "Department / province
   search" and "`category_zero` telemetry").
7. **F4 Option 1: reformulate the `celiaquia` prompt** (in progress, non-blocking; see "Chatbot Fase E").
8. Only if the `category_zero` telemetry shows it with real traffic: option C and a router rule for "locales / lugares /
   sitios" (careful: "dónde comprar" does imply `shop`), "Cerca hay…" (a proximity the system does not verify), the
   medical queries (Fase E follow-ups) and the pure cancels (Fase D).

## Validator `RUBRIC` (not the chatbot) — added 2026-09-30

This item edits `RUBRIC` in `agents/validator_agent.py`, not `prompts.ts`. It has its own gate (a real-model Validator
A/B, like `db/checks/validator_audit_ab.py`) and does **not** restart the chatbot's soft-launch count; it is listed here
so the "sin gluten" change reaches the Validator and the chat (item 5) together. Copies re-synced by
`tests/test_rubric_docs_sync.py`: `CLAUDE.md`, `prompts.md`, `README.md`. The MCP `validate_place` tool reuses the same
`RUBRIC`. **Not changed yet.**

9. **The "sin gluten without sin TACC" flag is out of date for Argentina** (Joint Resolution 32/2023: "sin gluten" is
   now the official term in Argentina; certified gluten-free oats can be suitable. Checked 2026-09-30: the 10 mg/kg limit is in the
   official text; certified oats and the new symbol are **not** verified, and the methodology document asks the
   Asociación Celíaca Argentina to validate oats before the criteria change: do not write oats into the `RUBRIC` until
   then). Today the `RUBRIC`
   lowers confidence with the flag `Menciona "sin gluten" pero no "sin TACC" (puede ser marketing, no médico)`, and its
   `approved` line accepts `"sin TACC"` or a *certified* `"sin gluten"` only. An Argentine place that follows the new
   rule and writes only "sin gluten" is penalized for using the official term. The public methodology document
   (`docs/metodologia/metodologia-celiacmap.md`, §11) already says this update is in progress.

   **Proposed wording** (draft for the A/B, not final):
   - `approved` line: `…con mención directa de "sin TACC"; en Argentina, también de "sin gluten" (denominación oficial
     desde la Resolución Conjunta 32/2023) cuando se refiere a lo que el lugar elabora o vende; de un sello oficial o un
     producto certificado; o descripción de protocolo anti-contaminación cruzada.`
   - The flag is replaced by: `Usa "sin gluten", "gluten free" o "libre de gluten" solo como reclamo publicitario
     (adjetivo suelto, hashtag, "opciones sin gluten" sin decir cuáles ni cómo se preparan), sin sello, sin producto
     certificado y sin describir una práctica concreta. En Argentina "sin gluten" es el término oficial: el término por sí
     solo no baja la confianza; lo que la baja es que no haya sello, certificación ni práctica concreta detrás.`
   - New flag: `Ofrece productos con avena sin indicar que la avena es certificada sin gluten.`
   - Unchanged: Uruguay (the flag keeps its current meaning there), the three verdicts, the 0.85 / 0.5 gates, the
     "lowest level when in doubt" rule, the 100% definition and Tope A/B/C. `_EXCLUSIVE_SIGNAL_RE` already accepts
     "sin gluten", so Tope C needs no change.

   **A/B that would validate it** (`db/checks/validator_sin_gluten_ab.py`, same shape as `validator_audit_ab.py`: both
   arms get the same user prompt, only the system `RUBRIC` differs, OLD = `main`, NEW = working tree; real model, n=4,
   synthetic places, no DB writes; reports the raw verdict, the confidence, the level after caps and the flags):

   | Case | Evidence | Acceptance (NEW arm) |
   |---|---|---|
   | AR official term | Argentine bakery: "todos nuestros panificados son sin gluten, elaborados en planta exclusiva" | confidence ≥ OLD on average; same or higher verdict; no "sin TACC" flag |
   | AR product + seal | Argentine café: "budines sin gluten con sello oficial" | no marketing flag; verdict ≥ OLD |
   | AR marketing only | Argentine restaurant, Instagram bio: "opciones sin gluten 🌱 #glutenfree" | **0 of 4 `approved`** (guard: the change must not open the gate to marketing) |
   | AR English marketing | "gluten free friendly" only | 0 of 4 `approved`; same as OLD |
   | UY control | the "AR official term" text on a Uruguayan place | verdict and confidence within OLD's range (the change is scoped to Argentina) |
   | "sin TACC" control | explicit "sin TACC" + cross-contamination protocol | same as OLD |
   | Oats, uncertified | "granola con avena" on a "sin gluten" menu | oats flag in ≥ 3 of 4; 0 `approved` |
   | Oats, certified | "avena certificada sin gluten" | no oats flag |
   | Community-only | only `declaraciones_comunidad` saying "todo sin gluten" | 0 `approved`, 0 `gluten_free_100` after caps (unchanged) |
   | Name only | a place named "X Sin Gluten", no evidence | 0 `approved`, 0 `gluten_free_100` (unchanged) |

   Then a **read-only replay** on real rows: run `ValidatorAgent.evaluate()` with both rubrics on a sample of Argentine
   `needs_review` / `approved` places whose evidence says "sin gluten" but not "sin TACC" (no writes), list every status
   change, and have the admin read each place that would move to `approved` before accepting. Record the runs in
   `db/checks/`, the decision in `docs/DECISIONS.md` and `prompts.md`, and the new `RUBRIC` text in its three copies.
   The map labels do not change ("Sponsorships": review them after December 2026).
