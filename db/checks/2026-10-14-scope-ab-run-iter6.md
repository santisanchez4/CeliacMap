# A/B del párrafo de alcance del Validator — iteración 6, prueba corta (2026-10-14)

`python db/checks/validator_scope_ab.py --only-new --n 5 --max-calls 75 --cases <15 casos>`: solo el brazo nuevo, 15 casos, 5
muestras. 75 llamadas planificadas, 75 hechas, tope 75, ~US$0,82. Ninguna falló.

Iteración 6: el apartado de alcance va al final del prompt (después del rubric de seguridad, antes de la forma del JSON); la regla
del comercio general independiente dice «cuya oferta sin gluten es una parte central y amplia de lo que vende, no una góndola», sin
vocabulario de seguridad; y «El alcance responde qué tipo de lugar es, nunca si es seguro».

Criterios del admin (2026-10-14). Referencia de la `RUBRIC` anterior: brazo OLD de las corridas de las iteraciones 1 y 2, 6 muestras.

| Caso | Criterio | Resultado | |
|---|---|---|---|
| Ramona | aprobado ≤ 1 de 5 | aprobado 2, revisión 3 | **FALLA** |
| Mi Cocina Sin Gluten | aprobado 0 de 5 | aprobado 1, revisión 4 | **FALLA** |
| Parrilla compartida | revisión 5 de 5 | revisión 5 de 5 (0,52) | pasa |
| EntreSano Healthy Supermarket | aprobado 5 de 5 | aprobado 5 de 5 | pasa |
| Minimarket La Isla | revisión 5 de 5 | revisión 5 de 5 | pasa |
| La Molienda | revisión 5 de 5 | revisión 5 de 5 | pasa |
| Zero Helados | revisión 5 de 5 | revisión 5 de 5 | pasa |
| Panadería que también da talleres | aprobado 5 de 5 | aprobado 5 de 5 | pasa |
| Autoservicio independiente con góndola | no aplica 5 de 5 | no aplica 5 de 5 | pasa |
| Devoto Express con góndola | no aplica 5 de 5 | no aplica 5 de 5 | pasa |
| By Gessi | no aplica 5 de 5 | no aplica 5 de 5 | pasa |
| Dietética, panadería exclusiva, fábrica, almacén natural | nunca no aplica | revisión 5 de 5 cada uno | pasa |

**Resultado: FALLA (2 casos).** Las aprobaciones de Ramona y Mi Cocina Sin Gluten bajan respecto de la iteración 5 (3 y 4 de 5)
pero siguen por encima de la `RUBRIC` anterior (1 de 6 y 0 de 6). Con 5 y 6 muestras la diferencia es chica y puede ser en parte
ruido, pero va en la dirección insegura, que es la que el criterio no admite. En la iteración 3 (apartado al principio, sin la
frase de la oferta) Mi Cocina Sin Gluten daba revisión 5 de 5; en la 4 (al principio, con «oferta dedicada») Ramona daba aprobado
5 de 5. Ninguna ubicación ni redacción probada deja a la vez la parrilla compartida y estos dos casos donde los dejaba la `RUBRIC`
anterior. Por instrucción del admin no hay séptima redacción: queda para su decisión.

## Salida

```text
PLAN: 15 case(s) x 1 arm(s) x n=5 = 75 call(s) to claude-sonnet-4-6, ~US$0.82; hard cap 75 call(s) (~US$0.82)

[out] devoto_con_gondola — Devoto Express
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
       No aplica al mapa: Devoto Express es una cadena de supermercados/autoservicios de comercio general en Uruguay, equivalente a las cadenas de supermercados excluidas explícitamente del alcance del mapa. Aunque la reseña menciona una góndola de productos sin TACC, este tipo de comercio general queda fuera del mapa porque la oferta varía por sucursal y no puede verificarse de forma confiable.

[out] by_gessi_escuela — By Gessi Cocina Inclusiva
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
       No aplica al mapa: La evidencia disponible (sitio web, reseñas de la comunidad) indica que By Gessi Cocina Inclusiva es una escuela de cocina y formación gastronómica que ofrece cursos presenciales y online sobre cocina sin gluten, no un establecimiento que vende ni sirve comida al público. Por lo tanto, queda fuera del alcance del mapa.

[in] zero_helados_cadena — Zero Helados
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.55, 0.52, 0.52, 0.52, 0.55]
       El nombre 'Zero Helados' sugiere un local de helados pero no aporta evidencia explícita de opciones sin TACC ni de protocolo de contaminación cruzada. La fuente es Google Places pero no se incluyen reseñas ni descripción del negocio que confirmen oferta apta para celíacos. Sin información adicional, la evidencia es insuficiente para aprobar o rechazar.

[in] ramona_cadena — Ramona
  NEW: verdict {'needs_review': 3, 'approved': 2} | status {'needs_review': 3, 'approved': 2} | confidence [0.72, 0.72, 0.72, 0.87, 0.87]
       La evidencia de descubrimiento indica que Ramona es una panadería y pastelería 100% sin gluten con 4 locales en Buenos Aires, lo cual apunta fuertemente a una cocina exclusiva. Sin embargo, la fuente es una sola publicación de redes sociales no verificada, y la dirección proviene de Google Places sin confirmación explícita de que este local específico (Av. Corrientes 1234) corresponde a una de esas sucursales activas, ni hay mención directa de 'sin TACC' o certificación.
  !! FAIL: approved in 2/5, more than with the previous RUBRIC (at most 1)

[in] mi_cocina_sin_gluten — Mi Cocina Sin Gluten
  NEW: verdict {'approved': 1, 'needs_review': 4} | status {'approved': 1, 'needs_review': 4} | confidence [0.87, 0.72, 0.72, 0.72, 0.62]
       El nombre del local, su categoría y la evidencia descubierta de su web indican explícitamente que es una tienda especializada en productos sin gluten con elaboración propia y venta directa al público, lo que la incluye claramente en el alcance del mapa. Sin embargo, la evidencia no confirma cocina 100% exclusiva libre de contaminación cruzada ni certificación celíaca explícita, por lo que el safety_level se limita a 'celiac_friendly'. La fuente es única y no verificada, pero el contexto es suficientemente específico para aprobar con revisión recomendada.
  !! FAIL: approved in 1/5, more than with the previous RUBRIC (at most 0)

[in] dietetica — Dietética Vida Sana
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La reseña menciona 'sin TACC' y asesoramiento personalizado, lo que es una señal positiva de que el local ofrece productos aptos para celíacos. Sin embargo, se trata de una única reseña comunitaria sin respaldo de evidencia adicional (sitio web, redes sociales, certificación), y no hay información sobre si la oferta sin TACC es central al negocio o complementaria. Se requiere confirmación humana para elevar la confianza y determinar el safety_level adecuado.

[in] panaderia_exclusiva — Panadería La Espiga
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La reseña de la comunidad indica que el local es 100% sin gluten y dedicado exclusivamente a celíacos, lo que es una señal positiva, pero por sí sola una reseña no verificada no es suficiente para aprobar ni para confirmar cocina exclusiva. No hay evidencia explícita de mención oficial de 'sin TACC', certificación o descripción de protocolos, y la fuente es Google Places sin mayor detalle adicional. Se requiere confirmación humana para elevar el veredicto.

[in] fabrica_con_venta_directa — Pastas Don Luis
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La evidencia de descubrimiento menciona explícitamente 'sin TACC' y venta al público directa desde fábrica, lo que es una señal positiva relevante. Sin embargo, proviene de una única fuente web no verificada, y no hay información sobre si la fábrica es exclusivamente sin TACC o si también elabora pastas con gluten, ni se menciona protocolo de contaminación cruzada. Esto impide alcanzar 'approved' y limita el safety_level a 'celiac_friendly' en lugar de 'gluten_free_100'.

[in] restaurante_con_opciones — La Parrilla de Juan
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.52, 0.52, 0.52, 0.52, 0.52]
       Hay una señal de la comunidad que menciona menú sin TACC, lo cual es evidencia parcial positiva, pero la misma reseña indica que comparten parrilla con productos con gluten, lo que representa un riesgo real de contaminación cruzada para celíacos. La ausencia de protocolo anti-contaminación cruzada verificado y el uso compartido de la parrilla impiden elevar el nivel de seguridad o aprobar el lugar.

[in] panaderia_que_tambien_da_talleres — Sin Trigo Panadería
  NEW: verdict {'approved': 5} | status {'approved': 5} | confidence [0.87, 0.87, 0.87, 0.87, 0.87]
       La evidencia de redes sociales indica explícitamente 'sin TACC' y describe un local especializado exclusivamente en panadería sin gluten (panes y facturas), lo que sugiere una cocina dedicada. No hay evidencia de que el local cocine también con gluten, y la especialización en un único tipo de producto sin TACC refuerza que es un establecimiento 100% libre de gluten.

[in] almacen_natural — Almacén Natural Don Pepe
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.52, 0.52, 0.52, 0.52, 0.52]
       El nombre sugiere un almacén de productos naturales, lo que es consistente con tener oferta sin gluten, pero la única señal disponible es una reseña comunitaria que menciona harinas y galletitas 'sin gluten' sin usar la denominación 'sin TACC' ni describir ningún protocolo especial. No hay evidencia explícita de especialización en celíacos ni de que la oferta sin gluten sea una parte central y amplia del negocio.

[in] entresano_supermercado_saludable — EntreSano Healthy Supermarket
  NEW: verdict {'approved': 5} | status {'approved': 5} | confidence [0.87, 0.87, 0.87, 0.88, 0.88]
       La evidencia de descubrimiento muestra una categoría dedicada 'Sin TACC' con 671 productos en su sitio web oficial, lo que indica que la oferta sin gluten es una parte central y amplia del negocio, no una simple góndola. La reseña de la comunidad refuerza esto con mención explícita de 'sin TACC'. No hay evidencia de protocolo de contaminación cruzada ni de cocina exclusiva, por lo que el safety_level se mantiene en 'celiac_friendly' y no se eleva a 'gluten_free_100'.

[in] minimarket_la_isla — Minimarket La Isla 24 hours.
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La evidencia descubierta en la web propia del lugar menciona más de 1.500 productos sin gluten y cocina propia, lo cual es una señal positiva y relevante; la reseña comunitaria refuerza que ofrecen variedad de productos sin TACC. Sin embargo, el local también vende almacén general, bebidas y vinos, y no hay mención explícita de protocolo anti-contaminación cruzada ni certificación, por lo que no se puede determinar si la cocina propia está dedicada exclusivamente a preparaciones sin TACC o si coexiste con productos con gluten.

[in] la_molienda_tienda_natural — La Molienda - Carrasco
  NEW: verdict {'needs_review': 5} | status {'needs_review': 5} | confidence [0.62, 0.62, 0.62, 0.62, 0.62]
       La evidencia muestra una tienda especializada en productos sin gluten (harinas, pastas, snacks, galletitas) con 444 artículos en categoría celíaco, lo que indica una oferta amplia y central, no una simple góndola. Sin embargo, la evidencia proviene de una única fuente web no verificada, no hay mención explícita de 'sin TACC', no se confirma protocolo anti-contaminación cruzada, y no está claro si esta dirección de Carrasco es un local físico activo o solo un punto de distribución de la tienda online.

[out] autoservicio_independiente — Autoservicio El Trébol
  NEW: verdict {'not_applicable': 5} | status {'discarded': 5} | confidence [None, None, None, None, None]
       No aplica al mapa: Autoservicio El Trébol es un autoservicio/almacén general independiente cuya única oferta sin gluten mencionada es una góndola de productos, lo que lo excluye del alcance del mapa. La reseña comunitaria confirma que se trata de una sección dentro de un comercio general, no de una tienda especializada en productos sin gluten.

calls made: 75 of a cap of 75
RESULT: FAIL (2 failing case(s))
```
