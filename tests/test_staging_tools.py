"""Staging tools (scripts/staging_guard.py, staging_db.py, seed_staging.py): nothing meant for staging reaches
production, and the seed copies only what the public map already shows. All offline: no network, no CLI call."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pytest

from scripts import seed_staging, staging_db
from scripts.staging_guard import PROD_REF, StagingGuardError, check_db_url, encoded_db_url, redact, staging_target

ROOT = Path(__file__).resolve().parent.parent
STAGING = "abcdefghijklmnopqrst"
OTHER = "zyxwvutsrqponmlkjihg"


def jwt(ref: str, role: str) -> str:
    def enc(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    return f"{enc({'alg': 'HS256'})}.{enc({'iss': 'supabase', 'ref': ref, 'role': role})}.sig"


def env(**over: str) -> dict[str, str]:
    values = {
        "STAGING_SUPABASE_URL": f"https://{STAGING}.supabase.co",
        "STAGING_SUPABASE_ANON_KEY": jwt(STAGING, "anon"),
        "STAGING_SUPABASE_SERVICE_ROLE_KEY": jwt(STAGING, "service_role"),
        "STAGING_DB_URL": f"postgresql://postgres.{STAGING}:p%40ss w&rd@aws-1-sa-east-1.pooler.supabase.com:5432/postgres",
    }
    values.update(over)
    return values


def test_a_consistent_staging_env_passes():
    assert staging_target(STAGING, env()) == STAGING


def test_production_ref_is_refused_as_target():
    with pytest.raises(StagingGuardError, match="PRODUCTION"):
        staging_target(PROD_REF, env())


@pytest.mark.parametrize("over, message", [
    ({"STAGING_SUPABASE_URL": f"https://{OTHER}.supabase.co"}, "not --project-ref"),
    ({"STAGING_SUPABASE_URL": f"https://{PROD_REF}.supabase.co"}, "not --project-ref"),
    ({"STAGING_SUPABASE_SERVICE_ROLE_KEY": jwt(PROD_REF, "service_role")}, "another project"),
    ({"STAGING_SUPABASE_SERVICE_ROLE_KEY": jwt(STAGING, "anon")}, "expected 'service_role'"),
    ({"STAGING_SUPABASE_ANON_KEY": jwt(STAGING, "service_role")}, "expected 'anon'"),
    ({"STAGING_SUPABASE_SERVICE_ROLE_KEY": "sb_secret_xxx"}, "cannot be checked"),
    ({"STAGING_DB_URL": f"postgresql://postgres.{PROD_REF}:pw@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"},
     "PRODUCTION"),
    ({"STAGING_DB_URL": f"postgresql://postgres:pw@db.{PROD_REF}.supabase.co:5432/postgres"}, "PRODUCTION"),
    ({"STAGING_DB_URL": f"postgresql://postgres.{OTHER}:pw@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"},
     "does not point"),
    ({"STAGING_DB_URL": f"postgresql://postgres.{STAGING}@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"},
     "no password"),
])
def test_any_value_outside_the_staging_project_is_refused(over, message):
    with pytest.raises(StagingGuardError, match=message):
        staging_target(STAGING, env(**over))


def test_direct_host_of_staging_is_accepted():
    check_db_url(f"postgresql://postgres:pw@db.{STAGING}.supabase.co:5432/postgres", STAGING)


def test_password_is_percent_encoded_and_redacted_whole():
    values = env()
    url = encoded_db_url(values["STAGING_DB_URL"])
    assert "p%40ss%20w%26rd" in url
    out = redact(f"error connecting to {url} with p@ss w&rd and {values['STAGING_SUPABASE_SERVICE_ROLE_KEY']}", values)
    assert "p@ss" not in out and "w%26rd" not in out and "service_role" not in out
    assert out.count("[REDACTED]") == 3


def test_query_is_wrapped_so_a_write_cannot_run():
    cmd = staging_db.query_command(["node", "supabase.js"], env()["STAGING_DB_URL"], "select 1 as a;")
    assert cmd[2:4] == ["db", "query"]
    assert cmd[-1] == "select * from (\nselect 1 as a\n) as q"
    with pytest.raises(StagingGuardError):
        staging_db.read_only_query("select 1; drop table public.places")


def test_commands_never_link_or_use_linked():
    cli = ["node", "supabase.js"]
    for cmd in (staging_db.query_command(cli, env()["STAGING_DB_URL"], "select 1"),
                staging_db.migrate_command(cli, env()["STAGING_DB_URL"], Path("wd"))):
        assert "--linked" not in cmd and "link" not in cmd
        assert "--db-url" in cmd
    source = (ROOT / "scripts" / "staging_db.py").read_text(encoding="utf-8")
    assert '"link"' not in source and '"--linked"' not in source


def test_stage_file_refuses_the_same_content_twice(tmp_path):
    sql = tmp_path / "x-y.sql"
    sql.write_text("select 1;", encoding="utf-8")
    first = staging_db.stage_file(sql, tmp_path / "wd")
    assert first.name.endswith("_x_y.sql") and re.match(r"\d{14}_", first.name)
    with pytest.raises(StagingGuardError, match="already applied"):
        staging_db.stage_file(sql, tmp_path / "wd")


def test_apply_without_flag_is_a_dry_run(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / ".env.staging"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in env().items()), encoding="utf-8")
    sql = tmp_path / "m.sql"
    sql.write_text("select 1;", encoding="utf-8")
    monkeypatch.setattr(staging_db, "run", lambda *a, **k: pytest.fail("dry run must not call the CLI"))
    code = staging_db.main(["--project-ref", STAGING, "--env-file", str(env_file), "--file", str(sql)])
    assert code == 0 and "dry run" in capsys.readouterr().out
    assert not (tmp_path / ".staging-db").exists()


# --- seed_staging -------------------------------------------------------------------------------------------------

def granted_place_columns() -> set[str]:
    schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    block = re.search(r"-- PLACES-PUBLIC-COLUMNS-BEGIN(.*?)-- PLACES-PUBLIC-COLUMNS-END", schema, re.S).group(1)
    grant = re.search(r"grant select\s*\((.*?)\)\s*on public\.places", block, re.S).group(1)
    return {c.strip() for c in grant.split(",")}


def test_seed_copies_exactly_the_public_columns():
    assert set(seed_staging.PUBLIC_COLUMNS) == granted_place_columns()


def test_seed_reads_production_only_with_its_anon_key():
    url, key = seed_staging.production_source()
    assert url == f"https://{PROD_REF}.supabase.co"
    assert json.loads(base64.urlsafe_b64decode(key.split(".")[1] + "==")).get("role") == "anon"


def test_seed_touches_only_places():
    source = (ROOT / "scripts" / "seed_staging.py").read_text(encoding="utf-8")
    assert set(re.findall(r"/rest/v1/([a-z_]+)", source)) == {"places"}
    for table in ("suggestions", "place_reports", "place_votes", "community_opinions", "agent_log", "chat_usage",
                  "place_evidence", "reviews", "outreach_messages", "partner_applications"):
        assert table not in source.split('"""', 2)[2], table
    assert "SUPABASE_SERVICE_ROLE_KEY" not in source.replace("STAGING_SUPABASE_SERVICE_ROLE_KEY", "")


class FakeResponse:
    def __init__(self, payload=None, status=200, headers=None):
        self.payload, self.status_code, self.headers, self.text = payload, status, headers or {}, ""

    def json(self):
        return self.payload

    def raise_for_status(self):
        assert self.status_code < 300


class FakeSession:
    def __init__(self, rows):
        self.rows, self.gets, self.posts = rows, [], []

    def get(self, url, headers, params, timeout):
        self.gets.append((url, headers, params))
        return FakeResponse(self.rows if params["offset"] == "0" else [])

    def post(self, url, headers, params, json, timeout):
        self.posts.append((url, headers, params, json))
        return FakeResponse(status=201)

    def head(self, url, headers, params, timeout):
        return FakeResponse(headers={"Content-Range": f"0-0/{len(self.rows)}"})


def row(**over):
    base = {c: None for c in seed_staging.PUBLIC_COLUMNS}
    base.update(id="00000000-0000-0000-0000-000000000001", name="X", status="approved", country="Uruguay")
    base.update(over)
    return base


def write_env(tmp_path) -> Path:
    env_file = tmp_path / ".env.staging"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in env().items()), encoding="utf-8")
    return env_file


def test_seed_dry_run_reads_approved_public_columns_and_writes_nothing(tmp_path):
    session = FakeSession([row()])
    code = seed_staging.main(["--project-ref", STAGING, "--env-file", str(write_env(tmp_path))], session=session)
    assert code == 0 and not session.posts
    url, headers, params = session.gets[0]
    assert url == f"https://{PROD_REF}.supabase.co/rest/v1/places"
    assert params["status"] == "eq.approved"
    assert params["select"].split(",") == list(seed_staging.PUBLIC_COLUMNS)
    assert json.loads(base64.urlsafe_b64decode(headers["apikey"].split(".")[1] + "==")).get("role") == "anon"


def test_seed_apply_writes_only_to_staging_places(tmp_path):
    session = FakeSession([row()])
    code = seed_staging.main(["--project-ref", STAGING, "--env-file", str(write_env(tmp_path)), "--apply"],
                             session=session)
    assert code == 0
    assert [p[0] for p in session.posts] == [f"https://{STAGING}.supabase.co/rest/v1/places"]
    assert session.posts[0][1]["apikey"] == env()["STAGING_SUPABASE_SERVICE_ROLE_KEY"]


def test_seed_refuses_a_row_that_is_not_approved(tmp_path):
    session = FakeSession([row(status="needs_review")])
    code = seed_staging.main(["--project-ref", STAGING, "--env-file", str(write_env(tmp_path)), "--apply"],
                             session=session)
    assert code == 2 and not session.posts


def test_seed_refuses_a_non_public_column(tmp_path):
    session = FakeSession([row(contact_email="a@b.co")])
    code = seed_staging.main(["--project-ref", STAGING, "--env-file", str(write_env(tmp_path)), "--apply"],
                             session=session)
    assert code == 2 and not session.posts


def test_seed_refuses_production_as_target(tmp_path):
    session = FakeSession([row()])
    code = seed_staging.main(["--project-ref", PROD_REF, "--env-file", str(write_env(tmp_path)), "--apply"],
                             session=session)
    assert code == 2 and not session.gets and not session.posts
