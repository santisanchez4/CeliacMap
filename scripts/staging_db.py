"""Run a read-only query or apply a SQL file on the STAGING database, never production.

    python -m scripts.staging_db --project-ref REF --sql "select count(*) from public.places"   # read-only
    python -m scripts.staging_db --project-ref REF --file db/schema.sql                          # dry run
    python -m scripts.staging_db --project-ref REF --file db/schema.sql --apply                  # writes

The connection string comes from ``STAGING_DB_URL`` in ``.env.staging`` and is checked against ``--project-ref``
(scripts/staging_guard.py). It never uses ``supabase link`` or ``--linked``: the CLI in this repo is linked to
production.

- ``--sql`` runs ``select * from (<query>) as q`` through ``supabase db query --db-url``. Postgres refuses DDL and
  INSERT / UPDATE / DELETE inside a subquery, so a write cannot slip in (a volatile function called from a SELECT
  still could: only call read functions).
- ``--file ... --apply`` copies the file into ``.staging-db/supabase/migrations/`` next to ``.env.staging``
  (gitignored) and runs ``supabase migration up --db-url --workdir .staging-db``, which applies the whole file in
  one transaction and records it in staging's migration history. ``supabase db query`` cannot run a file with
  more than one statement. The same content is not applied twice unless ``--reapply`` is given.

Secrets are redacted from everything it prints.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.staging_guard import ENV_FILE, ROOT, StagingGuardError, encoded_db_url, load_env, redact, staging_target


def supabase_cli(root: Path = ROOT) -> list[str]:
    """The CLI as ``node supabase.js``: the npm ``.cmd`` shim goes through cmd.exe, which would expand the ``%`` of
    the percent-encoded password. ``SUPABASE_CLI`` may point at the ``supabase.js`` of another checkout."""
    configured = os.environ.get("SUPABASE_CLI")
    candidates = [Path(configured)] if configured else sorted(
        (root / "node_modules").glob(".deno/supabase@*/node_modules/supabase/dist/supabase.js")
    ) + [root / "node_modules" / "supabase" / "dist" / "supabase.js"]
    node = shutil.which("node")
    for script in candidates:
        if script.is_file() and node:
            return [node, str(script)]
    raise StagingGuardError("Supabase CLI (supabase.js) or node not found: run npm ci or set SUPABASE_CLI")


def read_only_query(sql: str) -> str:
    body = sql.strip().rstrip(";").strip()
    if not body or ";" in body:
        raise StagingGuardError("--sql takes exactly one SELECT statement")
    return f"select * from (\n{body}\n) as q"


def query_command(cli: list[str], db_url: str, sql: str) -> list[str]:
    return [*cli, "db", "query", "--db-url", encoded_db_url(db_url), read_only_query(sql)]


def migrate_command(cli: list[str], db_url: str, workdir: Path) -> list[str]:
    return [*cli, "migration", "up", "--db-url", encoded_db_url(db_url), "--workdir", str(workdir)]


def stage_file(sql_file: Path, workdir: Path, *, reapply: bool = False, now: datetime | None = None) -> Path:
    """Copy the SQL file into the staging migrations folder with a fresh timestamp. Refuses content already there."""
    migrations = workdir / "supabase" / "migrations"
    migrations.mkdir(parents=True, exist_ok=True)
    content = sql_file.read_bytes()
    if not reapply:
        for existing in sorted(migrations.glob("*.sql")):
            if existing.read_bytes() == content:
                raise StagingGuardError(f"this content was already applied as {existing.name} (use --reapply)")
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d%H%M%S")
    target = migrations / f"{stamp}_{sql_file.stem.replace('-', '_')}.sql"
    target.write_bytes(content)
    return target


def run(cmd: list[str], env: dict[str, str]) -> int:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(redact(proc.stdout, env))
    sys.stderr.write(redact(proc.stderr, env))
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-ref", required=True, help="the staging project ref (refused if it is production's)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="SQL file to apply (writes: needs --apply)")
    group.add_argument("--sql", help="one read-only SELECT")
    parser.add_argument("--env-file", type=Path, default=ENV_FILE, help="default: .env.staging at the repo root")
    parser.add_argument("--apply", action="store_true", help="really apply --file to staging")
    parser.add_argument("--reapply", action="store_true", help="apply a file whose content was already applied")
    args = parser.parse_args(argv)

    try:
        env = load_env(args.env_file)
        ref = staging_target(args.project_ref, env)
        if args.sql is not None:
            print(f"target: staging {ref} · read-only query")
            return run(query_command(supabase_cli(), env["STAGING_DB_URL"], args.sql), env)
        path = args.file.resolve()
        if not path.is_file():
            raise StagingGuardError(f"{args.file} not found")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        print(f"target: staging {ref} · file: {args.file} · sha256 {digest}")
        if not args.apply:
            print("dry run: nothing was sent. Add --apply to apply it.")
            return 0
        workdir = args.env_file.resolve().parent / ".staging-db"
        cli = supabase_cli()
        staged = stage_file(path, workdir, reapply=args.reapply)
        print(f"staged as {staged.name}")
    except StagingGuardError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    code = run(migrate_command(cli, env["STAGING_DB_URL"], workdir), env)
    if code != 0:
        staged.unlink(missing_ok=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
