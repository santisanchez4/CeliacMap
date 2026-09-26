# Chat — department / province search: router and redactor measurements (2026-09-26)

Model `claude-haiku-4-5`, prompts = `supabase/functions/chat/prompts.ts` at HEAD (unchanged). No production writes.
Design and decisions: `docs/DECISIONS.md`, "Department / province search — `places.region`".

## 1. Router: what it extracts for a department / province (N=8)

`python db/checks/chat_region_router_check.py --n 8`

| Message | ciudad | zona | pais | category |
|---|---|---|---|---|
| "hay lugares sin tacc en Entre Ríos?" | 5/8 `Entre Ríos` · 3/8 null | 3/8 `Entre Ríos` · 5/8 null | Argentina | null |
| "algo sin tacc en Maldonado?" | 8/8 `Maldonado` | null | Uruguay | null |
| "lugares sin tacc en la provincia de Córdoba" | null | 8/8 `Córdoba` | Argentina | null |
| "lugares sin tacc en la provincia de Buenos Aires" | null | 8/8 `provincia de Buenos Aires` | Argentina | null |
| "…cerca de Fraile Muerto Cerro Largo?" | 8/8 `Fraile Muerto` | 8/8 `Cerro Largo` | Uruguay | `shop` |
| "y en cerro largo?" (after the turn above) | 8/8 `Cerro Largo` | null | Uruguay | `shop` |

The last two rows reproduce agent_log of 2026-09-25 (the real conversation). Consequences for the design: a province
usually arrives in `zona` with `ciudad=null`; the marker can ride inside the value; "Maldonado" arrives as `ciudad` (so
the city step alone would have hidden 15 of its 16 places).

## 2. Redactor, Option A (no prompt change), N=16 per shape

`python db/checks/chat_region_redactor_check.py --n 16` — the messages are built by the real code
(`searchPlacesForChat` + `buildResponderUserMessage`, via `chat_region_messages.ts`) over the two real places of Melo
(`EMPATIA GLUTEN FREE`, `Gluten Free | Sandra | Productos`), and the real `RESPONDER_PROMPT`.

Acceptance fixed before the run: `origin` = 0 and `names` = 0 in every shape; `where` >= 90%.

```
W message: modulo: buscar | <datos>[]</datos> | <datos_cercanos>{"city":"Cerro Largo (Melo)","count":2}</datos_cercanos> | Mensaje del usuario: que locales puedo visitar … cerca de Fraile Muerto Cerro Largo?

[W] widened: where 16/16 | origin 0/16 | names 0/16 | 'cerca' 16/16  -> PASS
   sample: Por ahora no tengo lugares confirmados en Fraile Muerto. Cerca hay 2 locales en Melo (Cerro Largo).
[R] department asked outright: where 16/16 | origin 0/16 | names 0/16 | 'cerca' 1/16  -> PASS
   sample: En Cerro Largo tengo confirmados 2 espacios sin TACC en Melo: • EMPATIA GLUTEN FREE — comercio, Espacio 100% sin gluten. … • Gluten Free | Sandra | Productos — …
[B0] control (production before the change): where 0/16 | origin 0/16 | names 0/16 | 'cerca' 15/16
   sample: Por ahora no tengo lugares confirmados cerca de Fraile Muerto, Cerro Largo.

RESULT: PASS (0 failing shape(s))
```

- `where`: both the department and the real town (Melo) are named (R also needs both places). `origin`: a sentence that
  says there ARE places in or near Fraile Muerto (a negated mention is fine). `names`: lists or names a place the model was
  not given (W) or an item that is not one of the two places in `<datos>` (R).
- **Not judged, reported:** `'cerca'` 16/16 in W. "Cerca hay 2 … en Melo (Cerro Largo)" comes from `RESPONDER_PROMPT`'s own
  example ("Cerca hay 3 en Villa Crespo") and is a proximity claim the system does not verify (same department, no distance).
  It is the same family as the 2c-vs-examples contradiction, deferred to the next prompt change.
- The control reproduces the production reply of 2026-09-25 ("no tengo lugares confirmados cerca de Fraile Muerto"): 0/16
  say anything about Cerro Largo.
