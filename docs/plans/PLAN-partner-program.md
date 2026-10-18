# Plan: "CeliacMap Aliado" (Plan Fundador) dentro de #aliados, con Mercado Pago Uruguay, primero en staging

**Estado:** Fase 0 cerrada (PR #27). Fase 1 en curso desde 2026-10-14: staging y base de datos (runbook `docs/runbooks/staging.md`); Mercado Pago espera el token de prueba. Decisión: [ADR-011](../architecture/ADR-011-partner-program-payments.md).
Borradores legales: `docs/legal/condiciones-aliados.md`, `docs/legal/politica-de-privacidad-v1.2-borrador.md` y
`docs/legal/terminos-de-uso-v1.2-borrador.md`. Son archivos aparte porque `tests/frontend_legal.test.js` exige que los `.md`
publicados coincidan con los `.html` y no digan "BORRADOR". En la Fase 3 reemplazan a los publicados.

## Decisiones del responsable (2026-10-14)

- **Opción A** (mapa neutral). Elegibilidad como se propone abajo.
- **Requisito de Fase 3:** reemplazar el ejemplo de Bienestar en `supabase/functions/chat/prompts.ts` (el chat no puede
  nombrar aliados), con la batería de jailbreak y el A/B real que exige el proyecto, re-sync de copias y registro.
- **`ref_code`:** si choca con uno existente (violación del unique de `ref_code`), el formulario genera otro y reintenta;
  "Ya tenemos tu solicitud" es solo para el duplicado email + comercio.
- Ahora solo **Fase 0** (documentos), rama y PR propios.
- **Precio (2026-10-15):** $U 790 por mes, en UYU, porque Mercado Pago rechazó USD en Uruguay (HTTP 400 `Cannot operate
  with currency id USD in MLU`). Plan Fundador: quien se sume en esta etapa mantiene el precio 12 meses. Un ajuste se avisa
  con 30 días y el aliado puede cancelar. Si el precio incluye IVA: pendiente, Fase 3 (contador).
- **Condiciones (al aprobar los textos):** al cancelar, la tarjeta sigue visible hasta el final del período ya pagado. Con un
  impago se oculta mientras el pago no esté al día y vuelve si se regulariza; a los 30 días sin pago el patrocinio termina.
  Si CeliacMap termina el acuerdo sin incumplimiento del aliado, devuelve la parte proporcional de los días no usados; si es
  por incumplir el punto 9 de las condiciones, no hay devolución. La retención fiscal queda "a confirmar con contador; en
  Uruguay suele ser de 5 años". Moneda, facturación (DGI/BPS) y la base legal de la retención fiscal quedan pendientes de la
  Fase 3.

## Contexto

Hoy #aliados (ADR-009) es contenido estático: un aliado gratis (Bienestar), la frase fija de independencia y un `mailto:`.
La idea es convertirlo en un programa pago mensual sin mezclar el pago con la seguridad. Contratar y publicar son pasos
separados: Mercado Pago (MP) cobra, CeliacMap comprueba el pago y el admin aprueba. Todo se construye y se prueba en
staging; en producción queda apagado detrás de un interruptor hasta tu «dale».

**Conflictos con las reglas actuales (los señalo, no los asumo):**
1. ADR-009 dice "sin cambios de base de datos" y "solo frontend". Las tablas nuevas no tocan `places`, pero contradicen el
   texto. Hace falta un **ADR-011** que reemplace los puntos 1 y 4 de ADR-009 (formulario, tablas propias, logos en
   Storage) y mantenga el punto 5 (nada de evaluación) sin cambios.
2. `tests/frontend_partners.test.js` fija la estructura actual: Bienestar como único destino de los enlaces, una sola `<p>`
   en la invitación y el logo local de menos de 40 KB. Cambia, pero las invariantes de independencia se mantienen y se
   agregan nuevas.
3. **Riesgo operativo serio:** el CLI de Supabase está *linkeado a producción* y `db query --linked` escribe en prod. Para
   staging nunca hay que hacer `supabase link`: siempre `--project-ref <staging>` explícito, o un worktree aparte con
   su propio link. `seed_staging.py` se niega a correr si la URL de destino es la de producción.
4. **Recomiendo revisar la elegibilidad antes de cobrar**, no después. El link de pago se manda solo a solicitudes que
   pasaron tu revisión. Así nunca hay que devolver plata a un comercio que no califica y no hay un endpoint público que
   cree cobros. El pedido decía "paga y después apruebo"; la publicación igual queda en un segundo paso, después del pago.

## 1. Estado actual de #aliados

- `index.html:842-870`: `section#aliados.section-alt`, la última de `<main>`. Tiene `.section-head` con el eyebrow, el
  título `#aliados-title` y `.partner-disclaimer`, que es la frase fija. Debajo van `article.partner-card` (con el logo
  `assets/images/bienestar-gluten-free.webp` de 192×192, lazy, y la etiqueta "Aliado"), el nombre, el texto y los enlaces
  IG/WA con `rel="sponsored noopener" target="_blank"`, y por último `.partner-invite` con el `mailto:` precargado.
  El header (6.º ítem) y el footer enlazan a la sección.
- i18n: el español está en el markup y el inglés en `js/main.js:253-259` (`partners.*`, más `data-i18n-href` para el mailto).
  `main.js:317` emite `celiacmap:lang` cuando cambia el idioma.
- Mapa y ficha: `js/map.js` muestra solo `approved`, y `safetyGroup()` es la única regla de etiqueta (100% / opciones).
  No existe ningún destaque, boost ni columna `sponsored`.
- **Confirmado:** no hay cuentas, autenticación ni panel de comercios. La administración se hace por scripts con
  `service_role` (`scripts/review_queue.py`, `moderate_opinions.py`) y por el email diario (`admin_digest.py`).
- Legales: términos §5 (los aliados no influyen; "un negocio no entra al mapa por ser aliado"); privacidad §3.8 (Cloudflare
  cuenta solo páginas vistas, sin eventos), §7 (proveedores; "los aliados no reciben ningún dato") y §6 (retención).

## 2. Componentes reutilizables

| Necesidad | Se reutiliza |
|---|---|
| Formulario anónimo | `js/suggest.js`: honeypot, `MIN_FILL_MS` 3 s, cooldown en `localStorage`, POST REST con la anon key y `return=minimal`, mensajes ES/EN |
| Tabla anon INSERT-only | `db/schema.sql:792-793` + la policy de `suggestions` (`:851-862`): `revoke all` → `grant insert`, `WITH CHECK` que fuerza el estado inicial y CHECKs de largo |
| Lectura pública acotada | El patrón de `community_opinions` (`revoke all` en la vista, grant mínimo, el `WHERE` como barrera) + el grant por columna de `places` |
| Webhook (Fase 2) | `supabase/functions/place-report-created/index.ts`: `timingSafeEqual`, 401/200/500 documentados, `import.meta.main` para testear; HMAC manual al estilo de `outreach-reply/index.ts` (Svix) |
| Admin CLI | La forma de `scripts/review_queue.py`: listar en solo lectura y escribir solo con `--apply` |
| Resumen diario | `scripts/admin_digest.py` `build_digest()`: sumar una sección de "Aliados" |
| Retención | `scripts/purge_chat_logs.py` `db.purge_rows(...)` + `chat-log-purge.yml` |
| Borrado a pedido | `scripts/delete_personal_data.py` (sumar las tablas nuevas) |
| Copia web→APK | `apps/mobile/scripts/web-bundle.mjs` / `sync-web.mjs` (se suma la opción de entorno) |
| Shell PWA | `service-worker.js` `SHELL` (agregar `js/partners.js`; lo exige `frontend_pwa.test.js`) |

## 3. UX/UI de la tarjeta "Plan Fundador"

**Lugar:** dentro de #aliados, después de las tarjetas de aliados y antes de `.partner-invite`. La frase de independencia
sigue siendo la bajada única, arriba de todo. La tarjeta del plan **no** lleva la etiqueta "Aliado" (no es un aliado,
es la oferta).

**Estructura** (`article.partner-plan`, con `aria-labelledby`):
- Un chip "Plan Fundador", un `h3` "CeliacMap Aliado" en Playfair y el subtítulo en DM Sans.
- El precio grande en Playfair: "$U 790" + "/ mes" en gris, y debajo "Pago mensual recurrente · Cancelás cuando quieras ·
  Sin permanencia".
- Una lista de beneficios con íconos SVG inline (`aria-hidden`, sin librerías): perfil destacado en Aliados; logo,
  imágenes y datos comerciales; enlace directo a WhatsApp, redes o web; difusión en publicaciones colectivas de aliados.
  "Estadísticas" no aparece.
- Un aviso dentro de un recuadro de borde verde suave: "Ser aliado es publicidad. No significa que CeliacMap certifique la
  seguridad alimentaria del comercio ni cambia cómo aparece en el mapa."
- El botón "Quiero ser aliado", que despliega el formulario en la misma tarjeta (sin modal, `aria-expanded` +
  `aria-controls`), y "Preguntas frecuentes" como `<details>` nativos (4 o 5: qué incluye, cómo se paga, cómo cancelo,
  si aparezco más arriba en el mapa (no), quién puede ser aliado).
- Mobile-first, en una columna. En ≥768 px, el precio y los beneficios van en dos columnas. Colores de los tokens
  existentes (`#1a3a2a`, `#2d6a4f`, `#b7e4c7`, fondo `#fdfaf5`, borde `#e7ded0`). Foco visible y contraste AA.

**Formulario** (dentro de la tarjeta): el nombre del comercio, la ciudad y el país (UY/AR), la persona responsable, el email
(obligatorio), el teléfono/WhatsApp (opcional), el link de la web o las redes, una descripción corta (≤ 300) y "¿Ya está en el
mapa de CeliacMap?" (sí/no/no sé). **Fase 3 (2026-10-17):** en staging la casilla enlaza a `privacidad.html` y el
resumen de las condiciones va en un `<details>` dentro del formulario, con `consent_version`
`condiciones-aliados-1.0-borrador`; antes de encender el interruptor en producción la casilla tiene que enlazar a las
condiciones publicadas y a la privacidad v1.2, con una versión final (lo exige un test de `frontend_partners.test.js`).
Antes de enviar, se muestran de nuevo el precio y las condiciones y una casilla
obligatoria de aceptación (que enlaza a la política y a las condiciones para aliados). Tiene honeypot, tiempo mínimo y
cooldown. Si el INSERT choca con el unique de `ref_code`, genera otro código y reintenta (hasta 3 veces), sin mostrar
nada. Solo el choque con el índice email + comercio muestra "Ya tenemos una solicitud tuya". Al enviar se ve: "Recibimos tu solicitud. Tu código es **CM-7F3K2Q**. Te escribimos en 5 días hábiles; si
califica, te mandamos el link de pago." No hay checkout en la página.

**Una sola fuente de configuración:** `js/partners.js` lleva `PROGRAM = { price, currency, benefits[], faq[], textos ES/EN }`
y un solo render. El link de pago de Mercado Pago **no** va en el frontend (con revisión previa se manda por email). El
interruptor es `PARTNER_PROGRAM: false` en `js/config.js`. Con el interruptor apagado, el markup de producción tiene solo
un punto de montaje vacío `<div id="partner-program" hidden>`: no se renderiza nada ni se carga contenido del plan.

## 4. Arquitectura

**Frontend**
- `js/partners.js`, nuevo: renderiza la tarjeta y el formulario si `CELIACMAP_CONFIG.PARTNER_PROGRAM === true`, vuelve a
  renderizar con `celiacmap:lang` y renderiza los aliados publicados (Fase 2, desde la vista; ver más abajo).
- Para Bienestar, en Fase 1, la tarjeta estática se queda como está: es un aliado sin pago, con ADR-009 vigente.
- No hay SDK de MP ni scripts de terceros: el pago se hace con un link externo que llega por email.

**Datos** (migración `db/migrations/AAAA-MM-DD-partner-program.sql` + `db/schema.sql`):

`partner_applications`, la solicitud y el estado en una sola fila:
- `id uuid`, `ref_code text unique` (lo genera el navegador con `crypto.getRandomValues`, formato `CM-[A-Z0-9]{6}`,
  con CHECK por regex; anon no tiene SELECT y no podría leer un código generado por la base), `business_name`, `city`,
  `country`, `contact_name`, `contact_email`, `contact_phone`, `links`, `description`, `on_map_claim`, `consent_version`.
- `place_id uuid null references places` (solo lo completa el admin y es solo un vínculo informativo: **nunca** se
  escribe en `places`).
- `payment_status` (`pending|active|past_due|cancelled`, default `pending`), `publication_status`
  (`requested|eligible|approved|suspended|ended|rejected`, default `requested`).
- `mp_preapproval_id text unique null`, `payer_email`, `paid_through date`, `approved_at`, `admin_notes`, `created_at`, `updated_at`.
- Datos públicos del aliado, que el admin completa al aprobar: `public_name`, `public_text_es/en`, `logo_path`,
  `public_links jsonb`.
- RLS. `revoke all` → `grant insert` a anon. La policy `WITH CHECK` fuerza `payment_status='pending'`,
  `publication_status='requested'`, `place_id is null`, `mp_preapproval_id is null` y los públicos en null. Tiene CHECKs
  de largo en todo.
- Duplicados: un índice único parcial en `(lower(contact_email), lower(business_name)) where publication_status in
  ('requested','eligible','approved')`. No lo usa ningún `ON CONFLICT`, así que no choca con la regla de restricciones
  completas. Un 409 se muestra como "Ya tenemos una solicitud tuya".

`partners_public` es una vista con el owner como barrera:
`select public_name, public_text_es, public_text_en, logo_path, public_links from partner_applications where
publication_status='approved' and (payment_status='active' or (payment_status='cancelled' and paid_through >=
current_date))`. Tiene `revoke all` y `grant select` a anon.
**La regla "visible solo si lo aprobaste y el pago está al día" queda en el `WHERE`**: un impago la oculta sola, sin tocar
la fila, y una cancelación la deja visible hasta el final del período pagado. A los 30 días de `past_due` el script
(o el barrido de la Fase 2) pasa la fila a `publication_status='ended'`.

`partner_payment_events` (Fase 2, solo servidor, sin grants a anon): `notification_id text unique`, `topic`, `resource_id`,
`received_at`, `processed_at`, `result`. Sirve para la idempotencia.

**Logos:** un bucket **público** de Supabase Storage `partner-logos`, solo lectura. Lo sube el admin con el script
(`service_role`), que valida webp/png, menos de 40 KB y 192×192 o 384×384. No hay binarios nuevos en el repo y el
límite de 40 KB de ADR-009 se mantiene.

**Edge Functions:** en Fase 1 no hay ninguna. En Fase 2 está `mp-webhook` (ver §5), con `verify_jwt` OFF y el secreto
validado adentro.

**Retención** (en `purge_chat_logs.py`): una solicitud `rejected` o que nunca se pagó se borra a los 6 meses. Un aliado
`ended` o `cancelled` pierde los datos de contacto a los 2 años del último cobro, igual que outreach. Lo que haga falta
para la facturación queda en MP y en el sistema de facturación electrónica, no en Supabase (a confirmar con el contador).
`partner_payment_events` se borra al año.

## 5. Estrategia de Mercado Pago (lo verificado y lo pendiente)

**Verificado en la documentación oficial (UY):**
- Las suscripciones están disponibles en Uruguay, con plan asociado (`/preapproval_plan` + `/preapproval`) y sin plan
  (con pago autorizado o pendiente). Se cobra semanal, mensual o anual y hay reintentos automáticos si el cobro se rechaza.
  [Overview](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/overview) ·
  [Con plan asociado](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/integration-configuration/subscription-associated-plan) ·
  [Sin plan, pago pendiente](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/integration-configuration/subscription-no-associated-plan/pending-payments)
- El "link de suscripción" se crea desde la cuenta, sin sitio web, y el pagador **no necesita** cuenta de MP. Acepta
  Visa, Mastercard, OCA, Diners, Creditel y Líder.
  [Herramienta Suscripciones](https://www.mercadopago.com.uy/herramientas-para-vender/suscripciones)
- Comisión: **5,99% + IVA** con el dinero al instante o **4,99% + IVA** a 21 días, sin costo fijo. Sobre $U 790 son unos
  $U 57,73 o $U 48,09 por mes (IVA de la comisión incluido).
  [Costos](https://www.mercadopago.com.uy/ayuda/recibir-pagos-costos_220)
- `/preapproval` requiere `payer_email` y acepta `external_reference` (texto libre; es obligatorio en las suscripciones sin
  plan). [API create preapproval](https://www.mercadopago.com.uy/developers/es/reference/online-payments/subscriptions/create-preapproval/post)
- Webhooks: header `x-signature: ts=…,v1=…` + `x-request-id`, con la clave secreta por aplicación (en Tus integraciones →
  Webhooks). Los tópicos son `subscription_preapproval`, `subscription_authorized_payment`, `subscription_preapproval_plan`
  y `payment`. Hay que responder 200/201 en menos de 22 s; si no, reintenta cada 15 minutos y sigue.
  [Webhooks](https://www.mercadopago.com.uy/developers/es/docs/your-integrations/notifications/webhooks)
- Pruebas: hay cuentas de prueba Vendedor y Comprador **del mismo país** (MLU), hasta 15, que no se pueden borrar. Se
  paga con tarjetas de prueba. Logueado con la cuenta de prueba no se ven las credenciales de prueba (se sacan desde la
  cuenta real del integrador).
  [Cuentas de prueba](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/additional-content/your-integrations/test/accounts) ·
  [Compra de prueba](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/integration-test/payment-approval)

**No pude confirmarlo en la documentación oficial (queda como tarea de la Fase 1 en staging):**
- ~~**Moneda USD.**~~ **Resuelto el 2026-10-15:** Mercado Pago rechaza USD en suscripciones de Uruguay (HTTP 400
  `Cannot operate with currency id USD in MLU`, con la cuenta vendedora de prueba MLU). El precio va en UYU: $U 790 por
  mes, en `PROGRAM.currency/price`.
- Los requisitos para cobrar como persona física: la página solo pide "tener cuenta". Hay que ver el alta como vendedor y
  los límites en tu cuenta real.
- La plantilla exacta del manifiesto HMAC. La página UY no la detalla. La forma conocida de los SDK es
  `id:{data.id};request-id:{x-request-id};ts:{ts};` con HMAC-SHA256 en hex. Se confirma contra el SDK oficial y con un
  evento real de prueba antes de darlo por bueno.
- Si una cuenta de prueba puede crear el "link de suscripción" desde el panel. Si no puede, el plan de prueba se crea por
  API (`POST /preapproval_plan` con el token de prueba), que devuelve el mismo tipo de link (`init_point`).

**Fase 1 (manual):** hay un solo plan "CeliacMap Aliado – Plan Fundador" y su link. Lo mandás por email **solo** a las
solicitudes que marcaste `eligible`, con el texto "pagá con el mismo email que usaste en la solicitud". La vinculación es
manual: buscás en el panel de MP la suscripción con ese email y corrés
`partners_admin --link REF --mp-preapproval ID --apply`. Si el email no coincide, se usa el código `CM-XXXXXX`, que el
comercio responde por email. El script consulta `GET /preapproval/{id}` con el token del entorno y **se niega** si
`status != authorized`. Volver del checkout no hace nada, porque no hay ningún `back_url` que active algo.

**Fase 2 (automática):** cuando la solicitud pasa a `eligible`, el script crea un `/preapproval` **sin plan, pendiente**, con
`external_reference = ref_code`, `payer_email` y el monto y la moneda de la config, y manda el `init_point` por email (por
Resend, que ya existe). Así cada cobro trae su referencia y no hay que vincular a mano. `mp-webhook` hace esto:
1. valida `x-signature` con `timingSafeEqual` y rechaza un `ts` de más de 5 min (401 sin escribir);
2. inserta `notification_id` en `partner_payment_events`; si ya existía, responde 200 y no hace nada (idempotencia);
3. **consulta el recurso a la API de MP** (`/preapproval/{id}` o `/authorized_payments/{id}`) y nunca confía en el cuerpo
   del webhook;
4. busca la fila por `external_reference` y comprueba que `payer_email`, el monto y la moneda coincidan con lo esperado
   (protege contra activaciones fraudulentas: un preapproval ajeno con tu referencia no activa nada);
5. mapea los estados: `authorized` + último cobro aprobado → `active` (y actualiza `paid_through`); un cobro rechazado
   después de los reintentos → `past_due`; `paused` → `past_due`; `cancelled` → `cancelled`.
   **Nunca toca `publication_status`.** Si hay error, devuelve 500 para que MP reintente; el webhook es idempotente.
Además, un barrido diario (dentro de `admin_digest` o un job propio) consulta MP por cada fila `active` o `past_due` y
corrige la que no coincida, por si se perdió un webhook (es el mismo papel que cumple `ReviewHandler.sweep()`).

**Google Play / App Store:** vender publicidad a comercios no figura entre las exenciones claras de la política de pagos
de Google Play (son exentos los bienes o servicios físicos, P2P y donaciones), y la política prohíbe dirigir a pagos
externos desde la app. [Play Payments policy](https://support.google.com/googleplay/android-developer/answer/10281818?hl=en)
Recomendación: **la app nunca muestra la oferta ni el formulario**. Las tarjetas de aliados sí se pueden mostrar, porque
mostrar anuncios no es cobrar. El APK lo resuelve con `PARTNER_PROGRAM: false` en la config que se empaqueta. Hoy el APK
es una demo sin publicar en tiendas y no le aplica, pero queda fijado en un test.

## 6. Ambiente de pruebas (staging)

- **Supabase:** un segundo proyecto gratis, `celiacmap-staging` (el plan gratis permite 2 proyectos activos; se pausa
  después de 7 días sin actividad).
  - El schema se aplica con `psql "$STAGING_DB_URL" -f db/schema.sql`. Las migraciones posteriores al schema ya están
    incorporadas en él; las nuevas se corren en staging primero.
  - Las funciones se despliegan con `node_modules/.bin/supabase functions deploy mp-webhook --project-ref <staging>`,
    **nunca** con `link`. Después se confirma que `verify_jwt=false` en el dashboard de staging.
  - Datos: `scripts/seed_staging.py` lee producción **con la anon key** (solo las columnas públicas de `approved`; no puede
    ver nada más) y escribe en staging con el `service_role` de staging. Se niega a correr si las dos URL coinciden o si
    el destino es `pgblbyvetclllaqvknvc`. No copia sugerencias, reportes, opiniones, votos, chat, emails ni evidencia.
- **Frontend sin duplicar código:** `js/config.js` sigue siendo el de producción, con `PARTNER_PROGRAM: false`. Hay un
  archivo nuevo, `config/frontend.staging.js`, con la URL y la anon key de staging (son públicas por diseño) y
  `PARTNER_PROGRAM: true`. Está fuera de `js/`, así que Pages no lo publica.
  - Local: `node scripts/stage_site.mjs --env staging` copia el sitio a `_staging/` (que está en gitignore) cambiando
    solo `js/config.js`, y se sirve con `python -m http.server`.
  - APK de prueba: `sync-web.mjs --env staging` hace el mismo cambio. Para mostrar el formulario en ese APK se usa una
    excepción explícita, `--partner-program`, que solo existe en staging.
- **Credenciales:** el token de acceso y la clave del webhook de **prueba** son secrets de la función en el proyecto de
  staging. Los de **producción** son secrets de la función en el proyecto de prod (recién en la Fase 3). Para los scripts
  hay un `.env.staging` local en gitignore y GitHub Environments `staging` / `production`, cada uno con sus secrets.
  Nunca van al navegador, al APK ni al repo; `.env.example` documenta solo los nombres.
- **Escenarios de MP** (cuentas de prueba MLU), cada uno con su resultado esperado en la base:

| Escenario | Esperado |
|---|---|
| Alta (pagar el link) | `payment_status=active`; sigue sin ser visible hasta `--approve` |
| Cobro aprobado (renovación) | `paid_through` avanza; un evento por notificación |
| Cobro rechazado | No activa nada; si era `active` y se agotan los reintentos → `past_due` y desaparece de `partners_public` |
| Impago (`past_due`) | Lo mismo; el resumen diario lo avisa |
| Cancelación | `cancelled`; visible hasta `paid_through`, después oculto; `publication_status` no cambia |
| Impago regularizado | `past_due` → `active`; vuelve a `partners_public` |
| 30 días en `past_due` | `publication_status='ended'`; deja de verse aunque después pague |
| Webhook duplicado | Segundo envío → 200, sin cambios (ya está en `partner_payment_events`) |
| Firma inválida / ts viejo | 401, cero escrituras |
| Volver del checkout sin pagar | Nada cambia (el `back_url` es una página estática de "gracias", sin lógica) |
| Preapproval con referencia ajena / monto distinto | Rechazado, queda en el log y no se activa |

## 7. Roadmap por fases

- **Fase 0, documentos (sin código):** ADR-011, borrador de las "Condiciones para aliados", borrador de privacidad v1.2 y
  términos v1.2 en `docs/legal/*.md` (primero se edita el `.md`). Una entrada en `docs/DECISIONS.md`.
- **Fase 1, staging, manual:** proyecto de staging + `seed_staging`; la migración; `js/partners.js` (tarjeta + formulario +
  render de `partners_public`); el interruptor; `stage_site.mjs`; `scripts/partners_admin.py`; la sección en
  `admin_digest`; las reglas de retención; el plan de prueba en MP (en UYU; la prueba de USD dio 400). *Depende de:* Fase 0
  (texto de consentimiento) y del proyecto de staging creado por vos.
- **Fase 2, staging, automática:** `mp-webhook` + `partner_payment_events`, preapproval por solicitud con
  `external_reference`, barrido diario y todos los escenarios de la tabla. *Depende de:* la Fase 1 y la plantilla HMAC
  confirmada con un evento real.
- **Fase 3, lanzamiento:** pruebas de staging aprobadas, DGI/BPS + facturación electrónica, privacidad y términos v1.2
  publicados con aviso previo (los borradores reemplazan a los `.md` y `.html` vigentes en un solo cambio) y las condiciones
  para aliados publicadas; **el ejemplo de Bienestar fuera de `supabase/functions/chat/prompts.ts`** (batería de jailbreak +
  A/B real + sincronización de las copias; reinicia el conteo del soft-launch); credenciales de prod cargadas, la migración en prod (SQL mostrado y tu «dale») y
  `PARTNER_PROGRAM: true` en `js/config.js` por PR. Recién ahí se contacta a comercios.
- **Fase 4:** autoservicio (consultar o cancelar con un link firmado por email, sin cuentas) y estadísticas. Primero UTM;
  medir clics solo con un cambio de política.

## 8. Riesgos

- **Seguridad:** que se filtren el token de MP o la clave del webhook (mitigación: solo secrets, el test que ya existe de
  "sin claves en el frontend" se extiende a `MP_`/`APP_USR-`/`TEST-`); un webhook falsificado (firma + consulta a la
  API + idempotencia); un formulario abusado como almacenamiento (CHECKs de largo + anti-spam); **el CLI linkeado a prod**
  (§Contexto 3).
- **Integridad de datos:** activaciones desde el retorno del checkout (no existe ese camino); un pago vinculado al
  aliado equivocado (Fase 1: el script verifica el email y el `status` en MP; Fase 2: `external_reference` + email + monto);
  webhooks perdidos (barrido diario).
- **Confianza sanitaria:** que un aliado se lea como "lugar seguro". Mitigación: la frase fija, el aviso de publicidad en
  la tarjeta, la Opción A (el mapa neutral) y tests que fijan que `map.js`, `chat.js`, `chat/index.ts`, `regions.ts` y
  `prompts.ts`-nuevo no leen `partner*`. **Deuda que se vuelve más urgente:** `prompts.ts` todavía usa a Bienestar como
  ejemplo few-shot "100% sin gluten" (ADR-009). **Decidido: reemplazarlo es requisito de la Fase 3**, con la batería
  de jailbreak, el A/B contra el modelo real, la sincronización de las copias y el registro en `DECISIONS.md` y
  `prompts.md`. En las Fases 1 y 2 no se toca.
- **Legales:** cobrar sin inscripción en DGI/BPS; publicidad sin condiciones comerciales; datos personales nuevos sin
  política actualizada; el riesgo de los datos de Google Places (`docs/legal/auditoria-datos-google.md`) pesa más cuando
  hay ingresos; la moneda/IVA de la factura.
- **Compatibilidad:** las tiendas de apps (resuelto con el interruptor apagado en las apps); el service worker (agregar
  `js/partners.js` al `SHELL`, nunca cachear la vista ni Storage).
- **Mantenimiento:** el proyecto de staging que se pausa (despertarlo antes de probar); dos rutas de render de aliados
  durante la transición (Bienestar estática, el resto desde la vista). Se unifican migrando a Bienestar a la vista cuando
  la Fase 1 esté estable, con su consentimiento.

## 9. Testing por fase

**Fase 1**
- `tests/frontend_partners.test.js`, actualizado: las invariantes de siempre (#aliados es la última sección, la frase
  aparece una vez, rotulada, `rel="sponsored noopener"`, sin scripts ni iframes) y además: con la config de **prod**, el
  montaje `#partner-program` queda vacío y oculto, y no hay ninguna URL de mercadopago en `index.html` ni en `js/`; con
  `PARTNER_PROGRAM: true`, la tarjeta está en ES/EN, sin "Estadísticas", con el aviso de publicidad, el precio y las
  condiciones antes del envío, y la configuración sale de un único objeto.
- `tests/frontend_partner_form.test.js`, nuevo: obligatorios, honeypot, tiempo mínimo, cooldown, formato de `ref_code`,
  un choque de `ref_code` → nuevo código y reintento, un choque de email + comercio → mensaje de duplicado, sin `place_id` ni estados en el payload.
- `tests/test_partner_independence.py`, nuevo (la "guarda" que pediste): las migraciones `partner*` no hacen ALTER ni
  UPDATE sobre `places`, `place_votes` ni `reviews`; `scripts/partners_admin.py` nunca escribe en `places` (análisis
  estático de la tabla en cada llamada de escritura); ni `chat/*.ts`, ni `map.js`, ni `ranking.js` mencionan `partner`.
- `tests/test_partners_admin.py`: con un `FakeDB` (como los tests de `review_queue`), `--approve` se niega si el pago no
  está `active`, `--link` se niega si MP no dice `authorized`, y no escribe nada sin `--apply`.
- Un test de schema al estilo `test_places_public_columns.py`: la vista expone solo las 5 columnas públicas, sin grant de
  tabla para anon, y el `WHERE` tiene las dos condiciones.
- `frontend_pwa.test.js` (`js/partners.js` en el `SHELL`) y `frontend_mobile.test.js` (el bundle de la app lleva
  `PARTNER_PROGRAM: false` por defecto).
- Manual en staging: Chrome a 390 px y en desktop, ES/EN, con un clic real en el botón (la regla de los `hidden`), 0
  errores de consola, la PWA instalada y el APK de prueba.

**Fase 2**
- `supabase/functions/mp-webhook/index.test.ts`: firma válida/inválida, ts viejo, duplicado, el mapeo de estados, una
  referencia ajena, un monto distinto y un error de la API de MP → 500. Con `fetch` simulado.
- Los escenarios de la tabla de §6 contra el MP de prueba, con un registro en `docs/runbooks/partner-program.md`.

## 10. Archivos

**Cambian:** `index.html` (el punto de montaje y el `<script src="js/partners.js">`), `js/config.js`
(`PARTNER_PROGRAM: false`), `css/styles.css` (sección "Partner plan"), `service-worker.js` (`SHELL`), `db/schema.sql`,
`scripts/admin_digest.py`, `scripts/purge_chat_logs.py`, `scripts/delete_personal_data.py`,
`agents/clients/supabase_client.py` (los métodos de las tablas nuevas), `apps/mobile/scripts/sync-web.mjs` /
`web-bundle.mjs` (`--env`), `tests/frontend_partners.test.js`, `.gitignore` (`_staging/`, `.env.staging`), `.env.example`,
`docs/legal/politica-de-privacidad.md` → `privacidad.html`, `docs/legal/terminos-de-uso.md` → `terminos.html` (Fase 3),
`docs/legal/inventario-datos.md`, `docs/DECISIONS.md`, `CLAUDE.md` (una línea del índice + la regla "Partners" ampliada),
`README.md`, `docs/architecture/C4-diagrams.md` (Fase 2: MP como sistema externo).

**Nuevos:** `docs/architecture/ADR-011-partner-program-payments.md`, `docs/legal/condiciones-aliados.md`,
`db/migrations/AAAA-MM-DD-partner-program.sql` (+ `-revert.sql`), `js/partners.js`, `config/frontend.staging.js`,
`scripts/stage_site.mjs`, `scripts/seed_staging.py`, `scripts/partners_admin.py`, `docs/runbooks/partner-program.md`, los
tests de §9 y, en la Fase 2, `supabase/functions/mp-webhook/{index.ts,index.test.ts}`.

**No se tocan (Fases 1 y 2):** `supabase/functions/chat/*` (`prompts.ts` cambia solo en la Fase 3, ver Riesgos), `agents/validator_agent.py`, `js/map.js`,
`js/ranking.js`, `js/chat.js` ni ninguna columna de `places`.

## 11. Destaque en el mapa: opciones A y B

**A: mapa neutral (recomendada).** El destaque vive en #aliados y en las redes. Un aliado que además es un lugar
`approved` se ve en el mapa igual que cualquier otro, sin marca. No cambia ADR-009 §5, ni los términos §5, ni el test.
Es coherente con lo que ya prometiste en público y no hay riesgo de que "pagó" se lea como "es más seguro".

**B: identificación en la ficha** (por ejemplo, un chip "Aliado · publicidad" en el panel, nunca en el pin).
Implicaría:
- un ADR nuevo que reemplace ADR-009 §5 ("ni el marcador o la ficha del lugar");
- términos v1.2 con aviso previo, porque §5 hoy dice que no influyen en el mapa y el cambio es importante (§8 de los
  términos);
- cambiar `frontend_partners.test.js` ("el mapa nunca menciona al aliado") y la regla de CLAUDE.md;
- que `map.js` lea el estado de pago o de aliado: una columna o un join nuevo expuesto a anon (con el grant por columna)
  o una segunda lectura de `partners_public` cruzada por `place_id`;
- el riesgo principal: en una herramienta de salud, cualquier distinción visual junto a la etiqueta de seguridad se lee
  como respaldo. Incluso con el rótulo "publicidad", un comercio "con opciones" se ve más confiable que uno igual sin
  chip, y el valor que vendés (la neutralidad del mapa) se erosiona.

Si alguna vez se hace, la única forma defendible es un chip en la ficha, nunca en el pin, debajo de la etiqueta de
seguridad, con el texto "publicidad", y sin ningún efecto en el orden, los filtros, "Cerca mío" ni el chat.

## Elegibilidad (punto 5)

Pueden ser aliados: (a) un lugar `approved` en el mapa, en el estado y la etiqueta que ya tenga, o (b) un comercio de
productos o servicios sin gluten relevantes para la comunidad (dietética especializada, panadería sin TACC con venta
online, servicios), aunque no esté en el mapa. Los dos casos necesitan tu aprobación manual (`--eligible`, después
`--approve`). No pueden ser aliados: el comercio general que excluye `map_scope.py`, un lugar `discarded` por razones de
seguridad o con un reporte negativo abierto, ni productos con mensajes médicos o de "curación". Ser aliado **nunca**
agrega un lugar al mapa ni lo saca de la cola del Validator. Si es un lugar `needs_review`, sigue en `needs_review`.

## Pendientes no técnicos antes de cobrar (sin resolver)

Lista de la Fase 3 (nada se cobra ni se contacta antes de cerrarla):

- **Consulta con un contador:** inscripción en DGI/BPS, facturación electrónica, IVA (si los $U 790 lo incluyen),
  y el plazo de retención de los datos de cobro (en Uruguay suele ser de 5 años).
- **Revisión de un abogado** de las condiciones para aliados (`docs/legal/condiciones-aliados.md`) y de la privacidad y los
  términos v1.2 (`docs/legal/*-v1.2-borrador.md`), incluida la base legal de la retención fiscal.
- **Moneda del cobro:** resuelto, UYU ($U 790 por mes; Mercado Pago rechazó USD en Uruguay).
- **Mercado Pago como proveedor:** dónde guarda los datos y por cuánto tiempo (§7 de la privacidad).

Detalle de lo que sigue abierto: la inscripción en DGI/BPS y la facturación electrónica (y si el precio en UYU incluye IVA), las condiciones comerciales para
aliados (alcance, baja, contenidos prohibidos, que no hay garantía de visitas), privacidad v1.2 (datos de responsables
de comercios, MP como proveedor nuevo en §7, plazos nuevos en §6, una §3.11 nueva, el aviso previo en el sitio), la
auditoría de Google Places, que pasa a ser más urgente con ingresos, y la confirmación de la cuenta de MP como vendedor
persona física. Estadísticas: UTM (`?utm_source=celiacmap&utm_medium=aliados`) en los links de cada aliado, sin medir
nada de nuestro lado. Medir clics cambiaría §3.8 ("solo páginas vistas, sin eventos") y la promesa de "sin tracking"
de ADR-009.

## Verificación

- `deno test` en los tests de frontend, `pytest` para Python y el CI completo en el PR (una rama por fase; nunca `main`).
- En staging: el sitio servido desde `_staging/`, una solicitud real desde el formulario, `partners_admin --eligible`,
  el pago con el comprador de prueba MLU, `--link` / webhook, `--approve` y la tarjeta visible. Después, cancelar en MP
  y comprobar que desaparece de `partners_public`.
- En producción (después de cada merge, solo lectura): `PARTNER_PROGRAM` en false, `#partner-program` vacío,
  `curl` de `partners_public` con la anon key → `[]` y los 0 cambios en `places` (los conteos antes y después).

## Recomendación

Lo más simple, barato y mantenible es: **la Opción A**, **revisar la elegibilidad antes de cobrar**, **la Fase 1 manual
con un único link de plan**, una tabla con la vista `partners_public` como única barrera de visibilidad y un script de
administración. No hay Edge Function hasta la Fase 2, ni SDK de MP, ni dependencias nuevas, ni panel. El costo fijo es
cero: Supabase gratis ×2 y MP solo cobra comisión. La Fase 2 agrega un único webhook idempotente cuando haya aliados
reales que lo justifiquen.
