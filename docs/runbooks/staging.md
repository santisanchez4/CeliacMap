# Staging (Supabase) — runbook

Second Supabase project (free plan), used to build and test the partner program before production
([ADR-011](../architecture/ADR-011-partner-program-payments.md), [plan](../plans/PLAN-partner-program.md) §6).
Project ref: `egqclfomloqmddvlpepx` (São Paulo). It pauses after 7 days without activity: wake it up in the
dashboard before testing.

## Rules

- **The Supabase CLI in this repo is linked to PRODUCTION.** Never run `supabase link` with staging and never pass
  `--linked` for staging work. The staging tools only use `--db-url`, built from `.env.staging`.
- Every write to staging is shown first (exact command) and waits for the owner's «dale», like production.
- Staging only holds places production already publishes. Never copy suggestions, reports, opinions, votes, chat
  logs, evidence, reviews, emails or any personal data into it.

## Keys

`.env.staging` at the repo root (gitignored by `.env.*`), never pasted in the chat:

| Variable | What | Secret |
|---|---|---|
| `STAGING_SUPABASE_URL` | `https://<ref>.supabase.co` | no |
| `STAGING_SUPABASE_ANON_KEY` | anon key (public by design) | no |
| `STAGING_SUPABASE_SERVICE_ROLE_KEY` | service_role key | **yes** |
| `STAGING_DB_URL` | Session pooler URI with the password | **yes** |

`scripts/staging_guard.py` refuses unless all four point at the `--project-ref` given and that ref is not
production's (`pgblbyvetclllaqvknvc`). It reads only `.env.staging`, never `.env`. Output is redacted.

## Tools

From a checkout without `node_modules` (a worktree), point `SUPABASE_CLI` at the main checkout's `supabase.js`
(`node_modules/.deno/supabase@<version>/node_modules/supabase/dist/supabase.js`) and pass `--env-file` to the main
checkout's `.env.staging`.

```bash
# Read-only: one SELECT, run as `select * from (<query>) as q` (Postgres refuses DDL / DML inside a subquery).
python -m scripts.staging_db --project-ref egqclfomloqmddvlpepx --sql "select count(*) from public.places"

# Apply a SQL file: dry run first, then --apply. It goes through `supabase migration up --db-url` (one
# transaction per file; `supabase db query` cannot run a file with several statements). A copy is kept in
# .staging-db/ next to .env.staging (gitignored) as staging's migration history; the same content is refused twice
# unless --reapply.
python -m scripts.staging_db --project-ref egqclfomloqmddvlpepx --file db/migrations/X.sql
python -m scripts.staging_db --project-ref egqclfomloqmddvlpepx --file db/migrations/X.sql --apply

# Places: reads production with the PUBLIC anon key of js/config.js (approved rows, the PLACES-PUBLIC-COLUMNS
# columns only) and upserts them into staging's public.places by id. Dry run without --apply.
python -m scripts.seed_staging --project-ref egqclfomloqmddvlpepx [--apply]
```

`--sql` still runs a function called from the SELECT: only call read functions.

## Bootstrap order (done once)

1. `db/schema.sql` as it is on `main` **before** the partner block (so the partner migration is tested exactly as it
   will run in production).
2. `db/migrations/2026-10-14-partner-program.PENDING.sql` (staging only; production in phase 3).
3. `python -m scripts.seed_staging ... --apply`.
4. Read-only checks: the tables, RLS, grants, `partners_public` empty, the anon count of approved places.
