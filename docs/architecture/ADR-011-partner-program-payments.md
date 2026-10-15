# ADR-011: Programa de aliados pago ("CeliacMap Aliado") con Mercado Pago, separado de la evaluación de seguridad

**Estado:** Propuesto (2026-10-14). Aprobado el diseño; se implementa por fases (plan:
[`docs/plans/PLAN-partner-program.md`](../plans/PLAN-partner-program.md)). Pasa a **Aceptado** cuando la Fase 3 se publique
en producción. Amplía [ADR-009](ADR-009-sponsorships-separate-from-safety.md) sin reemplazar su punto 5.

## Contexto

ADR-009 abrió la sección `#aliados` con un único aliado sin pago (Bienestar Gluten Free) y una regla: el patrocinio es solo
frontend y no toca nada de la evaluación. El proyecto quiere sostenerse con un patrocinio mensual, el **Plan Fundador**
("CeliacMap Aliado"), cobrado en forma recurrente con Mercado Pago Uruguay.

Eso necesita lo que ADR-009 dejó afuera a propósito: un formulario de solicitud con datos de personas, un estado de pago,
una lista de aliados que se publica y se despublica sola según el pago y logos de varios comercios. El riesgo de fondo no
cambia. En una herramienta de salud, si el pago se filtra hacia lo que el mapa dice que es seguro, se pierde lo único que el
proyecto tiene para ofrecer.

## Decisión

1. **Contratar y publicar son pasos separados.** Primero el comercio manda una solicitud. Después el admin revisa la
   elegibilidad, y solo entonces se manda el link de pago. CeliacMap comprueba el pago en el servidor de Mercado Pago y el
   admin aprueba la tarjeta. Un aliado es visible **solo si el admin lo aprobó y el pago está al día**: `active`, o
   `cancelled` hasta el final del período ya pagado (`paid_through`). Un impago (`past_due`) lo oculta; si se regulariza,
   vuelve; a los 30 días sin pago el patrocinio termina (`ended`). Volver del checkout no activa nada.
2. **El mapa queda neutral (Opción A).** Un aliado que además es un lugar aprobado se ve en el mapa, en su ficha, en el
   ranking, en «Cerca mío» y en el chat exactamente igual que cualquier otro lugar. No hay chip, pin, orden ni filtro de
   aliado. Se descartó la opción de identificarlo en la ficha (ver Alternativas).
3. **El punto 5 de ADR-009 sigue igual, palabra por palabra.** El patrocinio no toca `places` (`status`, `safety_level`,
   `validation_confidence`, `verified`), el Validator ni el `RUBRIC`, el ranking (`place_votes` / `vote_count`), el chatbot
   (prompts, búsqueda u orden de resultados) ni el marcador o la ficha del lugar en el mapa.
4. **Tablas propias, aisladas de la evaluación.** Hay una tabla `partner_applications` (solicitud + estado de pago + estado de
   publicación). El público solo hace INSERT y no lee nada. Una vista `partners_public` expone las columnas de la tarjeta y
   su `WHERE` (`publication_status = 'approved'` y `payment_status = 'active'`, o `'cancelled'` con
   `paid_through >= current_date`) es la única barrera de visibilidad. En la
   Fase 2 se suma `partner_payment_events` (idempotencia de webhooks, solo servidor). `place_id` en la solicitud es un
   vínculo informativo que pone el admin; nada escribe en `places` desde este flujo. Esto **amplía el punto 1 de ADR-009**
   ("solo frontend"): la evaluación sigue sin cambios, pero el programa ahora sí tiene base de datos.
5. **Logos en Supabase Storage**, en un bucket público de solo lectura que carga el admin, con los mismos límites del punto 4
   de ADR-009 (WebP/PNG, menos de 40 KB, `alt`, tamaño y `loading="lazy"`). El logo de Bienestar sigue en el repo hasta que
   migre a la lista dinámica. **Amplía el punto 4 de ADR-009.**
6. **Mercado Pago, sin SDK en la página.** El pago se hace con un link externo que llega por email. En la Fase 1 es un único
   link de plan y el admin vincula el pago a mano, verificándolo con `GET /preapproval/{id}`. En la Fase 2 es un
   `preapproval` por solicitud con `external_reference` y un Edge Function `mp-webhook` que valida la firma, registra el
   evento una sola vez, **consulta el recurso a la API de Mercado Pago** antes de cambiar estados y nunca toca
   `publication_status`. Los secretos (token, clave del webhook) viven solo en los secrets de Supabase o GitHub, separados
   por entorno (pruebas / producción).
7. **Rotulado.** La tarjeta del plan dice que ser aliado es publicidad y que no significa que CeliacMap certifique la
   seguridad alimentaria del comercio. Las tarjetas de aliados siguen con "Aliado" / "Partner", `rel="sponsored noopener"` y
   la frase fija de independencia una sola vez como bajada de la sección.
8. **Interruptor.** `PARTNER_PROGRAM` en `js/config.js` queda en `false` en producción hasta la Fase 3. Con el interruptor
   apagado, la página no renderiza la oferta ni el formulario. **Las apps de tiendas nunca muestran la oferta ni el
   formulario**, porque vender publicidad desde la app chocaría con las políticas de pago de Google Play y App Store. Sí pueden
   mostrar las tarjetas de aliados.
9. **Elegibilidad.** Pueden ser aliados un lugar `approved` del mapa (con la etiqueta que ya tenga) o un comercio de productos o
   servicios sin gluten relevantes para la comunidad aunque no esté en el mapa. No pueden serlo el comercio general excluido
   por `agents/map_scope.py`, un lugar descartado por seguridad o con un reporte negativo abierto, ni quien hace promesas
   médicas o de "curación". Cada aliado necesita la aprobación manual del admin. Ser aliado nunca agrega un lugar al mapa ni lo
   saca de la cola del Validator.
10. **El chat no nombra aliados por ser aliados.** Hoy `supabase/functions/chat/prompts.ts` usa a Bienestar como ejemplo
    few-shot (es una deuda de ADR-009). Reemplazar ese ejemplo, con la batería de jailbreak y el A/B contra el modelo real, es
    **requisito de la Fase 3**: no se lanza el plan pago con un aliado dentro del prompt.
11. **Staging primero.** Todo se construye y se prueba en un segundo proyecto de Supabase con credenciales de prueba de
    Mercado Pago. A staging se copian solo los lugares aprobados con sus columnas públicas (leídos con la anon key) y nunca
    datos personales. El CLI de Supabase del repo está vinculado a producción: staging se opera siempre con `--project-ref`
    explícito, nunca con `supabase link`.

## Alternativas descartadas

- **Identificar al aliado en el mapa o en la ficha (Opción B).** Exigiría reemplazar el punto 5 de ADR-009, publicar términos
  v1.2 con aviso previo (hoy la §5 dice que los aliados no influyen en el mapa), cambiar la guarda de
  `tests/frontend_partners.test.js` y exponer a anon un dato de aliado cruzado con `places`. Sobre todo, en una herramienta de
  salud cualquier distinción visual junto a la etiqueta de seguridad se lee como respaldo, aunque diga "publicidad".
- **Cobrar primero y revisar después.** Obliga a devolver dinero a quien no califica y necesita un endpoint público que cree
  cobros. Revisar antes es más simple y más seguro.
- **SDK o checkout embebido de Mercado Pago.** Agrega scripts de terceros a un sitio que hoy no tiene ninguno en sus formularios.
  El link externo alcanza.
- **Activar con la URL de retorno del checkout.** Se puede falsificar. El estado sale solo de la API de Mercado Pago.
- **Marcar al aliado en `places`** (columna `sponsored`, boost). Es lo que ADR-009 prohíbe.

## Verificación (prevista por fase)

- `tests/frontend_partners.test.js` mantiene sus invariantes y suma: con la config de producción, la oferta no se renderiza
  y no hay URLs de Mercado Pago en `index.html` ni en `js/`.
- `tests/test_partner_independence.py`, nuevo: las migraciones del programa no alteran `places`, `place_votes` ni `reviews`; el
  script de administración no escribe en `places`; ni el mapa, ni el ranking, ni el código del chat leen tablas `partner*`.
- Un test de schema para `partners_public`: solo columnas públicas, sin grant de tabla para anon, y el `WHERE` con las dos
  condiciones.
- Fase 2: `supabase/functions/mp-webhook/index.test.ts` (firma inválida, `ts` viejo, duplicado, referencia o monto ajenos,
  error de la API) y los escenarios de prueba de Mercado Pago del plan, registrados en un runbook.

## Consecuencias

**Positivas:**

- El proyecto puede cobrar sin tocar el mapa, y la separación queda fijada en tests además de en la política.
- Un impago oculta al aliado solo, por la vista, sin que nadie tenga que acordarse.
- No hay costo fijo: Supabase gratis para staging y Mercado Pago cobra solo comisión.

**Negativas / trade-offs aceptados:**

- Hay datos personales nuevos (la persona responsable del comercio, su email y teléfono) y un proveedor nuevo (Mercado Pago).
  Hacen falta la política de privacidad y los términos v1.2 con aviso previo, y unas condiciones para aliados.
- Antes de cobrar de verdad hay requisitos que no son técnicos: inscripción en DGI/BPS y facturación electrónica. El riesgo
  pendiente de los datos de Google Places (`docs/legal/auditoria-datos-google.md`) pesa más cuando hay ingresos.
- Durante la transición conviven dos formas de mostrar aliados: la tarjeta estática de Bienestar y la lista que sale de la vista.
- **Moneda (resuelto 2026-10-15):** Mercado Pago no acepta USD en suscripciones de Uruguay. Crear un plan de prueba con
  `currency_id: "USD"` respondió HTTP 400 `Cannot operate with currency id USD in MLU` y no creó nada. El precio es
  **$U 790 por mes (UYU)**; el Plan Fundador lo mantiene 12 meses. Si incluye IVA queda pendiente para la Fase 3.
