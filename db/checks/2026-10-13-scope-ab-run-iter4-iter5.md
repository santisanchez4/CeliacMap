# A/B del párrafo de alcance del Validator — iteraciones 4 y 5, pruebas cortas (2026-10-13)

`python db/checks/validator_scope_ab.py --only-new --n 5 --max-calls 75 --cases <15 casos>`: solo el brazo nuevo, 15 casos, 5
muestras. Cada prueba: 75 llamadas planificadas, 75 hechas, tope 75, ~US$0,82. Un intento previo se cortó en la primera llamada
(«credit balance is too low», sin resultados). Referencia de la `RUBRIC` anterior (brazo OLD de las corridas de las iteraciones 1 y
2, 6 muestras por caso): parrilla compartida `needs_review` 6 de 6; Ramona `approved` 1 de 6; Mi Cocina Sin Gluten `approved` 0 de 6;
EntreSano `approved` 3 de 3.

## Lectura

**Iteración 4** (apartado de alcance antes del rubric de seguridad; sin «nunca es needs_review»; regla del comercio general
independiente y de la oferta dedicada): **FALLA**. El restaurante con parrilla compartida sale `rejected` en 3 de 5. Además Ramona
da `approved` en 5 de 5.

**Iteración 5** (el mismo texto, movido al final del prompt, después del rubric de seguridad y antes de la forma del JSON): el
script da **PASA**, pero la redacción **no queda cerrada**.

- Parrilla compartida: `needs_review` 0,52 en 5 de 5, igual que con la `RUBRIC` anterior. El efecto lateral desaparece.
- Alcance: Devoto Express, By Gessi y el autoservicio independiente, `not_applicable` 15 de 15; ningún caso dentro de alcance
  excluido (0 de 60); EntreSano `approved` 5 de 5 como antes; La Isla y La Molienda `needs_review` 5 de 5.
- **Señal en la dirección insegura, sin criterio en el script:** Mi Cocina Sin Gluten da `approved` 0,87 en 4 de 5 (antes 0 de 6)
  y Ramona en 3 de 5 (antes 1 de 6), las dos con una sola fuente no verificada. Es el mismo tipo de señal que hizo descartar la
  iteración 1. Hipótesis: la frase nueva «oferta sin gluten dedicada (cocina o elaboración propia sin gluten, una sección sin
  gluten amplia y curada)» describe el alcance con palabras que el modelo lee como evidencia de seguridad; en la iteración 3, que
  no la tenía, Mi Cocina Sin Gluten daba `needs_review` en 5 de 5.

No se corrió la medición completa: la condición era una redacción cerrada.

## Salida — iteración 4

```text
PLAN: 15 case(s) x 1 arm(s) x n=5 = 75 call(s) to claude-sonnet-4-6, ~US$0.82; hard cap 75 call(s) (~US$0.82)

[out] devoto_con_gondola — Devoto Express
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
       No aplica al mapa: Devoto Express es una sucursal de la cadena de supermercados Devoto, que queda explícitamente fuera del alcance del mapa por ser comercio general. La reseña confirma que la oferta sin TACC se limita a una góndola de productos, lo cual es exactamente el caso excluido: supermercado con sección sin gluten pero sin especialización.

[out] by_gessi_escuela — By Gessi Cocina Inclusiva
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
       No aplica al mapa: Toda la evidencia disponible indica que By Gessi Cocina Inclusiva es una escuela de cocina y plataforma educativa que ofrece cursos presenciales y online de cocina sin gluten, no un establecimiento que vende o sirve comida o productos al público. Las reseñas de la comunidad confirman exclusivamente experiencias de aprendizaje (clases y cursos), y la web se presenta como formación gastronómica. Al ser un lugar que enseña sin vender ni servir alimentos al público, queda fuera del alcance del mapa.

[in] zero_helados_cadena — Zero Helados
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.55, 0.55, 0.55, 0.55, 0.55]
       El nombre 'Zero Helados' sugiere una heladería pero no hay evidencia explícita de opciones sin TACC, protocolo anticontaminación cruzada ni certificación celíaca en los datos aportados. La fuente es Google Places pero no se incluyen reseñas, descripción del negocio ni evidencia de descubrimiento que confirmen oferta apta para celíacos. Sin información verificable, se mantiene un nivel conservador y se escala a revisión humana.

[in] ramona_cadena — Ramona
  NEW: verdict {'approved': 5} | status {'approved': 5} | confidence [0.87, 0.87, 0.87, 0.87, 0.85]
       La evidencia de descubrimiento indica explícitamente que Ramona es una panadería y pastelería '100% sin gluten' con 4 locales en Buenos Aires, lo que sugiere una cocina exclusivamente libre de gluten. La mención directa de '100% sin gluten' en el perfil público de Instagram, combinada con la descripción del rubro (panadería/pastelería especializada), respalda el veredicto aprobado con safety_level gluten_free_100, aunque se recomienda confirmar el protocolo de cada sucursal individualmente.

[in] mi_cocina_sin_gluten — Mi Cocina Sin Gluten
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La evidencia de descubrimiento indica elaboración propia de productos sin gluten y venta directa en locales, lo que sugiere una tienda especializada con foco en productos sin TACC. Sin embargo, la fuente es única y no verificada, no se menciona explícitamente 'sin TACC' ni certificación, y no hay información sobre protocolo de contaminación cruzada o si la cocina es exclusivamente libre de gluten.

[in] dietetica — Dietética Vida Sana
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       Hay una reseña de la comunidad que menciona variedad de productos sin TACC y asesoramiento, lo cual es una señal positiva y relevante, pero proviene de una sola fuente sin evidencia adicional que confirme la oferta ni el protocolo de contaminación cruzada. No hay información sobre certificación, descripción oficial del local ni evidencia de que sea una tienda especializada exclusivamente en productos sin gluten.

[in] panaderia_exclusiva — Panadería La Espiga
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       Existe una reseña de la comunidad que afirma que el local es 100% sin gluten y cocina exclusivamente para celíacos, pero por sí sola no es suficiente para aprobar ni para asignar 'gluten_free_100': se necesita evidencia verificable como menciones explícitas de 'sin TACC', certificación o confirmación del establecimiento. No se cuenta con evidencia directa del local (sitio web, redes sociales, ficha verificada) que respalde la afirmación.

[in] fabrica_con_venta_directa — Pastas Don Luis
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La web del local menciona explícitamente 'sin TACC', lo cual es una señal positiva y específica para celíacos, y se trata de una fábrica con venta directa al público que aplica al mapa. Sin embargo, la fuente es única y no verificada, no se menciona protocolo de contaminación cruzada ni si la cocina es exclusivamente sin gluten, y no hay reseñas de la comunidad ni certificación que respalde la afirmación.

[in] restaurante_con_opciones — La Parrilla de Juan
  NEW: verdict {'rejected': 3, 'needs_review': 2} | status {'discarded': 3, 'needs_review': 2} | confidence [0.35, 0.35, 0.35, 0.52, 0.52]
       La única evidencia disponible es una reseña de la comunidad que menciona menú sin TACC, pero señala explícitamente que comparten parrilla con alimentos con gluten, lo que representa un riesgo serio de contaminación cruzada para celíacos. No hay mención de protocolo anti-contaminación cruzada ni certificación, y una parrilla compartida es una señal de alerta crítica en este tipo de establecimiento.
  !! FAIL: expected status needs_review in every sample (scope must not move the safety verdict)

[in] panaderia_que_tambien_da_talleres — Sin Trigo Panadería
  NEW: verdict {'approved': 5} | status {'approved': 5} | confidence [0.87, 0.88, 0.88, 0.87, 0.88]
       La evidencia de redes sociales menciona explícitamente 'sin TACC' y describe una panadería dedicada exclusivamente a productos sin gluten (panes y facturas), sin mención de elaboración con gluten. El nombre 'Sin Trigo' y la descripción refuerzan que es un establecimiento especializado con cocina dedicada. Los talleres de panificación son una actividad adicional y no contradicen el carácter exclusivo del local.

[in] almacen_natural — Almacén Natural Don Pepe
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.52, 0.55, 0.52, 0.52, 0.52]
       El lugar parece ser un almacén o tienda de productos naturales con al menos alguna oferta sin gluten (harinas y galletitas), pero la única señal es una reseña genérica que no menciona 'sin TACC' ni certificación, y no hay información sobre protocolos o especialización dedicada. La evidencia es insuficiente para aprobar sin confirmación humana.

[in] entresano_supermercado_saludable — EntreSano Healthy Supermarket
  NEW: verdict {'approved': 5} | status {'approved': 5} | confidence [0.87, 0.87, 0.88, 0.87, 0.87]
       La evidencia web muestra una categoría explícita 'Sin TACC' con 671 productos listados en su sitio oficial, lo que indica una oferta dedicada y amplia, no una góndola ocasional. Una reseña de la comunidad confirma variedad de productos sin TACC. Aunque se llama 'Supermarket', su perfil como tienda especializada en alimentación saludable con sección sin TACC curada lo distingue del comercio general y lo hace aplicable al mapa.

[in] minimarket_la_isla — Minimarket La Isla 24 hours.
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.72, 0.62, 0.62, 0.62]
       La evidencia muestra un minimarket con cocina propia y más de 1.500 productos sin gluten, lo que lo diferencia de un comercio general y lo coloca dentro del alcance del mapa; además, una reseña comunitaria menciona variedad de productos sin TACC. Sin embargo, ninguna fuente verificada especifica protocolo anti-contaminación cruzada ni certificación, y la web no usa el término 'sin TACC' ni detalla si la cocina propia es exclusiva o compartida, lo que impide aprobar con confianza.

[in] la_molienda_tienda_natural — La Molienda - Carrasco
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La evidencia muestra una tienda especializada con sección dedicada a productos sin gluten (harinas, pastas, snacks, galletitas, 444 artículos), lo que sugiere una oferta amplia y curada que va más allá de una góndola genérica. Sin embargo, la evidencia proviene de una única fuente web no verificada, no se menciona 'sin TACC' explícitamente ni protocolo de contaminación cruzada, y no hay reseñas de celíacos que confirmen la seguridad del local físico en Carrasco.

[out] autoservicio_independiente — Autoservicio El Trébol
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
       No aplica al mapa: Autoservicio El Trébol es un autoservicio general independiente cuya única oferta sin gluten consiste en una góndola de productos, exactamente el caso excluido del alcance del mapa. La reseña de la comunidad confirma que se trata de una góndola, no de un comercio especializado ni de gastronomía.

calls made: 75 of a cap of 75
RESULT: FAIL (1 failing case(s))
```

## Salida — iteración 5 (apartado de alcance al final)

```text
PLAN: 15 case(s) x 1 arm(s) x n=5 = 75 call(s) to claude-sonnet-4-6, ~US$0.82; hard cap 75 call(s) (~US$0.82)

[out] devoto_con_gondola — Devoto Express
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
       No aplica al mapa: Devoto Express es una cadena de supermercados/autoservicios de comercio general en Uruguay, categorizados explícitamente como excluidos del mapa. Aunque la reseña menciona una góndola sin TACC, este tipo de comercio general queda fuera del alcance del mapa porque la oferta varía por sucursal y no puede verificarse de forma confiable.

[out] by_gessi_escuela — By Gessi Cocina Inclusiva
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
       No aplica al mapa: Toda la evidencia disponible indica que By Gessi Cocina Inclusiva es una escuela de cocina y formación gastronómica sin gluten (cursos presenciales y online), no un restaurante ni un comercio que venda o sirva alimentos al público. Las reseñas de la comunidad confirman clases y formación, y la web describe la actividad como educación gastronómica.

[in] zero_helados_cadena — Zero Helados
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.52, 0.52, 0.55, 0.52, 0.52]
       El lugar aparece listado en Google Places pero no se cuenta con evidencia explícita de mención de 'sin TACC', certificación o protocolo de contaminación cruzada en la información disponible. El nombre 'Zero' podría sugerir una propuesta especial (sin azúcar, sin gluten), pero el nombre por sí solo no es evidencia válida. Se requiere confirmación directa de la oferta apta para celíacos y sus protocolos.

[in] ramona_cadena — Ramona
  NEW: verdict {'approved': 3, 'needs_review': 2} | status {'approved': 3, 'needs_review': 2} | confidence [0.87, 0.72, 0.87, 0.87, 0.72]
       La evidencia de descubrimiento proviene del perfil oficial de Instagram del negocio, que se describe explícitamente como 'panadería y pastelería 100% sin gluten', lo cual indica una cocina dedicada exclusivamente a productos sin gluten. La descripción es directa, inequívoca y coherente con la categoría estimada. Aunque la fuente no está verificada de forma independiente, la combinación de una autodescripción oficial tan clara con el perfil institucional justifica la aprobación con confianza moderada-alta.

[in] mi_cocina_sin_gluten — Mi Cocina Sin Gluten
  NEW: verdict {'approved': 4, 'needs_review': 1} | status {'approved': 4, 'needs_review': 1} | confidence [0.87, 0.87, 0.72, 0.87, 0.87]
       La evidencia de descubrimiento desde el sitio web oficial indica elaboración propia de productos sin gluten con puntos de venta físicos, lo que constituye una señal clara de especialización. El nombre del establecimiento refuerza la orientación al rubro sin gluten, aunque por sí solo no es evidencia. No hay información explícita sobre protocolo de contaminación cruzada ni certificación, y la fuente no está verificada, por lo que no alcanza para 'gluten_free_100'.

[in] dietetica — Dietética Vida Sana
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       Hay una reseña de la comunidad que menciona productos sin TACC y asesoramiento, lo cual es una señal positiva pero insuficiente por sí sola para aprobar: no hay evidencia explícita de especialización exclusiva en productos sin gluten, ni descripción de protocolos de contaminación cruzada. La evidencia se limita a una única reseña sin respaldo de fuentes adicionales (web, redes sociales u otras reseñas).

[in] panaderia_exclusiva — Panadería La Espiga
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La reseña de la comunidad indica que el local es 100% sin gluten y dedicado exclusivamente a celíacos, lo cual es una señal positiva, pero por sí sola no es suficiente para alcanzar 'approved' ni para confirmar 'gluten_free_100', ya que se trata de una única reseña no verificada. No se cuenta con evidencia documental directa (sitio web, redes sociales, certificación) que mencione explícitamente 'sin TACC' o describa protocolos de elaboración exclusiva. Se requiere confirmación humana para elevar la confianza y el safety_level.

[in] fabrica_con_venta_directa — Pastas Don Luis
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La evidencia descubierta menciona explícitamente 'sin TACC' y venta al público directa desde fábrica, lo que es una señal positiva y relevante. Sin embargo, al tratarse de una única fuente web no verificada, sin mención de protocolo anti-contaminación cruzada ni confirmación de si la cocina es exclusivamente sin TACC o también elabora productos con gluten, no alcanza para 'approved'. Se requiere confirmación humana para elevar la confianza.

[in] restaurante_con_opciones — La Parrilla de Juan
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.52, 0.52, 0.52, 0.52, 0.52]
       La reseña de la comunidad menciona menú sin TACC, lo que es una señal positiva, pero indica explícitamente que se comparte parrilla con productos con gluten, lo que representa un riesgo real de contaminación cruzada para celíacos. No hay evidencia de protocolo anti-contaminación cruzada ni certificación, y la parrilla compartida es una alerta de seguridad significativa.

[in] panaderia_que_tambien_da_talleres — Sin Trigo Panadería
  NEW: verdict {'approved': 5} | status {'approved': 5} | confidence [0.87, 0.87, 0.87, 0.87, 0.87]
       La evidencia de redes sociales indica explícitamente 'sin TACC' y describe un local dedicado exclusivamente a panes y facturas sin gluten, lo que sugiere cocina 100% dedicada. No se detectan menciones de elaboración con gluten ni señales de contaminación cruzada, y la descripción es coherente con un establecimiento especializado. Los talleres de panificación mencionados no invalidan la oferta de venta directa al público.

[in] almacen_natural — Almacén Natural Don Pepe
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.52, 0.52, 0.52, 0.55, 0.52]
       El nombre sugiere un almacén de productos naturales, y la única reseña menciona 'sin gluten' en referencia a harinas y galletitas, lo que indica alguna oferta en esa línea. Sin embargo, no hay mención explícita de 'sin TACC', ni de certificación, ni de que sea una tienda especializada exclusivamente en productos aptos para celíacos; la evidencia es insuficiente para determinar el alcance real de la oferta y los protocolos aplicados.

[in] entresano_supermercado_saludable — EntreSano Healthy Supermarket
  NEW: verdict {'approved': 5} | status {'approved': 5} | confidence [0.87, 0.87, 0.87, 0.87, 0.87]
       La web oficial del comercio lista explícitamente una categoría 'Sin TACC' con 671 productos, lo que constituye una sección dedicada y curada de productos aptos para celíacos, no una simple góndola genérica. Una reseña de la comunidad refuerza la variedad de oferta sin TACC. Dado que se trata de un supermarket saludable especializado con oferta sin TACC amplia pero que también vende otros productos, el safety_level corresponde a 'options_available', ya que no hay evidencia de cocina exclusiva ni certificación de protocolo anti-contaminación cruzada.

[in] minimarket_la_isla — Minimarket La Isla 24 hours.
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La evidencia descubierta indica más de 1.500 productos sin gluten y cocina propia, lo que sugiere una oferta sin gluten amplia y dedicada que lo distingue de un comercio general; sin embargo, el sitio web no usa los términos 'sin TACC' ni menciona protocolo de contaminación cruzada, y la reseña comunitaria, aunque entusiasta y con mención explícita de sin TACC, no es suficiente por sí sola para confirmar preparación segura para celíacos. El formato 'minimarket 24 horas' y la ausencia de certificación o descripción de cocina separada generan dudas sobre el nivel de seguridad real.

[in] la_molienda_tienda_natural — La Molienda - Carrasco
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La evidencia muestra una tienda con sección dedicada a productos sin gluten (444 artículos en categoría celíaco/sin gluten), lo que indica oferta especializada relevante para el mapa. Sin embargo, la evidencia proviene únicamente de la web del comercio y no confirma que esta sucursal física específica (Carrasco) tenga el mismo surtido ni condiciones de almacenamiento separado; tampoco se menciona protocolo anti-contaminación cruzada ni certificación 'sin TACC'.

[out] autoservicio_independiente — Autoservicio El Trébol
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
       No aplica al mapa: Autoservicio El Trébol es un autoservicio o almacén general independiente cuya única evidencia de oferta sin gluten es una góndola de productos, lo que corresponde exactamente al tipo de comercio general que queda fuera del alcance del mapa. No hay indicios de elaboración propia, cocina dedicada ni oferta especializada en productos sin TACC.

calls made: 75 of a cap of 75
RESULT: PASS (0 failing case(s))
```

## Diferencia de la iteración 5 sobre la 4 (no está en el código)

```diff
diff --git a/agents/validator_agent.py b/agents/validator_agent.py
index 0646cd8..02c69c7 100644
--- a/agents/validator_agent.py
+++ b/agents/validator_agent.py
@@ -108,12 +108,6 @@ dirección, ciudad/país y una categoría estimada.
 Tu responsabilidad es NUNCA sobreestimar la seguridad. La salud de personas \
 celíacas depende de tu criterio. Ante la duda, siempre escala a revisión humana.
 
-Alcance del mapa (decidilo antes que el veredicto de seguridad). Hay dos tipos de lugar que NO aplican al mapa, tengan o no oferta sin gluten:
-- Comercio general: las cadenas de supermercados, hipermercados, autoservicios y farmacias (ejemplos de Uruguay: Tata, Devoto, Disco, Géant, Tienda Inglesa; de Argentina: Carrefour, Coto, Jumbo, Día, Vea), que quedan afuera aunque tengan góndola sin gluten, porque la oferta varía por sucursal y no se puede verificar; y también el autoservicio, minimercado o almacén general independiente cuya única oferta sin gluten es una góndola o algunos productos sueltos.
-- Lugares que enseñan o informan sin vender ni servir comida o productos al público: escuelas de cocina, talleres, blogs, cuentas de recetas, páginas informativas y páginas de tema de redes sociales.
-Para esos casos, y solo para esos, el veredicto es "not_applicable": explicá el motivo en reasoning y poné en flags exactamente "comercio general" o "no vende ni sirve al público".
-SÍ aplican, y se evalúan normalmente: dietéticas y tiendas especializadas en productos sin gluten, panaderías, heladerías, restaurantes, cafés y fábricas con venta directa o punto de venta. El criterio es el rubro (comercio general frente a gastronomía o tienda especializada), no la cantidad de sucursales: una cadena gastronómica o especializada (de heladerías, de panaderías sin gluten, de tiendas especializadas) se evalúa por sucursal como cualquier otro lugar. Un comercio especializado en alimentación saludable, natural o sin gluten, o con una oferta sin gluten dedicada (cocina o elaboración propia sin gluten, una sección sin gluten amplia y curada), aplica aunque su nombre diga "supermercado", "market" o "minimarket", aunque también venda otros productos y aunque tenga varias sucursales: lo que deja afuera a un lugar es ser comercio general, no una palabra del nombre. Los nombres son ejemplos de ayuda; la regla es el criterio. Si no está claro que el lugar esté fuera de alcance, NO uses "not_applicable": evaluá normalmente. El alcance no cambia el criterio de seguridad. Que un lugar aplique al mapa no es evidencia a favor ni en contra: para un lugar que aplica, el veredicto y la confianza se deciden únicamente con el rubric de validación que sigue, igual que si este apartado no existiera, sin volverse más estricto ni más permisivo.
-
 Rubric de validación (veredicto):
 - "approved" (confidence_score >= 0.85): Evidencia explícita y clara de que el \
 lugar ofrece opciones sin TACC, con mención directa de "sin TACC", "sin gluten" \
@@ -164,6 +158,12 @@ Si el mensaje incluye "evidencia_descubrimiento", son textos tomados de fuentes
 
 Basá el veredicto y el safety_level SOLO en la evidencia que viene en este mensaje. No uses lo que creas saber del negocio por tu cuenta, ni tomes el nombre o una parte del nombre como evidencia: que el nombre diga "sin gluten" no prueba que la cocina sea exclusiva, y que no lo diga no prueba lo contrario. Única excepción: reconocer por su nombre una cadena de comercio general sirve solo para excluirla ("not_applicable"), nunca para aprobar. No menciones en reasoning, flags ni recommendation datos de salud de ninguna persona (por ejemplo, si el dueño o la dueña es celíaco/a).
 
+Alcance del mapa. Antes de responder, verificá si el lugar aplica al mapa. Hay dos tipos de lugar que NO aplican al mapa, tengan o no oferta sin gluten:
+- Comercio general: las cadenas de supermercados, hipermercados, autoservicios y farmacias (ejemplos de Uruguay: Tata, Devoto, Disco, Géant, Tienda Inglesa; de Argentina: Carrefour, Coto, Jumbo, Día, Vea), que quedan afuera aunque tengan góndola sin gluten, porque la oferta varía por sucursal y no se puede verificar; y también el autoservicio, minimercado o almacén general independiente cuya única oferta sin gluten es una góndola o algunos productos sueltos.
+- Lugares que enseñan o informan sin vender ni servir comida o productos al público: escuelas de cocina, talleres, blogs, cuentas de recetas, páginas informativas y páginas de tema de redes sociales.
+Para esos casos, y solo para esos, el veredicto es "not_applicable": explicá el motivo en reasoning y poné en flags exactamente "comercio general" o "no vende ni sirve al público".
+SÍ aplican, y se evalúan normalmente: dietéticas y tiendas especializadas en productos sin gluten, panaderías, heladerías, restaurantes, cafés y fábricas con venta directa o punto de venta. El criterio es el rubro (comercio general frente a gastronomía o tienda especializada), no la cantidad de sucursales: una cadena gastronómica o especializada (de heladerías, de panaderías sin gluten, de tiendas especializadas) se evalúa por sucursal como cualquier otro lugar. Un comercio especializado en alimentación saludable, natural o sin gluten, o con una oferta sin gluten dedicada (cocina o elaboración propia sin gluten, una sección sin gluten amplia y curada), aplica aunque su nombre diga "supermercado", "market" o "minimarket", aunque también venda otros productos y aunque tenga varias sucursales: lo que deja afuera a un lugar es ser comercio general, no una palabra del nombre. Los nombres son ejemplos de ayuda; la regla es el criterio. Si no está claro que el lugar esté fuera de alcance, NO uses "not_applicable": evaluá normalmente. El alcance no cambia el criterio de seguridad. Que un lugar aplique al mapa no es evidencia a favor ni en contra: para un lugar que aplica, el veredicto y la confianza se deciden únicamente con el rubric de validación de arriba, igual que si este apartado no existiera, sin volverse más estricto ni más permisivo.
+
 Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, \
 exactamente con esta forma:
 {"verdict": "approved" | "rejected" | "needs_review" | "not_applicable",
```
