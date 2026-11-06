# Instagram y Facebook como fuentes de evidencia — análisis

**Corte de datos:** 06-11-2026 (lectura de Supabase, solo `SELECT`). **Estado:** análisis para decidir; **no bloquea nada**
y no cambia código. La decisión la toma el responsable. Esto no es asesoramiento legal: es lo que hace el sistema, lo que
guarda y las opciones.

## 1. El problema

El 06-11-2026, al revisar las condiciones de las guías usadas como fuente (por el caso de findmeglutenfree.com, ver
[la decisión](../DECISIONS.md#findmeglutenfreecom-fuera-de-las-fuentes-automáticas-2026-11-06)), apareció que **Instagram y
Facebook son la fuente más frecuente** de `place_evidence` y que ambos restringen el acceso automático:

- **`robots.txt`** de `www.instagram.com` y `www.facebook.com`: `Disallow: /` para `ClaudeBot`, `GPTBot` y `PerplexityBot`
  (leído el 06-11-2026).
- **Condiciones de Meta:** las de Instagram y Facebook prohíben recolectar información o datos de sus productos por medios
  automáticos sin permiso previo (Instagram: no «collect information in an automated way without our express permission»;
  Facebook, condiciones §3.2: no acceder ni recolectar datos «using automated means (without our prior permission)»).
  *Texto a confirmar a mano en la versión vigente: no se descargó con un programa, justamente por esto.*

findmeglutenfree.com se sacó de las fuentes por el mismo tipo de motivo. La diferencia es de escala: sacar Instagram y
Facebook apagaría el agente Social y buena parte de la evidencia.

## 2. Qué hace el sistema hoy

- **Nuestro código no descarga Instagram ni Facebook.** `website_scraper` devuelve vacío para cualquier URL de redes
  (`is_social_url`), así que ni el agente Social ni `find_evidence` ni el outreach abren esas páginas.
- **Tavily sí.** El agente Social y `find_evidence` le piden a Tavily búsquedas con `include_domains=["instagram.com",
  "facebook.com"]`. Tavily devuelve título, URL y un fragmento de texto de su propio índice; cómo lo obtiene Tavily
  (rastreo propio, acuerdos, terceros) no lo sabemos. Lo que recibimos es contenido de Instagram/Facebook igual.
- **Lo que guardamos de esos resultados:**
  - El agente Social: un candidato en `places` (nombre, dirección geocodificada por Google, `social_url` solo si es la
    página de la cuenta) y una fila `social` en `place_evidence` con título + fragmento (hasta 1.000 caracteres).
  - `find_evidence`: nada en la base por sí solo; el reporte en `db/checks/evidence-proposals/` guarda la cita (≤ 160
    caracteres en la nota pública). Si el administrador acepta, la cita pasa a filas `web` y `admin`.
  - El mapa público muestra `social_url` como enlace (118 lugares aprobados lo tienen). Enlazar no es recolectar.

## 3. Cuánto pesa (06-11-2026)

**`place_evidence`: 87 filas.** Por `source`: 60 `admin`, 17 `web`, 10 `social`. Por dominio de la URL:

| Dominio | Filas |
|---|---|
| instagram.com | 41 |
| (sin URL: notas del administrador) | 18 |
| niter.com.uy | 6 |
| zerohelados.com.uy | 4 |
| glutengo.com.uy, facebook.com, artesaniapastelera.com.uy | 3 cada uno |
| otros sitios propios o guías | 1–2 cada uno |

**Las 44 filas de Instagram/Facebook, por autor:**

| Autor del texto | Filas | Detalle |
|---|---|---|
| Cuenta propia del comercio | 30 | 26 filas `admin` (bio o perfil de la cuenta que el administrador confirmó) y 4 `web` (cuenta enlazada desde la web del propio local: Moi, Artesanía Pastelera, Decreto Natural ×2) |
| Publicación de otra cuenta o sin autor verificado | 14 | 10 filas `social` del agente (4 marcadas «no atribuible», que el Validator no pesa), 3 `admin` de publicaciones (Felices Celíacos, Rico Rico, Celilife, este último descartado) y 1 `admin` de una página de Facebook de terceros (Amores Sin Gluten, descartado) |

**Dependencia del mapa:**

- 425 lugares aprobados; 46 tienen alguna fila en `place_evidence`.
- **25 aprobados tienen como única URL de evidencia una de Instagram/Facebook; 16 de ellos están en «Espacio 100% sin
  gluten».** Casi todos son las revisiones de Uruguay del 05-11-2026, donde el administrador leyó la cuenta oficial.
- **Agente Social:** 368 lugares tienen `source='social'`: 28 aprobados, 129 en `needs_review`, 211 descartados. Vive
  entero de resultados de Tavily restringidos a Instagram/Facebook (hasta 30 búsquedas por corrida mensual).

## 4. Accesos directos hechos en la sesión del 05/06-11-2026

Durante la revisión de la cola de Uruguay se bajaron con `curl` (sin programa del repo, desde la terminal del asistente)
páginas de Instagram y Facebook para leer sus metadatos `og:`. **No se repetirá.**

| Fecha (UTC) | Páginas | Qué devolvió |
|---|---|---|
| 05-11 20:29 | Facebook de víaSana (2 URLs) e Instagram `glutenfree.mvd` | Nombre de la página, ciudad, seguidores y la descripción corta de víaSana («Alimentos para celíacos, diabéticos…») |
| 05-11 21:50 | Instagram `locosuelto_uy`, `celiacos33`, `celisanosalto`, `viasana_tiendadealimentos`, `alapalaglutenfree`, `glutenfree.mvd`, `almacen_gelpi` | Solo nombre de la cuenta y conteos (seguidores, seguidos, publicaciones); **ninguna bio** |
| 06-11 14:01 | `robots.txt` de ambos sitios | Las reglas citadas arriba |

**Qué salió de eso:** sirvió para confirmar que las cuentas existían y cómo se llamaban, en la corrección de `social_url` de
6 lugares (SQL del 05-11, «cuenta oficial confirmada por el administrador»): A la Pala Gluten Free, Loco Suelto (Punta del
Este), De la Casa sin gluten, víaSana, Celíacos "33" y GLUTEN•FREE (glutenfree.mvd). La confirmación de cada cuenta la hizo
el administrador. **Ninguna fila de `place_evidence` copia texto de esas descargas:** las citas de bios en las filas `admin`
salieron de los fragmentos de Tavily o de la lectura del administrador. Lo único que vino de una descarga directa es la
descripción corta de víaSana, que se usó como pista y no se guardó como cita.

## 5. Alternativas

1. **Que el comercio confirme o nos pase su propia cita.** El outreach ya existe (fase 14–18, envío real limitado). Una
   respuesta del local es la mejor evidencia y no depende de ninguna plataforma. Costo: lento, tasa de respuesta baja.
2. **Que el administrador revise la cuenta a mano** (como Bicoque el 06-11). Una persona leyendo una página pública en su
   navegador no es acceso automático. Lo que se guarda es su nota y una cita corta con la URL. Costo: tiempo del
   administrador; no escala a cientos de lugares.
3. **API oficial de Meta.** La *Instagram Graph API* (Business Discovery) devuelve datos básicos públicos (nombre, bio,
   seguidores, publicaciones) de otras cuentas profesionales, pero exige una cuenta profesional propia de CeliacMap, una app
   de Meta y su revisión; no sirve para cuentas personales ni para buscar por texto («sin TACC Montevideo»). La API de
   Páginas de Facebook para contenido público pide el permiso *Page Public Content Access*, también con revisión. *Alcance y
   requisitos a confirmar en la documentación vigente de Meta.* Reemplazaría la verificación de una cuenta conocida, no el
   descubrimiento.
4. **Pedir permiso a Meta** para el uso actual. Poco probable para un proyecto de este tamaño, pero es la única forma de
   mantener el descubrimiento automático tal cual con cobertura contractual.
5. **Dejar de pedirle a Tavily Instagram/Facebook** (sumarlos a `BLOCKED_DOMAINS` o quitar el `include_domains`). Apaga el
   agente Social y el camino de evidencia de redes de `find_evidence`; las filas ya guardadas habría que decidir si se
   quedan (texto corto con URL, la mayoría escrito por el administrador) o se reescriben como las de findmeglutenfree.

## 6. Recomendación

Separar **descubrir** de **citar**:

- **Citar (la evidencia que sostiene una etiqueta):** que salga solo de la revisión a mano del administrador (opción 2) o
  del propio comercio (opción 1), con nota y cita corta propias. Las 30 filas de cuentas propias ya cumplen casi todo esto;
  las 14 de publicaciones no deberían sostener ninguna etiqueta (hoy ninguna de las 4 «no atribuible» se pesa, y 2 de las
  otras están en lugares descartados).
- **Descubrir (que un lugar entre a la cola):** mantener el agente Social mientras se decide, pero tratarlo como pista: un
  candidato `social` nunca se aprueba solo por el fragmento de Tavily. Si el responsable quiere cobertura contractual,
  evaluar la opción 3 para verificar cuentas conocidas y aceptar que el descubrimiento por texto quedaría sin reemplazo
  directo.
- **No más accesos directos** (`curl`, scripts) a Instagram o Facebook desde la terminal ni desde el código. Esto ya rige.
- Revisar el texto vigente de las condiciones de Meta a mano antes de decidir, y registrar la decisión en
  `docs/DECISIONS.md`.
