# Runbook: pedidos de acceso, corrección y borrado de datos

> 2026-09-29. Cómo responder un pedido que llega a **hola@celiacmap.org**. Los plazos legales son de referencia y
> están marcados **[A CONFIRMAR EN LA REVISIÓN LEGAL]**.

## Plazo

**Objetivo interno: responder en 5 días hábiles desde que llega el mail**, sea cual sea el país. Es el plazo más corto de
los de referencia:

| Pedido | Uruguay (Ley 18.331) | Argentina (Ley 25.326) |
|---|---|---|
| Acceso (qué datos tenemos) | 5 días hábiles (art. 14) | 10 días corridos (art. 14) |
| Rectificación, actualización o supresión | 5 días hábiles (art. 15) | 5 días hábiles (art. 16) |

**[A CONFIRMAR EN LA REVISIÓN LEGAL]** Los plazos, y desde cuándo se cuentan.

## Pasos

1. **Acusar recibo el mismo día o el siguiente.** Responder que el pedido llegó y que la respuesta llega en 5 días
   hábiles como máximo. Si falta información para encontrar los datos, pedirla en ese mismo mail: el lugar, la fecha
   aproximada, una frase de lo que escribió, el nombre que usó en una recomendación y si fue por el formulario o por el
   chat.
2. **Anotar el pedido** en el registro (ver abajo) con una referencia: `hola-AAAA-MM-DD` (o `-2`, `-3` si hay más de uno
   ese día).
3. **Buscar, sin borrar** (dry run, solo lectura):

   ```bash
   python -m scripts.delete_personal_data --text "<frase o nombre>" [--since AAAA-MM-DD --until AAAA-MM-DD]
   ```

   El script busca en `suggestions`, `place_reports`, `place_evidence` y el texto de los turnos marcados del chat
   (`agent_log`, agent `chatbot`). Lista cada coincidencia con su id, su fecha y un extracto. **Revisar que cada fila sea
   de la persona que lo pide**: una frase corta puede coincidir con textos de otras personas. Si hace falta, afinar el
   texto o las fechas.
4. **Buscar en el buzón**: los mails al admin (avisos urgentes y resumen diario) copian las notas de sugerencias y los
   textos de los reportes. Buscar la misma frase en la casilla de Zoho y en `hola@`.
5. **Responder según el pedido:**
   - **Acceso:** mandar lo que se encontró: el texto completo de cada fila (se lee de la base) y, si corresponde, que
     hay copias en los avisos por email. Aclarar que no guardamos nombre, email ni teléfono de quien usa el sitio, salvo
     el nombre opcional de una recomendación.
   - **Borrado:**
     ```bash
     python -m scripts.delete_personal_data --text "<frase>" --apply --request hola-AAAA-MM-DD            # todo lo listado
     python -m scripts.delete_personal_data --text "<frase>" --apply --request hola-AAAA-MM-DD --ids <id> <id>   # solo esas
     ```
     Después, borrar los mails del buzón que copian ese texto. El script deja un registro en `agent_log`
     (agent `privacy`) con la referencia, los conteos y los ids borrados, sin el contenido ni el texto buscado.
     Si la fila era una recomendación publicada, deja de verse en el sitio en ese momento.
   - **Rectificación:** si es una recomendación publicada, lo más simple es ofrecer borrarla y que la mande de nuevo. Si
     prefiere corregirla, la corrección es un `UPDATE` en producción: mostrar el SQL literal, hacer el ensayo
     begin/rollback y aplicarlo recién después del "dale" (regla vigente).
   - **Oposición o retiro del consentimiento:** igual que el borrado, para lo que ya mandó.
6. **Cerrar el pedido:** responder qué se hizo y cuándo, y anotar la fecha de respuesta en el registro.

## Lo que el script no cubre

- **Contadores del chat (`chat_usage`):** solo guardan un identificador al azar del navegador y un HMAC de la IP. Se
  borran solos a los 7 días (purga semanal). Si la persona quiere, puede borrar su identificador desde el navegador
  ("borrar datos del sitio").
- **Datos que quedan en el navegador (`localStorage`):** los borra la propia persona desde la configuración del
  navegador.
- **Datos de un negocio (`places`):** no son datos de quien usa el sitio. Si el pedido lo hace el negocio (por ejemplo,
  que no lo contactemos más o que corrijamos un dato), se trata con las reglas de `places`: `status='discarded'` más un
  encabezado `CORRECCIÓN MANUAL`, nunca un `DELETE`.
- **Logs de los proveedores** (Supabase, Cloudflare, GitHub, Resend, Anthropic): no los controlamos. Si piden
  información sobre esos datos, contar qué proveedor los procesa (ver la política) y que la retención depende de cada
  uno.

## Registro de pedidos

Llevarlo fuera del repositorio (tiene datos personales), por ejemplo en una planilla privada. Una fila por pedido:

| Referencia | Fecha de llegada | Tipo (acceso / rectificación / supresión / oposición) | Qué se encontró | Qué se hizo | Fecha de respuesta |
|---|---|---|---|---|---|

La referencia es lo único que se repite en `agent_log`, así se puede vincular sin guardar datos personales en la base.
Esas constancias (`agent='privacy'`) se guardan **5 años**; el resto de `agent_log`, 1 año (purga semanal).
