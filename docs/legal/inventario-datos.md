# Inventario de datos personales — CeliacMap

> Borrador del 2026-09-29, actualizado el mismo día con la **fase 1 de privacidad** (§9). Sale del código (`db/schema.sql`, `agents/`, `supabase/functions/`, `js/`, `index.html`,
> `.github/workflows/`) y de consultas de **solo lectura** a producción hechas ese día. No es asesoramiento legal: es la
> base de hechos para la política de privacidad y para la revisión legal.
>
> Marcas: 🩺 = **dato de salud** (sensible según el art. 18 de la Ley 18.331 y el art. 7 de la Ley 25.326) ·
> 🌐 = legible por cualquiera · ⚠️ = hallazgo que conviene corregir antes de publicar la política.

## 1. Resumen

- **No hay cuentas ni login.** Nadie deja email, teléfono ni documento en los formularios ni en el chat. El único dato
  que identifica directamente a quien escribe es el **nombre opcional** de una opinión (`place_reports.author_name`).
- Los datos personales que sí existen son: (a) **textos libres** que la gente escribe (notas, comentarios, chat) y que
  pueden traer cualquier cosa, datos de salud incluidos; (b) **identificadores seudónimos** (tokens aleatorios del
  navegador y un hash de la IP); (c) **datos de negocios** que pueden ser de una persona física (email de contacto,
  teléfono, respuestas a los emails de outreach); (d) datos técnicos que ven los proveedores (IP, navegador).
- Todo se guarda en **Supabase, región `sa-east-1` (AWS, São Paulo, Brasil)**, dato tomado de `supabase projects list`.
- Conteos al 2026-09-29: 2 sugerencias, 2 reportes (1 opinión publicada, 0 con nombre), 132 votos (8 de la comunidad,
  124 de la carga inicial), 100 filas de log del chat (45 marcadas), 58 contadores del chat, 56 mensajes de outreach,
  10 lugares con email de contacto, 281 reseñas de Google, 0 filas en `place_evidence`.

## 2. Datos que aporta la gente

| Dato | Dónde se guarda | Quién lo aporta | Para qué se usa | ¿Público? | Retención real | Proveedores |
|---|---|---|---|---|---|---|
| Nombre, dirección, ciudad, país y categoría de un lugar sugerido | `suggestions.name/address/city/country/category` | Cualquier persona (formulario “Agregalo” y chat) | Ubicar el lugar (Google Find Place / Geocoding) y crear un candidato para el Validator | No (tabla solo de inserción; si se aprueba, el **lugar** pasa a `places`, que es público) | **Sin borrado**: queda indefinidamente | Supabase (BR); Google (EE. UU.) para geocodificar |
| Link de referencia | `suggestions.evidence_url` → `places.social_url` y `place_evidence.url` | Idem | Evidencia para el Validator | `places.social_url` es 🌐 si el lugar se aprueba | Sin borrado | Supabase; Anthropic (EE. UU.) lo ve el Validator |
| Notas libres (“¿por qué es apto?”) | `suggestions.notes` → `place_evidence.text` (source `user`) | Idem | Evidencia para el Validator; mail diario al admin | No | Sin borrado. Copia en el buzón del admin (ver §5) | Supabase; Anthropic; Resend (EE. UU.) y Zoho (mail al admin) |
| 🩺 Cocina del lugar: `kitchen_exclusive`, `celiac_prep` | `suggestions.*`, `place_reports.*` (solo reportes positivos) | Idem (formulario y chat) | Evidencia no verificada para el Validator (ADR-007) | No | Sin borrado | Supabase; Anthropic (el Validator la recibe) |
| 🩺 **`owner_celiac`** (“¿el dueño o la dueña es celíaco/a?”) | `suggestions.owner_celiac`, `place_reports.owner_celiac` (columnas que se borran el 2026-10-07 o después) | **Ya no se junta**: el formulario no pregunta y el chat descarta la respuesta (desde la fase 1). El chat todavía pregunta hasta la próxima tanda de prompts | Nada: no lo ve el Validator, ni `review_queue`, ni el mail diario | No | **0 filas con el dato** (ver `owner-celiac-plan.md`) | Anthropic ve la respuesta en la conversación del chat mientras el chat siga preguntando |
| Comentario sobre un lugar (positivo o negativo) | `place_reports.description` (5–2000 caracteres) | Cualquier persona (formulario “Contanos” y chat) | Negativo: re-evaluación del Validator y aviso “Reportado por la comunidad”. Positivo: puede publicarse como opinión | Negativo: **nunca**. Positivo: 🌐 **solo si llegó por el formulario y el admin lo aprueba** (vista `community_opinions`). Las del chat (sin `reporter_token`) no se ofrecen para publicar (`moderate_opinions.from_the_form`) | Sin borrado. Una opinión publicada deja de verse si el admin la oculta (`moderate_opinions --hide`) o si el lugar sale del mapa | Supabase; Anthropic (reportes negativos); Resend + Zoho (texto completo en el mail urgente y en el mail diario) |
| Nombre para mostrar (opcional, máx. 40) | `place_reports.author_name` | Quien deja una opinión positiva | Firmar la opinión publicada (vacío = “Anónimo”) | 🌐 si la opinión se publica | Sin borrado | Supabase |
| Identificador de navegador para reportes | `place_reports.reporter_token` + localStorage `celiacmap-reporter-token` | Lo genera el navegador (aleatorio) | Contar reportes negativos **distintos** en 30 días | No | Sin borrado (0 filas hoy) | Supabase |
| Voto (“lo recomiendo”) | `place_votes.place_id` + `voter_token` | Cualquier persona; el token lo genera el navegador | Ranking (`places.vote_count`) | Solo el conteo (🌐); las filas no | Sin borrado | Supabase |
| Conversación con el chat | No se guarda entera. Se manda al modelo en cada turno (hasta 15 mensajes, 2000 caracteres c/u) | Quien usa el chat | Responder (router + redactor, `claude-haiku-4-5`) | No | En CeliacMap: solo los turnos marcados (fila siguiente). En Anthropic: según su política (a confirmar) | Anthropic (EE. UU.); Supabase Edge Functions |
| 🩺 Texto de turnos **marcados** del chat (fuera de alcance, límite médico, límite de uso, guardián de celiaquía) | `agent_log.result.raw_user_message` / `raw_bot_reply` / `guard.discarded_bot_reply` (agent `chatbot`) | Quien usa el chat | Auditoría de seguridad del chat | No | **30 días**, borrado por `.github/workflows/chat-log-purge.yml` (lunes 08:00 UTC → en la práctica hasta ~37 días) | Supabase; GitHub Actions ejecuta el borrado |
| Resto del log de turnos del chat (sin texto: módulo, nombre de lugar y ciudad buscados, tokens) | `agent_log` (agent `chatbot`, `chat_turn`) | Idem | Telemetría | No | 30 días, mismo job | Supabase |
| Token de sesión del chat | `chat_usage.bucket_key = 'session:<token>'` + localStorage `celiacmap-chat-token` | Lo genera el navegador | Límite de mensajes por sesión | No | **7 días**: la purga semanal (`chat-log-purge.yml`) borra los contadores con `day` de hace más de 7 días | Supabase |
| IP de quien usa el chat | `chat_usage.bucket_key = 'ip:<hmac>'`: **HMAC-SHA256 con el secreto `CHAT_IP_HASH_SECRET`**, nunca en claro (`ipBucketHash`, `supabase/functions/chat/index.ts`). Sin el secreto, no se guarda nada derivado de la IP | La toma la Edge Function del header `x-forwarded-for` | Límite de 40 mensajes por IP y por día | No | 7 días, mismo job | Supabase |

El HMAC sigue siendo un **seudónimo**, no un anonimato: con el secreto se podría comprobar si una IP dada escribió. Sin
el secreto no se puede revertir, a diferencia del SHA-256 sin clave que se usaba antes de la fase 1 (se podía revertir
probando las ~4.300 millones de IPv4). Los contadores viejos, con ese hash, desaparecen con la purga de 7 días.

## 3. Datos de negocios (pueden ser de una persona física)

| Dato | Dónde | De dónde sale | Para qué | ¿Público? | Retención | Proveedores |
|---|---|---|---|---|---|---|
| Nombre, dirección, coordenadas, teléfono, sitio web, horarios, rating | `places.*` | Google Places, páginas públicas (Social/Web), sugerencias | Mapa y chat | 🌐 si `status='approved'` | Sin borrado; el Updater lo actualiza cada mes | Google (EE. UU.), Tavily (EE. UU.), Anthropic |
| Email de contacto | `places.contact_email` (+ `contact_email_checked_at`) | Scraping del sitio web del propio negocio | Outreach: pedirle al negocio que confirme su información | **No.** Desde 2026-09-29 `places` tiene grant por columna: la clave pública lee solo 20 columnas y `contact_email` no está entre ellas (401 `42501`, verificado en vivo). Antes de ese día se podía leer en los lugares aprobados; ninguno de los 10 lo estaba | Sin borrado | Supabase; Resend (EE. UU.) |
| Emails de outreach enviados y respuestas del negocio | `outreach_messages.content` (56 filas) | El agente de outreach y el webhook de Resend | Re-evaluación del Validator; auditoría | No | Sin borrado | Resend (envío y recepción), Supabase, Anthropic (lee la respuesta) |
| Pedido de no recibir más emails | `places.outreach_opt_out` | Lo detecta el modelo en la respuesta | No volver a contactar | No (cerrada por el grant por columna, igual que `outreach_status`, `outreach_channel`, `validation_notes`, `flags` y `recommendation`) | Sin borrado | Supabase; Anthropic |
| Reseñas de Google (solo texto y rating, **sin autor**) | `reviews` (source `google`), 281 filas | Google Places | Evidencia para el Validator | No (solo servidor desde 2026-09) | **30 días**: la purga semanal borra las de más de 30 días (hasta ~37 en la práctica) y deja los `place_id` en `agent_log` para que el pipeline mensual las recargue. Al 2026-09-29 había 270 de 281 vencidas: se borran en la primera corrida de la purga | Google; Supabase; Anthropic |
| 🩺 Textos de reseñas y de páginas públicas que pueden decir “soy celíaca…” o “el dueño es celíaco” | `reviews.text`, `place_evidence.text` | Google, Tavily, Anthropic web search | Evidencia | No. El RUBRIC le prohíbe al Validator repetir datos de salud de personas en sus campos públicos, y el evidence finder filtra esas frases de la nota pública | Reseñas: 30 días (purga semanal). Evidencia: sin borrado | Google, Tavily, Anthropic |

## 4. Navegador de la persona (localStorage, sin cookies)

No hay cookies propias. Todo se guarda en el `localStorage` del navegador, no vence solo y nunca sale del navegador,
salvo los tres tokens marcados con →.

| Clave | Contenido | Archivo |
|---|---|---|
| `celiacmap-lang` | Idioma elegido (`es`/`en`) | `js/main.js` |
| `celiacmap-chat-token` → | Token aleatorio de sesión del chat (se manda como `session_token`) | `js/chat.js` |
| `celiacmap-chat-last` | Hora del último mensaje (freno anti-spam) | `js/chat.js` |
| `celiacmap-voter-token` → | Token aleatorio de votante (se manda como `voter_token`) | `js/ranking.js` |
| `celiacmap-voted` | Lugares ya votados desde este navegador | `js/ranking.js` |
| `celiacmap-vote-last` | Hora del último voto | `js/ranking.js` |
| `celiacmap-ranking-country` | País elegido en el ranking | `js/ranking.js` |
| `celiacmap-reporter-token` → | Token aleatorio de reportes (se manda como `reporter_token`) | `js/report.js` |
| `celiacmap-report-last` | Hora del último reporte | `js/report.js` |
| `celiacmap-suggest-last` | Hora de la última sugerencia | `js/suggest.js` |

## 5. Copias fuera de la base

- **Mails al admin** (Resend → buzón Zoho `santiagosanchez@celiacmap.org`, o el secreto `ADMIN_EMAIL`):
  - urgentes (`agents/admin_notify.py`): **texto completo** de cada reporte negativo;
  - diario (`scripts/admin_digest.py`): notas de sugerencias, links, respuestas de cocina (sin `owner_celiac` desde la fase 1) y
    textos de reportes. Los turnos del chat **solo se cuentan**, su texto nunca va por mail.
  - Retención: lo que guarde el buzón. **No hay regla de borrado.** Pendiente de definir.
- **Mails a `hola@celiacmap.org`** (Zoho): contacto, aliados, pedidos de baja de opiniones. Sin regla de borrado.
- **Logs de proveedores**: Supabase (API y Edge Functions, con la IP del request), GitHub Pages (visitas), Cloudflare,
  Resend. CeliacMap no los controla; la retención depende de cada proveedor.

## 6. Proveedores

| Proveedor | Qué procesa | País | Rol |
|---|---|---|---|
| **Supabase** (sobre AWS) | Toda la base; API REST pública; Edge Functions `chat`, `outreach-reply`, `place-report-created` (reciben la IP en el request) | Base en **Brasil** (`sa-east-1`); las Edge Functions corren en la red global de Supabase (a confirmar la región) | Encargado |
| **Anthropic** | Conversaciones del chat; candidatos y evidencia (notas de sugerencias, reportes negativos, reseñas, respuestas de outreach) para el Validator y los agentes | EE. UU. | Encargado. Retención según su política comercial de la API (a confirmar) |
| **Resend** | Mails de outreach a negocios, mails al admin (con textos de reportes y notas), respuestas entrantes | EE. UU. | Encargado |
| **Google** | Places / Find Place / Geocoding (nombre y dirección de lugares, también los sugeridos); **Google Fonts** (IP y navegador de cada visita) | EE. UU. | Encargado (Places); tercero (Fonts) |
| **Cloudflare** | Web Analytics: una baliza, páginas vistas, sin cookies y sin eventos propios (ve IP y navegador) | EE. UU. / red global | Encargado |
| **GitHub** | Código, hosting del sitio (GitHub Pages ve la IP de cada visita), GitHub Actions (corre los agentes y los borrados con la clave de servicio) | EE. UU. | Encargado |
| **Zoho** | Buzón del admin y alias `hola@celiacmap.org` | Depende del centro de datos de la cuenta (a confirmar: zoho.com = EE. UU.) | Encargado |
| **Tavily** (no estaba en la lista) | Búsquedas de páginas públicas de negocios (Social, evidence finder). No recibe datos de quien usa el sitio | EE. UU. | Encargado |
| **CARTO / OpenStreetMap** (no estaba en la lista) | Tiles del mapa: IP de cada visita y la zona que mira | CARTO: España / EE. UU. (a confirmar) | Tercero |
| **unpkg** (no estaba en la lista) | Sirve Leaflet (JS/CSS): IP de cada visita | EE. UU. | Tercero |

## 7. Datos de salud (resumen aparte)

1. 🩺 `owner_celiac`: salud de una **tercera persona**, sin su consentimiento. 0 filas guardadas. Ya no se junta ni se
   muestra (fase 1); las columnas se borran el 2026-10-07 o después y el chat deja de preguntar en la próxima tanda de
   prompts (`owner-celiac-plan.md`).
2. 🩺 Turnos marcados del chat: si alguien cuenta sus síntomas (`limite_medico`), ese texto queda 30 días. Hoy el aviso
   del chat informa la retención, pero no pide un consentimiento expreso.
3. 🩺 Textos libres (notas, comentarios, opiniones, respuestas de negocios, reseñas de Google, evidencia): pueden traer
   datos de salud propios o de otras personas. Las opiniones publicadas pasan por el admin, que no debería publicar
   datos de salud de terceros (regla vigente para las columnas públicas).
4. 🩺 Datos de cocina (`kitchen_exclusive`, `celiac_prep`): son datos **del negocio**, no de salud de una persona. Se
   listan acá porque viajan junto con `owner_celiac`.
5. Que alguien use CeliacMap no prueba que sea celíaco, pero un token de sesión junto con el texto de un turno marcado
   sí puede vincularse a una persona. Por eso se mantiene el borrado de 30 días y, desde la fase 1, `chat_usage` se
   borra a los 7.

## 8. Pendientes que salen del inventario

| # | Pendiente | Estado |
|---|---|---|
| P1 | Procedimiento para atender pedidos de acceso, rectificación y supresión | ✅ Fase 1: `scripts/delete_personal_data.py` + `docs/legal/runbook-pedidos-de-datos.md` (el registro en `agent_log` necesita la migración `agent-log-privacy`) |
| P2 | Borrado automático de `chat_usage` (7 días) y hash de IP con clave secreta (HMAC) | ✅ Fase 1 (el HMAC rige desde el deploy de `chat` con `CHAT_IP_HASH_SECRET`) |
| P3 | Cerrar la lectura pública de `contact_email` y de las columnas de outreach y de revisión | ✅ Fase 1: grant por columna aplicado y verificado |
| P4 | Borrado semanal de las reseñas de Google | ✅ Fase 1: en la purga semanal; la recarga sigue en el pipeline mensual |
| P5 | Retención para `suggestions`, `place_reports` no publicados, `place_votes`, `outreach_messages`, `agent_log` de los demás agentes y los mails del buzón | Abierto: decisión + job |
| P6 | Eliminar `owner_celiac` | Etapa 1 ✅ (formulario, admin, chat descarta). Etapa 2: próxima tanda de prompts. Etapa 3: SQL preparado para el 2026-10-07 o después |
| P7 | Confirmar la retención y el país de Anthropic, Resend, Cloudflare, Zoho, CARTO y las Edge Functions de Supabase | Abierto: lectura de las políticas de cada proveedor |
| P8 | Recomendaciones que llegan por el chat | ✅ Fase 1: no se ofrecen para publicar (sin `reporter_token`). El aviso de “Anónimo” en el chat va en la próxima tanda de prompts (`docs/plans/next-prompt-batch.md`, punto 2) |

## 9. Fase 1 de privacidad (2026-09-29)

Qué cambió respecto del relevamiento inicial (detalle en `docs/DECISIONS.md`):

- `places`: grant por columna, así que la clave pública ya no lee `contact_email`, `outreach_*`, `validation_notes`,
  `flags` ni `recommendation`.
- `owner_celiac`: fuera del formulario, de `review_queue`, del mail diario y de todo lo que guarda el chat.
- Purga semanal: `chat_usage` a los 7 días y reseñas de Google a los 30, además de los logs del chat.
- IP del chat: HMAC con `CHAT_IP_HASH_SECRET` en lugar de SHA-256 sin clave.
- Recomendaciones del chat: no se ofrecen para publicar.
- Pedidos de datos: script de búsqueda y borrado, más un runbook con plazo de respuesta.
