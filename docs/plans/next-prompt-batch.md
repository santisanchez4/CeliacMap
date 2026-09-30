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
