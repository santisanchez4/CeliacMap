# A/B de las reglas de alcance — iteraciones 2 y 3 del Validator, y prompts de Social y Web (2026-10-13)

Lugares y textos sintéticos, sin base de datos. OLD = `fix/social-agent-post-is-not-a-profile` (PR #22). En el A/B del Validator la
capa determinista (`agents/map_scope.py`) no interviene: todos los casos van al modelo. Se sumaron tres casos de control «dentro de
alcance» por decisión del admin: EntreSano Healthy Supermarket, Minimarket La Isla y La Molienda.

## Lectura

**Validator, iteración 2** (sin nombres de negocios que sí aplican, más «no es evidencia de seguridad»; n=3, 27 casos, 162 llamadas,
corrida completa): **FALLA**.

- Fuera de alcance: 42 de 42 muestras `not_applicable`.
- Dentro de alcance: **EntreSano Healthy Supermarket salió `not_applicable` en 1 de 3**, y en las otras dos bajó de `approved` 0,87
  (RUBRIC anterior, 3 de 3) a `needs_review` 0,62. Los otros 11 casos, 0 de 33.
- Efecto lateral: el restaurante con parrilla compartida pasó de `needs_review` 0,52 (3 de 3) a `rejected` 0,30–0,35 (3 de 3). En la
  iteración 1 había sido 1 de 3.
- Mi Cocina Sin Gluten dio `approved` 0,87 en 1 de 3 (antes 0 de 3); Ramona, 0 de 3 (antes 1 de 3). Zero Helados, 0,55 (antes 0,50–0,52).
- Informativo: un autoservicio independiente con góndola sin TACC salió `not_applicable` 3 de 3 (antes `needs_review` 0,62).

**Validator, iteración 3** (la que está en el código). Dos cambios sobre la 2: se agrega que un comercio especializado en
alimentación saludable, natural o sin gluten aplica aunque su nombre diga «supermercado», «market» o «minimarket», venda también
otros productos o tenga varias sucursales; y la última oración pasa a «no es evidencia a favor ni en contra de su seguridad: […]
decidí el veredicto y la confianza exactamente igual que si este párrafo no existiera».

- Prueba corta (solo brazo NEW, n=5, 7 casos, 35 llamadas): **PASA**. EntreSano vuelve a `approved` 0,87 en 5 de 5, igual que con
  la RUBRIC anterior; La Isla y La Molienda `needs_review` 0,62 en 5 de 5; Mi Cocina Sin Gluten `needs_review` en 5 de 5; Devoto
  Express `not_applicable` 5 de 5. El restaurante con parrilla compartida sigue saliendo `rejected` en 2 de 5 (antes 0 de 6): el
  efecto lateral se reduce pero no desaparece. El autoservicio independiente sigue `not_applicable` 5 de 5.
- **Corrida completa (n=3, los dos brazos): se cortó en el séptimo caso de 27** por «credit balance is too low». Los seis casos que
  llegaron a medirse son fuera de alcance y dieron `not_applicable` en 18 de 18. **Los 20 casos restantes de la iteración 3 no están
  medidos con la corrida completa.**

**Agente Social, `PARSE_RUBRIC`** (`db/checks/discovery_scope_ab.py social`, Haiku, n=3, 19 casos, 114 llamadas): **PASA**.

- Las seis páginas que no venden (blog, cuenta de recetas, escuela, taller, asociación, página informativa): `sells_to_public`
  `false` en 18 de 18.
- Los once negocios (incluidos EntreSano, La Isla, La Molienda, dos cadenas gastronómicas, una panadería que también da talleres y
  un emprendimiento por pedido): `false` en 0 de 33; nombre y categoría iguales a los del brazo OLD (una muestra de Zero Helados dio
  `shop` en vez de `cafe`).
- Informativos: un texto ambiguo da `null` 3 de 3 (sigue al Validator); una cuenta personal de reseñas con «mi tienda de premezclas
  en el link» da `true` 3 de 3: no se descarta en Social y la decide el Validator.

**Agente Web, `RESEARCH_RUBRIC`** (`db/checks/discovery_scope_ab.py web`): **sin medir.**

- Con el modelo por defecto (`WEB_SEARCH_MODEL=claude-haiku-4-5`) las ocho llamadas dieron 400: «'claude-haiku-4-5-20251001' does not
  support programmatic tool calling. The following tools have `allowed_callers` that require it: web_search, web_fetch». Es un
  defecto previo de `agents/clients/llm.py` (versiones `web_search_20260209` / `web_fetch_20260209`), no de este cambio: el agente
  Web no puede correr hoy con su modelo por defecto. Está deshabilitado en el pipeline desde la Fase 11.
- Se reintentó con `WEB_SEARCH_MODEL=claude-sonnet-4-6` (n=1, cuatro turnos de investigación en paralelo). No devolvió resultados
  antes de que la cuenta se quedara sin crédito; es la causa más probable del consumo.

## Salida — Validator, iteración 2 (corrida completa)

```text
[out] geant — Géant Fresh Market
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.52, 0.52, 0.52]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Géant Fresh Market es una cadena de hipermercados / comercio general en Uruguay, lo que la excluye del alcance del mapa independientemente de que cuente con góndola de productos sin gluten. La oferta sin TACC varía por sucursal y no puede verificarse de forma centralizada.

[out] tata — Ta-Ta
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.05, 0.05, 0.05]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Ta-Ta es una cadena de supermercados de comercio general en Uruguay, por lo que queda fuera del alcance del mapa. Este tipo de establecimientos no se pueden verificar de manera consistente por sucursal para garantizar una oferta sin TACC.

[out] devoto_con_gondola — Devoto Express
  OLD: verdict {'approved': 3} | status {'approved': 3} | confidence [0.87, 0.87, 0.87]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Devoto Express es una sucursal de la cadena de supermercados Devoto, que entra en la categoría de cadenas de comercio general excluidas del alcance del mapa. Aunque cuente con una góndola de productos sin TACC, la oferta varía por sucursal y no es verificable de forma sistemática. Este tipo de establecimientos está explícitamente fuera del alcance de CeliacMap.

[out] disco — Disco N° 5
  OLD: verdict {'needs_review': 1, 'rejected': 2} | status {'needs_review': 1, 'discarded': 2} | confidence [0.5, 0.1, 0.1]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Disco es una cadena de supermercados de Uruguay (comercio general), por lo que queda fuera del alcance del mapa independientemente de si tiene góndola de productos sin TACC. La oferta varía por sucursal y no es verificable de forma centralizada.

[out] tienda_inglesa_con_gondola — Tienda Inglesa
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Tienda Inglesa es una cadena de supermercados de comercio general en Uruguay, excluida del alcance del mapa independientemente de su oferta sin gluten. La góndola sin TACC mencionada en la reseña no cambia este criterio, ya que la oferta varía por sucursal y no puede verificarse de forma consistente.

[out] carrefour — Carrefour Market
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.15, 0.2, 0.15]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Carrefour Market es una cadena de comercio general (supermercado), por lo que queda fuera del alcance del mapa. La oferta de productos sin gluten varía por sucursal y no puede verificarse de forma centralizada.

[out] coto_con_gondola — Coto
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.55, 0.55, 0.55]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Coto es una cadena de supermercados de comercio general en Argentina, lo que la excluye del alcance del mapa. Este tipo de establecimientos queda fuera independientemente de que cuente con góndola de productos sin TACC, ya que la oferta varía por sucursal y no puede verificarse de forma consistente.

[out] jumbo — Jumbo
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.2, 0.15, 0.2]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Jumbo es una cadena de hipermercados de comercio general que queda fuera del alcance del mapa, aunque pueda contar con góndola de productos sin gluten. La oferta varía por sucursal y no es verificable de forma centralizada.

[out] dia — Supermercado DIA
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.1, 0.1, 0.1]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Supermercado DIA es una cadena de comercio general (hipermercado/supermercado) que queda fuera del alcance del mapa, independientemente de si cuenta con góndola de productos sin TACC. La oferta varía por sucursal y no puede verificarse de forma centralizada.

[out] cadena_no_listada — Supermercados Toledo
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.1, 0.1, 0.1]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Supermercados Toledo es una cadena de supermercados de comercio general, equivalente a los hipermercados y autoservicios mencionados como fuera de alcance del mapa. Este tipo de establecimientos queda excluido porque la oferta sin gluten varía por sucursal y no puede verificarse de forma centralizada.

[out] farmacia_de_cadena — Farmacity
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.1, 0.1, 0.05]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Farmacity es una cadena de farmacias de comercio general, no un comercio especializado en gastronomía ni tienda especializada en productos sin gluten. Este tipo de establecimiento queda fuera del alcance del mapa, ya que la oferta varía por sucursal y no puede verificarse de forma centralizada.

[out] by_gessi_escuela — By Gessi Cocina Inclusiva
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.15, 0.15, 0.2]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Toda la evidencia disponible —incluyendo las reseñas de la comunidad y la web oficial— indica que By Gessi Cocina Inclusiva es una escuela de cocina y plataforma de formación gastronómica (cursos presenciales y online), no un establecimiento que vende o sirve comida al público. Al tratarse de un espacio educativo sin venta de alimentos al consumidor, queda fuera del alcance del mapa.

[out] blog — Celíacos en Montevideo
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.15, 0.15, 0.18]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: La evidencia describe un blog con recetas, guías y novedades para la comunidad celíaca, lo que lo clasifica como un espacio informativo que no vende ni sirve comida o productos al público. Este tipo de recurso queda fuera del alcance del mapa según las reglas de alcance definidas.

[out] cuenta_de_recetas — Cocina Sin TACC con Lau
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.1, 0.1, 0.1]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: La evidencia disponible indica que se trata de una cuenta de redes sociales que publica recetas sin TACC, sin ninguna referencia a venta de productos o servicio de comida al público. No existe un local físico ni actividad comercial verificable: es un perfil informativo/educativo de recetas.

[in] zero_helados_cadena — Zero Helados
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.52, 0.5, 0.5]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.55, 0.55, 0.55]
       El nombre 'Zero Helados' podría sugerir una propuesta sin gluten o baja en azúcar, pero el nombre por sí solo no constituye evidencia válida de oferta sin TACC ni de protocolo de contaminación cruzada. No se cuenta con reseñas, evidencia de descubrimiento ni declaraciones de la comunidad que confirmen opciones sin TACC. La fuente es Google Places pero no se aportaron datos de la ficha (descripción, categorías, reseñas).

[in] ramona_cadena — Ramona
  OLD: verdict {'needs_review': 2, 'approved': 1} | status {'needs_review': 2, 'approved': 1} | confidence [0.72, 0.72, 0.85]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.72, 0.72, 0.72]
       La evidencia de descubrimiento indica explícitamente '100% sin gluten' y menciona que es una panadería/pastelería especializada con 4 locales, lo que sugiere una cocina dedicada; sin embargo, proviene de una única fuente de redes sociales no verificada y no hay reseñas de la comunidad ni confirmación independiente que respalde la exclusividad de la cocina para esta sucursal específica en Av. Corrientes 1234.

[in] mi_cocina_sin_gluten — Mi Cocina Sin Gluten
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'needs_review': 2, 'approved': 1} | status {'needs_review': 2, 'approved': 1} | confidence [0.62, 0.87, 0.62]
       La evidencia indica elaboración propia de productos sin gluten con venta directa al público, lo que sugiere especialización, pero no hay mención explícita de 'sin TACC', certificación oficial ni descripción de protocolo anti-contaminación cruzada. La fuente web no verificada y la ausencia de confirmación sobre si la cocina es exclusivamente sin gluten impiden alcanzar el umbral de 'approved'. Se requiere verificación humana para confirmar protocolos y si el establecimiento es 100% libre de gluten.

[in] dietetica — Dietética Vida Sana
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
       La reseña menciona 'sin TACC' y destaca asesoramiento, lo que sugiere conocimiento del tema celíaco, pero proviene de una única reseña comunitaria sin respaldo de evidencia adicional (web, redes, certificación). No hay información sobre protocolo de contaminación cruzada ni si el local es exclusivamente sin gluten o vende también productos con gluten.

[in] panaderia_exclusiva — Panadería La Espiga
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.55, 0.55]
       La única señal relevante proviene de una reseña de la comunidad que afirma que el local es 100% sin gluten y cocina exclusivamente para celíacos, pero las reseñas por sí solas no son suficiente para alcanzar 'approved' ni para confirmar 'gluten_free_100'. No hay evidencia explícita adicional (publicación oficial, certificación, descripción verificada) que respalde la exclusividad de la cocina ni el uso del término 'sin TACC'. Se requiere verificación humana para confirmar si la cocina es realmente dedicada y si el lugar opera bajo protocolo apto para celíacos.

[in] fabrica_con_venta_directa — Pastas Don Luis
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
       La evidencia principal es una sola fuente web no verificada que menciona explícitamente 'sin TACC', lo cual es una señal positiva y específica; sin embargo, al tratarse de una única fuente aislada no es suficiente para 'approved'. No hay información sobre protocolo de contaminación cruzada ni confirmación de si la cocina es exclusivamente sin gluten o también elabora pastas con gluten.

[in] restaurante_con_opciones — La Parrilla de Juan
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.52, 0.52, 0.52]
  NEW: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.3, 0.35, 0.32]
       La única evidencia disponible es una reseña de la comunidad que menciona menú sin TACC, pero advierte explícitamente que comparten parrilla, lo cual representa un riesgo serio de contaminación cruzada inaceptable para celíacos. La ausencia de protocolo de separación en la parrilla, siendo este el elemento central de cocción de un establecimiento de este tipo, impide cualquier nivel de confianza suficiente.

[in] panaderia_que_tambien_da_talleres — Sin Trigo Panadería
  OLD: verdict {'approved': 3} | status {'approved': 3} | confidence [0.88, 0.87, 0.88]
  NEW: verdict {'approved': 3} | status {'approved': 3} | confidence [0.87, 0.87, 0.87]
       La evidencia de redes sociales menciona explícitamente 'sin TACC' y describe una panadería que vende panes y facturas en el local, lo que indica un establecimiento especializado en productos sin gluten. El nombre refuerza la especialización, y la mención directa de 'sin TACC' en el perfil público es una señal clara de orientación a celíacos. Sin embargo, se detecta que el local también dicta talleres de panificación, lo que podría implicar presencia de insumos externos o personas manipulando harinas, aunque en el contexto de una panadería sin TACC esto es menos crítico.

[in] almacen_natural — Almacén Natural Don Pepe
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.52, 0.52, 0.52]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.52, 0.52, 0.52]
       La reseña menciona productos 'sin gluten' pero no hay referencia explícita a 'sin TACC', certificación ni protocolo de prevención de contaminación cruzada. El nombre sugiere un almacén de productos naturales que podría tener sección dedicada, pero la evidencia es insuficiente para confirmar especialización o seguridad para celíacos. Se requiere verificación directa del local.

[in] entresano_supermercado_saludable — EntreSano Healthy Supermarket
  OLD: verdict {'approved': 3} | status {'approved': 3} | confidence [0.87, 0.88, 0.88]
  NEW: verdict {'needs_review': 2, 'not_applicable': 1} | status {'needs_review': 2, 'discarded': 1} | confidence [0.62, None, 0.62]
       El sitio web muestra una categoría explícita 'Sin TACC' con 671 productos, lo que constituye evidencia relevante de oferta real para celíacos en un comercio especializado en alimentación saludable. Sin embargo, el nombre 'Healthy Supermarket' y la amplitud del catálogo sugieren que no es un local exclusivamente sin TACC, sino un comercio general saludable con sección dedicada, por lo que no puede descartarse contaminación cruzada ni asignarse un nivel mayor. Se recomienda revisión humana para confirmar protocolos de manipulación y si la tienda física opera igual que el e-commerce.
  !! FAIL: an in-scope place was excluded in 1/3

[in] minimarket_la_isla — Minimarket La Isla 24 hours.
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
       El sitio web del negocio menciona más de 1.500 productos sin gluten y cocina propia, y una reseña de la comunidad confirma variedad de productos sin TACC; sin embargo, la evidencia no especifica protocolo de contaminación cruzada ni certificación, y la combinación de minimarket general con cocina propia (que podría manejar productos con gluten) genera incertidumbre sobre la seguridad para celíacos. La mención de 'sin gluten' sin 'sin TACC' explícito y la ausencia de protocolo documentado impiden aprobar sin revisión humana.

[in] la_molienda_tienda_natural — La Molienda - Carrasco
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
       La evidencia muestra una tienda especializada en productos sin gluten en Uruguay con una sección dedicada (444 artículos), lo que es una señal positiva, pero la evidencia proviene de una única fuente web no verificada y no hay mención explícita de 'sin TACC', protocolo de contaminación cruzada ni confirmación de que esta sucursal específica (Carrasco, Av. Arocena 2014) tenga presencia física operativa. La evidencia parece referir a una tienda online, por lo que no queda claro si la dirección corresponde a un local físico de venta al público.

[report] autoservicio_independiente — Autoservicio El Trébol
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Autoservicio El Trébol es un autoservicio, es decir, un comercio general de alimentación equivalente a un supermercado o minimarket, categoría explícitamente excluida del alcance del mapa. La reseña confirma que tiene una góndola sin TACC, pero la oferta de un autoservicio varía y no puede verificarse de forma consistente por sucursal.

RESULT: FAIL (1 failing case(s))
exit 1
```

## Salida — Validator, iteración 3, prueba corta (`--only-new --n 5 --cases ...`)

```text
[out] devoto_con_gondola — Devoto Express
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
[in] mi_cocina_sin_gluten — Mi Cocina Sin Gluten
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
[in] restaurante_con_opciones — La Parrilla de Juan
  NEW: verdict {'needs_review': 3, 'rejected': 2} | status {'needs_review': 3, 'discarded': 2} | confidence [0.52, 0.52, 0.35, 0.35, 0.52]
[in] entresano_supermercado_saludable — EntreSano Healthy Supermarket
  NEW: verdict {'approved': 5} | status {'approved': 5} | confidence [0.87, 0.87, 0.87, 0.87, 0.87]
[in] minimarket_la_isla — Minimarket La Isla 24 hours.
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
[in] la_molienda_tienda_natural — La Molienda - Carrasco
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
[report] autoservicio_independiente — Autoservicio El Trébol
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]

RESULT: PASS (0 failing case(s))
```

## Salida — Validator, iteración 3, corrida completa (cortada)

```text
[out] geant — Géant Fresh Market
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.52, 0.52, 0.52]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Géant Fresh Market es una cadena de comercio general (supermercado/hipermercado) en Uruguay, similar a Géant, que queda explícitamente fuera del alcance del mapa. Aunque pueda tener góndola de productos sin gluten, la oferta varía por sucursal y no es verificable de forma centralizada. Este tipo de establecimientos no aplica al mapa CeliacMap.

[out] tata — Ta-Ta
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.05, 0.05, 0.05]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Ta-Ta es una cadena de supermercados de comercio general en Uruguay, equivalente a Tata/TA-TA, que aunque pueda tener góndola de productos sin TACC, queda fuera del alcance del mapa por ser un comercio general cuya oferta varía por sucursal y no puede verificarse de manera centralizada.

[out] devoto_con_gondola — Devoto Express
  OLD: verdict {'approved': 3} | status {'approved': 3} | confidence [0.87, 0.87, 0.87]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Devoto Express es una sucursal de la cadena de supermercados Devoto, que corresponde a la categoría de comercio general excluida del alcance del mapa. Aunque cuente con una góndola de productos sin TACC, la oferta varía por sucursal y no puede verificarse de forma centralizada. Este tipo de establecimiento queda fuera del mapa independientemente de su oferta.

[out] disco — Disco N° 5
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.1, 0.1, 0.1]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Disco es una cadena de supermercados de comercio general en Uruguay, por lo que queda fuera del alcance del mapa independientemente de que tenga góndola sin gluten. Este tipo de establecimientos se excluyen porque la oferta varía por sucursal y no puede verificarse de forma centralizada.

[out] tienda_inglesa_con_gondola — Tienda Inglesa
  OLD: verdict {'needs_review': 3} | status {'needs_review': 3} | confidence [0.62, 0.62, 0.62]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Tienda Inglesa es una cadena de supermercados de comercio general en Uruguay, lo que la excluye del alcance del mapa. Aunque cuente con una góndola de productos sin TACC, la oferta varía por sucursal y no es verificable de forma centralizada. Este tipo de establecimiento queda fuera del mapa independientemente de su oferta sin gluten.

[out] carrefour — Carrefour Market
  OLD: verdict {'rejected': 3} | status {'discarded': 3} | confidence [0.15, 0.2, 0.1]
  NEW: verdict {'not_applicable': 3} | status {'discarded': 3} | confidence [None, None, None]
       No aplica al mapa: Carrefour Market es una sucursal de Carrefour, cadena de comercio general (hipermercado/supermercado), que queda explícitamente fuera del alcance del mapa. Aunque pudiera tener góndola sin gluten, la oferta varía por sucursal y no puede verificarse de forma centralizada.

[out] coto_con_gondola — Coto
(corte: anthropic.BadRequestError 400, credit balance is too low)
```

## Salida — Social, `PARSE_RUBRIC`

```text
model: claude-haiku-4-5 · n=3 · OLD = fix/social-agent-post-is-not-a-profile

[out] blog — Celíacos en Montevideo (@celiacosenmvd) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'None': 1, 'Celíacos en Montevideo': 2} | category {'None': 3}
  NEW: sells_to_public {'False': 3} | name {'None': 3} | category {'None': 3}

[out] cuenta_de_recetas — Cocina Sin TACC con Lau (@cocinasintaccconlau) • Instagram photos and videos
  OLD: sells_to_public {"'—'": 3} | name {'Cocina Sin TACC con Lau': 3} | category {'None': 3}
  NEW: sells_to_public {'False': 3} | name {'None': 3} | category {'None': 3}

[out] escuela_de_cocina — By Gessi | Educación Gastronómica Sin Gluten (@bygessi) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'By Gessi': 3} | category {'cafe': 3}
  NEW: sells_to_public {'False': 3} | name {'By Gessi': 3} | category {'None': 3}

[out] taller — Taller de Panadería Sin Gluten - Facebook
  OLD: sells_to_public {"'—'": 3} | name {'Taller de Panadería Sin Gluten': 3} | category {'cafe': 3}
  NEW: sells_to_public {'False': 3} | name {'Taller de Panadería Sin Gluten': 3} | category {'None': 3}

[out] asociacion — ACELU - Asociación Celíaca del Uruguay | Facebook
  OLD: sells_to_public {"'—'": 3} | name {'ACELU - Asociación Celíaca del Uruguay': 3} | category {'None': 3}
  NEW: sells_to_public {'False': 3} | name {'None': 3} | category {'None': 3}

[out] pagina_informativa — Vivir sin gluten Argentina (@vivirsingluten.ar) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'Vivir sin gluten Argentina': 2, 'None': 1} | category {'None': 3}
  NEW: sells_to_public {'False': 3} | name {'None': 3} | category {'None': 3}

[in] panaderia — Panadería La Espiga Sin Gluten (@laespiga.singluten) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'Panadería La Espiga Sin Gluten': 3} | category {'cafe': 3}
  NEW: sells_to_public {'True': 3} | name {'Panadería La Espiga Sin Gluten': 3} | category {'cafe': 3}

[in] dietetica — Dietética Vida Sana - Facebook
  OLD: sells_to_public {"'—'": 3} | name {'Dietética Vida Sana': 3} | category {'shop': 3}
  NEW: sells_to_public {'True': 3} | name {'Dietética Vida Sana': 3} | category {'shop': 3}

[in] restaurante — La Parrilla de Juan (@laparrilladejuan) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'La Parrilla de Juan': 3} | category {'restaurant': 3}
  NEW: sells_to_public {'True': 3} | name {'La Parrilla de Juan': 3} | category {'restaurant': 3}

[in] heladeria_cadena — Zero Helados (@zerohelados) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'Zero Helados': 3} | category {'cafe': 3}
  NEW: sells_to_public {'True': 3} | name {'Zero Helados': 3} | category {'cafe': 2, 'shop': 1}

[in] panaderia_cadena — Ramona | Panadería y pastelería 100% sin gluten (@ramona.singluten) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'Ramona': 3} | category {'cafe': 3}
  NEW: sells_to_public {'True': 3} | name {'Ramona': 3} | category {'cafe': 3}

[in] panaderia_que_tambien_da_talleres — Sin Trigo Panadería (@sintrigo.panaderia) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'Sin Trigo Panadería': 3} | category {'cafe': 3}
  NEW: sells_to_public {'True': 3} | name {'Sin Trigo Panadería': 3} | category {'cafe': 3}

[in] fabrica_con_venta_directa — Pastas Don Luis - Fábrica de pastas sin TACC | Facebook
  OLD: sells_to_public {"'—'": 3} | name {'Pastas Don Luis': 3} | category {'shop': 3}
  NEW: sells_to_public {'True': 3} | name {'Pastas Don Luis': 3} | category {'shop': 3}

[in] emprendimiento_por_pedido — Dulce Miga – Pastelería libre de gluten (@dulcemiga.sg) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'Dulce Miga': 3} | category {'cafe': 3}
  NEW: sells_to_public {'True': 3} | name {'Dulce Miga': 3} | category {'cafe': 3}

[in] entresano — Entresano Supermercado Saludable (@entresano.supersaludable) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'Entresano Supermercado Saludable': 3} | category {'shop': 3}
  NEW: sells_to_public {'True': 3} | name {'Entresano Supermercado Saludable': 3} | category {'shop': 3}

[in] minimarket_la_isla — La Isla 24/7 (@laisla24_7) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'La Isla 24/7': 3} | category {'shop': 3}
  NEW: sells_to_public {'True': 3} | name {'La Isla 24/7': 3} | category {'shop': 3}

[in] la_molienda — La Molienda (@lamoliendauy) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'La Molienda': 3} | category {'shop': 3}
  NEW: sells_to_public {'True': 3} | name {'La Molienda': 3} | category {'shop': 3}

[report] texto_ambiguo — Sin Gluten Uruguay (@singlutenuy) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'Sin Gluten Uruguay': 3} | category {'shop': 2, 'None': 1}
  NEW: sells_to_public {'None': 3} | name {'Sin Gluten Uruguay': 3} | category {'None': 3}

[report] influencer_con_tienda — Celi Viajera (@celiviajera) • Instagram
  OLD: sells_to_public {"'—'": 3} | name {'Celi Viajera': 3} | category {'None': 3}
  NEW: sells_to_public {'True': 3} | name {'Celi Viajera': 3} | category {'None': 3}

RESULT: PASS (0 failing case(s))
```
