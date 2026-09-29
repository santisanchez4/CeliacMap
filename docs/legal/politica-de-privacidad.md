# Política de privacidad de CeliacMap

> **BORRADOR, no publicado (2026-09-29).** Falta la revisión legal. Las marcas **[PENDIENTE DE IMPLEMENTAR]** son
> prácticas que todavía no existen y que tienen que estar funcionando antes de publicar este texto, o hay que sacarlas
> del texto. Las marcas **[A CONFIRMAR]** son datos que hay que verificar. Todo lo demás coincide con
> `docs/legal/inventario-datos.md`.

**Última actualización:** [fecha de publicación]

## 1. Quién es responsable

CeliacMap es un proyecto personal de **Santiago Sánchez**, persona física con domicilio en Uruguay, que es el
responsable de los datos que se describen acá.

Contacto para cualquier tema de privacidad: **hola@celiacmap.org**.

## 2. Lo más importante, en pocas líneas

- No tenés que crear una cuenta. No te pedimos email, teléfono ni documento.
- Lo que escribís en los formularios y en el chat lo leen personas y sistemas de inteligencia artificial para revisar
  los lugares del mapa.
- Solo se publica lo que aceptás publicar: una recomendación positiva, con el nombre que elijas o como “Anónimo”, y
  siempre después de que la revisemos. Los reportes negativos nunca se publican.
- No usamos cookies propias ni publicidad. Guardamos algunas preferencias en tu propio navegador.
- Usamos proveedores de Brasil y de Estados Unidos para funcionar.

## 3. Qué datos juntamos y para qué

### 3.1 Cuando sugerís un lugar (“Agregalo” o el chat)

- **Qué:** nombre, dirección, ciudad, país y tipo del lugar; un link de referencia y notas, si los agregás; y, si las
  contestás, respuestas sobre la cocina del lugar (si es exclusivamente sin gluten y cómo preparan lo apto para
  celíacos).
- **Para qué:** ubicar el lugar en el mapa y que nuestro sistema de revisión lo evalúe. Las respuestas sobre la cocina
  se usan como un dato **no verificado**: ayudan a la revisión, pero por sí solas nunca definen la etiqueta del lugar.
- **Qué se publica:** si el lugar se aprueba, se publican sus datos como negocio (nombre, dirección, ubicación, tipo y
  etiqueta) y el link de referencia. Tus notas y tus respuestas sobre la cocina no se publican.

> **[PENDIENTE DE IMPLEMENTAR]** Hoy el formulario y el chat también preguntan si el dueño o la dueña del lugar es
> celíaco/a. Esa pregunta se va a sacar (ver `owner-celiac-plan.md`) y esta política no la menciona. No se publica esta
> versión mientras la pregunta siga en el sitio.

### 3.2 Cuando dejás un comentario sobre un lugar (“Contanos” o el chat)

- **Qué:** el lugar, si es una recomendación o un problema, tu comentario y, en las recomendaciones, un nombre para
  mostrar si querés poner uno.
- Por el chat pasa lo mismo, con dos diferencias: el chat no pide un nombre, y si le contás que un lugar que ya está
  en el mapa es apto, lo registra en ese momento como una recomendación.
  **[PENDIENTE DE IMPLEMENTAR]** Hoy una recomendación que llega por el chat puede publicarse como “Anónimo” sin que el
  chat lo avise. Antes de publicar esta política, o el chat avisa, o esas recomendaciones no se publican.
- **Para qué:**
  - Un **problema** (reporte negativo) hace que el sistema vuelva a revisar el lugar. Si hay varios reportes, el lugar
    puede mostrar el aviso “Reportado por la comunidad” o salir del mapa hasta que una persona lo revise. El texto del
    reporte **nunca se publica**.
  - Una **recomendación** puede publicarse en el sitio si la aprobamos, con el nombre que pusiste o como “Anónimo”.
- Tu navegador genera un identificador al azar para poder contar cuántos reportes distintos recibe un lugar. Ese
  identificador no dice quién sos.

### 3.3 Cuando votás un lugar

Guardamos el voto y un identificador al azar que genera tu navegador, para que el mismo navegador no vote dos veces el
mismo lugar. Solo se publica el total de votos de cada lugar.

### 3.4 Cuando usás el chat

- Tus mensajes (hasta los últimos 15 de la conversación) se envían a un modelo de inteligencia artificial para
  entender qué pedís y responderte. **La conversación completa no se guarda en nuestra base.**
- Guardamos un registro de cada turno sin el texto: qué tipo de consulta fue y, si buscaste, el lugar o la ciudad.
- **Guardamos el texto de algunos turnos:** los que el sistema marca como fuera de lo esperado (por ejemplo, un pedido
  que no es sobre lugares sin TACC ni sobre la celiaquía, un intento de cambiar las reglas del asistente, una consulta
  médica personal o un exceso de mensajes). Se guarda para revisar la seguridad del servicio y **se borra
  automáticamente a los 30 días** (el borrado corre una vez por semana, así que puede tardar hasta 7 días más).
- Para limitar cuántos mensajes se pueden mandar, guardamos un contador por día asociado a un identificador al azar de
  tu navegador y otro asociado a tu dirección IP **transformada con una función de hash** (no guardamos la IP tal
  cual).
  **[PENDIENTE DE IMPLEMENTAR]** Hoy esos contadores no se borran solos, y el hash de la IP no usa una clave secreta.
  Antes de publicar: borrado automático (propuesta: 7 días) y un hash con clave secreta. Después de eso, esta línea
  dice: “Esos contadores se borran a los 7 días”.
- **No escribas en el chat datos de salud tuyos ni de otras personas.** El chat no da consejo médico. Si contás
  síntomas, el sistema no te responde sobre eso, te sugiere consultar a un profesional y ese turno queda guardado 30
  días como se explica arriba.

### 3.5 Cuando nos escribís por email

Si escribís a hola@celiacmap.org, usamos tu dirección y tu mensaje para responderte.
**[PENDIENTE DE IMPLEMENTAR]** Plazo de borrado de los emails del buzón.

### 3.6 Datos de negocios

Los datos de los lugares del mapa (nombre, dirección, teléfono, sitio web, horarios y calificación) salen de fuentes
públicas: Google Maps, el sitio web o las redes del propio negocio, y los aportes de la comunidad. Para confirmar la
información de algunos lugares, les escribimos por email a la dirección que publican en su propio sitio web y
guardamos esa conversación. Si un negocio pide que no lo contactemos más, no lo volvemos a contactar.
**[PENDIENTE DE IMPLEMENTAR]** Hoy el email de contacto de un negocio aprobado se puede leer por la API pública del
sitio, aunque la página no lo muestra. Hay que cerrarlo antes de publicar.

Para evaluar los lugares también usamos fragmentos de reseñas públicas de Google, **sin el nombre de quien las
escribió**. Se guardan como máximo 30 días.
**[PENDIENTE DE IMPLEMENTAR]** Hoy el borrado corre una vez por mes, así que en la práctica pueden quedar hasta unos
60 días. Hay que moverlo a un borrado semanal o cambiar el texto.

### 3.7 Lo que queda en tu navegador

No usamos cookies propias. En el almacenamiento local de tu navegador (`localStorage`) guardamos el idioma, el país
elegido en el ranking, qué lugares votaste, la hora de tu último envío (para frenar el spam) y los identificadores al
azar del chat, de los votos y de los reportes. No vencen solos: los podés borrar desde la configuración de tu
navegador (“borrar datos del sitio”).

### 3.8 Estadísticas de visitas

Usamos **Cloudflare Web Analytics** para contar páginas vistas. No usa cookies, no te sigue entre sitios y no le
mandamos nada de lo que escribís en el chat ni en los formularios. Cloudflare recibe, como cualquier servidor, tu
dirección IP y los datos de tu navegador.

## 4. Base legal y consentimiento

- Tratamos los datos que nos mandás porque vos decidís mandarlos: al enviar un formulario, un voto o un mensaje al chat
  aceptás esta política (tu **consentimiento**, Ley 18.331 art. 9 y Ley 25.326 art. 5).
- Los datos de negocios salen de **fuentes públicas** o los aporta la comunidad.
- **Datos de salud:** no te pedimos datos de salud. Si los escribís igual en un texto libre, se tratan como se describe
  en esta política y los podés hacer borrar (sección 8).
  **[A CONFIRMAR EN LA REVISIÓN LEGAL]** Si alcanza con esto para los turnos del chat donde alguien cuenta sus
  síntomas, o si hace falta un consentimiento expreso antes de chatear.

## 5. Qué se publica

- Los lugares aprobados, con sus datos de negocio, su etiqueta, el total de votos y, si corresponde, el aviso
  “Reportado por la comunidad”.
- Las recomendaciones aprobadas, con el nombre que elegiste o “Anónimo”, el lugar y la fecha. Moderamos antes de
  publicar (ver los Términos de uso). Una recomendación publicada deja de verse si el lugar sale del mapa.
- **Nunca** se publican: los reportes negativos, tus notas, las respuestas sobre la cocina, los identificadores ni los
  textos del chat.

## 6. Cuánto tiempo guardamos los datos

| Dato | Plazo |
|---|---|
| Texto de turnos marcados del chat y registro de turnos | 30 días (borrado semanal automático) |
| Reseñas de Google | 30 días **[PENDIENTE: hoy hasta ~60, ver 3.6]** |
| Contadores del chat (identificador y hash de IP) | **[PENDIENTE DE IMPLEMENTAR: hoy sin plazo]** |
| Sugerencias, comentarios, votos, respuestas de negocios | **[PENDIENTE DE IMPLEMENTAR: hoy sin plazo definido]** |
| Recomendaciones publicadas | Mientras estén publicadas y el lugar siga en el mapa, o hasta que pidas que las saquemos |
| Emails recibidos y avisos internos por email | **[PENDIENTE DE IMPLEMENTAR]** |
| Datos en tu navegador | Hasta que los borres vos |

## 7. Proveedores y transferencia internacional

Para funcionar usamos estos proveedores, que procesan datos por cuenta nuestra:

| Proveedor | Para qué | Dónde |
|---|---|---|
| Supabase (sobre Amazon Web Services) | Base de datos y funciones del servidor | Brasil (São Paulo) **[A CONFIRMAR: región de las funciones]** |
| Anthropic | Inteligencia artificial del chat y de la revisión de lugares | Estados Unidos |
| Resend | Envío y recepción de emails | Estados Unidos |
| Zoho | Casilla de email | **[A CONFIRMAR]** |
| Google | Datos y ubicación de los lugares; tipografías del sitio | Estados Unidos |
| Cloudflare | Estadísticas de visitas | Estados Unidos |
| GitHub | Alojamiento del sitio y tareas automáticas | Estados Unidos |
| Tavily | Búsqueda de páginas públicas de negocios (no recibe tus datos) | Estados Unidos |
| CARTO / OpenStreetMap y unpkg | Imágenes del mapa y la librería del mapa (reciben tu IP al cargar la página) | **[A CONFIRMAR]** |

Esto implica transferir datos fuera de Uruguay y de Argentina.
**[A CONFIRMAR EN LA REVISIÓN LEGAL]** Si Brasil y Estados Unidos cuentan como países con nivel adecuado para la URCDP
y para la AAIP, y, si no, en qué se apoya la transferencia (consentimiento, cláusulas contractuales de cada proveedor).

No vendemos ni cedemos tus datos a nadie. Los aliados del sitio no reciben ningún dato de quienes lo usan.

## 8. Tus derechos

Podés pedir en cualquier momento:

- **Acceso:** saber qué datos tuyos tenemos.
- **Rectificación:** corregirlos.
- **Supresión:** que los borremos, por ejemplo una recomendación publicada o un comentario.
- **Oposición** y retiro del consentimiento para lo que venga.

**Cómo:** escribí a **hola@celiacmap.org** con el asunto “Privacidad”. Contanos qué querés y ayudanos a encontrar el
dato: como no hay cuentas, lo buscamos por el lugar, la fecha aproximada y el texto que escribiste, o por el nombre que
pusiste en una recomendación.

**[PENDIENTE DE IMPLEMENTAR]** Procedimiento interno para responder (buscar, borrar o corregir en todas las tablas y en
el buzón, y dejar constancia) y el plazo de respuesta. Hoy solo existe una herramienta para **ocultar** una
recomendación publicada, no para borrar datos. Plazos legales de referencia **[A CONFIRMAR]**: acceso en 5 días
hábiles (Uruguay, art. 14) y 10 días corridos (Argentina, art. 14); rectificación y supresión en 5 días hábiles
(ambas leyes).

Si no te respondemos o la respuesta no te conforma, podés reclamar ante la **Unidad Reguladora y de Control de Datos
Personales (URCDP)** de Uruguay o ante la **Agencia de Acceso a la Información Pública (AAIP)** de Argentina.

## 9. Menores

CeliacMap no pide la edad ni datos que identifiquen a nadie, y no está pensado especialmente para menores.
**[A CONFIRMAR EN LA REVISIÓN LEGAL]** Si hace falta fijar una edad mínima para usar el chat y los formularios, o
pedir la autorización de un adulto.

## 10. Seguridad

La base de datos solo deja que el sitio lea los lugares aprobados y las recomendaciones publicadas. Los formularios
solo pueden agregar filas, no leer las de otras personas. Las claves de los servicios nunca llegan al navegador.

## 11. Cambios en esta política

Si cambiamos esta política, publicamos la versión nueva en esta página con la fecha de actualización. Si el cambio es
importante (por ejemplo, un dato nuevo o un proveedor nuevo), lo avisamos en el sitio antes de aplicarlo.
