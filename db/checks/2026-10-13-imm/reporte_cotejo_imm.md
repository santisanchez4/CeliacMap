# Reporte de cotejo — IM Montevideo (Locales_Gluten_Free) vs. CeliacMap

- **Fuente:** capa pública `Locales_Gluten_Free` de la Intendencia de Montevideo (Servicio de Regulación Alimentaria),
  última edición de la capa 25/01/2024. Archivo `imm_locales_libres_de_gluten.csv`, capturado el 2026-10-13: 35 locales
  (17 con habilitación vigente, 18 vencida).
- **Base:** lectura de producción del 2026-10-13, solo `SELECT` (630 filas de Uruguay en `places`, en cualquier estado;
  además una búsqueda por nombre en toda la tabla). **No se escribió nada.**
- **Método:** por sucursal — distancia entre coordenadas (≤ 100 m), nombre normalizado (sin tildes, mayúsculas ni
  S.A./S.R.L.) y dirección normalizada (calle + número de puerta). Cada coincidencia fue revisada a mano: el nombre solo
  no alcanza (RAMONA, ZERO y MI COCINA SIN GLUTEN se repiten).

## Cómo se guarda el color (esquema real)

- `places.safety_level`: **verde** = `gluten_free_100` ("Espacio 100% sin gluten"); **ámbar** = `celiac_friendly` u
  `options_available` ("Tiene opciones sin TACC"). La regla única es `safetyGroup()` en `js/map.js`.
- `places.status`: solo `approved` se ve en el mapa; `needs_review`, `discarded`, `pending` y `outreach_confirmed` no.
- No hay columna de "última validación". Se informa la fecha de la decisión manual que figura en `validation_notes`
  cuando existe, y la del último registro del Validator en `agent_log`.

## Resumen

| Grupo | Cantidad | Detalle |
|---|---|---|
| YA ESTÁ en el mapa | 11 | 8 verdes, 3 ámbar |
| YA ESTÁ en la base, fuera del mapa | 5 | 2 `needs_review`, 3 `discarded` |
| DUDOSO (coincidencia parcial) | 3 | |
| NO ESTÁ | 16 | |
| **Total** | **35** | |

## 1. YA ESTÁ — publicado en el mapa (11)

| # | IM (nombre · dirección) | En CeliacMap | Color | Status | Última validación | Dist. | Habilitación IM |
|---|---|---|---|---|---|---|---|
| 10 | MI COCINA SIN GLUTEN · Av. L. A. de Herrera 1387 | Mi cocina sin gluten · Av. L. A. de Herrera **1379** | 🟢 verde | approved | Manual 2026-09-26 (Validator 2026-06-04, 0.92) | 39 m | vigente hasta 06/04/2027 |
| 11 | MI COCINA SIN GLUTEN · San José 1284 | Mi Cocina Sin Gluten · San José 1284 | 🟢 verde | approved | Manual 2026-09-26 (Validator 2026-06-04, 0.93) | 0 m | vigente hasta 24/02/2027 |
| 13 | PECORINO · Bv. España 2571 | Pecorino - apto Celiacos · Bv. España 2571 | 🟠 ámbar (`celiac_friendly`) | approved | Validator 2026-06-04 (0.92) | 7 m | vigente hasta 01/12/2027 |
| 15 | RIKURAS SIN GLUTEN · H. Yrigoyen 1728 bis | Rikuras Sin Gluten · H. Yrigoyen 1728 bis | 🟢 verde | approved | Manual 2026-09-27 (Validator 2026-06-04, 0.95) | 14 m | vigente hasta 13/02/2028 |
| 16 | UN LUGAR SIN GLUTEN · Dr. D. Terra 2148 | Un Lugar Sin Gluten · Dr. D. Terra 2148 | 🟢 verde | approved | Manual 2026-09-27 (Validator 2026-06-04, 0.95) | 0 m | vigente hasta 30/10/2027 |
| 18 | ALARABI · Colonia 1779 | Alárabi Cocina Inclusiva · Colonia 1779 | 🟠 ámbar (`celiac_friendly`) | approved | Validator 2026-06-04 (0.82) | 0 m | vencida 30/11/2025 |
| 25 | GLUTENO · Dr. J. Scoseria 2637 | gluteno Sana Ingesta · Dr. J. Scoseria 2637 | 🟠 ámbar (`celiac_friendly`) | approved | Validator 2026-06-04 (0.72) | 4 m | vencida 30/04/2024 |
| 26 | GOÛT GLUTEN FREE · Solano García 2496 | **Casa & Dispensa** · Solano García 2496 (nombre actual del local) | 🟢 verde | approved | Override manual 2026-09-07 | 4 m | vencida 30/11/2025 |
| 30 | RAMONA · Av. L. A. de Herrera 1196 | Café Ramona - WTC · Av. L. A. de Herrera 1196 | 🟢 verde | approved | Override manual 2026-09-07 | 15 m | vencida 06/04/2024 |
| 31 | RAMONA · San José 900 | Café Ramona - Centro · San José 900 | 🟢 verde | approved | Override manual 2026-09-07 | 10 m | vencida 18/02/2025 |
| 33 | SELKKIS · Paysandú 1846 bis | Selkkis Gluten Free · Paysandú 1846 bis | 🟢 verde | approved | Manual 2026-10-06 (Validator 2026-06-04, 0.95) | 5 m | vencida 14/07/2025 |

Notas:

- **#10:** mismo nombre y misma cuadra, pero el número de puerta difiere (IM 1387, base 1379). Lo tomo como la misma
  sucursal; conviene confirmar el número.
- **#18 y #25** se aprobaron en junio con el rubric binario anterior y confianza menor a 0,85 (0,82 y 0,72); hoy no
  pasarían el gate automático. No es parte de este cotejo, queda señalado.
- **#18:** además existe una fila duplicada `discarded` (fuente social, marcada "duplicado de…"). Correcto como está.
- **#26 (corregido el 2026-10-13):** en la primera versión figuraba como dudoso. El fix del 2026-09-07 que aprobó Casa & Dispensa ya
  anotaba «formerly Goût Gluten Free»: la habilitación IM es de ese local, que está en el mapa en verde con su nombre actual. La fila
  «Goût» de Paraguay 1962 (needs_review) es otro negocio y no se toca.
- **#31:** en San José 894 hay otra fila verde, "La Panadería de Ramona" (17 m); la IM tiene una sola habilitación en el 900.
- Cuatro de los verdes (**#26, #30, #31, #33**) figuran con habilitación vencida en la fuente.

## 2. YA ESTÁ en la base, pero NO en el mapa (5)

Coincidencia segura por nombre + dirección; el Validator ya los juzgó y no los aprobó.

| # | IM (nombre · dirección · rubro) | En CeliacMap | Status | Última validación | Dist. | Habilitación IM |
|---|---|---|---|---|---|---|
| 3 | ARTESANIA PASTELERA · Av. Gral. Rivera 3431 · Exp-elab | Artesanía Pastelera | needs_review (0.52) | Validator 2026-09-06 | 6 m | vigente hasta 30/10/2027 |
| 6 | FERNILAND · Cochabamba 2949 · Elab | FERNILAND S.A. | discarded (0.10) | Validator 2026-07-20 | 37 m | vigente hasta 21/10/2027 |
| 9 | ME GUSTA · Carlos Roxlo 1374 · Exp-elab | Me Gusta | discarded (0.75) | Validator 2026-06-04 | 4 m | vigente hasta 04/08/2028 |
| 23 | ENCANTO · Uruguayana 3419 bis · Elab | Alimentos Encanto | needs_review (0.52) | Validator 2026-09-06 | 2 m | vencida 17/05/2024 |
| 28 | HELIX · Joffre 1005 · Elab | Cooperativa de Trabajo Helix Uruguay | discarded (0.95) | Validator 2026-06-04 | 1 m | vencida 28/05/2024 |

En los cinco el motivo fue el mismo: el Validator no tenía ninguna evidencia de "sin gluten / sin TACC" (solo nombre y
dirección). La habilitación de la IM es justamente la evidencia que faltaba.

**Decisión que necesito para la Fase 2:** estas filas no pueden volver a entrar como `pending` (ya existen, y la regla
vigente dice que un `discarded` / `needs_review` no se manda de nuevo por `pending`). Propongo sumarles la evidencia en
`place_evidence` (IM + web/redes) y **re-evaluarlas en su misma fila con el Validator**, como hacen el re-validador
retroactivo y el handler de reportes. Alternativa: dejarlas fuera de este trabajo.

## 3. DUDOSO — coincidencia parcial (3)

| # | IM (nombre · dirección) | Lo que hay en la base | Por qué es dudoso | Habilitación IM |
|---|---|---|---|---|
| 12 | MILENA GLUTEN FREE · El Greco 5994 | Milena Gluten Free · Bv. Gral. Artigas 2748 — 🟢 verde, approved (manual 2026-10-06) | Mismo nombre, a 10,4 km. ¿Otra sucursal, planta de elaboración o dirección anterior? | vigente hasta 26/09/2028 |
| 27 | HELADERIA ZERO · Av. Millán 3665 | **Piu Helados Prado** · Av. Millán 3665 — 🟢 verde, approved (manual 2026-09-27), a 17 m | Misma dirección, otro nombre: probable cambio de marca o de dueño. | vencida 09/03/2026 |
| 32 | RICCA · Cuaró 3139 | **Ríccoli** · Cuaró 3151 — needs_review (0.52, Validator 2026-07-17), a 27 m | Nombre parecido, misma cuadra, otro número de puerta. Puede ser el mismo negocio o un vecino. | vencida 16/08/2024 |

## 4. NO ESTÁ (16)

Sin fila en `places` por coordenadas, nombre ni dirección. La columna "Tipo" es una lectura **preliminar** del rubro y los
giros de la IM (`Exp` = expendio al público, `Elab` = elaboración); la clasificación real sale de la Fase 2.

| # | IM (nombre) | Dirección | Rubro | Tipo (preliminar) | Habilitación IM |
|---|---|---|---|---|---|
| 1 | (sin nombre) JOVECA S.R.L. | Convenio 827 bis | Elab | Elaborador — posible "no aplica al mapa" | vigente hasta 31/03/2027 |
| 2 | (sin nombre) TOMASI ZUNINO ENRIQUE | Manuel Correa 3514 bis | Elab | Panificadora — posible "no aplica al mapa" | vigente hasta 04/08/2027 |
| 4 | BLARTIS S.A. | Ruta 1 8398 | Exp | Distribuidor sin depósito — posible "no aplica al mapa" | vigente hasta 06/02/2027 |
| 5 | CELICATESSEN | Santa Mónica 2533 | Elab | Elabora y vende alimentos libres de gluten — a verificar si atiende al público | vigente hasta 27/09/2028 |
| 7 | GRUPO D ALIMENTOS | Núñez de Arce 5045 | Elab | Panificados — posible "no aplica al mapa" | vigente hasta 22/04/2028 |
| 8 | INTEGRO | Gral. Pagola 1765 | Elab | Congelados + comercio electrónico — posible "no aplica al mapa" | vigente hasta 10/07/2028 |
| 14 | RAWY LIVING FOODS | Av. Italia 6547 | Elab | Elaborador y fraccionador — posible "no aplica al mapa" | vigente hasta 11/04/2028 |
| 17 | VICTORIA | 26 de Marzo 3265 apto. 904 | Exp | Distribuidor sin depósito (un apartamento) — posible "no aplica al mapa" | vigente hasta 01/12/2027 |
| 19 | ALBERTA | Gabriel A. Pereira 2820 | Elab | Comidas en bandejas + distribuidor — posible "no aplica al mapa" | vencida 24/01/2025 |
| 20 | ALFAJORES JUANA LA LOCA | Marcelino Sosa 2433 | Elab | Elaboración de alfajores + distribuidor — posible "no aplica al mapa" | vencida 17/03/2026 |
| 21 | CONAPROLE | Virrey J. J. de Vértiz 1969 | Elab | Planta láctea + distribuidor — "no aplica al mapa" | vencida 24/11/2025 |
| 22 | DE LA TIERRA | Ing. A. Caubarrere 4608 | Elab | Procesado de frutas + distribuidor — posible "no aplica al mapa" | vencida 20/03/2024 |
| 24 | GIBUR | Cnel. J. Belinzon 5005 | Elab | Conservas + distribuidor — posible "no aplica al mapa" | vencida 13/09/2024 |
| 29 | MOLINO GUIDO | Av. Gral. Flores 3123 | Elab | Elaboración de harinas — posible "no aplica al mapa" | vencida 23/06/2025 |
| 34 | ZERO | 26 de Marzo 1325 | Exp-elab | Heladería con expendio — candidato al mapa | vencida 22/10/2025 |
| 35 | ZERO | Av. Alfredo Arocena 1997 | Exp-elab | Heladería con expendio — candidato al mapa | vencida 25/01/2026 |

Descartes revisados a mano en este grupo: "Bazar Grupo Dos" (6 km) no es GRUPO D ALIMENTOS; "Alimentos Saludables
VICTORIA" está en Tacuarembó; "La Molienda - Carrasco" (Arocena 2014, 72 m) no es ZERO; las filas "Zero Gluten" son de
Argentina.

## Lo que sigue (no ejecutado)

Con tu OK, la Fase 2 toma los 16 de **NO ESTÁ** y, según lo que decidas, los 5 de la sección 2 y los 3 dudosos. Con la
lectura preliminar, solo #34 y #35 (y tal vez #5) son claramente locales para visitar; el resto parece elaboración o
distribución y terminaría en "no aplica al mapa", pero eso lo decide la evidencia, no este reporte.
