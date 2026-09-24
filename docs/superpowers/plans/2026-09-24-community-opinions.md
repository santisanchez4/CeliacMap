# Opiniones de la comunidad visibles — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar en "La voz de la comunidad" las recomendaciones positivas que el administrador apruebe, con el nombre opcional de quien las escribió ("Anónimo" si no puso ninguno).

**Architecture:** Dos columnas nuevas en `place_reports` (`author_name`, `published_at`), la política de inserción pública endurecida para que nadie se auto-publique, y una vista `community_opinions` como único contrato público de lectura. El formulario B suma un campo de nombre; un `js/opinions.js` dibuja la sección; un script de moderación (`--approve` / `--hide`, dry-run por defecto) es la única forma de publicar. El chatbot no cambia.

**Tech Stack:** PostgreSQL/Supabase (SQL + RLS), Python 3 (pytest, supabase-py, pglast), HTML/CSS/JS ES5 sin build, Deno + linkedom para los tests de frontend.

**Spec:** `docs/superpowers/specs/2026-09-24-community-opinions-design.md`

## Global Constraints

- Sin frameworks ni librerías nuevas. JS en el estilo del repo: IIFE, `"use strict"`, `var`, sin build.
- **Todo texto de personas (comentario, nombre) entra al DOM solo con `textContent`, nunca como HTML.**
- Las tarjetas dibujadas por JS **no llevan la clase `reveal`** (el observer de `main.js` corre al cargar; una tarjeta dinámica con `reveal` quedaría invisible).
- La vista expone **exactamente** estas 8 columnas: `id, description, author_name, published_at, place_id, place_name, city, country`. Nunca `status`, `place_name_text`, `kitchen_exclusive`, `celiac_prep`, `owner_celiac`.
- `author_name`: nulo o entre 1 y 40 caracteres tras `btrim`. Solo una recomendación **positiva** puede tener `published_at`.
- El campo de nombre va con `autocomplete="off"` (que el navegador no autocomplete un nombre real que se va a publicar).
- Copy en español rioplatense (voseo) con su versión EN en `js/main.js`; toda clave `data-i18n` nueva necesita entrada EN.
- **Nunca `git add -A`** (hay `outputs/social-2026-09-23/` sin versionar que no debe commitearse): agregar rutas explícitas.
- Los mensajes de commit terminan con `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Todo lo que toca producción (migración, merge/push, filas de prueba, aprobar un comentario) **muestra el comando o SQL literal y espera un OK antes de ejecutar**; después, verificación de solo lectura.
- Líneas base antes de empezar: Python **332**, frontend (Deno) **39**, chat (Deno) **201**. Ninguna suite baja.

## Review Focus

Entradas y fallas que el spec implica y que ningún test de tarea "feliz" cubriría; cada una tiene su test en la tarea indicada:

1. Un cliente anónimo inserta `published_at` ya cargado (se auto-publica) → la política lo rechaza (Tarea 1: test + check SQL).
2. Un comentario con HTML/`<script>` → se ve como texto, no se ejecuta (Tarea 4).
3. Un reporte **negativo** que termina publicado → CHECK + filtro de la vista + el script no lo aprueba (Tareas 1 y 2).
4. Un lugar deja de estar `approved` → su opinión desaparece de la vista sola (Tarea 1: check SQL).
5. Nombre tipeado y después cambio a "Reportar" → el nombre **no** se envía; nombre de solo espacios → no se envía y la BD lo rechazaría (Tareas 1 y 3).
6. Comentario de 2000 caracteres → la tarjeta lo recorta en una palabra completa y el administrador ve el texto entero al aprobar (Tareas 2 y 4).

---

### Task 0: Rama y estado de partida

**Files:**
- Commit: `index.html`, `js/main.js` (cambios ya hechos: texto "académico" y LinkedIn del footer), `docs/superpowers/specs/2026-09-24-community-opinions-design.md`, este plan.

- [ ] **Step 1: Crear la rama y confirmar la línea base**

```bash
git checkout -b feat/community-opinions
.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -2
deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_*.test.js 2>&1 | tail -2
```
Expected: `332 passed` y `39 passed | 0 failed`. Si no, parar y avisar.

- [ ] **Step 2: Marcar el spec como aprobado**

En el spec, reemplazar la línea `**Estado:** diseño aprobado en conversación por Santiago; pendiente de revisión del spec escrito.` por `**Estado:** aprobado por Santiago (2026-09-24); plan en `docs/superpowers/plans/2026-09-24-community-opinions.md`.`

- [ ] **Step 3: Commit (solo rutas explícitas)**

```bash
git add index.html js/main.js
git commit -m "content: remove the academic wording and add LinkedIn to the footer

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git add docs/superpowers/specs/2026-09-24-community-opinions-design.md docs/superpowers/plans/2026-09-24-community-opinions.md
git commit -m "docs: spec and plan for public community opinions

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git status --short
```
Expected: solo queda `?? outputs/social-2026-09-23/`.

---

### Task 1: Esquema — columnas, política endurecida y vista pública

**Files:**
- Modify: `db/schema.sql` (bloque nuevo después de `-- KITCHEN-DECLARATIONS-END`; política de inserción de `place_reports`)
- Create: `tests/test_schema_opinions.py`
- Create: `db/checks/2026-09-24-opinions-columns.sql`

**Interfaces:**
- Produces: columnas `place_reports.author_name text`, `place_reports.published_at timestamptz`; vista `public.community_opinions` (8 columnas, ver Global Constraints) con `grant select` a `anon, authenticated`. Las Tareas 2 y 4 dependen de estos nombres.

- [ ] **Step 1: Write the failing test** — `tests/test_schema_opinions.py`

```python
"""Guards the community-opinions block in db/schema.sql
(docs/superpowers/specs/2026-09-24-community-opinions-design.md).

The public read path is a VIEW with an explicit column list, and the anonymous INSERT policy must refuse
a row that arrives already published. pglast only checks syntax, so these tests read the statements.
"""
import re
from pathlib import Path

from pglast import parse_sql
from pglast.ast import ViewStmt

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
PUBLIC_COLUMNS = {
    "id", "description", "author_name", "published_at",
    "place_id", "place_name", "city", "country",
}


def _text() -> str:
    return SCHEMA.read_text(encoding="utf-8").replace("\r\n", "\n")


def _block() -> str:
    text = _text()
    return text[text.index("-- COMMUNITY-OPINIONS-BEGIN"): text.index("-- COMMUNITY-OPINIONS-END")]


def _expression(block: str, constraint: str) -> str:
    m = re.search(rf"{constraint}\s+check \((.*?)\);", block, re.DOTALL)
    assert m, f"{constraint} not found"
    return " ".join(m.group(1).split())


def _view() -> ViewStmt:
    for raw in parse_sql(_block()):
        stmt = raw.stmt
        if isinstance(stmt, ViewStmt) and stmt.view.relname == "community_opinions":
            return stmt
    raise AssertionError("view community_opinions not found")


def test_whole_schema_still_parses():
    assert parse_sql(_text())


def test_author_name_is_optional_and_bounded():
    expr = _expression(_block(), "place_reports_author_name_check")
    assert "author_name is null" in expr, expr
    assert "between 1 and 40" in expr, expr
    assert "btrim(author_name)" in expr, "a name of only spaces must be rejected"


def test_only_a_positive_report_can_be_published():
    expr = _expression(_block(), "place_reports_publish_positive_only_check")
    assert "published_at is null" in expr, expr
    assert "report_type = 'positive'" in expr, expr


def test_anonymous_insert_policy_refuses_an_already_published_row():
    text = _text()
    m = re.search(
        r'create policy "public can submit place reports"(.*?);\n', text, re.DOTALL
    )
    assert m, "policy not found"
    body = " ".join(m.group(1).split())
    assert "published_at is null" in body, body
    assert "status = 'new'" in body, body


def test_view_exposes_exactly_the_public_columns():
    names = []
    for target in _view().query.targetList:
        names.append(target.name or target.val.fields[-1].sval)
    assert set(names) == PUBLIC_COLUMNS, names
    assert len(names) == len(PUBLIC_COLUMNS), f"duplicate column in {names}"


def test_view_only_shows_published_positive_reports_of_approved_places():
    block = " ".join(_block().split())
    where = block[block.index("where r.report_type"): block.index("grant select on public.community_opinions")]
    assert "r.report_type = 'positive'" in where
    assert "r.published_at is not null" in where
    assert "p.status = 'approved'" in where


def test_view_is_public_but_the_table_stays_closed():
    assert "grant select on public.community_opinions to anon, authenticated" in " ".join(_block().split())
    assert not re.search(r"grant\s+select[^;]*on\s+public\.place_reports", _text(), re.IGNORECASE)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_schema_opinions.py -q`
Expected: FAIL — `test_whole_schema_still_parses` pasa; los demás fallan con `ValueError: substring not found` (`COMMUNITY-OPINIONS-BEGIN` no existe todavía).

- [ ] **Step 3: Implement — bloque nuevo en `db/schema.sql`**

Insertar inmediatamente después de la línea `-- KITCHEN-DECLARATIONS-END`:

```sql

-- Community opinions (docs/superpowers/specs/2026-09-24-community-opinions-design.md)
-- ---------------------------------------------------------------------
-- A POSITIVE report can be shown on the public site once the admin approves it
-- (published_at = when). author_name is what the person chose to show; empty
-- means "Anónimo" (the frontend decides the label). place_reports itself stays
-- closed to the public: the ONLY public read path is the view below, with an
-- explicit column list, so kitchen_exclusive / celiac_prep / owner_celiac
-- (a third party's health condition), status and place_name_text never leave.
-- The view runs with its owner's rights (that is what lets it read the closed
-- table); its WHERE is the only barrier and includes p.status = 'approved', so
-- an opinion disappears by itself if its place stops being published.
-- COMMUNITY-OPINIONS-BEGIN
alter table public.place_reports add column if not exists author_name  text;
alter table public.place_reports add column if not exists published_at timestamptz;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'place_reports_author_name_check') then
    alter table public.place_reports add constraint place_reports_author_name_check
      check (author_name is null or char_length(btrim(author_name)) between 1 and 40);
  end if;
end $$;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'place_reports_publish_positive_only_check') then
    alter table public.place_reports add constraint place_reports_publish_positive_only_check
      check (published_at is null or report_type = 'positive');
  end if;
end $$;

create or replace view public.community_opinions as
select r.id,
       r.description,
       r.author_name,
       r.published_at,
       p.id   as place_id,
       p.name as place_name,
       p.city,
       p.country
from public.place_reports r
join public.places p on p.id = r.place_id
where r.report_type = 'positive'
  and r.published_at is not null
  and p.status = 'approved';

grant select on public.community_opinions to anon, authenticated;
-- COMMUNITY-OPINIONS-END
```

Y en la política de inserción existente (`create policy "public can submit place reports"`), agregar `and published_at is null` justo después de `status = 'new'`, y ampliar el comentario que la precede con una línea: `-- published_at must be NULL on insert: only the admin (service_role) publishes.`

```sql
  with check (
    status = 'new'
    and published_at is null
    and (place_id is not null or place_name_text is not null)
    and char_length(description) between 5 and 2000
  );
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_schema_opinions.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Escribir el check SQL** — `db/checks/2026-09-24-opinions-columns.sql`

```sql
-- Verificación de la migración de opiniones de la comunidad. Se corre DESPUÉS de aplicarla;
-- todo queda dentro de una transacción que termina en ROLLBACK (no deja filas).
-- Uso: node_modules/.bin/supabase db query --linked --file db/checks/2026-09-24-opinions-columns.sql
-- Resultado esperado: termina sin error. Cualquier `expected ...` en un mensaje = FALLA.
begin;

-- Como dueño (postgres): estructura, CHECKs y qué muestra la vista.
do $$
declare
  ok_place  uuid;
  bad_place uuid;
  r_pub     uuid;
  n         int;
  cols      text;
begin
  select id into ok_place  from public.places where status = 'approved'  limit 1;
  select id into bad_place from public.places where status <> 'approved' limit 1;
  if ok_place is null or bad_place is null then
    raise exception 'need one approved and one non-approved place to run this check';
  end if;

  -- 1) una positiva publicada de un lugar aprobado aparece en la vista
  insert into public.place_reports (place_id, report_type, description, author_name, published_at)
  values (ok_place, 'positive', '__chk_opinion_1', 'Prueba', now()) returning id into r_pub;
  select count(*) into n from public.community_opinions where id = r_pub;
  if n <> 1 then raise exception 'expected the published positive report in the view'; end if;

  -- 2) sin publicar, no aparece
  insert into public.place_reports (place_id, report_type, description)
  values (ok_place, 'positive', '__chk_opinion_2');
  select count(*) into n from public.community_opinions where description = '__chk_opinion_2';
  if n <> 0 then raise exception 'expected an unpublished report to stay out of the view'; end if;

  -- 3) publicada, pero el lugar NO está aprobado -> no aparece
  insert into public.place_reports (place_id, report_type, description, published_at)
  values (bad_place, 'positive', '__chk_opinion_3', now());
  select count(*) into n from public.community_opinions where description = '__chk_opinion_3';
  if n <> 0 then raise exception 'expected a non-approved place to hide its opinion'; end if;

  -- 4) un lugar que deja de estar aprobado se lleva su opinión
  update public.places set status = 'needs_review' where id = ok_place;
  select count(*) into n from public.community_opinions where id = r_pub;
  if n <> 0 then raise exception 'expected the opinion to vanish when its place stops being approved'; end if;
  update public.places set status = 'approved' where id = ok_place;

  -- 5) columnas exactas de la vista
  select string_agg(column_name, ',' order by column_name) into cols
  from information_schema.columns where table_schema = 'public' and table_name = 'community_opinions';
  if cols <> 'author_name,city,country,description,id,place_id,place_name,published_at' then
    raise exception 'expected the public view columns, got %', cols;
  end if;

  -- 6) violaciones de CHECK
  begin
    insert into public.place_reports (place_id, report_type, description, published_at)
    values (ok_place, 'negative', '__chk_bad_1', now());
    raise exception 'expected check violation: a negative report cannot be published';
  exception when check_violation then null; end;

  begin
    insert into public.place_reports (place_id, report_type, description, author_name)
    values (ok_place, 'positive', '__chk_bad_2', '   ');
    raise exception 'expected check violation: a name of only spaces';
  exception when check_violation then null; end;

  begin
    insert into public.place_reports (place_id, report_type, description, author_name)
    values (ok_place, 'positive', '__chk_bad_3', repeat('x', 41));
    raise exception 'expected check violation: a name longer than 40';
  exception when check_violation then null; end;
end $$;

-- Como anónimo (la clave pública): no se puede auto-publicar, se puede escribir, la tabla sigue cerrada.
do $$
declare
  ok_place uuid;
  n        int;
begin
  select id into ok_place from public.places where status = 'approved' limit 1;
  set local role anon;

  begin
    insert into public.place_reports (place_id, report_type, description, published_at)
    values (ok_place, 'positive', '__chk_anon_1', now());
    raise exception 'expected RLS rejection: anon inserting an already published row';
  exception when insufficient_privilege then null; end;

  insert into public.place_reports (place_id, report_type, description, author_name)
  values (ok_place, 'positive', '__chk_anon_2', 'Ana');

  begin
    perform 1 from public.place_reports limit 1;
    raise exception 'expected permission denied: anon reading place_reports';
  exception when insufficient_privilege then null; end;

  select count(*) into n from public.community_opinions where description = '__chk_opinion_1';
  if n <> 1 then raise exception 'expected anon to read the published opinion through the view'; end if;
  select count(*) into n from public.community_opinions where description = '__chk_anon_2';
  if n <> 0 then raise exception 'expected anon to NOT see an unpublished opinion'; end if;

  reset role;
end $$;

rollback;
```

- [ ] **Step 6: Sintaxis del check y suite completa**

Run: `.venv/Scripts/python.exe -c "import pglast,pathlib; print(len(pglast.parse_sql(pathlib.Path('db/checks/2026-09-24-opinions-columns.sql').read_text(encoding='utf-8'))), 'statements')"`
Expected: `4 statements` (begin, dos `do`, rollback). Después `.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -2` → `339 passed`.

- [ ] **Step 7: Commit**

```bash
git add db/schema.sql tests/test_schema_opinions.py db/checks/2026-09-24-opinions-columns.sql
git commit -m "feat(db): published community opinions - columns, hardened insert policy, public view

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Moderación — métodos del cliente y script `moderate_opinions.py`

**Files:**
- Modify: `agents/clients/supabase_client.py` (dos métodos nuevos, junto a `fetch_community_claims`)
- Modify: `tests/test_supabase_client.py` (tests de los dos métodos)
- Create: `scripts/moderate_opinions.py`
- Create: `tests/test_moderate_opinions.py`

**Interfaces:**
- Consumes: columnas de la Tarea 1.
- Produces: `SupabaseClient.fetch_unpublished_opinions(limit: int = 100) -> list[dict]` (filas `place_reports` positivas, sin publicar, de lugares aprobados, con `places(name, city, country, status)` embebido, más antiguas primero) y `SupabaseClient.set_opinions_published(ids: list[str], published: bool) -> list[dict]`. `scripts.moderate_opinions.run(db, approve, hide, apply, out=print) -> int`.

- [ ] **Step 1: Write the failing tests del cliente** — agregar al final de `tests/test_supabase_client.py`

```python
def test_fetch_unpublished_opinions_asks_only_for_positive_unpublished_reports_of_approved_places():
    client = _client_with_mock_db()
    table = client._db.table
    chain = (table.return_value.select.return_value.eq.return_value.is_.return_value
             .eq.return_value.order.return_value.limit.return_value)
    chain.execute.return_value = MagicMock(data=[{"id": "r1"}])

    assert client.fetch_unpublished_opinions(limit=7) == [{"id": "r1"}]

    table.assert_called_with("place_reports")
    selected = table.return_value.select.call_args.args[0]
    assert "owner_celiac" not in selected, selected
    assert "places!inner" in selected, selected
    table.return_value.select.return_value.eq.assert_called_once_with("report_type", "positive")
    table.return_value.select.return_value.eq.return_value.is_.assert_called_once_with("published_at", "null")
    (table.return_value.select.return_value.eq.return_value.is_.return_value
     .eq.assert_called_once_with("places.status", "approved"))
    chain.execute.assert_called_once()


def test_set_opinions_published_stamps_now_or_null_and_only_touches_positive_reports():
    client = _client_with_mock_db()
    update = client._db.table.return_value.update
    update.return_value.in_.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "r1"}])

    assert client.set_opinions_published(["r1"], True) == [{"id": "r1"}]
    payload = update.call_args.args[0]
    assert set(payload) == {"published_at"} and payload["published_at"]
    update.return_value.in_.assert_called_once_with("id", ["r1"])
    update.return_value.in_.return_value.eq.assert_called_once_with("report_type", "positive")

    client.set_opinions_published(["r1"], False)
    assert update.call_args.args[0] == {"published_at": None}


def test_set_opinions_published_with_no_ids_does_not_touch_the_database():
    client = _client_with_mock_db()
    assert client.set_opinions_published([], True) == []
    client._db.table.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_supabase_client.py -q -k opinions`
Expected: 3 FAIL con `AttributeError: 'SupabaseClient' object has no attribute 'fetch_unpublished_opinions'`.

- [ ] **Step 3: Implement** — en `agents/clients/supabase_client.py`, justo después de `fetch_community_claims` (ver que `datetime`/`timezone` ya estén importados; si no, agregar `from datetime import datetime, timezone` a los imports)

```python
    def fetch_unpublished_opinions(self, limit: int = 100) -> list[dict]:
        """Positive reports waiting for moderation: not published yet, about a place that is
        currently ``approved``. Oldest first. The full ``description`` is returned on purpose —
        the admin reads everything before publishing."""
        res = (
            self._db.table("place_reports")
            .select("id, description, author_name, created_at, place_id, places!inner(name, city, country, status)")
            .eq("report_type", "positive")
            .is_("published_at", "null")
            .eq("places.status", "approved")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return res.data or []

    def set_opinions_published(self, ids: list[str], published: bool) -> list[dict]:
        """Publish (``published_at = now``) or hide (``null``) positive reports. Returns the rows
        changed. Only positive reports are touched (the table CHECK forbids publishing a negative)."""
        if not ids:
            return []
        stamp = datetime.now(timezone.utc).isoformat() if published else None
        res = (
            self._db.table("place_reports")
            .update({"published_at": stamp})
            .in_("id", ids)
            .eq("report_type", "positive")
            .execute()
        )
        return res.data or []
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_supabase_client.py -q`
Expected: todos pasan (los tres nuevos incluidos).

- [ ] **Step 5: Write the failing tests del script** — `tests/test_moderate_opinions.py`

```python
"""The moderation script: list by default, write only with --apply, approve only what is pending."""
import pytest

from scripts.moderate_opinions import run

ID_A = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10"
ID_B = "9a1c5d7e-2b44-4f60-8c31-5e0d7a9b1c22"
ID_C = "c0ffee00-1234-4abc-8def-0123456789ab"


def row(rid, name=None, text="Muy rico todo"):
    return {
        "id": rid, "description": text, "author_name": name, "created_at": "2026-09-23T10:00:00+00:00",
        "place_id": "p1", "places": {"name": "San Felipa", "city": "Gualeguaychú", "country": "Argentina", "status": "approved"},
    }


class FakeDB:
    def __init__(self, pending):
        self.pending = pending
        self.writes = []

    def fetch_unpublished_opinions(self, limit=100):
        return self.pending

    def set_opinions_published(self, ids, published):
        self.writes.append((list(ids), published))
        return [{"id": i} for i in ids]


def capture():
    lines = []
    return lines, lambda text="": lines.append(str(text))


def test_no_ids_lists_pending_with_the_full_text_and_anonymous_label():
    long_text = "palabra " * 250  # ~2000 chars: the admin must see all of it
    db = FakeDB([row(ID_A, name=None, text=long_text), row(ID_B, name="Ana")])
    lines, out = capture()

    assert run(db, approve=[], hide=[], apply=False, out=out) == 0

    text = "\n".join(lines)
    assert ID_A in text and ID_B in text
    assert "San Felipa" in text and "Gualeguaychú" in text
    assert "Anónimo" in text and "Ana" in text
    assert long_text.strip() in text
    assert db.writes == []


def test_approve_is_a_dry_run_without_apply():
    db = FakeDB([row(ID_A)])
    lines, out = capture()
    assert run(db, approve=[ID_A], hide=[], apply=False, out=out) == 0
    assert db.writes == []
    assert "DRY RUN" in "\n".join(lines)


def test_approve_with_apply_publishes_only_the_pending_ids():
    db = FakeDB([row(ID_A), row(ID_B)])
    lines, out = capture()
    code = run(db, approve=[ID_A, ID_C], hide=[], apply=True, out=out)
    assert db.writes == [([ID_A], True)]
    assert ID_C in "\n".join(lines)  # reported as skipped, not silently dropped
    assert code == 1  # an id was skipped: the operator must notice


def test_approve_never_publishes_an_id_that_is_not_pending():
    db = FakeDB([row(ID_A)])
    _, out = capture()
    assert run(db, approve=[ID_C], hide=[], apply=True, out=out) == 1
    assert db.writes == []


def test_hide_with_apply_unpublishes():
    db = FakeDB([])
    _, out = capture()
    assert run(db, approve=[], hide=[ID_B], apply=True, out=out) == 0
    assert db.writes == [([ID_B], False)]


def test_hide_is_a_dry_run_without_apply():
    db = FakeDB([])
    _, out = capture()
    run(db, approve=[], hide=[ID_B], apply=False, out=out)
    assert db.writes == []


def test_an_invalid_id_is_rejected_before_touching_anything():
    db = FakeDB([row(ID_A)])
    _, out = capture()
    assert run(db, approve=["no-es-un-uuid"], hide=[], apply=True, out=out) == 2
    assert db.writes == []


def test_approve_and_hide_together_are_refused():
    with pytest.raises(ValueError):
        run(FakeDB([]), approve=[ID_A], hide=[ID_B], apply=True, out=lambda *_: None)
```

- [ ] **Step 6: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_moderate_opinions.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.moderate_opinions'`.

- [ ] **Step 7: Implement** — `scripts/moderate_opinions.py`

```python
"""Moderate the community's positive recommendations before they show on the public site.

A positive report becomes public only when the admin sets ``published_at``. This script is the way to
do it: it lists what is waiting (the FULL text — read it before approving), publishes chosen ids, or
hides a published one. Dry-run by default; nothing is written without ``--apply``.

    python -m scripts.moderate_opinions                              # list pending
    python -m scripts.moderate_opinions --approve ID [ID ...]        # dry run
    python -m scripts.moderate_opinions --approve ID --apply         # publish
    python -m scripts.moderate_opinions --hide ID --apply            # take one down

Only positive reports of currently approved places can be approved (the database also forbids
publishing a negative one). See docs/superpowers/specs/2026-09-24-community-opinions-design.md.
"""
from __future__ import annotations

import argparse
import re
import sys

from agents.clients.supabase_client import SupabaseClient
from config.settings import get_settings

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _print_pending(pending: list[dict], out) -> None:
    if not pending:
        out("No hay recomendaciones pendientes de aprobar.")
        return
    out(f"{len(pending)} recomendación(es) pendiente(s):")
    for r in pending:
        place = r.get("places") or {}
        name = (r.get("author_name") or "").strip() or "(sin nombre → se publicaría como Anónimo)"
        out("")
        out(f"  id:     {r['id']}")
        out(f"  lugar:  {place.get('name')} — {place.get('city')}, {place.get('country')}")
        out(f"  autor:  {name}")
        out(f"  fecha:  {r.get('created_at')}")
        out(f"  texto:  {r.get('description')}")


def run(db, approve: list[str], hide: list[str], apply: bool, out=print) -> int:
    if approve and hide:
        raise ValueError("use --approve or --hide, not both")
    invalid = [i for i in (approve + hide) if not _UUID.match(i)]
    if invalid:
        out(f"Id inválido (se espera un uuid): {', '.join(invalid)}")
        return 2

    if not approve and not hide:
        _print_pending(db.fetch_unpublished_opinions(), out)
        return 0

    if hide:
        if not apply:
            out(f"DRY RUN — se retirarían {len(hide)} comentario(s): {', '.join(hide)}. Agregá --apply para escribir.")
            return 0
        changed = db.set_opinions_published(hide, False)
        out(f"Retirados: {len(changed)} de {len(hide)}.")
        return 0

    pending_ids = {r["id"] for r in db.fetch_unpublished_opinions()}
    allowed = [i for i in approve if i in pending_ids]
    skipped = [i for i in approve if i not in pending_ids]
    if skipped:
        out(f"Omitidos (no son una recomendación positiva pendiente de un lugar aprobado): {', '.join(skipped)}")
    if not allowed:
        return 1
    if not apply:
        out(f"DRY RUN — se publicarían {len(allowed)} comentario(s): {', '.join(allowed)}. Agregá --apply para escribir.")
        return 1 if skipped else 0
    changed = db.set_opinions_published(allowed, True)
    out(f"Publicados: {len(changed)} de {len(allowed)}.")
    return 1 if skipped else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--approve", nargs="+", default=[], metavar="ID", help="publish these report ids")
    group.add_argument("--hide", nargs="+", default=[], metavar="ID", help="take these report ids down")
    parser.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key")
    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    return run(db, args.approve, args.hide, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Run to verify pass + suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_moderate_opinions.py -q` → `8 passed`. Luego `.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -2` → `350 passed` (332 + 7 + 3 + 8).

- [ ] **Step 9: Commit**

```bash
git add agents/clients/supabase_client.py tests/test_supabase_client.py scripts/moderate_opinions.py tests/test_moderate_opinions.py
git commit -m "feat(agents): moderation script and client methods for public opinions

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Formulario B — nombre opcional y aviso

**Files:**
- Modify: `index.html` (campo + dos avisos dentro de `#rp-details`)
- Modify: `js/report.js` (visibilidad según tipo, payload)
- Modify: `js/main.js` (4 claves EN)
- Modify: `css/styles.css` (`.rp-author-notice`)
- Create: `tests/frontend_opinions.test.js` (sección del formulario; la Tarea 4 agrega la de la sección)

**Interfaces:**
- Produces: ids `rp-author-field`, `rp-author`, `rp-author-notice-positive`, `rp-author-notice-negative`; el cuerpo enviado suma `author_name` solo si es positivo y no vacío.

- [ ] **Step 1: Write the failing tests** — `tests/frontend_opinions.test.js`

```js
// Public opinions: the optional name in Form B and the "La voz de la comunidad" section.
// No network, no browser.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_opinions.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import vm from "node:vm";
import assert from "node:assert/strict";

const PLACE = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10";

async function page(scripts, respond) {
  const html = await Deno.readTextFile("index.html");
  const { window, document } = parseHTML(html);
  const browser = { CELIACMAP_CONFIG: { SUPABASE_URL: "https://fixture.invalid", SUPABASE_ANON_KEY: "fixture-anon" } };
  const calls = [];
  let now = 1_700_000_000_000; // realistic epoch: a tiny value trips the 60 s cooldown
  const context = {
    window: browser, document, setTimeout, clearTimeout, CustomEvent: window.CustomEvent,
    Date: { now: () => (now += 5000) },
    fetch: async (url, init = {}) => {
      calls.push({ url: String(url), init, body: init.body ? JSON.parse(init.body) : null });
      return respond ? respond(String(url)) : { ok: true };
    },
  };
  for (const file of scripts) vm.runInNewContext(await Deno.readTextFile(file), context);
  await new Promise((r) => setTimeout(r, 0));
  return { window, document, browser, calls };
}

const setType = (f, type) => {
  const radios = [...f.document.querySelectorAll('input[name="rp-type"]')];
  for (const r of radios) r.checked = r.value === type;
  radios.find((r) => r.value === type).dispatchEvent(new f.window.Event("change", { bubbles: true }));
};

async function submitReport({ type = "positive", author, switchTo } = {}) {
  const f = await page(["js/kitchen.js", "js/report.js"]);
  const d = f.document;
  d.getElementById("rp-place-id").value = PLACE;
  d.getElementById("rp-description").value = "Muy buena atención y opciones para celíacos";
  setType(f, type);
  if (author !== undefined) d.getElementById("rp-author").value = author;
  if (switchTo) setType(f, switchTo);
  d.getElementById("report-form").dispatchEvent(new f.window.Event("submit", { cancelable: true }));
  await new Promise((r) => setTimeout(r, 0));
  return { f, sent: f.calls.filter((c) => c.url.endsWith("/place_reports")).map((c) => c.body) };
}

/* ------------------------------- Form B -------------------------------- */

Deno.test("form B: the name field sits inside #rp-details, capped at 40, never autofilled", async () => {
  const f = await page(["js/kitchen.js", "js/report.js"]);
  const input = f.document.getElementById("rp-author");
  assert.ok(input, "#rp-author missing");
  assert.ok(f.document.getElementById("rp-details").contains(input));
  assert.equal(input.getAttribute("maxlength"), "40");
  assert.equal(input.getAttribute("autocomplete"), "off");
  assert.equal(f.document.getElementById("rp-author-notice-negative").hasAttribute("hidden"), true);
  assert.equal(f.document.getElementById("rp-author-notice-positive").hasAttribute("hidden"), false);
});

Deno.test("form B: a positive recommendation sends the trimmed name", async () => {
  const { sent } = await submitReport({ author: "  Ana  " });
  assert.equal(sent[0].author_name, "Ana");
});

Deno.test("form B: without a name the payload is exactly today's (no author_name key)", async () => {
  const { sent } = await submitReport({});
  assert.deepEqual(Object.keys(sent[0]).sort(), ["description", "place_id", "report_type"]);
});

Deno.test("form B: a name of only spaces is not sent", async () => {
  const { sent } = await submitReport({ author: "     " });
  assert.equal("author_name" in sent[0], false);
});

Deno.test("form B: a name is cut at 40 characters", async () => {
  const { sent } = await submitReport({ author: "x".repeat(60) });
  assert.equal(sent[0].author_name.length, 40);
});

Deno.test("form B: a report hides the name field, shows its own notice and never sends a name", async () => {
  const { f, sent } = await submitReport({ author: "Ana", switchTo: "negative" });
  const d = f.document;
  assert.equal(d.getElementById("rp-author-field").hidden, true);
  assert.equal(d.getElementById("rp-author-notice-negative").hidden, false);
  assert.equal(sent[0].report_type, "negative");
  assert.equal("author_name" in sent[0], false, "a typed name must not survive switching to 'Reportar'");
});

Deno.test("form B: after SENDING a report the name field and notices follow the type again", async () => {
  const f = await page(["js/kitchen.js", "js/report.js"]);
  const d = f.document;
  const pos = d.getElementById("rp-type-positive");
  const neg = d.getElementById("rp-type-negative");
  // linkedom has no radio-group reset: emulate a browser's form.reset() (re-selects "Recomendar", no change event)
  d.getElementById("report-form").reset = () => { pos.checked = true; neg.checked = false; d.getElementById("rp-author").value = ""; };
  d.getElementById("rp-place-id").value = PLACE;
  d.getElementById("rp-description").value = "Me contaminaron la comida";
  setType(f, "negative");
  d.getElementById("report-form").dispatchEvent(new f.window.Event("submit", { cancelable: true }));
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(pos.checked, true);
  assert.equal(d.getElementById("rp-author-field").hidden, false);
  assert.equal(d.getElementById("rp-author-notice-negative").hidden, true);
});

Deno.test("form B: every new data-i18n key has an EN entry", async () => {
  const main = await Deno.readTextFile("js/main.js");
  const en = new Set([...main.matchAll(/"([\w.]+)":\s*"/g)].map((m) => m[1]));
  const { document } = parseHTML(await Deno.readTextFile("index.html"));
  const keys = [...document.querySelectorAll("#rp-details [data-i18n], #rp-details [data-i18n-placeholder]")]
    .map((n) => n.getAttribute("data-i18n") || n.getAttribute("data-i18n-placeholder"));
  assert.deepEqual(keys.filter((k) => !en.has(k)), []);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_opinions.test.js 2>&1 | tail -20`
Expected: fallan los que usan el campo nuevo (`#rp-author missing` / `Cannot read properties of null`); "without a name" y "every new data-i18n key" pasan ya, porque describen comportamiento que hoy existe.

- [ ] **Step 3: Implement — `index.html`**

En `#rp-details`, entre el `</div>` del campo de descripción y el `<fieldset ... id="rp-kitchen">`, insertar:

```html
            <div class="field field-full" id="rp-author-field">
              <label for="rp-author" data-i18n="report.author.label">Tu nombre (opcional)</label>
              <input id="rp-author" name="author_name" type="text" maxlength="40" autocomplete="off"
                placeholder="Cómo querés que aparezca tu nombre"
                data-i18n-placeholder="report.author.ph" />
              <p class="rp-author-notice" id="rp-author-notice-positive" data-i18n="report.author.noticePositive">
                Si es una recomendación, puede mostrarse en el sitio después de que la revisemos. Sin nombre, aparece como Anónimo.
              </p>
            </div>
            <p class="rp-author-notice field-full" id="rp-author-notice-negative" data-i18n="report.author.noticeNegative" hidden>
              Los reportes no se publican: los revisamos internamente.
            </p>
```

- [ ] **Step 4: Implement — `js/report.js`**

Después de `var kitchen = ...`:

```js
  var authorField = document.getElementById("rp-author-field");
  var authorEl = document.getElementById("rp-author");
  var authorNoticeNegativeEl = document.getElementById("rp-author-notice-negative");
```

Reemplazar el bloque `syncKitchen` (definición + la llamada `syncKitchen();` que le sigue) por:

```js
  // Kitchen block and the public name only apply to a recommendation; a report never carries them
  // and is never published, so its own notice replaces the name field.
  function syncTypeFields() {
    var positive = currentType() === "positive";
    if (kitchen) kitchen.setVisible(positive);
    if (authorField) authorField.hidden = !positive;
    if (authorNoticeNegativeEl) authorNoticeNegativeEl.hidden = positive;
    if (!positive && authorEl) authorEl.value = "";
  }
  syncTypeFields();
```

Reemplazar **todas** las demás llamadas `syncKitchen()` del archivo (el listener de cambio de tipo y los dos `syncKitchen(); // form.reset() ...` del submit) por `syncTypeFields()`. Verificar con `grep -n syncKitchen js/report.js` → sin resultados.

En el armado de `data` (después del bloque `if (kitchen && currentType() === "positive") { ... }`):

```js
    var author = (authorEl && authorEl.value || "").trim();
    if (currentType() === "positive" && author) data.author_name = author.slice(0, 40);
```

- [ ] **Step 5: Implement — `js/main.js`** (después de `"report.form.descriptionPh"`)

```js
    "report.author.label": "Your name (optional)",
    "report.author.ph": "How you want your name to appear",
    "report.author.noticePositive": "If it's a recommendation, it may be shown on the site after we review it. Without a name, it appears as Anonymous.",
    "report.author.noticeNegative": "Reports are not published: we review them internally.",
```

- [ ] **Step 6: Implement — `css/styles.css`** (junto a `.kitchen-intro`)

```css
.rp-author-notice { color: var(--color-text-muted); font-size: 0.88rem; margin: 6px 0 0; }
```

- [ ] **Step 7: Run to verify pass**

Run: `deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_*.test.js 2>&1 | tail -3`
Expected: `47 passed | 0 failed` (39 + 8). Verificar que el test viejo "No sé everywhere sends exactly today's payload" sigue verde.

- [ ] **Step 8: Commit**

```bash
git add index.html js/report.js js/main.js css/styles.css tests/frontend_opinions.test.js
git commit -m "feat(forms): optional public name in the recommendation form

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: La sección "La voz de la comunidad" con datos reales

**Files:**
- Create: `js/opinions.js`
- Modify: `index.html` (sección `#reviews`: sacar las 3 tarjetas inventadas, contenedor nuevo, `<script>`, subtítulo)
- Modify: `js/main.js` (`reviews.lead`; borrar `reviews.r1/r2/r3.*`; claves de la sección si hicieran falta)
- Modify: `css/styles.css` (avatar anónimo, botón del lugar, tarjeta de invitación)
- Modify: `tests/frontend_opinions.test.js` (sección nueva)

**Interfaces:**
- Consumes: la vista `community_opinions` (Tarea 1), el evento `celiacmap:open-place` de `map.js`, el ancla `#report-form`.
- Produces: `#opinions-grid` dibujado por `js/opinions.js`.

- [ ] **Step 1: Write the failing tests** — agregar al final de `tests/frontend_opinions.test.js`

```js
/* ---------------------------- Opinions section ---------------------------- */

const rowsOf = (n, extra = {}) => Array.from({ length: n }, (_, i) => ({
  id: `id-${i}`, description: `Comentario ${i}`, author_name: `Persona ${i}`,
  place_id: `place-${i}`, place_name: `Lugar ${i}`, city: "Rosario", country: "Argentina", ...extra,
}));
const okJson = (rows) => ({ ok: true, json: async () => rows });
const cards = (f) => [...f.document.querySelectorAll("#opinions-grid .review:not(.review-cta)")];
const cta = (f) => f.document.querySelector("#opinions-grid .review-cta");

async function opinions(rows, opts = {}) {
  const f = await page(["js/opinions.js"], () => (rows instanceof Error ? Promise.reject(rows) : okJson(rows)));
  if (opts.lang) {
    f.document.documentElement.setAttribute("lang", opts.lang);
    f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:lang", { detail: opts.lang }));
  }
  return f;
}

Deno.test("#reviews: the three invented testimonials are gone and the grid is there", async () => {
  const html = await Deno.readTextFile("index.html");
  const { document } = parseHTML(html);
  const section = document.getElementById("reviews");
  assert.ok(section.querySelector("#opinions-grid"));
  for (const invented of ["María L.", "Joaquín R.", "Valentina S.", "Celíaca hace 8 años"]) {
    assert.equal(section.textContent.includes(invented), false, invented);
  }
  assert.ok(html.includes('<script src="js/opinions.js"></script>'));
  const main = await Deno.readTextFile("js/main.js");
  assert.equal(/"reviews\.r[123]\./.test(main), false, "orphaned EN keys for the removed testimonials");
});

Deno.test("#reviews: every data-i18n key has an EN entry", async () => {
  const main = await Deno.readTextFile("js/main.js");
  const en = new Set([...main.matchAll(/"([\w.]+)":\s*"/g)].map((m) => m[1]));
  const { document } = parseHTML(await Deno.readTextFile("index.html"));
  const keys = [...document.querySelectorAll("#reviews [data-i18n]")].map((n) => n.getAttribute("data-i18n"));
  assert.deepEqual(keys.filter((k) => !en.has(k)), []);
});

Deno.test("opinions: reads the public view with the anon key, newest first, at most 6", async () => {
  const f = await opinions(rowsOf(1));
  const call = f.calls[0];
  assert.ok(call.url.startsWith("https://fixture.invalid/rest/v1/community_opinions?select="), call.url);
  assert.ok(call.url.includes("order=published_at.desc"));
  assert.ok(call.url.includes("limit=6"));
  assert.equal(call.init.headers.apikey, "fixture-anon");
  assert.equal(call.url.includes("place_reports"), false, "must never read the closed table");
});

Deno.test("opinions: a name is shown with its initial, no name means Anónimo with the neutral avatar", async () => {
  const f = await opinions([
    { ...rowsOf(1)[0], author_name: "ana" },
    { ...rowsOf(1)[0], id: "b", author_name: null },
    { ...rowsOf(1)[0], id: "c", author_name: "   " },
  ]);
  const [a, b, c] = cards(f);
  assert.equal(a.querySelector("strong").textContent, "ana");
  assert.equal(a.querySelector(".avatar").textContent, "A");
  assert.equal(a.querySelector(".avatar").classList.contains("avatar--anon"), false);
  for (const anon of [b, c]) {
    assert.equal(anon.querySelector("strong").textContent, "Anónimo");
    assert.equal(anon.querySelector(".avatar").classList.contains("avatar--anon"), true);
    assert.equal(anon.querySelector(".avatar").textContent, "");
  }
});

Deno.test("opinions: each card names the place and its city", async () => {
  const f = await opinions(rowsOf(1));
  assert.equal(cards(f)[0].querySelector(".review-place").textContent, "sobre Lugar 0 · Rosario");
});

Deno.test("opinions: three or more show only opinions; fewer add the invitation card", async () => {
  assert.equal(cta(await opinions(rowsOf(3))), null);
  const two = await opinions(rowsOf(2));
  assert.equal(cards(two).length, 2);
  assert.ok(cta(two));
  assert.equal(cta(two).querySelector("a").getAttribute("href"), "#report-form");
});

Deno.test("opinions: none published -> only the invitation card, with the empty-state copy", async () => {
  const f = await opinions([]);
  assert.equal(cards(f).length, 0);
  assert.ok(cta(f).textContent.includes("Todavía no hay comentarios publicados"));
});

Deno.test("opinions: a failed load shows the empty state and does not throw", async () => {
  const f = await opinions(new Error("network down"));
  assert.equal(cards(f).length, 0);
  assert.ok(cta(f));
});

Deno.test("opinions: a comment with HTML is text, never markup", async () => {
  const evil = `<img src=x onerror="alert(1)"><script>alert(2)</script>`;
  const f = await opinions([{ ...rowsOf(1)[0], description: evil, author_name: `<b>Ana</b>` }]);
  const card = cards(f)[0];
  assert.equal(card.querySelector("img"), null);
  assert.equal(card.querySelector("script"), null);
  assert.equal(card.querySelector("b"), null);
  assert.ok(card.querySelector(".review-text").textContent.includes("<img src=x"));
  assert.equal(card.querySelector("strong").textContent, "<b>Ana</b>");
});

Deno.test("opinions: a long comment is cut at a whole word with an ellipsis; a short one is untouched", async () => {
  const long = "palabra ".repeat(250).trim();
  const f = await opinions([{ ...rowsOf(1)[0], description: long }, { ...rowsOf(1)[0], id: "s", description: "Corto y bueno" }]);
  const [big, small] = cards(f).map((c) => c.querySelector(".review-text").textContent);
  const inner = big.slice(1, -1); // the curly quotes
  assert.ok(inner.endsWith("…"));
  assert.ok(inner.length <= 281, String(inner.length));
  assert.equal(inner.slice(0, -1).endsWith("palabra"), true, "cut mid-word");
  assert.equal(small, "“Corto y bueno”");
});

Deno.test("opinions: dynamic cards never use .reveal (the observer would leave them invisible)", async () => {
  const f = await opinions(rowsOf(2));
  assert.equal(f.document.querySelectorAll("#opinions-grid .reveal").length, 0);
});

Deno.test("opinions: switching to English redraws the labels", async () => {
  const f = await opinions([{ ...rowsOf(1)[0], author_name: null }], { lang: "en" });
  assert.equal(cards(f)[0].querySelector("strong").textContent, "Anonymous");
  assert.equal(cards(f)[0].querySelector(".review-place").textContent, "about Lugar 0 · Rosario");
  assert.ok(cta(f).textContent.includes("Tell us about your experience"));
});

Deno.test("opinions: clicking the place opens it on the map through the shared event", async () => {
  const f = await opinions(rowsOf(1));
  let detail = null;
  f.document.addEventListener("celiacmap:open-place", (e) => { detail = e.detail; });
  cards(f)[0].querySelector(".review-place").dispatchEvent(new f.window.Event("click", { bubbles: true }));
  assert.deepEqual(JSON.parse(JSON.stringify(detail)), { id: "place-0" });
});

Deno.test("opinions: rows missing a place or a text are ignored", async () => {
  const f = await opinions([{ ...rowsOf(1)[0], place_name: null }, { ...rowsOf(1)[0], description: "" }, ...rowsOf(1)]);
  assert.equal(cards(f).length, 1);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_opinions.test.js 2>&1 | tail -30`
Expected: los tests nuevos fallan (`js/opinions.js` no existe → error al leerlo; el de HTML falla porque las tarjetas inventadas siguen).

- [ ] **Step 3: Implement — `js/opinions.js`**

```js
/* =====================================================================
   CeliacMap — js/opinions.js
   "La voz de la comunidad": shows the positive recommendations the admin
   approved, read from the public view community_opinions (anon key,
   read-only; the closed place_reports table is never touched). Every piece
   of people's text goes in through textContent — never as HTML. Cards are
   built here, so they must not use .reveal (the observer in main.js ran
   at load). See docs/superpowers/specs/2026-09-24-community-opinions-design.md.
   ===================================================================== */
(function () {
  "use strict";

  var cfg = window.CELIACMAP_CONFIG || {};
  var grid = document.getElementById("opinions-grid");
  if (!grid) return;

  var LIMIT = 6;
  var MAX_CHARS = 280;
  var ENOUGH = 3; // with this many opinions the invitation card is not needed

  var MSG = {
    es: {
      anonymous: "Anónimo",
      about: "sobre",
      emptyTitle: "Todavía no hay comentarios publicados",
      emptyText: "Sé la primera persona en contar cómo te fue.",
      moreTitle: "¿Fuiste a un lugar del mapa?",
      moreText: "Contanos cómo te fue.",
      cta: "Contanos tu experiencia"
    },
    en: {
      anonymous: "Anonymous",
      about: "about",
      emptyTitle: "No comments published yet",
      emptyText: "Be the first to tell us how it went.",
      moreTitle: "Been to a place on the map?",
      moreText: "Tell us how it went.",
      cta: "Tell us about your experience"
    }
  };

  var items = [];
  var loaded = false;

  function lang() {
    return document.documentElement.getAttribute("lang") === "en" ? "en" : "es";
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  // Cut at a whole word so the card never ends mid-word.
  function clip(text) {
    text = String(text || "").replace(/\s+/g, " ").trim();
    if (text.length <= MAX_CHARS) return text;
    var cut = text.slice(0, MAX_CHARS);
    var space = cut.lastIndexOf(" ");
    if (space > MAX_CHARS * 0.6) cut = cut.slice(0, space);
    return cut.replace(/[\s.,;:!?-]+$/, "") + "…";
  }

  function firstLetter(name) {
    var chars = Array.from(name);
    return chars.length ? chars[0].toUpperCase() : "";
  }

  function valid(row) {
    return row && typeof row.description === "string" && row.description.trim() &&
      typeof row.place_name === "string" && row.place_name && row.place_id;
  }

  function card(item) {
    var m = MSG[lang()];
    var name = (item.author_name || "").trim();
    var anonymous = !name;
    var article = el("article", "review");
    article.appendChild(el("p", "review-text", "“" + clip(item.description) + "”"));

    var author = el("div", "review-author");
    var avatar = el("span", "avatar" + (anonymous ? " avatar--anon" : ""), anonymous ? "" : firstLetter(name));
    avatar.setAttribute("aria-hidden", "true");
    author.appendChild(avatar);

    var who = el("div");
    who.appendChild(el("strong", null, anonymous ? m.anonymous : name));
    var place = el("button", "review-place", m.about + " " + item.place_name + (item.city ? " · " + item.city : ""));
    place.type = "button";
    place.setAttribute("data-place-id", item.place_id);
    who.appendChild(place);
    author.appendChild(who);
    article.appendChild(author);
    return article;
  }

  function inviteCard(hasItems) {
    var m = MSG[lang()];
    var box = el("article", "review review-cta");
    box.appendChild(el("p", "review-cta-title", hasItems ? m.moreTitle : m.emptyTitle));
    box.appendChild(el("p", "review-cta-text", hasItems ? m.moreText : m.emptyText));
    var link = el("a", "btn btn-outline", m.cta);
    link.setAttribute("href", "#report-form");
    box.appendChild(link);
    return box;
  }

  function render() {
    if (!loaded) return;
    while (grid.firstChild) grid.removeChild(grid.firstChild);
    items.forEach(function (item) { grid.appendChild(card(item)); });
    if (items.length < ENOUGH) grid.appendChild(inviteCard(items.length > 0));
  }

  grid.addEventListener("click", function (e) {
    var target = e.target && e.target.closest ? e.target.closest("[data-place-id]") : null;
    if (!target) return;
    try {
      document.dispatchEvent(new CustomEvent("celiacmap:open-place", { detail: { id: target.getAttribute("data-place-id") } }));
    } catch (err) {}
  });

  document.addEventListener("celiacmap:lang", render);

  function load() {
    if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) {
      loaded = true;
      render();
      return;
    }
    var url = cfg.SUPABASE_URL.replace(/\/+$/, "") +
      "/rest/v1/community_opinions?select=id,description,author_name,place_id,place_name,city,country" +
      "&order=published_at.desc&limit=" + LIMIT;
    fetch(url, { headers: { apikey: cfg.SUPABASE_ANON_KEY, Authorization: "Bearer " + cfg.SUPABASE_ANON_KEY } })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (rows) { items = Array.isArray(rows) ? rows.filter(valid) : []; })
      .catch(function () { items = []; })
      .then(function () { loaded = true; render(); });
  }

  load();
})();
```

- [ ] **Step 4: Implement — `index.html`**

En `<section ... id="reviews">`: cambiar el subtítulo (`data-i18n="reviews.lead"`) a `Lo que cuentan quienes ya fueron a estos lugares.`, y reemplazar el bloque `<div class="grid grid-3"> ...tres <article class="review reveal">... </div>` completo por:

```html
        <div class="grid grid-3" id="opinions-grid" aria-live="polite"></div>
```

Y agregar después de `<script src="js/ranking.js"></script>`:

```html
  <script src="js/opinions.js"></script>
```

- [ ] **Step 5: Implement — `js/main.js`**

Reemplazar `"reviews.lead": "Real experiences that build trust.",` por `"reviews.lead": "What people say who have already been to these places.",` y **borrar** las seis líneas `"reviews.r1.text"`, `"reviews.r1.role"`, `"reviews.r2.text"`, `"reviews.r2.role"`, `"reviews.r3.text"`, `"reviews.r3.role"`.

- [ ] **Step 6: Implement — `css/styles.css`** (en la sección `/* Reviews */`, después de `.review-author div { ... }`)

```css
.avatar--anon {
  background: var(--color-primary-light)
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232d6a4f' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='8' r='4'/%3E%3Cpath d='M4 21c0-4 4-6 8-6s8 2 8 6'/%3E%3C/svg%3E")
    center / 24px no-repeat;
}
.review-place {
  align-self: flex-start;
  background: none; border: 0; padding: 6px 0; margin: 0;
  font: inherit; font-size: 0.875rem; text-align: left;
  color: var(--color-primary); text-decoration: underline; text-underline-offset: 3px;
  cursor: pointer;
}
.review-cta { display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 12px; }
.review-cta-title { margin: 0; font-family: var(--font-serif); font-size: 1.3125rem; line-height: 1.4; color: var(--color-text); }
.review-cta-text { margin: 0; color: var(--color-text-muted); }
```

Antes de dar por buena la tarjeta, verificar cómo se ve `.review`: `grep -n "\.review[ ,{]" css/styles.css`. Si `.review` no tiene caja propia (borde/fondo/padding), agregar `.review { background: var(--color-surface, #fff); border: 1px solid var(--color-border); border-radius: var(--radius-lg, 16px); padding: 28px; }` usando las variables que existan (`grep -n "^  --" css/styles.css`); si ya la tiene, no tocar.

- [ ] **Step 7: Run to verify pass**

Run: `deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_*.test.js 2>&1 | tail -3`
Expected: `61 passed | 0 failed` (47 + 14).

- [ ] **Step 8: Commit**

```bash
git add js/opinions.js index.html js/main.js css/styles.css tests/frontend_opinions.test.js
git commit -m "feat(site): show approved community opinions in 'La voz de la comunidad'

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Documentación

**Files:**
- Create: `docs/architecture/ADR-008-published-community-opinions.md`
- Modify: `CLAUDE.md`, `README.md`, `docs/architecture/C4-diagrams.md`, el spec (estado)

- [ ] **Step 1: ADR-008** — misma estructura que `docs/architecture/ADR-007-kitchen-info-as-evidence.md` (Estado, Contexto, Decisión, Consecuencias, Alternativas descartadas, Verificación). Estado: `Propuesto` hasta que la Tarea 6 lo verifique en vivo. Contenido: la vista como único contrato público y por qué no una política de lectura sobre la tabla (columnas explícitas; `owner_celiac` nunca sale); aprobación previa del administrador y por qué (sin cuentas, plataforma de salud); solo positivas; sin efecto sobre `places.status` / ranking; `published_at` con `with check ... is null` como defensa contra la auto-publicación; alternativas descartadas (publicación automática, moderación por IA, columna booleana `is_public`, pedir el nombre en el chatbot).

- [ ] **Step 2: `CLAUDE.md`** — (a) **Schema refinements:** una viñeta: `place_reports` gana `author_name` y `published_at`; lo público de `place_reports` es solo la vista `community_opinions` (8 columnas). (b) **File Structure:** agregar `js/opinions.js` y `scripts/moderate_opinions.py`. (c) **Decisions Log:** entrada `### Community opinions on the public site (2026-09-24)` con el diseño, las decisiones (nombre opcional → "Anónimo", solo positivas, aprobación previa, chatbot sin cambios, testimonios inventados eliminados) y el hallazgo de que "Experiencias reales" mostraba ejemplos inventados; y actualizar en `### \`#suggest\` section` la frase de la pieza 3 ("not built") a "built, see Community opinions". (d) **Build status:** `Phase 26 — Community opinions` (🚧 hasta el despliegue; ✅ después). (e) Actualizar `**Suggested Sections**` punto 7 (Reviews) sin cambios de fondo; no tocar el texto histórico "academic" de *Project Context* / *Quality Criteria* (es contexto histórico; se lo aclara con una nota corta debajo de *Project Context*: `> El proyecto ya no se presenta como académico en el sitio público (2026-09-24).`).

- [ ] **Step 3: `README.md`** — sección de funcionalidades: opiniones de la comunidad con aprobación previa; estructura: `js/opinions.js`, `scripts/moderate_opinions.py`; cómo moderar (los 3 comandos del script).

- [ ] **Step 4: `C4-diagrams.md`** — Nivel 2: contenedor frontend `js/opinions.js` (lee la vista) y `js/report.js` (ahora también envía `author_name`); la vista `community_opinions` sobre `place_reports`; el script `moderate_opinions.py` (service_role) como el único camino de publicación.

- [ ] **Step 5: Verificar y commit**

```bash
.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -2
git add CLAUDE.md README.md docs/architecture/ADR-008-published-community-opinions.md docs/architecture/C4-diagrams.md docs/superpowers/specs/2026-09-24-community-opinions-design.md
git commit -m "docs: ADR-008 and documentation for public community opinions

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
Expected: suite verde (incluye `test_rubric_docs_sync` y `test_chat_prompts_sync`, que no deben verse afectados).

---

### Task 6: Revisión de rama, despliegue y verificación en vivo (cada paso de producción pide OK)

**Files:**
- Create: `db/checks/opinions_live.py` (verificación en vivo con la clave pública + el script de moderación)
- Create: `db/checks/2026-09-24-opinions-live-run.md` (evidencia)

- [ ] **Step 1: Suites completas** — `.venv/Scripts/python.exe -m pytest -q` (esperado 350 passed), `deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_*.test.js` (61 passed), `deno test --no-lock -A supabase/functions/chat/` (201 passed, sin cambios), `git diff main --stat` sin archivos inesperados, y `git status --short` con solo `outputs/`.

- [ ] **Step 2: Revisión de rama con contexto fresco** — revisión de toda la rama contra el spec y este plan (subagente si está disponible; si no, autorrevisión declarada). Foco: el Review Focus de arriba. Críticos/Importantes → una sola pasada de arreglos, cada uno con test rojo→verde; menores → lista de diferidos.

- [ ] **Step 3: Ensayo de la migración dentro de una transacción con ROLLBACK (PIDE OK, muestra el archivo)** — armar en el scratchpad `rehearsal.sql` = `begin;` + el bloque `COMMUNITY-OPINIONS-BEGIN…END` extraído de `db/schema.sql` + el `drop policy` / `create policy` de `place_reports` extraído de `db/schema.sql` + el cuerpo de `db/checks/2026-09-24-opinions-columns.sql` sin su `begin;` inicial. Termina en `rollback;`. Mostrarlo completo y ejecutar `node_modules/.bin/supabase db query --linked --file <rehearsal.sql>`. Esperado: sin error. Verificación posterior de solo lectura: `place_reports` sin columnas nuevas (el rollback no dejó nada).

- [ ] **Step 4: Aplicar la migración (PIDE OK, muestra el SQL literal)** — el mismo bloque + la política, sin `rollback`, más un `commit`. Verificación de solo lectura: columnas presentes, política con `published_at is null`, vista con sus 8 columnas, `places` sin cambios. Después correr `db/checks/2026-09-24-opinions-columns.sql` (termina en rollback). Esperado: sin error.

- [ ] **Step 5: Publicar el frontend (PIDE OK)** — `git checkout main && git merge --no-ff feat/community-opinions`, `git push origin main`; esperar `deploy-pages.yml` en verde (`gh run watch`). Orden obligatorio: la migración va **antes** (el formulario nuevo manda `author_name`).

- [ ] **Step 6: Verificación en vivo (PIDE OK; el script escribe una fila de prueba con marcador exacto)** — `db/checks/opinions_live.py`: (a) con la clave anon, POST a `place_reports` con `published_at` cargado → esperado 401/403 y **nada** insertado; (b) POST de una recomendación de prueba (`description` = `PRUEBA-OPINIONES <uuid>`, `author_name` = `Prueba`) sobre un lugar real aprobado → 201; (c) GET `community_opinions` → **no** aparece; (d) `python -m scripts.moderate_opinions` la lista con su texto completo; (e) `--approve <id> --apply` → GET la muestra con el nombre; (f) `--hide <id> --apply` → desaparece; (g) mirar la sección en https://celiacmap.org en ES y EN y a 390 px (Chrome), y el formulario B (campo de nombre, aviso, cambio a "Reportar"). **Reversión:** mostrar el `DELETE from public.place_reports where description like 'PRUEBA-OPINIONES %'` literal, contar antes, borrar, y verificar contra la línea base (`place_reports` n = 2, la de San Felipa intacta con `published_at` nulo). Registrar todo en `db/checks/2026-09-24-opinions-live-run.md`.

- [ ] **Step 7: Publicar el comentario de San Felipa (Santiago ya lo pidió; muestra el comando literal antes)** — `python -m scripts.moderate_opinions` para releerlo, y después `python -m scripts.moderate_opinions --approve <id de San Felipa> --apply`. Verificar en el sitio que aparece como **Anónimo**, "sobre San Felipa - Sin gluten · Gualeguaychú".

- [ ] **Step 8: Cierre de documentación** — ADR-008 → `Aceptado` con su sección **Verificación**; Fase 26 de `CLAUDE.md` → ✅ con los hallazgos reales; commit y push (PIDE OK).
