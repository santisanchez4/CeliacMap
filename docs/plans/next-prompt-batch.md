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

## Earlier items (from `docs/DECISIONS.md`)

3. **Replace the Bienestar Gluten Free example** in the prompts (a partner since 2026-09-28; see "Sponsorships",
   pre-existing finding, `prompts.ts` lines ~467–474).
4. **Redactor glossary: Argentina's official term is now "sin gluten"** (Joint Resolution 32/2023; see "Sponsorships").
5. **The 2c-vs-examples contradiction** ("Por ahora no tengo lugares confirmados en…"; see "Department / province
   search" and "`category_zero` telemetry").
6. **F4 Option 1: reformulate the `celiaquia` prompt** (in progress, non-blocking; see "Chatbot Fase E").
7. Only if the `category_zero` telemetry shows it with real traffic: option C and a router rule for "locales / lugares /
   sitios" (careful: "dónde comprar" does imply `shop`), "Cerca hay…" (a proximity the system does not verify), the
   medical queries (Fase E follow-ups) and the pure cancels (Fase D).
