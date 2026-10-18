"""The partner program never touches the safety side (ADR-009 point 5, ADR-011, PLAN-partner-program.md §9).

Static checks, no network: the partner migrations do not write to places / place_votes / reviews, the admin script only
writes to partner_applications, the frontend module only talks to its two endpoints, and the map, ranking and chat code
never mention partners.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAFETY_TABLES = ("places", "place_votes", "reviews")
WRITE_SQL = re.compile(
    r"\b(alter\s+table|update|insert\s+into|delete\s+from|drop\s+table|truncate(?:\s+table)?|create\s+trigger\s+\w+[^;]*?\bon)"
    r"\s+(?:if\s+exists\s+|only\s+)?(?:public\.)?(" + "|".join(SAFETY_TABLES) + r")\b",
    re.IGNORECASE | re.DOTALL,
)


def _partner_migrations() -> list[Path]:
    files = [p for d in ("db/migrations", "db/staging") for p in (ROOT / d).glob("*partner*.sql")]
    assert files, "no partner migration found: the glob is wrong"
    return files


def _strip_sql_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def test_partner_migrations_never_write_to_the_safety_tables():
    for path in _partner_migrations():
        hits = [m.group(0) for m in WRITE_SQL.finditer(_strip_sql_comments(path.read_text(encoding="utf-8")))]
        assert not hits, f"{path.name} writes to a safety table: {hits}"


def test_the_write_pattern_catches_what_it_must():
    for sql in ("alter table public.places add column x int", "update places set status = 'approved'",
                "insert into public.reviews (x) values (1)", "delete from place_votes", "truncate table places",
                "create trigger t after insert on public.places for each row execute function f()"):
        assert WRITE_SQL.search(sql), sql
    assert not WRITE_SQL.search("place_id uuid references public.places (id)")


def _strings(tree: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_partners_admin_only_writes_to_partner_applications():
    tree = ast.parse((ROOT / "scripts" / "partners_admin.py").read_text(encoding="utf-8"))
    endpoints = {s for s in _strings(tree) if "/rest/v1/" in s}
    assert endpoints == {"/rest/v1/partner_applications"}, endpoints
    writes = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr in ("post", "patch", "put", "delete")]
    assert writes, "no write call found: the check is not looking at the right thing"
    for call in writes:
        target = call.func.value
        assert isinstance(target, ast.Attribute) and target.attr == "_session", ast.unparse(call)
        url = call.args[0] if call.args else None
        assert isinstance(url, ast.Attribute) and url.attr == "_base", f"write to something else: {ast.unparse(call)}"
    for name in SAFETY_TABLES:
        assert not any(re.fullmatch(rf"(public\.)?{name}", s) for s in _strings(tree)), f"names the {name} table"


def test_partners_js_only_talks_to_its_two_endpoints():
    source = (ROOT / "js" / "partners.js").read_text(encoding="utf-8")
    assert set(re.findall(r"/rest/v1/([a-z_]+)", source)) == {"partner_applications", "partners_public"}
    assert "/storage/v1/object/public/" in source
    assert not re.search(r"/(?:rest|functions)/v1/(?!partner)", source)


def test_map_ranking_and_chat_never_mention_partners():
    files = [ROOT / "js" / f for f in ("map.js", "ranking.js", "chat.js", "geo.js")]
    files += sorted((ROOT / "supabase" / "functions" / "chat").glob("*.ts"))
    assert len(files) > 4
    for path in files:
        source = path.read_text(encoding="utf-8").lower()
        assert "partner" not in source and "aliado" not in source, f"{path.relative_to(ROOT)} mentions partners"


def test_the_supabase_client_partner_methods_only_touch_partner_applications():
    tree = ast.parse((ROOT / "agents" / "clients" / "supabase_client.py").read_text(encoding="utf-8"))
    client = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SupabaseClient")
    methods = [n for n in client.body if isinstance(n, ast.FunctionDef) and "partner" in n.name]
    assert {m.name for m in methods} == {"fetch_partner_applications_for_digest", "purge_partner_applications"}
    for method in methods:
        tables = {c.args[0].value for c in ast.walk(method) if isinstance(c, ast.Call)
                  and isinstance(c.func, ast.Attribute) and c.func.attr == "table"
                  and c.args and isinstance(c.args[0], ast.Constant)}
        assert tables == {"partner_applications"}, (method.name, tables)
        assert not any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                       and c.func.attr in ("update", "insert", "upsert") for c in ast.walk(method)), method.name
    assert "partner_applications" not in _purgeable_tables(client)


def _purgeable_tables(client: ast.ClassDef) -> set[str]:
    """The generic purge_rows allowlist: partner_applications is purged only by its own method."""
    for node in client.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "_PURGEABLE" for t in node.targets):
            return {e.value for e in node.value.elts}
    raise AssertionError("_PURGEABLE not found")
