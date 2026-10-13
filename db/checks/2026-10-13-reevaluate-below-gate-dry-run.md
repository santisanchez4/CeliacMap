# Dry-run — cuatro aprobados por debajo del gate de 0,85 (2026-10-13)

`python db/checks/reevaluate_dry_run.py --ids … --extra-evidence db/checks/2026-10-13-reevaluate-extra-evidence.json`

**Solo lectura: no se cambió ningún estado.** El script no tiene `--apply`. Para cada lugar: ficha de Google en vivo (estado, sitio y
reseñas con señal de gluten, usadas en memoria y no guardadas), buscador de evidencia con la regla nueva de atribución (8 búsquedas de
Tavily en total) y el Validator actual (`RUBRIC` y gates sin cambios), **tres veces por variante** porque el modelo no responde siempre
igual. Para Alárabi y gluteno hay una segunda variante que suma la habilitación de la IM (ambas vencidas) como evidencia.

Los cuatro se aprobaron en junio con el rubric binario anterior, sin evidencia: por el nombre o por conocimiento propio del modelo.

## Resultado

| Lugar | Hoy en el mapa | Veredicto nuevo (3 corridas) | Con la habilitación IM |
|---|---|---|---|
| Alárabi Cocina Inclusiva | approved · ámbar · 0,82 | needs_review 0,52 / 0,52 / 0,52 | needs_review 0,52 / 0,52 / 0,52 |
| gluteno Sana Ingesta | approved · ámbar · 0,72 | needs_review 0,62 / 0,62 / 0,62 | needs_review 0,72 / 0,72 / 0,62 |
| By Gessi Cocina Inclusiva | approved · ámbar · 0,82 | **discarded** 0,20 / 0,20 / 0,25 | (no figura en la capa de la IM) |
| Géant Fresh Market | approved · ámbar · 0,70 | needs_review 0,52 / 0,52 / 0,52 | (no figura en la capa de la IM) |

Ninguno llega al gate de aprobación automática. Ninguno sube a verde.

## Alárabi Cocina Inclusiva (Colonia 1779) — `09713c52…`

- **Ficha de Google:** `OPERATIONAL`, sin sitio web. La fila no tiene cuenta oficial.
- **Citas atribuibles (2), las dos del mismo blog de viajes** (`pajaritosviajeros.com/america/viaje-sin-gluten-uruguay`):
  «El otro restaurante al que fuimos, es el restaurante Alárabi, Cocina Inclusiva, que es 100% sin gluten y que cuenta con variedad
  opciones para comer.» y «Para comer, aprovechamos para ir a un par de restaurantes aptos para celiacos…».
- **No atribuibles (10):** comentarios de un reel de Instagram sin autor verificable; no cuentan.
- **Reseñas de Google con señal (2), las dos negativas:** una persona dice que no recomienda la comida para celíacos y que la
  elaboración le parece peligrosa para quien es sensible al gluten; otra supone que la comida está contaminada y cuenta que recibió
  un producto distinto del pedido. Son opiniones de terceros, sin verificar.
- **Habilitación IM:** «Libre de gluten- Comidas al paso», vencida el 30/11/2025.
- **Razón del Validator:** hay evidencia de que es un espacio sin gluten (el blog; la habilitación), pero las reseñas negativas de
  celíacos con mención de contaminación cruzada impiden aprobarlo sin revisión humana. El modelo propuso 100% y el tope lo dejó en
  `celiac_friendly` con el flag de 100% pendiente.

**Propuesta: mandarlo a revisión (`needs_review`)** hasta que confirmes con el local o por conocimiento propio. Es el único de los
cuatro con una señal de riesgo concreta para celíacos. Alternativa más suave: mantenerlo en el mapa con la advertencia comunitaria.

## gluteno Sana Ingesta (Dr. José Scoseria 2637) — `e3e6dd26…`

- **Ficha de Google:** `OPERATIONAL`, sitio `glutenouy.com`. Su sitio enlaza la cuenta `instagram:glutenosanaingesta` (relevamiento
  de cuentas), pero la fila no la tiene cargada.
- **Citas atribuibles: ninguna.** El buscador encontró frases como «Todo pensado para disfrutar sin TACC» y «celíacos e intolerantes
  al gluten, sin perder ese sabor casero», pero en reels sin autor en la dirección: **no atribuibles**.
- **Reseñas de Google con señal (1), positiva:** dice que siempre fue su opción segura para comer sin gluten, con algún detalle
  puntual «nada grave».
- **Habilitación IM:** «Comidas al paso- Libre de gluten- Elaboración de comidas preparadas», vencida el 30/04/2024.
- **Razón del Validator:** el registro oficial y la reseña apoyan que se especializa en sin gluten, pero la habilitación está vencida
  y no hay descripción de protocolo ni certificación vigente.

**Propuesta: mantenerlo en ámbar.** No hay ninguna señal en contra; lo que falta es evidencia explícita, no seguridad. Sugerencia:
cargar su cuenta oficial para que el buscador pueda atribuirle sus publicaciones, y volver a correr este dry-run.

## By Gessi Cocina Inclusiva (Treinta y Tres 1374) — `d6a3edb8…`

- **Ficha de Google:** `OPERATIONAL`, sitio `bygessi.com`. El `social_url` de la fila es un reel.
- **Citas atribuibles: ninguna.** No atribuibles: «Chef y formadora en cocina sin gluten. Educación Gastronómica Sin Gluten»
  (`facebook.com/gessilusich.pasteleriaartesanal`), y publicaciones de `instagram.com/bygessi.singluten`.
- **Reseñas de Google con señal (4), todas positivas y todas sobre cursos:** hablan de clases, de un curso online de panificados sin
  gluten, de «la profe» y de «la escuela byGessi».
- **Razón del Validator:** parece una escuela o servicio de cursos de cocina sin gluten, no un restaurante, café ni comercio donde
  comer o comprar; no hay evidencia de venta de comida al público.

**Propuesta: sacarlo del mapa (`discarded`) con una `CORRECCIÓN MANUAL`** si confirmás que solo da cursos. Si además vende al
público, corresponde revisión, no descarte.

## Géant Fresh Market — `9f9abf53…`

- **Ficha de Google:** `OPERATIONAL`, sitio `geant.com.uy`, que enlaza las cuentas `instagram:geantuy` y `facebook:hipermercadogeant`.
- **Citas atribuibles: ninguna.** Las que hay son de **otras cuentas** del mismo grupo («Del 27 de abril al 10 de mayo encontrá
  ofertas imperdibles en productos gluten free en Fresh Market», en `facebook.com/discouruguay` y `facebook.com/DevotoOficial`) o de
  reels sin autor.
- **Reseñas de Google con señal: ninguna.**
- **Razón del Validator:** un supermercado que probablemente tiene productos sin TACC, sin ninguna evidencia explícita de sección,
  etiquetado o protocolo. En junio se aprobó por conocimiento propio del modelo.

**Propuesta: mandarlo a revisión (`needs_review`)**, o mantenerlo con una `APROBACIÓN MANUAL` tuya si lo conocés: hoy no tiene
ninguna evidencia en el sistema.

## Observaciones

- La habilitación de la IM, aun vencida, sube un escalón la confianza de gluteno (0,62 → 0,72 en dos de tres corridas) y no cambia la
  de Alárabi, donde pesan más las reseñas negativas.
- En los cuatro, lo que el buscador encontró en redes quedó «no atribuible»: ninguna fila tiene su cuenta oficial cargada
  (`db/checks/2026-10-13-official-accounts-survey.md`).
- En esta corrida no se pudieron leer los enlaces del sitio de gluteno (la descarga falló esa vez); no cambia el resultado, porque
  las citas estaban en reels sin autor.

## Cierre — qué se decidió (2026-10-13)

Las propuestas de arriba son las del dry-run; lo que sigue es lo que decidió el admin (Santiago Sánchez) el mismo día. En los cuatro
casos la nota anterior del Validator quedó debajo del encabezado nuevo, y `validation_confidence` y `verified` no se tocaron.

| Lugar | Decisión final | Estado | Archivo en `db/fixes/` |
|---|---|---|---|
| Géant Fresh Market | Descartado: cadena de supermercados, comercio general; no aplica al mapa | `approved` → `discarded` | `2026-10-13-below-gate-admin-decisions.sql` |
| By Gessi Cocina Inclusiva | Descartado: escuela de cocina, sin venta de comida ni productos al público | `approved` → `discarded` | `2026-10-13-below-gate-admin-decisions.sql` |
| Alárabi Cocina Inclusiva | A revisión para que el admin lo verificara, y luego aprobado por él como 100% | `approved` → `needs_review` → `approved` · `gluten_free_100` | `2026-10-13-below-gate-admin-decisions.sql`, `2026-10-13-alarabi-admin-evidence.sql`, `2026-10-13-alarabi-manual-approval.sh` |
| gluteno Sana Ingesta | Sin cambio de estado ni de nivel; solo se cargó su cuenta oficial | sigue `approved` · `celiac_friendly` | `2026-10-13-below-gate-admin-decisions.sql` |

- **Géant Fresh Market** — `CORRECCIÓN MANUAL 2026-10-13: no aplica al mapa…`. Se apartó de la propuesta del dry-run (revisión o
  aprobación manual): el admin decidió que una cadena de comercio general no corresponde a este mapa.
- **By Gessi Cocina Inclusiva** — `CORRECCIÓN MANUAL 2026-10-13: no es un comercio…`, como se propuso.
- **Alárabi Cocina Inclusiva** — tres pasos, cada uno en su archivo:
  1. `2026-10-13-below-gate-admin-decisions.sql`: `OVERRIDE MANUAL` que lo baja a `needs_review` con lo que había que verificar (las
     dos reseñas negativas resumidas, sin su texto; la cita del blog; la habilitación vencida de la IM). La cita del blog entra
     también en `place_evidence` (`source = 'web'`).
  2. `2026-10-13-alarabi-admin-evidence.sql`: la revisión del propio admin como evidencia (dos filas `source = 'admin'`: la bio de
     `@alarabi__glutenfree` y la carta online) y su cuenta oficial en `social_url`. No aprueba nada.
  3. `2026-10-13-alarabi-manual-approval.sh`: `APROBACIÓN MANUAL` en 100% con `scripts.review_queue --approve … --level 100`. Las dos
     reseñas negativas quedan registradas, sin refutar, en el `OVERRIDE MANUAL` de abajo.
- **gluteno Sana Ingesta** — como se propuso: `social_url = https://www.instagram.com/glutenosanaingesta`, la cuenta que enlaza su
  propio sitio (`glutenouy.com`), para que el buscador de evidencia pueda atribuirle sus publicaciones. Queda pendiente volver a
  correr este dry-run con la cuenta cargada.

Los dos descartes son el origen de la regla de alcance del mapa (cadenas de comercio general y lugares que enseñan o informan sin
vender), que se trabaja como tarea aparte.
