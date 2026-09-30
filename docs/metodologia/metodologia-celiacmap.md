# CeliacMap — Cómo funciona y con qué criterios

**Documento de metodología · Versión 1.0 · 30 de septiembre de 2026**

Preparado para la Asociación Celíaca Argentina. Este documento explica, sin tecnicismos, cómo CeliacMap encuentra
lugares, cómo decide qué mostrar en el mapa y qué límites tiene. Todo lo que se describe acá es lo que el sistema hace
hoy; lo que todavía está en desarrollo figura como tal.

---

## 1. Qué es CeliacMap y qué no es

CeliacMap es un mapa de lugares con opciones sin gluten / sin TACC en Uruguay y Argentina: restaurantes, cafés,
panaderías y comercios. Reúne información pública y aportes de la comunidad, la ordena con ayuda de inteligencia
artificial y la somete a criterios conservadores antes de mostrarla. Incluye además un asistente de conversación para
buscar lugares, recomendar o reportar uno, y consultar información general sobre la celiaquía.

**Lo que CeliacMap no es:**

- **No certifica ni inspecciona.** Nadie de CeliacMap visita las cocinas ni audita procesos. No reemplaza a ningún
  registro oficial, sello ni certificación.
- **Sus etiquetas son una estimación**, hecha a partir de la evidencia disponible, y no una garantía médica. El sitio lo
  dice junto al mapa: *"Los niveles son una estimación de la comunidad y del sistema, no una garantía médica. Confirmá con
  el local."*
- **La recomendación es siempre confirmar en el lugar** antes de consumir: preguntar cómo preparan los alimentos, si
  cocinan también con gluten y cómo evitan la contaminación cruzada.

Que un lugar esté publicado en el mapa no significa que haya sido verificado.

## 2. Las dos etiquetas del mapa

Cada lugar publicado lleva una de dos etiquetas:

| Etiqueta | Qué significa |
|---|---|
| **Espacio 100% sin gluten** | Un establecimiento donde se cocinan y se venden **únicamente** productos aptos para celíacos (cocina exclusiva). |
| **Tiene opciones sin TACC** | Ofrece opciones sin gluten, pero **no** es un espacio exclusivo: en el mismo lugar se elabora o se vende también con gluten. |

Un local que cocina con gluten y ofrece un menú para celíacos, preparación aparte o incluso una cocina separada **no**
es "100% sin gluten": lleva la etiqueta "Tiene opciones sin TACC".

**Ante la duda, siempre la etiqueta más baja.** Si la información no alcanza para distinguir, el lugar queda como
"Tiene opciones sin TACC". Internamente el sistema diferencia a los lugares que atienden explícitamente a celíacos de
los que solo tienen alguna opción, pero en el mapa ambos se muestran con la misma etiqueta, justamente para no sugerir
más seguridad de la que hay.

Hay además un aviso que puede aparecer sobre cualquier lugar: **"Reportado por la comunidad: consultá antes de ir"**
(ver sección 9).

## 3. Los agentes de inteligencia artificial

CeliacMap funciona con varios programas automáticos ("agentes"), cada uno con una tarea acotada. Ninguno publica un
lugar por su cuenta: todos alimentan a un único evaluador, que es la puerta de entrada al mapa.

- **Búsqueda en Google Maps.** Busca comercios con términos como "sin TACC", "sin gluten" o "apto celíacos" en una
  lista definida de ciudades de Uruguay y Argentina. Cada lugar encontrado entra como *candidato*, no como publicado.
  El país y la ciudad se toman de la dirección real del comercio, y lo que queda fuera de Uruguay y Argentina se descarta.
- **Búsqueda en redes sociales.** Busca páginas públicas de Instagram y Facebook de comercios que se presentan como sin
  TACC y las ubica en el mapa a partir de su nombre y dirección.
- **Búsqueda en la web.** Existe una búsqueda web general, pero **hoy está desactivada**.
- **Sugerencias de la comunidad.** Cualquier persona puede sugerir un lugar desde el sitio o desde el asistente. La
  sugerencia se ubica en el mapa; si no puede ubicarse en una dirección real no entra como candidato y queda para que la
  revise el administrador, y si el lugar ya existe no se duplica. Una sugerencia es un candidato más, que pasa por el mismo evaluador.
- **Evaluador.** Es el corazón del sistema: analiza cada candidato con los criterios de la sección 5 y decide si se
  publica, si queda para revisión humana o si se descarta.
- **Actualizador.** Revisa periódicamente los lugares ya publicados que vienen de Google Maps. Si un comercio figura
  como cerrado definitivamente, lo retira del mapa; si cambió su nombre, dirección o rubro, lo corrige; si deja de
  encontrarse, lo marca para que lo revise una persona, sin retirarlo por un error que puede ser pasajero.
- **Consultas a comercios.** Escribe por correo a algunos comercios que quedaron en revisión, para preguntarles
  directamente por sus opciones sin TACC (ver sección 7).
- **Reportes.** Cuando alguien informa un problema con un lugar publicado, un agente lo vuelve a evaluar teniendo en
  cuenta el reporte (ver sección 9).

La búsqueda y la evaluación se ejecutan una vez por mes, con una ronda adicional de evaluación a mitad de mes; las
sugerencias de la comunidad se procesan cada semana y los reportes, apenas llegan.

## 4. Fuentes de información

El evaluador trabaja solo con la información que el sistema reúne sobre cada lugar:

- **Datos del comercio en Google Maps:** nombre, dirección, ubicación y rubro.
- **Fragmentos de reseñas públicas de Google** que mencionan términos como "sin gluten" o "celíaco". Se usan como
  evidencia de apoyo, **nunca se publican** en CeliacMap y se borran a los 30 días.
- **Textos públicos de redes sociales y páginas web** de los comercios, con el enlace de dónde salen.
- **Aportes de la comunidad:** sugerencias, recomendaciones y reportes enviados desde el sitio o el asistente, incluidas
  las respuestas opcionales sobre la cocina de un lugar (si es exclusivamente sin gluten, cómo preparan lo apto para
  celíacos). Se tratan siempre como **información no verificada**.
- **Respuestas de los comercios** a las consultas por correo.
- **Evidencia que aporta el administrador**, siempre con una nota que explica de dónde viene.

**Qué no se pide ni se guarda.** CeliacMap no pide datos de salud de nadie: ni de quien escribe ni de terceros (por
ejemplo, ya no se pregunta si el dueño de un comercio es celíaco). Las conversaciones con el asistente se borran a los
30 días; las sugerencias y los reportes que no se publican, a los 2 años.

## 5. Los criterios del evaluador

El evaluador es un modelo de inteligencia artificial que recibe, para cada candidato, toda la información reunida y
responde con un resultado, una etiqueta y una **puntuación de confianza** entre 0 y 1 que expresa qué tan sólida es la
evidencia. Sus instrucciones le piden, en primer lugar, **no sobreestimar nunca la seguridad**: *"La salud de personas
celíacas depende de tu criterio. Ante la duda, siempre escala a revisión humana."*

**Qué cuenta como evidencia fuerte.** Una mención explícita y clara de "sin TACC", de un "sin gluten" certificado o la
descripción de un protocolo para evitar la contaminación cruzada.

**Señales de alerta** (cada una baja la confianza):

- Dice "sin gluten" pero no "sin TACC" (puede ser un término de marketing y no una práctica real; ver sección 11).
- No menciona cómo evita la contaminación cruzada.
- Solo ofrece opciones vegetarianas o veganas, sin mención explícita de sin TACC.
- La información tiene más de 12 meses.
- Hay reseñas negativas de personas celíacas.
- La descripción es ambigua ("apto para dietas especiales").

**Solo la evidencia recibida.** El evaluador debe basarse únicamente en la información que se le entrega sobre ese
lugar. No puede usar lo que "cree saber" de un comercio por su cuenta, ni tomar el nombre como prueba: que un local se
llame "Sin Gluten" no demuestra que su cocina sea exclusiva, y que no lo diga no demuestra lo contrario. Las reseñas
entusiastas pesan como apoyo, pero nunca por encima de la evidencia. Los aportes de la comunidad orientan la revisión,
pero por sí solos no alcanzan para publicar un lugar ni para darle la etiqueta 100%. Si un lugar solo pudo ubicarse por
su dirección (sin una ficha de Google Maps que confirme que el comercio existe y funciona ahí), la evidencia se
considera más débil.

**Los tres resultados posibles:**

| Resultado | Cuándo | Qué pasa |
|---|---|---|
| **Aprobado** | Evidencia explícita y clara, con una confianza de **0,85 o más** (85 sobre 100). | Se publica en el mapa. |
| **Revisión humana** | Evidencia parcial o ambigua: confianza entre **0,5 y 0,85**. | No se publica; queda en espera de que una persona lo revise. |
| **Descartado** | Evidencia insuficiente, contradictoria o con señales de riesgo: confianza **menor a 0,5**. | No se publica. |

Estos umbrales no dependen solo de lo que "diga" el modelo: el propio programa los aplica siempre. Aunque el modelo
proponga aprobar un lugar, si su confianza no llega a 0,85 el lugar va a revisión humana; y si está por debajo de 0,5 se
descarta. Es decir: **para aparecer en el mapa sin intervención humana hace falta evidencia fuerte; todo lo intermedio
lo decide una persona.**

## 6. La regla del 100%

La etiqueta "Espacio 100% sin gluten" es la que más confianza transmite, y por eso tiene controles propios, aplicados
por el programa además de las instrucciones al modelo:

- **Exige evidencia explícita de elaboración exclusiva.** El sistema solo mantiene la etiqueta 100% si en los textos
  recibidos (reseñas, redes, páginas web) hay una afirmación expresa como "100% sin TACC", "todo es sin gluten" o
  "cocina exclusiva". El nombre del local no cuenta, ni lo que el modelo crea saber. Sin esa frase, el lugar queda como
  **"Tiene opciones sin TACC"** y pasa a una lista de espera para que el administrador confirme o no el 100%.
- **Si alguien declara que la cocina no es exclusiva**, el lugar no puede quedar como 100%.
- **Un lugar sugerido por la comunidad nunca recibe el 100% de forma automática:** solo el administrador puede darle esa
  etiqueta.
- **El caso inverso también se revisa:** si la evidencia sí afirma exclusividad pero el evaluador eligió una etiqueta
  más baja, el sistema no la sube solo; el lugar entra en la misma lista para que decida una persona.

En resumen: el 100% se muestra solo con evidencia escrita y explícita de elaboración exclusiva, o con la confirmación
del administrador. Mientras tanto, el lugar se muestra como "Tiene opciones sin TACC".

## 7. Consultas a comercios

Para los lugares que quedaron en revisión humana por falta de evidencia, CeliacMap puede escribir un correo breve al
comercio preguntándole por sus opciones sin TACC.

- **La respuesta es evidencia, nunca una aprobación automática.** El comercio tiene un interés legítimo en aparecer en
  el mapa, y eso no garantiza que su respuesta sea precisa o que conozca los protocolos de contaminación cruzada. Por
  eso su respuesta vuelve al mismo evaluador junto con el resto de la información. Aun con una respuesta favorable, el
  lugar queda esperando la **aprobación final de una persona**: ninguna consulta lleva por sí sola a un lugar al mapa.
- **Opción de no ser contactado.** Cada correo incluye una línea fija explicando cómo pedir no recibir más mensajes. Si
  un comercio lo pide, queda excluido de forma permanente. Si el sistema no logra clasificar una respuesta, no la toma
  como pedido de baja, para no dejar de lado por error a un comercio que quiso responder.
- **Volumen acotado.** Está en una etapa inicial y el envío está limitado a un máximo de tres comercios por mes, para
  observar las respuestas antes de ampliarlo. Solo se escribe a comercios que tienen datos de contacto públicos.

## 8. Revisión humana

Hoy la revisión humana la hace el administrador de CeliacMap, que recibe un resumen diario por correo con todo lo
pendiente y avisos inmediatos cuando algo es urgente (un reporte negativo, un lugar retirado del mapa, la respuesta de un
comercio). Revisa:

- los lugares que el evaluador dejó en **revisión humana**;
- los lugares en espera de **confirmación del 100%**;
- los **reportes de la comunidad** y los lugares con aviso;
- las **recomendaciones de la comunidad** antes de publicarlas;
- las sugerencias que no pudieron ubicarse en el mapa.

Cada decisión manual queda registrada con una nota que dice quién decidió, con qué conocimiento directo y qué había
concluido el evaluador. Una decisión manual nunca es silenciosa ni modifica la puntuación de confianza del evaluador.

Hay una **revisión en curso** de los lugares en espera de confirmación del 100%. Para agilizarla se usa una
herramienta que busca en fuentes públicas y **propone** una etiqueta citando textualmente lo que encontró, después de
comprobar que la cita está realmente en la página. La herramienta no escribe nada ni cambia ningún lugar: cada
propuesta la acepta o la rechaza el administrador.

## 9. Reportes de la comunidad

Cualquier persona puede reportar un problema con un lugar publicado, desde el sitio o desde el asistente. Un reporte es
evidencia, no una orden: nunca cambia por sí solo el estado de un lugar, salvo por las reglas fijas que siguen.

- **Aviso en el mapa.** Con uno o dos reportes negativos distintos en 30 días, el lugar sigue publicado pero muestra el
  aviso **"Reportado por la comunidad: consultá antes de ir"**.
- **Retiro del mapa.** Con **tres** reportes distintos en 30 días, o con **un solo** reporte que el evaluador considere
  creíble sobre contaminación con gluten o síntomas después de comer en el lugar, el lugar sale del mapa hasta que el
  administrador lo revise.
- Un reporte **nunca sube** la etiqueta de un lugar. Si el administrador aprobó un lugar manualmente, un reporte no
  cambia la etiqueta que definió ni borra el registro de su decisión, aunque sí puede retirar el lugar del mapa hasta que
  lo revise.
- **Los reportes negativos nunca se publican.** Publicar una acusación sin verificar sobre un comercio sería un riesgo
  para el comercio y para la comunidad. Las **recomendaciones positivas** pueden publicarse en el sitio, pero solo
  después de que el administrador las aprueba, con el nombre que la persona haya elegido o como "Anónimo". Una
  recomendación publicada no cambia la etiqueta ni la posición del lugar.

## 10. El asistente de conversación

El sitio incluye un asistente que responde solo sobre cuatro temas: buscar lugares del mapa, recomendar o reportar un
lugar, ayudar a confirmar un lugar en revisión e información general sobre la celiaquía. Sus límites:

- **Solo nombra lugares que están en el mapa.** No usa conocimiento propio sobre restaurantes o cadenas.
- **No da consejos médicos:** ni diagnósticos, ni interpretación de síntomas, ni tratamientos, ni juicios sobre la
  gravedad o la urgencia de lo que cuenta una persona.
- **No da cifras de gluten** (ni miligramos, ni cantidades "tolerables"). Si le preguntan, explica que no hay una
  cantidad que pueda asegurarse como segura para toda persona celíaca, que la indicación médica es evitarlo por
  completo, y que los límites legales de rotulado son una concentración máxima en el alimento y no una dosis diaria.
  Además de las instrucciones, un control automático revisa sus respuestas sobre celiaquía.
- **Deriva a profesionales y asociaciones.** Ante preguntas sobre síntomas propios o diagnóstico, deriva a un
  profesional de la salud y a las asociaciones: en Argentina, ACELA y la Asociación Celíaca Argentina; en Uruguay, ACELU.
- **Nunca afirma que un lugar es "seguro"** en términos absolutos, y aclara que las etiquetas son una estimación.
- Lo que una persona recomienda o reporta por el asistente sigue el mismo camino que un formulario: pasa por revisión.

## 11. Límites conocidos y mejoras en curso

**Límites que conocemos:**

- **La evidencia es texto público y puede estar desactualizada.** Un comercio puede cambiar su cocina, su menú o sus
  proveedores sin que eso aparezca en internet.
- **La inteligencia artificial puede equivocarse.** Por eso existen los umbrales, los controles del 100% y la revisión
  humana, y por eso cada etiqueta es una estimación.
- **Hay una cola de lugares esperando revisión humana**, en particular los que no tienen datos de contacto públicos, que
  por eso no pueden recibir una consulta. Mientras tanto, esos lugares no se muestran.
- **Los aportes son anónimos.** No hay cuentas de usuario, así que no se puede saber si varios reportes vienen de la
  misma persona; por eso los reportes activan avisos y revisiones, no decisiones definitivas.
- **El actualizador solo revisa automáticamente los lugares que vienen de Google Maps.** Un comercio que solo existe en
  redes sociales no se controla de la misma forma.
- **Cobertura:** Uruguay y Argentina, en una lista definida de ciudades. La búsqueda web general está desactivada.

**Mejoras en curso:**

- **Actualización de criterios por la Resolución Conjunta 32/2023.** Hoy el evaluador baja la confianza cuando un lugar
  dice "sin gluten" y no "sin TACC", porque "sin gluten" podía ser un término de marketing. Según la Resolución Conjunta
  32/2023, un alimento es libre de gluten que no supera los 10 mg/kg de gluten, y "sin gluten" pasa a ser el término de uso en
  Argentina. Entendemos además que admite avena libre de gluten certificada; nos gustaría validarlo con ustedes antes de
  actualizar los criterios. Estamos actualizando los criterios para reflejarlo: la idea es dejar de penalizar "sin gluten" en Argentina y seguir
  distinguiendo un uso publicitario de la expresión de un sello o una práctica real. El cambio se va a probar antes de
  aplicarse. Por ahora, las etiquetas del mapa se mantienen como están.
- **Revisión de la lista de espera del 100%** con la herramienta de propuestas citadas descrita en la sección 8.
- **Consultas a comercios:** ampliar el volumen de forma gradual, a medida que se observen las respuestas.

## 12. Contacto

Para consultas, correcciones, pedidos de baja de un comercio o cualquier comentario sobre esta metodología:

- **Correo:** hola@celiacmap.org
- **Sitio:** https://celiacmap.org
- **Responsable:** Santiago Sánchez, creador y administrador de CeliacMap.

Nos interesa especialmente la mirada de las asociaciones de pacientes sobre estos criterios.
