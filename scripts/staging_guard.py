"""Guards shared by the staging tools: a write meant for staging can never reach production.

Staging is a second Supabase project (ADR-011, docs/plans/PLAN-partner-program.md §6). Its keys live in the local,
gitignored ``.env.staging``; this module reads ONLY that file (never ``.env``, which holds the production
service_role key) and refuses unless every value points at the project ref given on the command line, and that
ref is not production's. The Supabase CLI in this repo is linked to production: the staging tools never use
``supabase link`` or ``--linked``.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env.staging"
PROD_REF = "pgblbyvetclllaqvknvc"
REQUIRED = (
    "STAGING_SUPABASE_URL",
    "STAGING_SUPABASE_ANON_KEY",
    "STAGING_SUPABASE_SERVICE_ROLE_KEY",
    "STAGING_DB_URL",
)
_REF = re.compile(r"[a-z0-9]{20}")


class StagingGuardError(RuntimeError):
    """A staging tool was pointed at something that is not the staging project. Messages never carry a secret."""


def load_env(path: Path = ENV_FILE) -> dict[str, str]:
    if not path.is_file():
        raise StagingGuardError(f"{path.name} not found (see docs/runbooks/staging.md)")
    values = {k: (v or "").strip() for k, v in dotenv_values(path).items()}
    missing = [k for k in REQUIRED if not values.get(k)]
    if missing:
        raise StagingGuardError(f"{path.name} is missing: {', '.join(missing)}")
    return values


def jwt_claims(key: str) -> dict:
    """The payload of a Supabase JWT key (``ref`` and ``role`` are not secret). Empty for any other format."""
    parts = key.split(".")
    if len(parts) != 3:
        return {}
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return {}
    return claims if isinstance(claims, dict) else {}


def ref_from_url(url: str) -> str:
    host = urlsplit(url).hostname or ""
    m = re.fullmatch(r"([a-z0-9]{20})\.supabase\.co", host)
    if not m:
        raise StagingGuardError("STAGING_SUPABASE_URL is not a https://<ref>.supabase.co URL")
    return m.group(1)


def _check_key(name: str, key: str, ref: str, role: str) -> None:
    claims = jwt_claims(key)
    if not claims:
        raise StagingGuardError(f"{name} is not a Supabase JWT key; its project cannot be checked")
    if claims.get("ref") != ref:
        raise StagingGuardError(f"{name} belongs to another project, not {ref}")
    if claims.get("role") != role:
        raise StagingGuardError(f"{name} has role {claims.get('role')!r}, expected {role!r}")


def check_db_url(db_url: str, ref: str) -> None:
    parts = urlsplit(db_url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise StagingGuardError("STAGING_DB_URL is not a postgresql:// URL")
    host, user = parts.hostname or "", parts.username or ""
    if PROD_REF in host or PROD_REF in user:
        raise StagingGuardError("STAGING_DB_URL points at the PRODUCTION project")
    pooler = host.endswith(".pooler.supabase.com") and user == f"postgres.{ref}"
    direct = host == f"db.{ref}.supabase.co"
    if not (pooler or direct):
        raise StagingGuardError(f"STAGING_DB_URL does not point at project {ref}")
    if not parts.password:
        raise StagingGuardError("STAGING_DB_URL has no password")


def staging_target(project_ref: str, env: dict[str, str]) -> str:
    """Return the staging ref after checking every staging value against it. Raises StagingGuardError otherwise."""
    if not _REF.fullmatch(project_ref or ""):
        raise StagingGuardError("--project-ref must be a 20-character Supabase project ref")
    if project_ref == PROD_REF:
        raise StagingGuardError("--project-ref is the PRODUCTION project; staging tools refuse it")
    url_ref = ref_from_url(env["STAGING_SUPABASE_URL"])
    if url_ref != project_ref:
        raise StagingGuardError(f"STAGING_SUPABASE_URL is project {url_ref}, not --project-ref {project_ref}")
    _check_key("STAGING_SUPABASE_ANON_KEY", env["STAGING_SUPABASE_ANON_KEY"], project_ref, "anon")
    _check_key("STAGING_SUPABASE_SERVICE_ROLE_KEY", env["STAGING_SUPABASE_SERVICE_ROLE_KEY"], project_ref, "service_role")
    check_db_url(env["STAGING_DB_URL"], project_ref)
    return project_ref


def encoded_db_url(db_url: str) -> str:
    """The same URL with the password percent-encoded exactly once, as the CLI's ``--db-url`` requires."""
    parts = urlsplit(db_url)
    netloc = f"{parts.username}:{quote(unquote(parts.password or ''), safe='')}@{parts.hostname}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def redact(text: str, env: dict[str, str]) -> str:
    """Replace every staging secret (whole value, never a partial hint) before printing tool output."""
    secrets = [env.get("STAGING_SUPABASE_SERVICE_ROLE_KEY", ""), env.get("STAGING_DB_URL", "")]
    db_url = env.get("STAGING_DB_URL", "")
    if db_url:
        raw = urlsplit(db_url).password or ""
        secrets += [encoded_db_url(db_url), raw, unquote(raw), quote(unquote(raw), safe="")]
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text
