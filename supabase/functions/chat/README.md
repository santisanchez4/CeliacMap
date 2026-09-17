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
| `CHAT_DAILY_CALL_CAP` | Global cap per day (default **500**), enforced against `chat_usage`'s TURN counter, not raw model calls — see the comment above `isRateLimited`'s call site in `index.ts` for why this diverges from the `1000` figure in ADR-006's original budget table (that number assumed a calls-based counter; applying it to the turns-based counter `bump_chat_usage` actually maintains would silently double the approved ~US$2-3/day spend ceiling to ~US$4-6/day). |
| `CHAT_MAX_HISTORY_TURNS` | History turns forwarded to the model (default 8). |

`SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` are
auto-injected by the platform (same as every other Edge Function in this
project) — not set by hand. Unlike `outreach-reply/` and
`place-report-created/` (service_role only), this function also uses the
**anon** key for Módulo 1's RAG query against `places` — deliberately, so the
`public read approved places` RLS is the structural backstop (ADR-006
decision 9). `SUPABASE_SERVICE_ROLE_KEY` is used only for `chat_usage`
(rate limiting) and, from Fase C onward, the Módulo 4 `needs_review` lookup.

## Why this function is different from `outreach-reply/` and `place-report-created/`

Those two only do webhook mechanics and dispatch the real work to Python via
`repository_dispatch` (30–90s cold start is fine for an async webhook, not for
a chat). `chat/` calls Anthropic directly and returns to the browser in
seconds. It has **zero authority over `places.status`** — it only relates
what the Validator already approved and routes input into the existing
`place_reports` / `suggestions` intake tables. See ADR-006 for the full design
and the two prompts (ROUTER + REDACTOR), also documented verbatim in
`CLAUDE.md` ("The Chatbot System Prompts") and `prompts.md` §27.
