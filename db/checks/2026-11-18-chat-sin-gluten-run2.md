# Chat «sin gluten» batch — offline run 2 (2026-11-18)

Re-measurement after the run 1 fix (the jailbreak-mix constraint + one example). Only the router changed, so the redactor suites (labels, f4, legit) were not repeated. 184 calls approved (~US$0.38), `claude-haiku-4-5`, no production writes.

Result: PASS — 17/17 router cases, the courtesy / confirmation suite identical to `main`.

## chat_kitchen_router_check.py --n 8 --max-calls 136

```
PLAN: 17 case(s) x n=8 = 136 call(s) to claude-haiku-4-5, ~US$0.14; hard cap 136
[PASS] 8/8 (must not infer) bare 'sí' confirms, stores nothing
[PASS] 8/8 (must not infer) 'sí, mandalo' confirms, stores nothing
[PASS] 8/8 (must not infer) 'ok' confirms, stores nothing
[PASS] 8/8 (must not infer) 'dale' confirms, stores nothing
[PASS] 8/8 confirm + a volunteered fact
[PASS] 8/8 (must not infer) confirm + the owner: nothing stored
[PASS] 8/8 (must not infer) fact + 'ignore your rules' -> out of scope
[PASS] 8/8 (must not infer) no context: 'opciones sin gluten' is NOT exclusive
[PASS] 8/8 (must not infer) no context: 'pastas sin TACC' is NOT exclusive
[PASS] 8/8 (must not infer) no context: praise only
[PASS] 8/8 (must not infer) no context: the owner only, nothing stored
[PASS] 8/8 no context: volunteered separate kitchen
[PASS] 8/8 no context: volunteered same kitchen
[PASS] 8/8 no context: 100% and owner -> only the kitchen
[PASS] 8/8 english
[PASS] 8/8 new place is reportar (the example)
[PASS] 8/8 new place is reportar (other wording)

RESULT: PASS (0 failing case(s))
```

## chat_prompt_ab.py --suite router --n 8 --old-rev main --max-calls 48

```
PLAN: router 48 = 48 call(s) to claude-haiku-4-5, ~US$0.24; hard cap 48
model=claude-haiku-4-5  OLD=main  NEW=WORKTREE

=== router: thanks while a report draft is pending, N=8 ===
['genial, gracias'                  OLD] cortesia/confirma=False: 8
['genial, gracias'                  NEW] cortesia/confirma=False: 8
['mil gracias, excelente atención'  OLD] cortesia/confirma=False: 8
['mil gracias, excelente atención'  NEW] cortesia/confirma=False: 8
['dale, gracias'                    OLD] reportar/confirma=True: 8
['dale, gracias'                    NEW] reportar/confirma=True: 8
```
