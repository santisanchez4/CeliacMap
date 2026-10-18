# Partner program «CeliacMap Aliado» — admin runbook

Step by step for the admin, from a request to a published card, with `scripts/partners_admin.py` and the emails sent by
hand from **hola@celiacmap.org**. Design: [ADR-011](../architecture/ADR-011-partner-program-payments.md),
[plan](../plans/PLAN-partner-program.md), [conditions](../legal/condiciones-aliados.md) (draft) and
[privacy v1.2](../legal/politica-de-privacidad-v1.2-borrador.md) §3.11 and §6 (draft).

> **Until phase 3 everything runs on staging only** (`--env staging`, the Mercado Pago test account, the plan's test
> link). `partner_applications` does not exist in production: the admin digest and the weekly purge skip the partner
> part there. Being a partner never changes `places`, the Validator, the ranking, the chatbot or the map.

## Rules

- Every write is a dry run until `--apply`. Read the dry run, then repeat with `--apply`.
- Never paste a business's email or phone in a public place (issues, PRs, commits). The script prints the email masked.
- A business never pays before our reply (conditions §5). Reply within **5 business days** of the request.
- Returning to the site after paying activates nothing: only `--link` with an approved first charge does.
- The payer's email in Mercado Pago is only a suggestion (`--suggest`); the link is made with the **operation number**
  the business sends.

Shortcut used below (staging):

```bash
PA="python -m scripts.partners_admin --env staging --project-ref egqclfomloqmddvlpepx --env-file C:/Repos/CeliacMap/.env.staging"
```

## Step by step

| # | When | Command | Email |
|---|---|---|---|
| 1 | The daily digest lists `SOLICITUDES DE ALIADO NUEVAS` | `$PA` (list, read-only) | — |
| 2a | The business qualifies (conditions §4) | `$PA --eligible CM-XXXXXX [--note "..."]`, then `--apply` | **A. Solicitud elegible** |
| 2b | It does not qualify | `$PA --reject CM-XXXXXX --note "motivo interno"`, then `--apply` | **B. Solicitud no elegible** |
| 3 | The business replies with its code and operation number | `$PA --suggest CM-XXXXXX` (optional, read-only) and `$PA --link CM-XXXXXX --mp-payment NUMERO`, then `--apply` | **C. Pago recibido** |
| 4 | The business sends logo, text and links | `$PA --approve CM-XXXXXX --public-name "..." --text-es "..." --text-en "..." --public-link "Instagram=https://..."`, then `--apply` | **D. Tarjeta publicada** |
| 5 | Every day the digest is read, and whenever it shows `PARA CERRAR` | `$PA --sync`, then `--apply` | — |

Notes:

- **2b:** the `--note` is internal (`admin_notes`, never published, never sent). The email does not give the reason.
- **3:** `--link` refuses unless every check passes (eligible and unpaid; first charge `approved`, of this plan, this
  account, the plan's amount and currency; subscription `authorized`; not linked to another request). If it refuses
  because the charge was **rejected**, nothing is written: the business opens the same link again with another card
  and sends the new operation number.
- **4:** `--approve` needs `eligible` + payment `active`. The card shows in Aliados right away (view `partners_public`).
  **Pending:** the logo upload to the `partner-logos` bucket is not in the script yet (plan, «Logos»); until it is, the
  card goes out without a logo.
- **5:** `--sync` reads the charges from Mercado Pago. `cancelled` keeps the card until `paid_through` and then ends it;
  a missed charge (`past_due`) hides the card, and 30 days after `paid_through` ends it. **The purge only deletes
  `ended` partners**: a partner left open keeps its data longer than the privacy policy says, which is why the digest
  lists them under `PARA CERRAR (correr --sync)`.

## What the digest shows (`scripts/admin_digest.py`)

Only the CM code, the business name, the states and `paid_through`; never a name, email or phone of the contact.

- Sends the email: `SOLICITUDES DE ALIADO NUEVAS` (last 24 h), partners `past_due`, and `PARA CERRAR (correr --sync)`
  (`cancelled` with `paid_through` past, or `past_due` more than 30 days after `paid_through`, not yet `ended`).
- Listed only when the email goes out anyway: `ELEGIBLES ESPERANDO PAGO` and `ALIADOS POR ESTADO DE PAGO` (active,
  past_due, cancelled, with `paid_through`).

## Retention (`scripts/purge_chat_logs.py`, weekly)

From privacy v1.2 §6 (draft):

- A request **never charged** (no first payment linked): deleted **6 months** after the request, whatever its state.
- An **ended** partner: deleted **2 years after its last charge**. The last charge is not stored: it is taken as
  `paid_through` minus one month, which assumes the monthly plan.
- Pending, not implemented: billing data for tax purposes (to confirm with an accountant; usually 5 years in Uruguay),
  Mercado Pago payment notices (1 year, when the phase 2 webhook stores them), and the logo files in Storage (no
  window defined).

## Email templates (Spanish, sent by hand)

Replace what is between `<...>`. Subject first, then the body. Never include another business's data.

### A. Solicitud elegible

**Asunto:** Tu solicitud para ser aliado de CeliacMap (<CM-XXXXXX>)

```text
Hola, <nombre de la persona>:

Gracias por querer sumar a <nombre del comercio> como aliado de CeliacMap. Revisamos la solicitud <CM-XXXXXX> y
podés sumarte al Plan Fundador.

- Precio: $U 790 por mes, en pesos uruguayos, con cobro mensual automático por Mercado Pago. Sin permanencia: podés
  cancelar cuando quieras y la tarjeta sigue visible hasta el final del período ya pagado.
- Plan Fundador: mantenés este precio durante 12 meses desde tu primer pago.
- Para pagar, entrá a este link de Mercado Pago:
  <LINK_DE_PAGO>

Si Mercado Pago rechaza la tarjeta, no pasa nada: volvé a entrar al mismo link y probá con otra tarjeta.

Después de pagar, respondé este email con:
1. tu código de solicitud: <CM-XXXXXX>
2. el número de operación que te muestra Mercado Pago.

Con eso comprobamos el pago y te pedimos el contenido de la tarjeta. Ser aliado es publicidad: no cambia cómo aparece
ningún lugar en el mapa ni significa que CeliacMap certifique el comercio.

Las condiciones completas están en <LINK_A_LAS_CONDICIONES>.

Saludos,
CeliacMap
hola@celiacmap.org
```

### B. Solicitud no elegible

**Asunto:** Tu solicitud para ser aliado de CeliacMap (<CM-XXXXXX>)

```text
Hola, <nombre de la persona>:

Gracias por tu interés en CeliacMap. Revisamos la solicitud <CM-XXXXXX> y por ahora no podemos sumar a
<nombre del comercio> como aliado.

No se hizo ningún cobro y no tenés que hacer nada más.

Saludos,
CeliacMap
hola@celiacmap.org
```

### C. Pago recibido

**Asunto:** Recibimos tu pago — <CM-XXXXXX>

```text
Hola, <nombre de la persona>:

Confirmamos el pago de la suscripción de <nombre del comercio> (solicitud <CM-XXXXXX>). ¡Gracias por sumarte!

Para armar la tarjeta en la sección Aliados, respondé este email con:
1. El logo: PNG o WEBP, cuadrado (192×192 o 384×384 px), de menos de 40 KB.
2. El nombre comercial tal como querés que aparezca.
3. Un texto corto sobre el comercio, de hasta 400 caracteres, en español y, si podés, en inglés (si no, te mandamos
   una traducción para que la apruebes).
4. Los enlaces: WhatsApp, redes o sitio web (direcciones que empiecen con https://).

Antes de publicar revisamos el contenido: la tarjeta no puede decir o sugerir que CeliacMap certifica o recomienda el
comercio, ni prometer resultados médicos, ni decir que algo es "seguro para celíacos" sin respaldo. Siempre lleva la
etiqueta "Aliado".

Saludos,
CeliacMap
hola@celiacmap.org
```

### D. Tarjeta publicada

**Asunto:** Tu tarjeta de aliado ya está en CeliacMap

```text
Hola, <nombre de la persona>:

La tarjeta de <nombre del comercio> ya está publicada en la sección Aliados de CeliacMap:
https://santisanchez4.github.io/CeliacMap/#aliados

Se cobra una vez por mes por Mercado Pago. Si un cobro no se acredita, la tarjeta se oculta hasta que el pago esté al
día; si pasan 30 días sin pago, el patrocinio termina. Podés cancelar cuando quieras desde tu cuenta de Mercado Pago
o escribiendo a hola@celiacmap.org: la tarjeta sigue visible hasta el final del período ya pagado.

Si querés cambiar algo de la tarjeta, respondé este email.

Saludos,
CeliacMap
hola@celiacmap.org
```
