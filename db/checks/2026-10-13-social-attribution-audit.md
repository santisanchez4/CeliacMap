# Auditoría — citas de redes sociales sin autor verificable (2026-10-13)

Solo lectura sobre producción (`SELECT`), más la repetición de tres corridas viejas del buscador sobre sus fuentes congeladas
(`--replay`: sin búsquedas, sin escrituras). **No se cambió ningún estado.** `places` 1387 filas y `place_evidence` 19, igual que antes.

**Regla aplicada** (la del arreglo, `agents/evidence_finder.py`): una fuente de Instagram / Facebook es del negocio solo si la cuenta
que publica es una cuenta oficial suya (la de su fila, o una enlazada desde su sitio propio). `instagram.com/reel/…` y `/p/…` no dicen
quién publicó: **no atribuible**.

## Resumen

| Pregunta | Respuesta |
|---|---|
| Filas de `place_evidence` con URL social | 8: 6 de tipo `social` (agente Social, corrida del 2026-10-01) y 2 de tipo `admin` (revisión manual de hoy) |
| De las 6 `social`, autor verificable | **0**: 5 son un reel o un post sin cuenta en la dirección y 1 es una página de tema de Instagram, no una cuenta |
| Lugares **aprobados en el mapa** que dependen de esas citas | **Ninguno**: los 6 lugares están en `needs_review` |
| Propuestas del buscador aceptadas con una cita social | **Ninguna**: las únicas filas `web` de `place_evidence` son las de Zero Helados (sitio propio, de hoy) |
| Aprobados cuyo `social_url` es un reel o un post | 8 (de 207 filas en total con ese problema; más 34 con un post de Facebook). Su aprobación no salió de una cita social: salió del nombre |

## 1. Filas `social` de `place_evidence` (6) — todas en lugares fuera del mapa

Las seis las escribió el agente Social el 2026-10-01 y son la **única** evidencia de su lugar (1 fila, 0 reseñas): el veredicto del
Validator de ese día se apoyó por completo en ellas. Ninguna llegó a aprobarse.

| Lugar | Estado | Confianza | URL de la cita | Autor | Qué dice la cita | Dependencia |
|---|---|---|---|---|---|---|
| Atahualpa (Montevideo) | needs_review · `celiac_friendly` | 0,62 | `instagram.com/reel/DZFheLlJnEF` | no verificable | Hashtags #SinTACC #ContaminaciónCruzada y una dirección (Millán 3294) | Total (única evidencia) |
| Dalí (Montevideo) | needs_review · `options_available` | 0,62 | `instagram.com/p/DLYQfHKy4rP` | no verificable (el texto nombra «dalimontevideo», la dirección no) | «hamburguesa CON Y SIN TACC» | Total |
| **Empieza entero** (Montevideo) | needs_review · `options_available` | 0,52 | `instagram.com/p/DduWNHUivVN` | no verificable | «100% libre de gluten. Recoleta: Montevideo 1480, CABA. Rosario II: Montevideo 319» — **es una publicación de GOUT (Argentina)**; «Empieza entero» es el comienzo del texto, no un negocio. Tiene frase de exclusividad | Total. El Validator lo frenó por la inconsistencia geográfica y dejó el flag de 100% pendiente |
| La Clave (El Tesoro) | needs_review · `options_available` | 0,52 | `instagram.com/p/Da6JT08OJfb` | no verificable | «Comer sin gluten también es comer rico… El sabor de La Clave, ahora en tu freezer» | Total |
| **Pan Sin Gluten En Panetera** (Montevideo) | needs_review · `options_available` | 0,52 | `instagram.com/popular/pan-sin-gluten-en-panetera` | no es una cuenta: es una página de tema de Instagram | «Watch short videos about pan sin gluten en panetera…» | Total. **No es un negocio** |
| Sabores propios (Montevideo) | needs_review · `celiac_friendly` | 0,62 | `instagram.com/reel/DPh9gFTDMP7` | no verificable | «Helado artesanal libre de gluten… #aptocelíaco», con direcciones | Total |

Lectura: el daño en el mapa es cero, pero dos de las seis filas ni siquiera son un negocio real («Empieza entero» y «Pan Sin Gluten En
Panetera»): son candidatos a `discarded` con una `CORRECCIÓN MANUAL` («no es un comercio»). No lo hago sin tu decisión.

## 2. Filas `admin` con URL social (2) — decisiones manuales, no se tocan

| Lugar | Estado | URL | Autor contra la fila |
|---|---|---|---|
| FERNILAND S.A. | approved · verde · `APROBACIÓN MANUAL` 2026-10-13 | `instagram.com/fernilanduy` | Coincide con el `social_url` de la fila |
| Me Gusta | approved · verde · `APROBACIÓN MANUAL` 2026-10-13 | `instagram.com/megusta_uy` | La fila no tiene `social_url`: la cuenta figura solo en tu nota y en la evidencia |

Sugerencia sin ejecutar: cargar `social_url` en Me Gusta y Cooperativa Helix, para que la cuenta oficial quede en la fila.

## 3. Aprobados en el mapa cuyo `social_url` es un reel o un post (8)

Ninguno tiene filas en `place_evidence` ni reseñas guardadas: **su aprobación no dependió de una cita social** (cuando se validaron,
la evidencia del agente Social todavía no llegaba al Validator). Lo que muestran sus notas es otro riesgo ya documentado: se aprobaron
por el **nombre**. Con el buscador corregido, nada de redes se les puede atribuir mientras su `social_url` siga siendo una publicación.

| Lugar | Color | Confianza | Validado | En qué se apoyó el Validator (su nota) | En tu cola de 100% |
|---|---|---|---|---|---|
| ALITA GLUTEN FREE (San Justo, AR) | 🟢 verde | 0,87 | 2026-07-17 | El nombre incluye «GLUTEN FREE» | Sí |
| Celilife (Ciudad de la Costa, UY) | 🟢 verde | 0,85 | 2026-06-07 | El nombre «implica» un negocio para celíacos | Sí |
| Comarca Sin Gluten (Viedma, AR) | 🟢 verde | 0,87 | 2026-06-09 | El nombre «es inequívoco» | Sí |
| MisiaMasa Sin Gluten (Buenos Aires, AR) | 🟢 verde | 0,93 | 2026-06-07 | El nombre incluye «Sin Gluten» | Sí |
| Bella Vista SINTACC (Bella Vista, AR) | 🟠 ámbar | 0,85 | 2026-07-24 | El nombre incluye «SINTACC» | No |
| QQ - Quinoa Queen - Cocina SIN TACC… (Maschwitz, AR) | 🟠 ámbar | 0,88 | 2026-07-09 | El nombre incluye «Cocina SIN TACC» | No |
| By Gessi Cocina Inclusiva (Montevideo, UY) | 🟠 ámbar | **0,82** | 2026-06-05 | «Cocina Inclusiva» sugiere restricciones alimentarias | No |
| Géant Fresh Market (Montevideo, UY) | 🟠 ámbar | **0,70** | 2026-06-07 | Conocimiento propio del modelo: «a large supermarket chain… typically stocks…» | No |

By Gessi y Géant están, como Alárabi y gluteno Sana Ingesta, por debajo del gate actual de 0,85.

## 4. Propuestas viejas del buscador que cambian con el arreglo (repetición sobre congelados)

Estas propuestas eran solo reportes locales; ninguna se aceptó en la base con una cita social. Sirven para medir el efecto.

| Lugar | Propuesta antes → ahora | Por qué | Estado actual en la base |
|---|---|---|---|
| Apto Libre de Gluten (San Nicolás, AR) | 100 → insuficiente | Sus 3 citas eran de redes (`facebook.com/aptolibredeglutenok`, `instagram.com/apto.libredegluten` y un reel); la fila no tiene `social_url` | approved · verde · 0,82 · en tu cola de 100% (aprobado por el nombre) |
| Pagana Gluten Free (Ciudad de la Costa, UY) | 100 → options | La frase de exclusividad venía de un reel sin autor; su cuenta oficial (`paganaglutenfree`) sí está en la fila | approved · verde · 0,88 · en tu cola de 100% |
| @TACCTOMDP (Mar del Plata, AR) | options → insuficiente | Su única cita era un post de Instagram sin autor | approved · verde · 0,95 · en tu cola de 100% |
| Matilde Gluten Free (San Pedro, AR) | 100 → 100 | Pierde 2 reels; quedan 2 citas de páginas web | approved · verde · 0,95 · en tu cola de 100% |
| GOUT GLUTEN FREE (Buenos Aires, AR) | 100 → 100 | Pierde la cita de `instagram.com/goutglutenfree` (la fila no tiene `social_url`); quedan 3 | `APROBACIÓN MANUAL` 2026-10-06: no se toca |
| Selkkis Gluten Free (Montevideo, UY) | options → insuficiente | Sus citas eran de Facebook y de un reel | `APROBACIÓN MANUAL` 2026-10-06: no se toca |
| Rikuras Sin Gluten (Montevideo, UY) | options → insuficiente | Su cita era de `facebook.com/rikurassingluten` | `APROBACIÓN MANUAL` 2026-09-27: no se toca |

Dos cambios más de esas repeticiones no vienen del arreglo sino de que el modelo de alcance no responde siempre igual (TACCOFF
options → 100; Vichenzo Monserrat options → insuficiente): ninguno tenía citas de redes.

**Costo de la regla nueva, a la vista:** perfiles que a simple vista son del negocio (`instagram.com/apto.libredegluten`,
`facebook.com/rikurassingluten`) quedan «no atribuibles» cuando la fila no tiene esa cuenta y el sitio propio no la enlaza. Se resuelve
cargando el perfil en `social_url` (decisión del admin) o pasando la web de la ficha de Google; no aflojando la regla.

## Lo que queda para decidir (nada ejecutado)

1. «Empieza entero» y «Pan Sin Gluten En Panetera»: ¿los descarto con `CORRECCIÓN MANUAL` (no son comercios)?
2. Los 6 de la sección 1 y los 207 + 34 lugares con una publicación como `social_url` salen del agente Social, que sigue guardando el
   post del que sacó el lead como perfil y como evidencia. Propongo arreglarlo en un PR aparte (guardar el perfil solo cuando la
   dirección nombra la cuenta, y marcar la evidencia de un post sin autor).
3. Los 4 aprobados de la sección 4 que siguen en verde por el nombre ya están en tu cola de 100%; el buscador ya no les propone 100
   con citas de redes.
