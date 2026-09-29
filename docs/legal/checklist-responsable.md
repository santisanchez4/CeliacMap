# Checklist del responsable (Santiago)

> 2026-09-29. Tareas que no puede hacer el código. Las referencias legales son orientativas: confirmalas en la revisión
> legal.

## Uruguay — URCDP (Ley 18.331)

- [ ] **Registrar la base de datos** en el Registro de Bases de Datos Personales de la URCDP (art. 28). Datos para el
      formulario: responsable (persona física, Uruguay), finalidad (mapa comunitario de lugares sin gluten, moderación y
      seguridad del chat), categorías de datos (sección 2 del inventario), datos sensibles (ver abajo), encargados y
      transferencias internacionales (sección 6), medidas de seguridad (RLS, claves solo en el servidor).
- [ ] Preguntar si alcanza con **una sola base** o si hay que registrar varias (comunidad, outreach a negocios, logs del
      chat).
- [ ] Declarar o resolver los **datos sensibles**: `owner_celiac` (se elimina, 0 filas), los turnos del chat con
      síntomas (30 días) y los textos libres.
- [ ] Confirmar si **Brasil** (base en `sa-east-1`) y **Estados Unidos** (Anthropic, Resend, Google, Cloudflare,
      GitHub) necesitan autorización o una garantía para la transferencia internacional (arts. 23 y siguientes).

## Argentina — AAIP (Ley 25.326)

- [ ] **Consultar a la AAIP** si una base de un responsable domiciliado en Uruguay, que junta datos de personas en
      Argentina por un sitio web, tiene que inscribirse en el Registro Nacional de Bases de Datos (art. 21).
- [ ] Preguntar si la transferencia a Brasil y a Estados Unidos necesita cláusulas contractuales o si alcanza con el
      consentimiento (art. 12).
- [ ] Revisar si en Argentina hace falta un **aviso de derechos** con un texto obligatorio (el que remite a la AAIP
      como órgano de control) y agregarlo a la política.

## Revisión legal (abogado/a con práctica en datos personales, UY y AR)

- [ ] Revisar `politica-de-privacidad.md` y `terminos-de-uso.md`, en especial cada marca **[A CONFIRMAR EN LA REVISIÓN
      LEGAL]**: consentimiento para datos de salud en el chat, edad mínima, base de la transferencia internacional,
      plazos de respuesta, alcance de la limitación de responsabilidad frente a las leyes de consumo, jurisdicción y
      qué idioma prevalece.
- [ ] Revisar el outreach a negocios: scraping del email de contacto en el sitio del negocio, emails no solicitados y
      opt-out.
- [ ] Revisar la publicación de recomendaciones con nombre y la moderación.
- [ ] Revisar la relación con los aliados (sección Aliados, `rel="sponsored"`).

## Proveedores

- [ ] Leer y archivar la política de datos y el DPA de cada proveedor: Supabase, Anthropic, Resend, Google, Cloudflare,
      GitHub, Zoho, Tavily y CARTO. Anotar para cada uno el país, la retención y si el DPA se acepta por defecto o
      hay que firmarlo.
- [ ] Confirmar el centro de datos de la cuenta de **Zoho** y la región de las **Edge Functions** de Supabase.
- [ ] Confirmar cuánto tiempo guarda Anthropic los datos de la API y que no se usen para entrenar.

## Implementación antes de publicar (código, con plan y “dale” para producción)

- [ ] P6 — eliminar `owner_celiac` (`owner-celiac-plan.md`, etapas 1 a 4).
- [ ] P1 — procedimiento y script para atender pedidos de acceso, rectificación y supresión en todas las tablas y en
      el buzón, con registro de cada pedido.
- [ ] P2 — borrado automático de `chat_usage` y hash de IP con clave secreta.
- [ ] P3 — cerrar la lectura pública de `places.contact_email` y de las columnas de outreach.
- [ ] P4 — borrado semanal de las reseñas de Google (hoy 270 de 281 tienen más de 30 días; la próxima corrida mensual
      las borra el 2026-10-01).
- [ ] P5 — plazos de retención para sugerencias, reportes, votos, outreach, `agent_log` y el buzón.
- [ ] P8 — decidir qué pasa con las recomendaciones que llegan por el chat.
- [ ] Cambios de frontend (`cambios-frontend.md`).
- [ ] Registrar las decisiones en `docs/DECISIONS.md` y en el índice de `CLAUDE.md`.

## Después de publicar

- [ ] Llevar un registro simple de los pedidos de derechos (fecha, qué se pidió, qué se hizo, fecha de respuesta).
- [ ] Revisar la política cada vez que se sume un dato, un proveedor o un agente, y como mínimo una vez por año.
