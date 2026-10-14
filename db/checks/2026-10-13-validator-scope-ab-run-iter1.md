# A/B del párrafo de alcance del Validator — iteración 1 (2026-10-13)

`python db/checks/validator_scope_ab.py --old-rev HEAD --n 3` (OLD = RUBRIC del #22, NEW = primera redacción del párrafo de alcance, que nombraba a
Zero Helados, Ramona y Mi Cocina Sin Gluten como ejemplos de cadenas que sí aplican). Lugares sintéticos, sin base de datos. La capa
determinista (`agents/map_scope.py`) no interviene: todos los casos van al modelo.

**La corrida se cortó en el último caso** (`autoservicio_independiente`, solo informativo): la API de Anthropic respondió 400,
«Your credit balance is too low». Los 23 casos con criterio de aceptación sí se midieron (138 llamadas).

## Lectura

- **Fuera de alcance (14 casos): 42 de 42 muestras `not_applicable` → `discarded`.** Con la RUBRIC anterior, Devoto Express con una
  reseña de góndola sin TACC salía `approved` 3 de 3 (0,86–0,87), y Géant, Tienda Inglesa, Coto y Disco (2 de 3) quedaban en `needs_review`.
  Incluye una cadena que no está en ninguna lista (Supermercados Toledo), una farmacia de cadena, By Gessi con su evidencia real
  (reseñas sobre cursos), un blog y una cuenta de recetas.
- **Dentro de alcance (9 casos): 0 de 27 muestras `not_applicable`.** La panadería que también dicta talleres sigue `approved` 3 de 3.
- **Señal a corregir:** en los tres casos cuyos nombres figuraban en la RUBRIC la confianza subió. Zero Helados pasó de 0,50–0,52 a
  0,62–0,65 y su razonamiento cita la «reputación» de la cadena (conocimiento propio); Ramona y Mi Cocina Sin Gluten dieron
  `approved` 0,87 en 1 de 3 (antes 0 de 3). Con n=3 no es concluyente, pero va en la dirección insegura. La iteración 2 saca los
  nombres de negocios que sí aplican y agrega que aplicar al mapa no es evidencia de seguridad. **La iteración 2 no está medida**
  (sin crédito en la API).
- `restaurante_con_opciones`: 1 de 3 `rejected` (0,35) con la RUBRIC nueva, por la parrilla compartida; antes 3 de 3 `needs_review`.
  Va en la dirección conservadora; a mirar en la próxima corrida.

## Salida

```text

[out] geant — Géant Fresh Market
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.52, 0.52, 0.52]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Géant Fresh Market es una cadena de supermercado/hipermercado de comercio general en Uruguay. Este tipo de establecimientos quedan fuera del alcance del mapa porque la oferta sin gluten varía por sucursal y no puede verificarse de forma consistente.

[out] tata — Ta-Ta
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.05, 0.05, 0.05]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Ta-Ta es una cadena de supermercados de comercio general en Uruguay. Aunque pueda contar con góndola de productos sin gluten, queda fuera del alcance del mapa porque la oferta varía por sucursal y no es un comercio especializado ni gastronómico.

[out] devoto_con_gondola — Devoto Express
  OLD: verdict {'approved': 3} | status {'approved': 3} | confidence [0.86, 0.87, 0.86]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Devoto Express es una sucursal de la cadena de supermercados Devoto, que corresponde al tipo de cadena de comercio general excluida del alcance del mapa. Aunque cuente con una góndola de productos sin TACC, la oferta varía por sucursal y no puede verificarse de forma centralizada. Este tipo de establecimiento queda fuera del alcance del sistema independientemente de su oferta sin gluten.

[out] disco — Disco N° 5
  OLD: verdict {'rejected': 1, 'needs_review': 2} | status {'discarded': 1, 'needs_review': 2} | confidence [0.05, 0.5, 0.5]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Disco es una cadena de supermercados de comercio general en Uruguay, por lo que queda fuera del alcance del mapa. Aunque pueda tener góndola de productos sin TACC, la oferta varía por sucursal y no puede verificarse de forma centralizada.

[out] tienda_inglesa_con_gondola — Tienda Inglesa
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Tienda Inglesa es una cadena de supermercados/hipermercados de Uruguay, lo que la excluye del alcance del mapa. Aunque cuente con góndola de productos sin TACC, la oferta varía por sucursal y no es verificable de manera consistente. Este tipo de comercio general queda fuera del alcance definido.

[out] carrefour — Carrefour Market
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.15, 0.15, 0.15]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Carrefour Market es una cadena de comercio general (supermercado/hipermercado), lo que lo excluye del alcance de CeliacMap. Aunque pueda tener góndola con productos sin gluten, la oferta varía por sucursal y no es verificable de forma centralizada.

[out] coto_con_gondola — Coto
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.55, 0.55]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Coto es una cadena de supermercados de comercio general, excluida del alcance del mapa independientemente de que cuente con góndola de productos sin TACC. La oferta varía por sucursal y no puede verificarse de forma centralizada.

[out] jumbo — Jumbo
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.2, 0.15, 0.2]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Jumbo es una cadena de hipermercados de comercio general, excluida del alcance del mapa. Aunque pueda contar con góndola de productos sin gluten, la oferta varía por sucursal y no es verificable de manera centralizada.

[out] dia — Supermercado DIA
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.1, 0.1, 0.1]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Supermercado DIA es una cadena de comercio general (hipermercado/supermercado) que queda fuera del alcance del mapa, independientemente de si cuenta con góndola sin gluten. La oferta varía por sucursal y no puede verificarse de forma centralizada.

[out] cadena_no_listada — Supermercados Toledo
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.1, 0.1, 0.1]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Supermercados Toledo es una cadena de supermercados de comercio general, por lo que queda fuera del alcance del mapa independientemente de si cuenta con góndola de productos sin gluten. Este tipo de establecimientos no se pueden verificar de forma consistente por sucursal.

[out] farmacia_de_cadena — Farmacity
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.05, 0.05, 0.05]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Farmacity es una cadena de farmacias de comercio general, no un comercio especializado en alimentos sin gluten ni un establecimiento gastronómico. Aunque pueda tener productos sin TACC en góndola, la oferta varía por sucursal y no es verificable de forma centralizada. Este tipo de lugar queda fuera del alcance del mapa.

[out] by_gessi_escuela — By Gessi Cocina Inclusiva
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.15, 0.15, 0.15]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Toda la evidencia disponible —reseñas de la comunidad y la web oficial— indica que By Gessi Cocina Inclusiva es una escuela de cocina y plataforma de cursos (presenciales y online) de cocina sin gluten, sin evidencia de que venda o sirva comida o productos al público. Se trata de un espacio educativo/formativo, categoría expresamente excluida del alcance del mapa.

[out] blog — Celíacos en Montevideo
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.15, 0.15, 0.15]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: La evidencia indica que 'Celíacos en Montevideo' es un blog con recetas, guías y novedades para la comunidad celíaca, sin venta ni servicio de comida o productos al público. Este tipo de espacio informativo queda fuera del alcance del mapa según las reglas de alcance definidas.

[out] cuenta_de_recetas — Cocina Sin TACC con Lau
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.1, 0.1, 0.1]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: La evidencia muestra que se trata de una cuenta de redes sociales dedicada a publicar recetas sin TACC, no un local físico que vende o sirve alimentos al público. No hay indicios de que opere como establecimiento gastronómico o comercio; la dirección aportada no está respaldada por ninguna verificación de existencia del negocio.

[in] zero_helados_cadena — Zero Helados
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.5, 0.52, 0.5]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.65, 0.65, 0.62]
       Zero Helados es una cadena de heladerías conocida en Uruguay con reputación de ofrecer productos sin TACC, pero al tratarse de una ficha de Google Places sin evidencia explícita adjunta en este mensaje (no se incluyen reseñas, evidencia_descubrimiento ni declaraciones_comunidad), no hay datos suficientes para confirmar el protocolo anti-contaminación cruzada ni la oferta específica de esta sucursal en Av. Italia 3456. Se evalúa como lugar gastronómico/especializado y no como cadena de comercio general, por lo que sí aplica al mapa. Se requiere verificación humana para confirmar la oferta sin TACC y los protocolos de esta sucursal específica.

[in] ramona_cadena — Ramona
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.72, 0.72, 0.72]
  NEW: verdict {'needs_review': 2, 'approved': 1} | status {'needs_review': 2, 'approved': 1} | confidence [0.72, 0.72, 0.87]
       La evidencia de descubrimiento menciona explícitamente '100% sin gluten' y se trata de una panadería/pastelería especializada, lo que es una señal fuerte. Sin embargo, la fuente es únicamente una cuenta de Instagram no verificada, y la dirección fue geocodificada sin ficha de Google Places que confirme que este local específico existe y opera en Av. Corrientes 1234; además, el perfil no menciona 'sin TACC' ni describe protocolo anti-contaminación cruzada. Para elevar a 'approved' y a 'gluten_free_100' se requiere verificación del local en esa dirección y confirmación de cocina exclusivamente sin gluten.

[in] mi_cocina_sin_gluten — Mi Cocina Sin Gluten
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'approved': 1, 'needs_review': 2} | status {'approved': 1, 'needs_review': 2} | confidence [0.87, 0.62, 0.62]
       La evidencia de descubrimiento indica elaboración propia de productos sin gluten con venta directa en locales propios, lo que sugiere una tienda especializada exclusivamente en productos sin gluten. El nombre del establecimiento y la descripción apuntan consistentemente a un comercio 100% dedicado a productos sin TACC, sin indicios de que se trabaje con gluten en el mismo espacio. Sin embargo, la fuente no está verificada y no menciona explícitamente certificación ni protocolo anti-contaminación cruzada, por lo que el nivel gluten_free_100 se sustenta principalmente en la descripción de elaboración propia exclusiva.

[in] dietetica — Dietética Vida Sana
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.65, 0.62]
       Hay una reseña de la comunidad que menciona 'sin TACC' y variedad de productos, lo que es una señal positiva y específica. Sin embargo, una sola reseña no es suficiente evidencia para aprobar: no hay información sobre protocolo de contaminación cruzada, certificaciones ni descripción del establecimiento que confirme especialización exclusiva en productos sin gluten. Se requiere confirmación humana del local.

[in] panaderia_exclusiva — Panadería La Espiga
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
       La única señal de que el local es exclusivamente sin gluten proviene de una reseña de la comunidad, que por sí sola no es suficiente para alcanzar 'approved' ni para confirmar 'gluten_free_100'. No hay evidencia explícita de certificación, mención de 'sin TACC', descripción de protocolos o fuentes verificadas que respalden la afirmación. Se requiere confirmación humana para elevar el veredicto.

[in] fabrica_con_venta_directa — Pastas Don Luis
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
       La evidencia de descubrimiento menciona explícitamente 'sin TACC' y venta directa al público, lo que es una señal positiva relevante; sin embargo, proviene de una única fuente web no verificada. No se especifica si la fábrica es exclusivamente sin TACC o si también elabora pastas con gluten, y no hay información sobre protocolos de contaminación cruzada ni reseñas de la comunidad que respalden la afirmación.

[in] restaurante_con_opciones — La Parrilla de Juan
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.52, 0.52, 0.52]
  NEW: verdict {'needs_review': 2, 'rejected': 1} | status {'needs_review': 2, 'discarded': 1} | confidence [0.52, 0.35, 0.52]
       Existe una reseña comunitaria que menciona menú sin TACC, lo cual es una señal positiva, pero la misma reseña advierte que comparten parrilla con productos con gluten, lo que representa un riesgo real de contaminación cruzada para celíacos. No hay evidencia de protocolo anti-contaminación cruzada ni certificación, y el uso de parrilla compartida es una alerta de seguridad significativa.

[in] panaderia_que_tambien_da_talleres — Sin Trigo Panadería
  OLD: verdict {'approved': 3} | status {'approved': 3} | confidence [0.87, 0.87, 0.87]
  NEW: verdict {'approved': 3} | status {'approved': 3} | confidence [0.87, 0.87, 0.87]
       La evidencia de descubrimiento en redes sociales menciona explícitamente 'sin TACC' y describe un local de venta de panes y facturas, lo que indica especialización en productos sin gluten. No hay indicios de que se trabaje con ingredientes con gluten en el local, y el nombre refuerza la orientación exclusiva, aunque el nombre por sí solo no se toma como evidencia. El hecho de que también dicten talleres no cambia el rubro principal, que es la panadería con venta al público.

[in] almacen_natural — Almacén Natural Don Pepe
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.52, 0.52, 0.52]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.55, 0.55, 0.55]
       La reseña menciona 'sin gluten' pero no 'sin TACC', lo que podría ser marketing genérico sin certificación médica. El nombre sugiere un almacén de productos naturales que podría tener sección sin gluten, pero no hay evidencia explícita de especialización, certificación ni protocolo anti-contaminación cruzada. La señal es parcial y requiere confirmación humana.

[report] autoservicio_independiente — Autoservicio El Trébol
(corte: anthropic.BadRequestError 400, credit balance is too low)
```
