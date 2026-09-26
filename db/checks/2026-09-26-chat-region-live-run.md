# Chat v20 — live verification of the department / province search (2026-09-26)

`python db/checks/chat_region_live.py --out db/checks/2026-09-26-chat-region-live-run.json` against the DEPLOYED `chat`
function (v20, `verify_jwt=false`, source identical to `HEAD` 317ed94). Raw results: the JSON next to this file.
Design and measurements: `docs/DECISIONS.md`, "Department / province search — `places.region`";
offline router / redactor runs: `2026-09-26-chat-region-run.md`.

Each reply is checked against the database itself (the approved places of the region, read with the same anon key the
browser uses), not only against what the model said. Window 2026-09-26 23:13:39 .. 23:14:16 UTC, 6 turns, **6/6 PASS**.

| # | Message | What was checked | Logged (`agent_log.result.query`) |
|---|---|---|---|
| 1 | "…cerca de Fraile Muerto Cerro Largo?" | `places` empty; names Cerro Largo and Melo; no place claimed in Fraile Muerto; no list, no place names | `fallback`, region Cerro Largo, `result_count` 0, `nearby_count` 2 |
| 2 | "y en cerro largo?" | the two places of Melo, both city Melo, both named, no mention of Fraile Muerto | `region`, Cerro Largo, `result_count` 2 |
| 3 | "veo en el mapa 2 lugares en Melo" | the same two places, both named | `city`, `result_count` 2 |
| 4 | "lugares sin tacc en la provincia de Buenos Aires" | 8 places, all with region Buenos Aires in the database, none of the 63 CABA places | `region`, Buenos Aires (`zona` = "provincia de Buenos Aires", `ciudad` null) |
| 5 | "algo sin tacc en Córdoba" | 8 places, all with region Córdoba, capital first | `region`, Córdoba |
| 6 | "algo sin tacc en Maldonado?" | 8 places, all with region Maldonado, the place of the city of Maldonado first, then Punta del Este | `region`, Maldonado |

- **Córdoba cannot show the ordering today**: all 46 approved places of the province are in the capital, so "capital first"
  is trivially true there. Turn 6 (Maldonado: 1 place in the city, 15 elsewhere in the department) is the real check of
  `orderRegionRows`; it was added to the requested list for that reason.
- One sample per turn: live evidence, not proof (the offline N=16 in `2026-09-26-chat-region-run.md` is the measurement).
- Turn 1 again answered "Cerca hay 2 locales en Melo (Cerro Largo)": the unverified-proximity phrasing that comes from the
  prompt's own example, deferred to the next prompt change (see DECISIONS).

## Writes and cleanup

The run wrote only normal chat usage: 6 `agent_log` rows and `chat_usage` counters (4 `session:celiac-test-region-*`
buckets plus the day's `global` and `ip:` rows, 6 calls each). No `place_reports`, `suggestions` or `places` rows were
written or touched.

Baseline taken before the run: `agent_log` chatbot 100, `chat_usage` of the day empty, `chat_usage` of other days 58,
`place_reports` 2, `suggestions` 2.

**Reverted the same day**, with the SQL shown and approved before running it: one transaction, guards before deleting (no
foreign traffic in the window, the day's buckets held only the run's 6 calls, no intake rows created), each `DELETE` asserting
its exact count (6 `agent_log` by id, 4 session buckets, the `global` and `ip:` rows), and a final assertion against the
baseline. No guard aborted. Read-back afterwards (8 checks, all as expected): `agent_log` chatbot 100, 0 rows since 23:13,
`chat_usage` of the day 0, other days 58, `place_reports` 2, `suggestions` 2, 0 places touched, 1 263 places with a region.
