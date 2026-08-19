# Plan — Reportes comunitarios (recomendar / reportar un lugar ya publicado)

**Estado:** Propuesto
**ADR relacionado:** `docs/architecture/ADR-004-community-reports-evidence-not-direct-action.md` (Propuesto)

## Objetivo
Cerrar el gap de que un lugar `approved` queda "congelado" tras la
aprobación del Validator, dándole a la comunidad una forma de reportar
que un lugar ya no cumple (o de reforzar que sí cumple), sin que ese
reporte tenga autoridad directa sobre `places.status` — mismo principio
que el Outreach Agent (ADR-002), aplicado ahora a evidencia que viene de
la comunidad en vez de del comercio.

## Contexto
El formulario "Suggest a Place" (`js/suggest.js` → tabla `suggestions`)
ya cubre lugares **nuevos**, no publicados. No existe ningún canal para
que alguien reporte sobre un lugar **ya aprobado**: ni una mala
experiencia reciente (protocolo abandonado, cambio de dueño) ni una
confirmación positiva adicional. ADR-004 decide que ese reporte se trata
como evidencia nueva reinyectada al mismo rubric del Validator — nunca
como una acción directa sobre `places`.

## Mecanismo actual reusado (investigación previa)

El patrón de Etapa 2 del Outreach Agent (ADR-002/ADR-003) ya resuelve
"un evento externo dispara una re-evaluación del Validator sin correr
en el cron mensual", y este plan lo reusa casi sin cambios:

```
Resend (email.received)                    Database Webhook (INSERT)
        │                                            │
        ▼                                            ▼
supabase/functions/outreach-reply/         supabase/functions/place-report-created/
  (Deno/TS, verifica firma Svix HMAC,        (Deno/TS, verifica un header
   persiste la respuesta, marca               secreto simple, no hay Svix
   outreach_status='replied')                 porque Database Webhooks no
        │                                      firman HMAC nativamente)
        ▼                                            ▼
repository_dispatch                        repository_dispatch
  event_type: outreach_reply_received         event_type: place_report_received
  client_payload: {place_id}                  client_payload: {place_id, report_id}
        │                                            │
        ▼                                            ▼
.github/workflows/outreach-reply.yml       .github/workflows/place-report-review.yml
  → python -m agents.outreach_reply_handler  → python -m agents.review_handler
      --place-id <id>                            --place-id <id> --report-id <id>
        │                                            │
        ▼                                            ▼
agents/outreach_reply_handler.py           agents/review_handler.py
  RUBRIC + ValidatorAgent._normalize()       RUBRIC + ValidatorAgent._normalize()
  (import sin duplicar el rubric)            (mismo import, cero duplicación)
```

Piezas concretas que se reusan **sin modificar**:
- `agents/validator_agent.py`: `RUBRIC` (el prompt del Validator) y
  `ValidatorAgent._normalize()` / `._decide_status()` — el mismo gate
  0.85/0.7/0.5 que usa el pipeline diario y Etapa 2 de outreach.
- `ValidatorAgent._build_user_prompt(place, reviews)` — el bloque base
  de datos del lugar; `review_handler.py` le agrega el reporte de la
  comunidad como contexto extra, igual que `outreach_reply_handler.py`
  agrega la respuesta del comercio (`_build_reply_prompt`).
- El patrón de `agent_log` + `BaseAgent.log()` de `agents/base.py`.
- El patrón de dos secret stores separados (secrets de la Edge Function
  vía `supabase secrets set`, nunca en `.env` / GitHub Actions) — este
  plan reusa el `GITHUB_DISPATCH_TOKEN` que ya existe (mismo PAT
  fine-grained scoped a este repo, ya usado por `outreach-reply/`), y
  agrega un secreto nuevo propio (`PLACE_REPORTS_WEBHOOK_SECRET`, ver
  más abajo por qué es más simple que la firma Svix de outreach).

**Una diferencia clave del disparador (no un webhook de Resend):**
`outreach-reply` recibe el webhook nativo `email.received` de Resend,
firmado con Svix HMAC. Acá no hay Resend — el disparador es un
**Supabase Database Webhook** nativo (`INSERT` sobre `place_reports`),
que llama a una Edge Function con el payload estándar de Supabase
(`{type, table, record, schema, old_record}`) y permite agregar
**headers HTTP fijos** configurados en el dashboard, pero **no firma
HMAC** como Svix. Por eso `place-report-created/index.ts` verifica un
header secreto simple (`x-webhook-secret` == `PLACE_REPORTS_WEBHOOK_SECRET`,
comparación en tiempo constante) en vez de portar la verificación Svix —
es un modelo de seguridad más simple porque Supabase no ofrece nada más
fuerte para Database Webhooks nativos, y el payload solo dispara una
*re-evaluación* (el Validator sigue siendo el único que decide), nunca
una escritura directa.

**Otra diferencia — mapeo de status, no hay caso especial ADR-002:**
`outreach_reply_handler.py` nunca deja que una respuesta del comercio
llegue directo a `'approved'` (mapea a `'outreach_confirmed'`) porque el
lugar viene de `needs_review` — nunca pasó el gate de aprobación. Acá el
lugar **ya es `approved`** (ya pasó el gate una vez); ADR-004 dice
explícitamente que el Validator puede "confirmar el estado actual,
bajarlo a `needs_review`, o descartarlo" — o sea, el output de
`_decide_status` se usa **tal cual**, sin remapeo: si el Validator
sigue diciendo `approved`, el lugar se confirma como `approved` (es el
mismo gate reconsiderando con evidencia nueva, no una fuente nueva
saltándose el gate).

## Diseño

### 1. Schema (`db/schema.sql`)

**Tabla nueva `place_reports`:**

```sql
create table if not exists public.place_reports (
  id               uuid primary key default gen_random_uuid(),
  -- Nullable: un reporte sin match en el autocomplete queda con
  -- place_name_text y place_id null (ver Frontend abajo).
  place_id         uuid references public.places(id) on delete set null,
  place_name_text  text
                     check (place_name_text is null or char_length(place_name_text) between 2 and 120),
  report_type      text not null
                     check (report_type in ('positive', 'negative')),
  description      text not null
                     check (char_length(description) between 5 and 2000),
  -- Estado de procesamiento (no el status del lugar):
  --   new        -> recién insertado; también el estado TERMINAL para
  --                 positive, para negative sobre un lugar no-approved,
  --                 y para reportes sin match (ADR-004 puntos 2-4) —
  --                 quedan para revisión manual, nada los mueve de acá.
  --   dispatched -> negative + place approved: la Edge Function ya
  --                 disparó el repository_dispatch (best-effort — sin
  --                 reintento automático de Supabase, ver "Barrido
  --                 mensual" abajo para lo que cubre esta laguna).
  --   processing -> ReviewHandler.handle() reclamó este reporte de forma
  --                 atómica (CAS: new/dispatched -> processing) y está
  --                 evaluándolo ahora mismo. Este estado es lo que hace
  --                 que el webhook en tiempo real y el barrido mensual
  --                 nunca procesen el mismo reporte dos veces.
  --   processed  -> review_handler.py terminó de re-evaluar y persistió
  --                 un veredicto del Validator.
  --   skipped    -> el dispatch llegó pero el lugar ya no era accionable
  --                 (otro reporte lo cambió de estado antes de correr).
  --   error      -> falló la re-evaluación (LLM o persistencia).
  status           text not null default 'new'
                     check (status in
                       ('new', 'dispatched', 'processing', 'processed', 'skipped', 'error')),
  created_at       timestamptz not null default now(),
  constraint place_reports_has_target
    check (place_id is not null or place_name_text is not null)
);

create index if not exists place_reports_place_id_idx on public.place_reports (place_id);
create index if not exists place_reports_status_idx   on public.place_reports (status);
```

**Columna nueva en `suggestions`** (pedida explícitamente para este
plan, no viene de ADR-004): el fallback "sin match" del segundo
formulario (ver Frontend) reusa la tabla `suggestions` existente en vez
de duplicar el flujo de geocode+dedup+promoción — así que `suggestions`
necesita distinguir de dónde vino cada fila.

```sql
alter table public.suggestions add column if not exists origin text
  not null default 'community'
  check (origin in ('community', 'business'));
```

**Decisión confirmada:** `'community'` no queda como default implícito
sin más — el único formulario que escribe en `suggestions` hoy
(`js/suggest.js`, Form A, "Sugerir lugar") manda `origin: 'community'`
de forma explícita en cada submit (ver el ajuste puntual más abajo).
`'business'` queda disponible en el `CHECK` de la columna para el día
que se decida diferenciar comercios que se auto-sugieren (p. ej. desde
una respuesta de outreach), pero **sin ningún flujo nuevo** para eso
ahora — ni tabla, ni agente, ni formulario. El fallback sin match del
formulario nuevo (§2 abajo) también manda `origin: 'community'`
explícito, mismo criterio.

Defensa adicional en RLS (mismo patrón de "estado forzado" que ya usa
la política de `suggestions` para `status`/`promoted_place_id`): la
política de INSERT existente gana `and origin = 'community'` en su
`WITH CHECK`, así que hoy ningún insert público —ni siquiera uno mal
armado— puede colar `'business'` mientras no exista el flujo que lo
justifique:

```sql
drop policy if exists "public can submit suggestions" on public.suggestions;
create policy "public can submit suggestions"
  on public.suggestions
  for insert
  to anon, authenticated
  with check (
    status = 'new'
    and promoted_place_id is null
    and address is not null
    and char_length(address) between 2 and 200
    and origin = 'community'
  );
```

**Ajuste puntual a `js/suggest.js`** (Form A existente, no forma parte
del formulario nuevo de §2-§3): el objeto `data` que arma antes del
`fetch(... "/suggestions", ...)` gana un campo fijo:

```diff
     var data = {
       name: (nameEl.value || "").trim(),
       address: (addressEl.value || "").trim(),
       city: (cityEl.value || "").trim(),
       country: countryEl.value || "",
       category: categoryEl.value || null,
       evidence_url: (urlEl.value || "").trim() || null,
-      notes: (notesEl.value || "").trim() || null
+      notes: (notesEl.value || "").trim() || null,
+      origin: "community"
     };
```

Sin variable, sin config — es un literal fijo, igual criterio que
`OPT_OUT_FOOTER` en el Outreach Agent: el único emisor posible hoy es
la comunidad, así que no hay nada que parametrizar todavía.

**Widening de `agent_log.agent`** (mismo patrón `DO $$ ... $$` que cada
agente nuevo anterior):

```sql
do $$
begin
  alter table public.agent_log drop constraint if exists agent_log_agent_check;
  alter table public.agent_log
    add constraint agent_log_agent_check
    check (agent in
      ('search', 'validator', 'updater', 'social', 'web', 'pipeline', 'suggestion',
       'outreach', 'outreach_reply', 'review_handler'));
end $$;
```

**RLS** (mismo patrón que `suggestions`: anon solo INSERT, nunca lee de
vuelta):

```sql
alter table public.place_reports enable row level security;
revoke all on public.place_reports from anon, authenticated;
grant insert on public.place_reports to anon, authenticated;

drop policy if exists "public can submit place reports" on public.place_reports;
create policy "public can submit place reports"
  on public.place_reports
  for insert
  to anon, authenticated
  with check (
    status = 'new'
    and (place_id is not null or place_name_text is not null)
    and char_length(description) between 5 and 2000
  );
```

`place_reports` no necesita política de SELECT para `anon` — igual que
`agent_log`/`outreach_messages`, es server-only para lectura
(`service_role` la bypasea).

### 2. Frontend (`index.html` + `js/report.js` nuevo)

Segundo formulario dentro de la sección `#suggest` existente (al lado
del form de "Suggest a Place", como pide el mensaje — mismos estilos
`.suggest-form`, propia intro/copy), con:

- Selector **Recomendar (positive) / Reportar un problema (negative)**
  — dos botones tipo toggle, no un `<select>`, para que la elección sea
  visualmente clara antes de escribir nada.
- Input de búsqueda con **autocomplete contra `places`**: cada
  keystroke (debounced ~300ms) dispara
  `GET {SUPABASE_URL}/rest/v1/places?select=id,name,city&status=eq.approved&name=ilike.*{term}*&limit=8`
  con la anon key — la RLS existente (`public read approved places`) ya
  restringe esto a lugares publicados, sin política nueva. El usuario
  selecciona una fila de la lista → se guarda `place_id` (oculto) +
  se muestra el nombre elegido, campo de texto se bloquea.
- **Fallback sin match:** si el usuario escribe y no selecciona ninguna
  sugerencia (o hace click en "no encuentro el lugar"), el formulario
  cambia a modo "sugerir como nuevo lugar" — reutiliza los mismos
  campos del form de `suggestions` (address, city, country) con un
  texto explicando "no encontramos ese lugar en el mapa; contanos más
  para que lo revisemos", y al enviar hace `POST .../suggestions` con
  `origin: 'community'` (el mismo endpoint que ya usa
  `js/suggest.js`) — **no** escribe en `place_reports` en este caso,
  porque sin `place_id` no hay nada que re-evaluar automáticamente.
- Textarea de `description` (requerido, refleja el `CHECK` 5-2000
  caracteres del lado del servidor con validación de largo en el
  cliente).
- Mismas defensas anti-spam que `js/suggest.js` (honeypot,
  `MIN_FILL_MS`, cooldown en `localStorage`) — mismo nivel de esfuerzo,
  sin reinventar.
- Al enviar con `place_id` set: `POST {SUPABASE_URL}/rest/v1/place_reports`
  con `{place_id, report_type, description}` (anon key, `Prefer:
  return=minimal`, igual que `suggest.js`).

### 3. Backend — disparo de re-evaluación

**Supabase Database Webhook** (configurado en el dashboard, no en
`db/schema.sql` — igual que el webhook de Resend no está en SQL):
`INSERT` sobre `public.place_reports` → llama a
`place-report-created` con un header fijo `x-webhook-secret`.

**`supabase/functions/place-report-created/index.ts`** (nuevo,
Deno/TS, mecánica de webhook únicamente — nunca llama al LLM, mismo
principio que `outreach-reply/index.ts`):

1. Verifica `x-webhook-secret` contra `PLACE_REPORTS_WEBHOOK_SECRET`
   (comparación en tiempo constante, reusando la misma
   `timingSafeEqual` que ya existe en `outreach-reply/index.ts` —
   duplicada acá porque cada función Edge es su propio deploy aislado,
   sin módulo compartido hoy en el repo). Si no matchea → 401, sin
   escrituras.
2. Parsea el payload nativo de Database Webhooks:
   `{type: "INSERT", table: "place_reports", record: {...}}`.
3. Función pura exportada y testeable (mismo patrón que
   `extractPlaceId`):
   ```ts
   export function isAutoRevaluationCandidate(
     record: { report_type?: string; place_id?: string | null },
   ): boolean {
     return record.report_type === "negative" && !!record.place_id;
   }
   ```
   Si `false` → `200 "Not actionable"`, sin tocar `place_reports.status`
   (queda `'new'`, ADR-004 puntos 3 y 4).
4. Si `true`: lee `places.status` por `record.place_id` (service_role).
   Si no es `'approved'` → `200 "Place not approved"`, sin tocar
   `place_reports.status` (ADR-004 punto 2 es explícito: solo lugares
   `approved`).
5. `update place_reports set status = 'dispatched' where id = record.id`.
6. `repository_dispatch` a `santisanchez4/CeliacMap`
   (`event_type: "place_report_received"`,
   `client_payload: {place_id, report_id: record.id}`), reusando
   `GITHUB_DISPATCH_TOKEN` (secreto ya existente, mismo PAT que usa
   `outreach-reply/`).
7. `200 "OK"`. Si el paso 5 o 6 falla → `500` **solo para que quede
   registrado en el log de invocaciones del Dashboard** — a diferencia
   de `outreach-reply.ts`, acá el código de status **no dispara ningún
   reintento** (ver Fase 0, resuelta: los Database Webhooks de Supabase
   no reintentan automáticamente en no-2xx ni en timeout — a diferencia
   del comportamiento de Resend en el que se apoya Etapa 2 de outreach).
   Esto es una limitación real, no cosmética: si el paso 5 o 6 falla, el
   reporte queda `'new'` (o a medio camino) sin ningún seguimiento
   automático. Mitigación propuesta — ver la nota al final de **Fases**
   abajo, pendiente de tu decisión antes de Fase 1.

**`.github/workflows/place-report-review.yml`** (nuevo, copia casi
literal de `outreach-reply.yml`):

```yaml
name: Community report review

on:
  repository_dispatch:
    types: [place_report_received]

permissions:
  contents: read

jobs:
  revalidate:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      PYTHONPATH: ${{ github.workspace }}
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: pip
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Re-evaluate place with the community report
        run: |
          python -m agents.review_handler \
            --place-id "${{ github.event.client_payload.place_id }}" \
            --report-id "${{ github.event.client_payload.report_id }}"
```

No pide secrets nuevos en GitHub Actions — reusa los tres que
`outreach-reply.yml` ya declara.

**`agents/review_handler.py`** (nuevo):

```python
"""Community reports — automatic re-evaluation trigger (ADR-004).

Triggered by a GitHub repository_dispatch event fired from the Supabase
Edge Function (supabase/functions/place-report-created/) when a negative
community report lands on an already-approved place — never by the
monthly cron, and never for 'positive' reports (see ADR-004).

Re-evaluates a single approved place after a negative report arrives,
combining the original evidence with the report through the *same*
Validator rubric (RUBRIC, ValidatorAgent._normalize) — zero duplicated
rubric/gate logic, same reuse pattern as outreach_reply_handler.py.
Per ADR-004, the Validator's own verdict is trusted directly — approved
stays approved (confirmed), needs_review downgrades, discarded
discards — unlike outreach's ADR-002 special case, since the place
already passed this gate once and this is the same gate reconsidering
it with new evidence, not a new source trying to fast-track approval.
"""

from __future__ import annotations

import argparse
import logging

from agents.base import BaseAgent
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient
from agents.validator_agent import RUBRIC, ValidatorAgent

logger = logging.getLogger("celiacmap.agent")

# Only an approved place can be automatically re-evaluated by a report
# (ADR-004 point 2). A place already moved by an earlier report in the
# same batch (needs_review/discarded) is left alone — no re-triggering.
ACTIONABLE_STATUSES = ("approved",)


def _build_report_prompt(place: dict, reviews: list[dict], report_description: str) -> str:
    base = ValidatorAgent._build_user_prompt(place, reviews)
    return (
        f"{base}\n\n"
        "Reporte directo de la comunidad (no verificado; puede ser un caso "
        "aislado, un error, o mal intencionado — pesar con la misma cautela "
        "que cualquier fuente sin verificar, nunca como confirmación "
        "automática):\n"
        f"{report_description}"
    )


class ReviewHandler(BaseAgent):
    name = "review_handler"

    def __init__(self, db: SupabaseClient, llm: LLMClient, model: str | None = None):
        super().__init__(db)
        self.llm = llm
        self.model = model
        self.validator = ValidatorAgent(db, llm)  # reused only for ._normalize()

    def handle(self, place_id: str, report_id: str) -> dict:
        # Atomic claim (CAS: status new/dispatched -> processing). This is
        # the ONE guard that makes the real-time webhook path and the
        # monthly sweep (see .sweep() below) safe to race against each
        # other: whichever call reaches this UPDATE first wins and
        # proceeds; the other gets False back and exits immediately,
        # never calling the LLM or touching `places`.
        if not self.db.claim_place_report(report_id):
            self.log(
                "review_already_claimed",
                {"place_id": place_id, "report_id": report_id},
                status="success",
                place_id=place_id,
            )
            return {"skipped": "already claimed"}

        place = self.db.fetch_place_by_id(place_id)
        if not place:
            self.log("review_unknown_place", {"place_id": place_id}, status="error")
            return {"skipped": "place not found"}

        if place.get("status") not in ACTIONABLE_STATUSES:
            self.db.update_place_report_status(report_id, "skipped")
            self.log(
                "review_skipped_wrong_status",
                {"place_id": place_id, "report_id": report_id, "status": place.get("status")},
                status="success",
                place_id=place_id,
            )
            return {"skipped": f"status={place.get('status')}"}

        report = self.db.fetch_place_report_by_id(report_id)
        description = (report.get("description") or "").strip() if report else ""
        if not description:
            self.db.update_place_report_status(report_id, "error")
            self.log(
                "review_no_report_content",
                {"place_id": place_id, "report_id": report_id},
                status="error",
                place_id=place_id,
            )
            return {"skipped": "no report content"}

        try:
            reviews = self.db.fetch_reviews_for_place(place_id)
        except Exception:  # noqa: BLE001 - review context is best-effort
            logger.exception("fetching review context failed for %s", place_id)
            reviews = []

        prompt = _build_report_prompt(place, reviews, description)

        try:
            raw_verdict = self.llm.complete_json(RUBRIC, prompt, model=self.model)
            v = self.validator._normalize(raw_verdict, place)
        except Exception as exc:  # noqa: BLE001
            self.db.update_place_report_status(report_id, "error")
            logger.exception("report re-evaluation failed for %s", place_id)
            self.log(
                "review_evaluate_failed",
                {"place_id": place_id, "report_id": report_id, "error": str(exc)},
                status="error",
                place_id=place_id,
            )
            return {"skipped": "evaluation failed"}

        # No remapping (unlike ADR-002's outreach_confirmed): the place
        # already passed this gate once, so its own verdict is trusted as-is.
        db_status = v["status"]

        try:
            self.db.update_place_validation(
                place_id,
                status=db_status,
                confidence=v["confidence"],
                notes=v["reason"],
                category=v["category"],
                safety_level=v["safety_level"],
                flags=v["flags"],
                recommendation=v["recommendation"],
            )
            self.db.update_place_report_status(report_id, "processed")
        except Exception as exc:  # noqa: BLE001
            logger.exception("persisting report verdict failed for %s", place_id)
            self.log(
                "review_persist_failed",
                {"place_id": place_id, "report_id": report_id, "error": str(exc)},
                status="error",
                place_id=place_id,
            )
            return {"skipped": "persist failed"}

        self.log(
            "review_evaluated",
            {"place_id": place_id, "report_id": report_id, "verdict": v["verdict"], "status": db_status},
            status="success",
            place_id=place_id,
        )
        return {"place_id": place_id, "status": db_status}

    def sweep(self, limit: int = 50) -> dict:
        """Monthly safety net (8th pipeline stage): re-drive any negative
        report left stuck in 'new' or 'dispatched' because the real-time
        webhook path (Edge Function -> repository_dispatch -> this same
        handle()) never reached 'processed' — Supabase Database Webhooks
        do not auto-retry on a non-2xx response or a timeout, unlike the
        Resend webhook Etapa 2 of outreach relies on.

        Safe to call unconditionally on every monthly run, including when
        nothing is stuck (the common case): calling handle() on a report
        the real-time path already finished is a no-op, because
        claim_place_report() only succeeds from 'new'/'dispatched' — a
        'processed'/'skipped'/'error' report can't be re-claimed. Whether
        the associated place is still 'approved' is re-checked inside
        handle() itself (ACTIONABLE_STATUSES), so this sweep does not
        need its own place-status filter.
        """
        stuck = self.db.fetch_stuck_negative_reports(limit)
        processed = skipped = errors = already_claimed = 0
        for r in stuck:
            result = self.handle(r["place_id"], r["id"])
            if result.get("skipped") == "already claimed":
                # The real-time path won the race in between the sweep's
                # fetch and this call — not a sweep outcome, just a sign
                # the real-time path is working.
                already_claimed += 1
            elif "status" in result:
                processed += 1
            elif "skipped" in result:
                skipped += 1
            else:
                errors += 1

        summary = {
            "stuck_seen": len(stuck),
            "processed": processed,
            "skipped": skipped,
            "already_claimed": already_claimed,
            "errors": errors,
        }
        self.log("review_sweep_complete", summary, status="success")
        return summary


def main() -> int:
    """Run the review handler for one place (invoked by the GitHub Actions
    workflow triggered from the Supabase Edge Function)."""
    from config.settings import get_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--place-id", required=True)
    parser.add_argument("--report-id", required=True)
    args = parser.parse_args()

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key", "anthropic_api_key")
    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    llm = LLMClient(settings.anthropic_api_key, settings.validator_model)

    result = ReviewHandler(db, llm).handle(args.place_id, args.report_id)
    print("Review handled:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**`agents/clients/supabase_client.py`** gana dos métodos nuevos (mismo
estilo que `fetch_latest_received_message` / `update_place`, sin test
propio — como el resto de `SupabaseClient`, se ejercitan indirectamente
vía los tests de `review_handler.py` que mockean `db`):

```python
def fetch_place_report_by_id(self, report_id: str) -> dict | None:
    res = (
        self._db.table("place_reports")
        .select("*")
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None

def update_place_report_status(self, report_id: str, status: str) -> None:
    self._db.table("place_reports").update({"status": status}).eq("id", report_id).execute()

def claim_place_report(self, report_id: str) -> bool:
    """Atomic claim (compare-and-swap on status) — the idempotency guard
    shared by the real-time webhook path and the monthly sweep. Returns
    True only if this call transitioned the row from 'new'/'dispatched'
    to 'processing'; False means another call already claimed or
    finished it, and the caller MUST NOT proceed (no LLM call, no writes
    to `places`).
    """
    res = (
        self._db.table("place_reports")
        .update({"status": "processing"})
        .eq("id", report_id)
        .in_("status", ["new", "dispatched"])
        .execute()
    )
    return bool(res.data)

def fetch_stuck_negative_reports(self, limit: int = 50) -> list[dict]:
    """Negative reports still in 'new'/'dispatched' — candidates for the
    monthly sweep (ReviewHandler.sweep()). Whether the place is still
    'approved' is intentionally NOT filtered here: handle() re-checks it
    via ACTIONABLE_STATUSES, so filtering twice would just duplicate
    logic without changing the outcome.
    """
    res = (
        self._db.table("place_reports")
        .select("id, place_id")
        .eq("report_type", "negative")
        .in_("status", ["new", "dispatched"])
        .not_.is_("place_id", "null")
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return res.data or []
```

## Control de gasto / alcance

- Sin techo de reportes por lugar en esta versión (ADR-004 punto 5,
  trade-off aceptado explícitamente).
- **Camino rápido (tiempo real) sin presupuesto propio:** el webhook →
  Edge Function → `repository_dispatch` → `review_handler.py` corre
  fuera del pipeline mensual, como Etapa 2 de outreach — no consume
  `AGENT_DAILY_BUDGET` porque no hay forma de acotarlo por corrida (es
  un evento, no un batch).
- **Barrido mensual (`ReviewHandler.sweep()`) SÍ es una etapa nueva de
  `scripts/run_agents.py`** (la 8va, después de Outreach) y SÍ consume
  el `AGENT_DAILY_BUDGET` compartido, acotada además por su propio techo
  — nueva setting `MAX_REVIEW_SWEEP_PER_RUN` (mismo patrón que
  `OUTREACH_MONTHLY_LIMIT` / `max_validations_per_run`), default bajo
  (p. ej. 20) porque en el caso normal esta etapa no encuentra nada que
  barrer (el camino rápido ya proceso todo) — el costo real solo
  aparece cuando el webhook en tiempo real falló.
- Un reporte `positive` o sin match cuesta cero LLM — solo un INSERT, y
  nunca entra al barrido (`fetch_stuck_negative_reports` filtra
  `report_type='negative'`).

## Fases

1. **Fase 0 — resuelta (investigación, sin tocar código todavía):**
   - **(a) Reintentos en no-2xx: NO hay.** A diferencia del webhook de
     Resend que usa Etapa 2 de outreach (que sí redelivera en
     no-2xx, y por eso `outreach-reply.ts` devuelve `500` como señal
     "reintentable"), los Database Webhooks nativos de Supabase
     **no tienen reintento automático incorporado** — confirmado vía
     la doc oficial y un discussion abierto de Supabase donde ni
     siquiera un maintainer confirma la feature ("no built-in
     configuration... users must implement custom solutions if webhook
     resilience is required"). Esto cambia el diseño: el `500` de
     `place-report-created/index.ts` deja de ser una señal de
     reintentabilidad real — ver la nota de mitigación abajo.
   - **(b) Payload shape: confirmado.**
     `{type: "INSERT", table: "place_reports", schema: "public",
     record: {...fila nueva...}, old_record: null}` — coincide
     exactamente con lo ya asumido en el diseño de §3, sin cambios
     ahí.
   - **(c) Headers custom en el Dashboard:** casi seguro que la UI de
     "Create a new Database Webhook" tiene una sección de HTTP Headers
     (estándar en el producto), pero no lo pude confirmar con las
     fuentes que rastreé esta sesión — se verifica al crear el webhook
     real en Fase 1/2. Fallback sin depender de eso: el secreto también
     puede ir como query string en la URL del webhook
     (`.../place-report-created?secret=...`), que sí es 100% seguro que
     el campo "URL" del Dashboard soporta.

   **Mitigación decidida: red de seguridad mensual.** El pipeline
   mensual existente (`scripts/run_agents.py`) suma una 8va etapa que
   barre lo que el webhook en tiempo real no haya podido terminar, y
   llama a `ReviewHandler.handle()` **directo**, sin pasar por la Edge
   Function ni el Database Webhook. Diseño completo (incluida la
   garantía de que un mismo reporte nunca se procesa dos veces si el
   webhook en tiempo real y el barrido mensual coinciden en el tiempo):
   ver **"Barrido mensual + idempotencia"** dentro de la sección
   Backend (§3) abajo.
2. **Fase 1 — Schema:** `place_reports`, `suggestions.origin`, RLS
   (incluido el `WITH CHECK` reforzado de `suggestions`), widening de
   `agent_log.agent`, y el ajuste puntual a `js/suggest.js` para mandar
   `origin: 'community'` — va junto con la columna, no con el
   formulario nuevo de Fase 3. Aplicar el SQL en el SQL Editor de
   Supabase (mismo flujo manual que cada migración anterior de este
   proyecto).
3. **Fase 2 — Backend (TDD):** `agents/review_handler.py` (incluido
   `.claim_place_report()`/`.sweep()`) +
   `supabase/functions/place-report-created/` +
   `.github/workflows/place-report-review.yml` + la 8va etapa
   (`ReviewHandler.sweep()`) wireada en `scripts/run_agents.py` bajo el
   `AGENT_DAILY_BUDGET` compartido, con `MAX_REVIEW_SWEEP_PER_RUN`. Ver
   **Tests a cubrir** abajo. Verificar `deno check` sobre la Edge
   Function nueva antes de deployarla (mismo paso que atrapó bugs reales
   en `outreach-reply/`).
4. **Fase 3 — Frontend:** segundo formulario + autocomplete + fallback
   a `suggestions`. Verificación manual en Chrome (como
   `Suggest-a-Place`): un reporte `negative` sobre un lugar `approved`
   real dispara el ciclo completo end-to-end.
5. **Fase 4 — Aceptar ADR-004:** una vez verificado en vivo, cambiar su
   `Estado` a `Aceptado` y agregar el pointer correspondiente en el
   Decisions Log de `CLAUDE.md` (mismo patrón que ADR-002/ADR-003).

## Tests a cubrir (mismo nivel de TDD que `outreach_reply_handler.py`)

**`tests/test_review_handler.py`** (Python, offline, `db`/`llm`
mockeados con `MagicMock`, `ValidatorAgent._normalize`/`._decide_status`
**reales** — no mockeados, para probar que el reuso del gate 0.85/0.7/0.5
sostiene de verdad, mismo criterio que `test_outreach_reply_handler.py`.
El fixture `make_handler()` deja `db.claim_place_report.return_value =
True` por default, para que los tests existentes de `handle()` no
tengan que preocuparse por el claim salvo los que lo prueban
explícitamente):

- `test_build_report_prompt_includes_report_description` — el texto del
  reporte aparece en el prompt final.
- **`test_handle_returns_early_when_claim_fails`** — `db.claim_place_report`
  devuelve `False` → `handle()` retorna `{"skipped": "already claimed"}`
  **sin** llamar `fetch_place_by_id`, `llm.complete_json`, ni ningún
  `update_place_*` — esta es la prueba central de idempotencia: sea cual
  sea la razón por la que el claim falló (webhook en tiempo real ya lo
  tomó, barrido mensual ya lo tomó, ya estaba `processed`), `handle()`
  no debe hacer ningún trabajo.
- `test_handle_skips_unknown_place` — `place_id` no existe.
- `test_handle_skips_place_not_approved` — status `pending` /
  `needs_review` / `discarded` / `outreach_confirmed` → `skipped`,
  `update_place_report_status(report_id, "skipped")` llamado.
- `test_handle_skips_when_report_not_found` — `fetch_place_report_by_id`
  devuelve `None`.
- `test_handle_skips_when_report_description_is_blank`.
- `test_approved_verdict_stays_approved` — confianza alta → `status`
  final `'approved'` (sin remapeo, a diferencia de outreach).
- `test_needs_review_verdict_downgrades_to_needs_review`.
- `test_rejected_verdict_discards`.
- `test_low_confidence_approved_falls_back_to_needs_review` — prueba el
  gate real de `_decide_status` (< 0.85 no aprueba aunque el modelo diga
  `approved`).
- `test_llm_failure_is_skipped_without_persisting` — `update_place_validation`
  nunca se llama; `update_place_report_status(report_id, "error")` sí.
- `test_persist_failure_is_skipped`.
- `test_report_status_marked_processed_on_successful_evaluation`.

**`.sweep()` — mismo archivo, mismo estilo de fixture:**

- `test_sweep_calls_handle_for_each_stuck_report` — `db.fetch_stuck_negative_reports`
  devuelve 2 filas → `handle()` se invoca una vez por cada una, con sus
  `place_id`/`id` respectivos.
- `test_sweep_counts_already_claimed_separately_from_processed` — uno de
  los reportes stuck resulta `{"skipped": "already claimed"}` (el
  webhook en tiempo real le ganó la carrera entre el fetch del barrido y
  el `handle()`) → cuenta en `already_claimed`, no en `processed` ni en
  `errors`, y el summary lo refleja.
- `test_sweep_returns_zero_counts_when_nothing_stuck` — `fetch_stuck_negative_reports`
  devuelve `[]` → `handle()` nunca se llama, summary todo en cero (el
  caso normal de cada corrida mensual).
- `test_sweep_logs_summary` — `self.log("review_sweep_complete", ...)`
  se llama con los conteos correctos.

**`supabase/functions/place-report-created/index.test.ts`** (Deno,
mismo alcance que `outreach-reply/index.test.ts`: solo la lógica pura
testeable sin red/servidor):

- `isAutoRevaluationCandidate` devuelve `true` para
  `{report_type: "negative", place_id: "<uuid>"}`.
- devuelve `false` para `report_type: "positive"` (con `place_id` set).
- devuelve `false` para `place_id: null` / `undefined`.
- devuelve `false` para `report_type` ausente o desconocido.

**Frontend:** sin test automatizado (no hay runner de JS en el
proyecto, mismo criterio que `js/suggest.js`) — verificación manual en
Chrome: autocomplete devuelve resultados reales, selección llena
`place_id` oculto, fallback sin match muestra los campos de
`suggestions` y hace el POST correcto, y un reporte `negative` real
sobre un lugar `approved` real disp
ara el ciclo completo (confirmado
en `agent_log` con `agent='review_handler'`).

## Fuera de alcance por ahora

- Cualquier acción automática sobre un reporte `positive` (ADR-004
  punto 3) — queda solo como evidencia visible para revisión manual.
- Vincular manualmente un reporte sin match (`place_name_text`) a un
  `place_id` existente, o derivarlo al flujo de `suggestions` — ADR-004
  punto 4 lo deja para un humano, no automatizado en esta versión.
- Techo de volumen / rate limit por lugar (ADR-004 punto 5, riesgo
  aceptado a monitorear).
- El flujo `origin='business'` en `suggestions` — columna reservada,
  sin ningún form ni agente que la escriba todavía.
- Notificar al autor del reporte del resultado de la re-evaluación (no
  hay autenticación, no hay a quién notificar — Fase 1 de este
  proyecto sigue sin auth de usuarios).

## TODO — deuda técnica detectada al implementar

- **`deno.lock` inconsistente entre las dos Edge Functions — investigado
  y resuelto (2026-08-19).** Al correr `deno check`/`deno test` sobre
  `place-report-created/` por primera vez (con `--node-modules-dir=auto`,
  necesario para resolver sus imports `npm:`) Deno generó un `deno.lock`
  en la raíz del repo — el primero que existe en el proyecto.
  `outreach-reply/` (la Edge Function anterior) nunca tuvo uno propio: se
  verificó en su momento sin fijar versiones. El lock en la raíz cubre
  las dependencias `npm:` de **ambas** funciones (Deno resuelve un único
  lockfile por raíz de proyecto, no por función), así que
  `outreach-reply/` quedó cubierta de hecho — pero no fue una decisión
  deliberada tomada para esa función en su momento, solo un efecto
  colateral de agregar la segunda.

  **Diagnóstico (sesión 2026-08-19, sin tocar código hasta confirmar):**

  1. **`deno check`/`deno test` de `outreach-reply/` contra el lockfile
     actual: limpio, 6/6 tests pasan** (requieren `--allow-env`, un
     permiso de sandboxing de Deno para que el SDK de Resend lea
     `RESEND_BASE_URL` — no relacionado al lockfile). Coincide
     exactamente con lo ya documentado en CLAUDE.md antes de que
     existiera este lock ("deno test passes 6/6"). Cero regresión
     funcional detectable.
  2. **Historial de deploys reales** (`supabase functions list`, CLI ya
     autenticado): `outreach-reply` está en la versión 7, con su último
     deploy real el **2026-08-04 01:06 UTC** — **4 días antes** de que
     existiera el `deno.lock` (creado 2026-08-08). Es decir, la versión
     que corre hoy en producción se deployó sin ningún lock, resolviendo
     lo que Deno considerara "latest" en ese momento. `place-report-created`
     (versión 3) se deployó el 2026-08-18, ya con el lock presente.
  3. **Cruce con el historial de versiones en el registry de npm:**
     - `resend`: el lock fija `4.8.0`, que es la **única versión 4.x que
       existió jamás** (publicada 2025-08-04; el paquete saltó a 5.x/6.x
       después). No hay ningún otro valor posible al que
       `npm:resend@4` pudiera resolver, ni en agosto de 2026 ni ahora —
       cero riesgo de drift en esta dependencia, por diseño del propio
       rango semver.
     - `@supabase/supabase-js`: el lock fija `2.112.0`. Hubo movimiento
       real de versiones en la ventana relevante — `2.112.0` se publicó
       2026-08-03T07:34 UTC (horas antes del deploy de `outreach-reply`
       del 08-04), pero luego salieron `2.112.1` (08-05T10:45) y
       `2.112.2` (08-06T13:36), **antes** de que se generara el lockfile
       (08-08). Si el lockfile hubiera resuelto "latest" en frío el
       08-08, se esperaría `2.112.2`; en cambio fijó `2.112.0` — la
       versión que ya estaba resuelta/cacheada localmente desde que se
       trabajó en `outreach-reply` días antes. La explicación más
       plausible es que la generación del lock reutilizó la resolución
       ya cacheada localmente (npm/Deno cache) en lugar de resolver
       "latest" en frío — lo que significa que el lock terminó fijando,
       por las fechas involucradas, la **misma** versión que ya estaba
       viva en producción, no una más nueva y no probada.

  **Conclusión: no hay drift real detectado.** El lockfile compartido
  cayó en las mismas versiones que `outreach-reply/` ya tenía en
  producción — exacto en `resend` por ser determinístico (una sola
  versión 4.x posible), y con evidencia fuerte de ser exacto también en
  `supabase-js` por la lógica de caché de resolución. Los tests offline
  y el type-check lo confirman de forma directa e independiente de la
  teoría de versiones.

  **Decisión: se mantiene un único `deno.lock` en la raíz para todas las
  Edge Functions del proyecto** — no se separa por función. Razones:
  Deno resuelve un lock por raíz de proyecto, no por archivo/función,
  así que forzar lockfiles separados requeriría pasar `--lock <path>` en
  cada invocación local y en cada workflow, agregando complejidad
  operativa permanente para un problema que hoy no existe: ambas
  funciones comparten `@supabase/supabase-js@2` sin ningún conflicto de
  versión, y `resend` solo lo usa `outreach-reply/` y es de resolución
  única. Compartir el lock es, de hecho, una garantía de consistencia
  (ambas funciones corren contra el mismo SDK ya probado), no un riesgo.
  El formato v5 del lockfile además ya soporta múltiples versiones
  resueltas del mismo paquete npm bajo especificadores distintos (p. ej.
  `@2` y un futuro `@3` convivirían sin problema), así que un conflicto
  real de versiones en el futuro tampoco forzaría la separación — se
  resolvería dentro del mismo lock. Registrada también en el Decisions
  Log de `CLAUDE.md`.
