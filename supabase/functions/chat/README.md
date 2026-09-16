# `chat` Edge Function

Chatbot RAG for CeliacMap (ADR-006 / `docs/plans/PLAN-chatbot-rag.md`) — the
first Edge Function in this project that calls an LLM directly, synchronously,
from the browser. `index.ts` (Fase B) implements the request handler; this
README documents the secrets it needs.

## Secrets

Set with `supabase secrets set`, **never** in `.env` or GitHub Actions
(same criterion as `RESEND_WEBHOOK_SECRET` / `GITHUB_DISPATCH_TOKEN` for the
other Edge Functions — these are only ever needed inside this function):

| Secret | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Calls Claude for the router + redactor. |
| `CHAT_MODEL` | Model id, default `claude-haiku-4-5` (escape hatch to Sonnet — ADR-006 decision 12). |
| `CHAT_MAX_MESSAGES_PER_SESSION` | Per-session-token cap (default 15). |
| `CHAT_MAX_MESSAGES_PER_IP_DAY` | Per-IP-hash daily cap (default 40). |
| `CHAT_DAILY_CALL_CAP` | Global model-call cap per day (default 1000). |
| `CHAT_MAX_HISTORY_TURNS` | History turns forwarded to the model (default 8). |

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are auto-injected by the
platform (same as every other Edge Function in this project) — not set by
hand.

## Why this function is different from `outreach-reply/` and `place-report-created/`

Those two only do webhook mechanics and dispatch the real work to Python via
`repository_dispatch` (30–90s cold start is fine for an async webhook, not for
a chat). `chat/` calls Anthropic directly and returns to the browser in
seconds. It has **zero authority over `places.status`** — it only relates
what the Validator already approved and routes input into the existing
`place_reports` / `suggestions` intake tables. See ADR-006 for the full design
and the two prompts (ROUTER + REDACTOR), also documented verbatim in
`CLAUDE.md` ("The Chatbot System Prompts") and `prompts.md` §27.
