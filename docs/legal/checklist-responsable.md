# Checklist del responsable (Santiago)

> 2026-09-29, actualizado 2026-09-30 (fase 2). Tareas que no puede hacer el código. Las referencias legales son
> orientativas: confirmalas en la revisión legal.

## Uruguay — URCDP (Ley 18.331)

- [ ] **Registrar la base de datos** en el Registro de Bases de Datos Personales de la URCDP (art. 28). Datos para el
      formulario: responsable (persona física, Uruguay), finalidad (mapa comunitario de lugares sin gluten, moderación y
      seguridad del chat), categorías de datos (sección 2 del inventario), datos sensibles (ver abajo), encargados y
      transferencias internacionales (sección 6), medidas de seguridad (RLS, grant por columna, claves solo en el
      servidor) y plazos de conservación (política, sección 6).
- [ ] Preguntar si alcanza con **una sola base** o si hay que registrar varias (comunidad, outreach a negocios, logs del
      chat).
- [ ] Declarar o resolver los **datos sensibles**: `owner_celiac` (ya no se junta; columnas a borrar desde el 2026-10-07),
      los turnos del chat con síntomas (30 días) y los textos libres.
- [ ] Confirmar si **Brasil** (base en `sa-east-1`) y **Estados Unidos** (Anthropic, Resend, Google, Cloudflare,
      GitHub, Zoho) necesitan autorización o una garantía para la transferencia internacional (arts. 23 y siguientes).

## Argentina — AAIP (Ley 25.326)

- [ ] **Consultar a la AAIP** si una base de un responsable domiciliado en Uruguay, que junta datos de personas en
      Argentina por un sitio web, tiene que inscribirse en el Registro Nacional de Bases de Datos (art. 21).
- [ ] Preguntar si la transferencia a Brasil y a Estados Unidos necesita cláusulas contractuales o si alcanza con el
      consentimiento (art. 12).

## Revisión legal (abogado/a con práctica en datos personales, UY y AR)

Los textos publicados no llevan marcas: en cada duda se eligió la **lectura más prudente**. Estas son las decisiones que
tiene que confirmar la revisión (política = `politica-de-privacidad.md`, términos = `terminos-de-uso.md`):

- [ ] **Datos de salud en textos libres y en el chat** (política 3.4 y 4). Lectura prudente: no se piden, se pide no
      escribirlos, no se publican, plazos cortos (30 días en el chat) y borrado a pedido. No se pide un consentimiento
      expreso por escrito antes de chatear. ¿Alcanza, o hace falta una casilla de consentimiento para el chat?
- [ ] **Menores de edad** (política 9, términos 1; redacción de la v1.1). El sitio está pensado para personas adultas
      y mirar el mapa no tiene límite; a quien tiene menos de 18 años se le pide usar los formularios, los votos y el chat
      acompañado por una persona adulta responsable. No se exige una edad ni una autorización porque, sin cuentas, no se
      pueden verificar; los datos de una persona menor se borran si una madre, un padre o un tutor avisa. ¿Alcanza para
      Uruguay y Argentina, o hace falta un mecanismo de consentimiento de los padres?
- [ ] **Transferencia internacional** (política 7). Lectura prudente: se informa que los países pueden no tener un
      nivel equivalente, la transferencia se apoya en el consentimiento y en los compromisos contractuales de cada
      proveedor. ¿Hace falta algo más (autorización de la URCDP, cláusulas firmadas)?
- [ ] **Plazo de respuesta** (política 8, runbook). Lectura prudente: 5 días hábiles para todo pedido (el más corto de
      referencia: Uruguay arts. 14 y 15; Argentina art. 16; el acceso en Argentina es de 10 días corridos, art. 14).
- [ ] **Leyendas de la Disposición 10/2008** (política 8). Se incluyeron las dos, con la AAIP en lugar de la Dirección
      Nacional. Confirmar la redacción vigente y si además tienen que aparecer **en cada formulario** (la disposición
      pide que se vean en los formularios de recolección; hoy los formularios enlazan a la política).
- [ ] **Limitación de responsabilidad** (términos 7). Lectura prudente: “en la medida en que lo permita la ley” y sin
      renunciar a los derechos de consumo (Ley 17.250, Ley 24.240). ¿Alcance real para un servicio gratuito?
- [ ] **Ley aplicable y jurisdicción** (términos 9). Lectura prudente: ley uruguaya, sin imponer tribunales y dejando a
      salvo los derechos y la jurisdicción del domicilio de quien usa el sitio.
- [ ] **Idioma que prevalece** (política 11, términos 9): el español.
- [ ] Revisar el **outreach a negocios**: scraping del email de contacto en el sitio del negocio, emails no solicitados
      y opt-out (y el plazo de 2 años desde el último contacto).
- [ ] Revisar la publicación de recomendaciones con nombre (consentimiento en el aviso del campo) y la moderación.
- [ ] Revisar la relación con los aliados (sección Aliados, `rel="sponsored"`).

## Proveedores

- [x] País y retención de cada proveedor, con fuentes oficiales (inventario, §6, fase 2).
- [x] Plan de Supabase: **Free** (confirmado por el responsable, 2026-10-05): 1 día de logs (la política, §7, lo dice así) y sin
      copias de respaldo automáticas. **Si se cambia de plan, revisar esa fila y los respaldos, y publicar una versión nueva.**
- [ ] Leer y archivar el DPA de cada proveedor (Supabase, Anthropic, Resend, Google, Cloudflare, GitHub, Zoho, Tavily,
      CARTO) y anotar si se acepta por defecto o hay que firmarlo.
- [x] Zoho configurado, con una regla que borra automáticamente los avisos internos a los **90 días**, como dice la
      política (confirmado por el responsable, 2026-10-05).
- [ ] Sin publicar por el proveedor (se informa así en la política): cuánto guardan la IP Google Fonts, GitHub Pages,
      unpkg y los logs de Cloudflare. Opcional: servir las tipografías y Leaflet desde el propio sitio para no enviar la
      IP a Google Fonts ni a unpkg.

## Implementación

- [ ] P6 — `owner_celiac`: etapa 1 hecha; etapa 2 en la próxima tanda de prompts; etapa 3, el SQL
      `db/migrations/2026-10-07-drop-owner-celiac.PENDING.sql`, el 2026-10-07 o después.
- [x] P1 — `scripts/delete_personal_data.py` + `runbook-pedidos-de-datos.md` (fase 1).
- [x] P2 — purga de `chat_usage` a los 7 días + HMAC de la IP (fase 1).
- [x] P3 — `places` con grant por columna (fase 1).
- [x] P4 — reseñas de Google en la purga semanal (fase 1).
- [x] P5 — plazos de 2 años / 1 año en la purga semanal: activos (corrida del 2026-10-05 verificada en Actions).
- [x] P7 — proveedores (fase 2).
- [x] P8 — las recomendaciones del chat no se publican; el aviso en el chat va en la próxima tanda de prompts.
- [x] Publicar `privacidad.html` y `terminos.html` (v1.0, 2026-10-05, solo ES), links en el footer y avisos en los
      formularios y el chat. La traducción al inglés queda sin hacer.

## Después de publicar

- [ ] Llevar un registro simple de los pedidos de derechos (fecha, qué se pidió, qué se hizo, fecha de respuesta).
- [ ] Revisar la política cada vez que se sume un dato, un proveedor o un agente, y como mínimo una vez por año.
