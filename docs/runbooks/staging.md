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

## Mercado Pago (test) and the partner admin script

`.env.staging` also holds `MP_TEST_ACCESS_TOKEN` (a Mercado Pago **test** seller of Uruguay; the script refuses any
other) and `MP_TEST_PLAN_ID` (the test plan, $U 790/month, UYU). Production credentials are separate and not wired
until phase 3.

```bash
python -m scripts.partners_admin --env staging --project-ref egqclfomloqmddvlpepx                  # list (read-only)
python -m scripts.partners_admin --env staging --project-ref egqclfomloqmddvlpepx --suggest CM-XXXXXX
python -m scripts.partners_admin --env staging --project-ref egqclfomloqmddvlpepx --link CM-XXXXXX --mp-payment ID [--apply]
```

Every write is a dry run without `--apply`, and every staging write is shown first and waits for the owner's «dale».
`db/staging/2026-10-15-partner-payment-columns.sql` (staging only) moved staging's table to the current shape
(`payer_email` out, `mp_first_payment_id` in).

## Pending live test: end of the paid period after a cancellation (on or after 2026-11-16)

State on 2026-10-15: `CM-TEST10` (fictional request, `prueba-link@staging-test.invalid`) is linked to the test
subscription `6d8f041212884c8790dc0d6b13b9fa4f` (first payment `184244837074`), `paid_through 2026-11-15`, card
approved and visible in `partners_public`. The subscription is being cancelled from the test buyer account; after
`--sync --apply` the row is `cancelled` and the card stays visible until 2026-11-15.

On **2026-11-16 or later**, in this order, each write only with the owner's «dale»:

1. Read-only: `partners_public` with the anon key must return `[]` (the view hides a cancelled row once
   `paid_through` has passed).
2. Read-only: `python -m scripts.partners_admin --env staging --project-ref egqclfomloqmddvlpepx --sync` (dry run)
   must propose `CM-TEST10: {"publication_status": "ended"}` and nothing else.
3. Write (dale): the same `--sync` with `--apply`.
4. Write (dale): delete the test row:
   ```sql
   delete from public.partner_applications where ref_code = 'CM-TEST10' and contact_email = 'prueba-link@staging-test.invalid';
   ```
   through `python -m scripts.staging_db --project-ref egqclfomloqmddvlpepx --file <that SQL in a file> --apply`, then
   a read-only count that must be 0.
