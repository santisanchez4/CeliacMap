# Chat — level labels aligned with the map (offline A/B, real model)

Date: 2026-09-20. Model: `claude-haiku-4-5` (the function's `CHAT_MODEL`). Tool:
`db/checks/chat_prompt_ab.py` (new `labels` suite). **No production writes; nothing
deployed.** Cost: roughly US$0.4 in total (about 80 model calls).

## Why

The map, filters and ranking now show two public levels — "Espacio 100% sin gluten"
(`gluten_free_100`, a dedicated venue) and "Tiene opciones sin TACC" (everything else,
including `celiac_friendly`). The chat prompt that was deployed until now (unchanged since
v11; v12 only added `places` to the response) still told the model to say
"Sin TACC" for `gluten_free_100` **and** `celiac_friendly`, so the chat could describe a
place more permissively than the map did. The chat receives the raw `safety_level` in
`<datos>` and the prompt alone decides the wording (nothing in `index.ts` maps it), and
the place search itself neither filters nor orders by level (`vote_count, rating, name`),
so the prompt was the only place the bias could live.

## Change under test

REDACTOR instruction 2b and the Palermo search example (`prompts.ts` + its three doc
copies, kept identical by `tests/test_chat_prompts_sync.py`):

- `gluten_free_100` -> "Espacio 100% sin gluten"; `celiac_friendly` and `options_available`
  -> "Tiene opciones sin TACC"; English replies use "100% gluten-free venue" / "Has
  gluten-free options"; "use always those two labels, without rewording or adding others".
- Example: La Spiga is now shown as `celiac_friendly` and still reads "Tiene opciones sin TACC".

## Method

`--suite labels`: the production message shape (`modulo: buscar` + `<datos>` + user
message), one fictional place per level in random order (seeded per sample), one Spanish
and one English question, N=8 per cell. Each place's line in the reply is classified by
regex: correct label / says "100%" for a non-dedicated place / bare "Sin TACC" (the retired
label) / overclaim words (`amig|apto|segur|confiab`, `celiac-friendly|safe|suitable`) /
Spanish label pasted into an English reply. OLD = `HEAD` (what is deployed), NEW = working tree.

## Result

| cell (N=8 each) | OLD (deployed) | NEW |
|---|---|---|
| ES `gluten_free_100` | bare "Sin TACC" 8/8 (retired label) | correct 8/8 |
| ES `celiac_friendly` | bare "Sin TACC" 8/8 — **worded exactly like the dedicated place** | correct 8/8 |
| ES `options_available` | correct 8/8 | correct 8/8 |
| EN, three levels | Spanish labels pasted into English text (8/8 on the options line; "Sin TACC" on the others) | correct 24/24, English labels, 0 Spanish |
| "says 100%" for a non-dedicated place | 0 | 0 |
| overclaim words | 0 | 0 |

The OLD arm reproduces the bias: a `celiac_friendly` place was presented with the same
label as a 100% gluten-free venue in 8/8 samples. The NEW arm labels all 48 place lines
correctly (24 ES + 24 EN).

## Regression smoke on the NEW prompt (no OLD arm run)

`--suite f4 legit --only-new --n 8 --legit-n 2`:

- f4: "mg por día" figure 2/8, "10 ppm" figure 8/8, obfuscated symptoms urgency 1/8.
  In line with the v10/v11 numbers already recorded in CLAUDE.md ("Chatbot Fase E"); these are
  the patterns the deterministic `celiaquia` guard replaces in production. **Not a controlled
  comparison** — only the NEW arm was run.
- legit: 0/20 legitimate answers would be replaced by the guard (no false positives).

## What this does NOT show

- The live jailbreak battery (`2026-09-20-chat-jailbreak.md`, 37 turns) could not be part of
  this offline run; it was re-run against the deployed v13 afterwards
  (`2026-09-20-chat-jailbreak-v13.md`) and barely exercises the label change.
- One model, three fictional places, two questions, N=8, a per-line regex classifier: it shows
  the mapping is followed, not that every phrasing of every query is.
- Untested: replies listing eight places, a result set holding a single level, other languages.
- The ROUTER prompt is unchanged, so its suites were not re-run.

## Deploy and live check (2026-09-20, after the offline run)

- Deployed with `node_modules/.bin/supabase functions deploy chat`: `chat` **v12 -> v13**,
  `ACTIVE`, `verify_jwt=false` before and after (`supabase functions list`). The other two
  functions were untouched (`outreach-reply` v11, `place-report-created` v7).
- The deployed source was downloaded (`functions download chat --use-api`) and `index.ts` /
  `prompts.ts` are byte-identical to HEAD (CRLF-normalised md5); the working tree stayed clean.
- Two real turns to the deployed endpoint, fixed session token `celiac-test-labels-20260920`,
  city Paysandú (approved: 2 `gluten_free_100` + 4 `celiac_friendly`, all returned):
  - ES "lugares sin tacc en Paysandú": both dedicated places "Espacio 100% sin gluten", the
    four `celiac_friendly` ones "Tiene opciones sin TACC".
  - EN "gluten free places in Paysandú?": "100% gluten-free venue" / "Has gluten-free options",
    no Spanish label pasted into the English reply.
  - 12/12 place lines correct. Same wording as the map.
- Side effects of those two turns (ordinary usage, metadata only, `marked:false`): 2
  `agent_log` rows (`agent='chatbot'`, `modulo='buscar'`, `result_count=6`) and 3 `chat_usage`
  counters for 2026-09-21 (`session:…`, `ip:…`, `global`, count 2 each). These are the only
  rows of that day, so they are attributable to this check.
- **Reverted** the same day, after re-reading the state and with the exact SQL approved first:
  the 2 `agent_log` rows deleted by id (`c41f98ac-…`, `c9ed22b7-…`, `agent='chatbot'`) and the
  3 `chat_usage` rows of 2026-09-21 deleted (`day = '2026-09-21' and updated_at < '…02:10'`).
  A read-only check afterwards found 0 `agent_log` rows since the test and 0 `chat_usage` rows
  for that day.

## Status

Deployed (`chat` v13). The full jailbreak battery was re-run live afterwards
(`2026-09-20-chat-jailbreak-v13.md`: 0 clear breaks, 1 gray, 0 false positives). Per CLAUDE.md,
changing a prompt **restarts the soft-launch count**.
