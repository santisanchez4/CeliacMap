# Chat v21 — live verification of the `category_zero` telemetry (2026-09-27)

`python db/checks/chat_category_zero_live.py --out db/checks/2026-09-27-chat-category-zero-live-run.json` against the
DEPLOYED `chat` function (v21, `verify_jwt=false`, `index.ts` / `regions.ts` / `prompts.ts` identical to `HEAD` 739d850).
Raw result: the JSON next to this file. Design: `docs/DECISIONS.md`, "`category_zero` telemetry".

One turn, one sample: live evidence that the fields are written and that the answer did not change, not a measurement.
Window 2026-09-27 00:59:11 .. 00:59:18 UTC.

| Message | Ground truth (anon key, same as the browser) | Returned |
|---|---|---|
| "hay cafés sin tacc en Cerro Largo?" | 2 approved places in Cerro Largo, both `shop`; 0 `cafe` | `places: []`, no action, no pending submission; reply: "Por ahora no tengo lugares confirmados en Cerro Largo. Si conocés algún café sin TACC en esa zona, contame y lo sumamos para que el equipo lo revise." |

The four checks of the script pass (no cafés in the region; `places` empty; no action or pending submission; the reply names
no place of the region). The reply is what the redactor says when `<datos>` is empty (RESPONDER_PROMPT 2c and its
examples); the change adds nothing to it.

## What `agent_log` recorded

Read back with the CLI before the cleanup (`result`, trimmed of the token counters):

```json
{"modulo": "buscar", "marked": false, "result_count": 0, "nearby_count": null,
 "query": {"pais": "Uruguay", "zona": "Cerro Largo", "ciudad": null, "region": "Cerro Largo", "region_plan": "region",
           "category": "cafe", "nivel": null, "texto_libre": null, "lugar_nombre": null,
           "category_zero": true, "count_without_category": 2}}
```

As expected: the router put `category = cafe`; the search was by department (`region_plan: region`); it found 0 rows;
`category_zero` is true and the same search without the category counts **2** (the two shops of Melo): a filter that emptied
a region that has places. `nivel` is now logged (`null`: the message did not ask for 100%). No raw text was kept (`marked:
false`).

## Writes and cleanup

The turn wrote only what normal chat usage writes: 1 `agent_log` row and 3 `chat_usage` counters (`session:celiac-test-catzero-20260927`,
the `ip:` bucket and `global`, day 2026-09-27, count 1 each). No `place_reports`, `suggestions` or `places` row was written.

Baseline taken before the run: `agent_log` chatbot 100 (last row 2026-09-25 15:45:18.432019+00), `chat_usage` 58 (0 for the
day), `place_reports` 2, `suggestions` 2, `places` 1 312 (1 263 with a region).

**Reverted right after**, with the SQL shown and approved before running it: one transaction, three guards before deleting (exactly one
chatbot row after the baseline and it is the `buscar` / `category_zero` turn; the day's `chat_usage` is exactly the run's three
rows at count 1; `place_reports` / `suggestions` / `places` at the baseline), each `DELETE` asserting its exact count (1
`agent_log` by id, 1 session bucket, 1 `global`, 1 `ip:`) and a final assertion against the baseline. No guard aborted.

Read-back afterwards, read-only and independent of the transaction: `agent_log` chatbot 100, 0 chatbot rows since the baseline,
0 rows with `category_zero`, `chat_usage` 58 (0 for the day, 0 `celiac-test-catzero-*` sessions), `place_reports` 2,
`suggestions` 2, `places` 1 312 with 1 263 carrying a region.
