# Reporte final — IM Montevideo (Locales_Gluten_Free) en CeliacMap

- **Fuente:** capa pública `Locales_Gluten_Free` de la Intendencia de Montevideo (Servicio de Regulación Alimentaria), última edición
  25/01/2024; 35 locales, capturados el 2026-10-13 (`imm_locales_libres_de_gluten.csv`).
- **Aplicado en producción el 2026-10-13**, con el SQL y los comandos mostrados antes y verificado en solo lectura después de cada paso.
- Cotejo: [`reporte_cotejo_imm.md`](reporte_cotejo_imm.md). Decisión y motivo por fila: [`plan.json`](plan.json).

## Resumen (35 locales)

| Resultado | Cantidad | Detalle |
|---|---|---|
| Ya estaban en el mapa | 11 | 8 verdes, 3 ámbar |
| Agregados al mapa | 3 | 3 verdes (aprobación manual del admin), 0 ámbar |
| En la base, fuera del mapa (pendientes de aprobación) | 4 | 2 nuevos (Zero) + 2 que ya estaban en `needs_review` |
| No insertado por decisión del admin | 1 | Alfajores Juana La Loca |
| Rechazado (indicios de cierre) | 1 | Celicatessen |
| No aplica al mapa | 14 | elaboradores / distribuidores sin venta al público verificable |
| Solo reporte | 1 | Heladería Zero (Av. Millán) |

Ningún lugar quedó en ámbar con el flag «100% pendiente de confirmación del administrador».

## 1. Ya estaban en el mapa (11) — sin cambios

Verdes (8): Mi Cocina Sin Gluten (L. A. de Herrera), Mi Cocina Sin Gluten (San José 1284), Rikuras Sin Gluten, Un Lugar Sin Gluten,
Café Ramona - WTC, Café Ramona - Centro, Selkkis Gluten Free y **Casa & Dispensa** (Solano García 2496: es el local que la IM registra como
«GOÛT GLUTEN FREE», habilitación vencida el 30/11/2025).

Ámbar (3): Pecorino - apto Celiacos, Alárabi Cocina Inclusiva, gluteno Sana Ingesta.

Verificación: estado, color, `updated_at` y hash de las 11 filas son idénticos antes y después. A Casa & Dispensa solo se le sumó una fila
en `place_evidence` con la habilitación IM (evidencia complementaria; no cambia su estado ni su color).

## 2. Agregados al mapa (3) — verdes, por decisión manual del admin

Las tres filas existían como `discarded` (el Validator no había tenido ninguna evidencia). El admin (Santiago Sánchez) revisó redes y web y
las aprobó como «Espacio 100% sin gluten» con `APROBACIÓN MANUAL (2026-10-13)`; la nota anterior del Validator queda debajo y
`validation_confidence` / `verified` no se tocaron. No pasaron por el Validator: su veredicto de prueba (dry-run) figura como referencia.

| IM | Fila | Antes | Ahora | Evidencia guardada (`place_evidence`, `admin`) | Dry-run del Validator | Habilitación IM |
|---|---|---|---|---|---|---|
| HELIX · Joffre 1005 | Cooperativa de Trabajo Helix Uruguay | discarded 0,95 | approved · 🟢 | Revisión del admin: sitio cooperativahelix.com.uy y WhatsApp 092 410 428 | needs_review 0,62 | vencida 28/05/2024 |
| FERNILAND · Cochabamba 2949 | FERNILAND S.A. | discarded 0,10 | approved · 🟢 | Bio de Instagram @fernilanduy, teléfono y sitio | approved 0,87 ámbar | vigente hasta 21/10/2027 |
| ME GUSTA · Carlos Roxlo 1374 | Me Gusta | discarded 0,75 | approved · 🟢 | Bio de Instagram @megusta_uy y teléfonos | approved 0,92 ámbar + 100% pendiente | vigente hasta 04/08/2028 |

Helix y Ferniland figuran en la IM con rubro de elaboración (`Elab`): quedan en el mapa por decisión del admin.

## 3. En la base, fuera del mapa — pendientes de aprobación (4)

| IM | Fila | Estado | Motivo |
|---|---|---|---|
| ZERO · 26 de Marzo 1325 | **Zero Helados - Pocitos** (nueva, `2525eb19…`) | needs_review 0,72 · `celiac_friendly` | Entró como `pending` y la validó el Validator. El sitio propio dice «no contiene gluten ni T.A.C.C.», pero la habilitación IM figura vencida (22/10/2025) y no hay evidencia de exclusividad ni de protocolo. Google: `OPERATIONAL`. |
| ZERO · Av. Alfredo Arocena 1997 | **Zero Helados - Carrasco** (nueva, `21d2e7e1…`) | needs_review 0,72 · `celiac_friendly` | Ídem; además Google no tiene ficha del local en esa dirección (solo se geocodificó la dirección). El sitio propio lista las tiendas «Zero Carrasco» y «Zero Pocitos». Habilitación IM vencida el 25/01/2026. |
| ARTESANIA PASTELERA · Av. Gral. Rivera 3431 | Artesanía Pastelera | needs_review 0,52 (sin cambios) | Por decisión del admin queda como está. El dry-run daba approved 0,88 en ámbar (sitio propio: «productos sin conservantes, libre de gluten (aptos para celíacos)»). Habilitación vigente hasta 30/10/2027. |
| ENCANTO · Uruguayana 3419 bis | Alimentos Encanto | needs_review 0,52 (sin cambios) | Por decisión del admin queda como está. El dry-run daba needs_review 0,62. Habilitación vencida el 17/05/2024. |

## 4. No se agregan

**No insertado por decisión del admin (1)** — ALFAJORES JUANA LA LOCA (Marcelino Sosa 2433): elaborador con tienda online y «pick up»; el
dry-run daba needs_review 0,72. Habilitación vencida el 17/03/2026.

**Rechazado (1)** — CELICATESSEN (Santa Mónica 2533): indicios de cierre. Google lo marca `CLOSED_PERMANENTLY` y su sitio no responde.
Habilitación IM vigente hasta 27/09/2028.

**Solo reporte (1)** — HELADERIA ZERO (Av. Millán 3665): habilitación IM vencida el 09/03/2026; dirección ocupada por otro negocio
(Piu Helados Prado, ya en el mapa). No se agrega ni se mezcla con Piu.

**No aplica al mapa (14)** — no son lugares para visitar o no tienen venta al público verificable:

| IM | Motivo | Habilitación IM |
|---|---|---|
| MILENA GLUTEN FREE · El Greco 5994 | Google no tiene ficha ahí (devuelve la de Bv. Artigas 2748, ya en el mapa). El sitio propio lista una sola «TIENDA-CAFÉ» y, aparte, una «PLANTA»: sería la planta. **Comparte nombre con la fila existente.** | vigente hasta 26/09/2028 |
| RICCA · Cuaró 3139 | Elaborador y distribuidor; sin comercio «Ricca» en la dirección (Ríccoli, a 27 m, es otro negocio). | vencida 16/08/2024 |
| RAWY LIVING FOODS · Av. Italia 6547 | Elaborador con tienda online; dirección con horario de oficina. Sin citas sobre gluten: además, no verificable. | vigente hasta 11/04/2028 |
| CONAPROLE · Virrey J. J. de Vértiz 1969 | Planta láctea y distribuidor. | vencida 24/11/2025 |
| DE LA TIERRA · Ing. A. Caubarrere 4608 | Procesado de frutas, importador y distribuidor; su sitio no menciona venta al público ni gluten. | vencida 20/03/2024 |
| GIBUR · Cnel. J. Belinzon 5005 | Fábrica de conservas y distribuidor; ídem. | vencida 13/09/2024 |
| MOLINO GUIDO · Av. Gral. Flores 3123 | Molino con tienda online y puntos de venta de terceros; su sitio también vende harina de trigo. | vencida 23/06/2025 |
| JOVECA S.R.L. · Convenio 827 bis | Giros de elaboración; Google no tiene ningún comercio con ese nombre en la dirección ni cerca. | vigente hasta 31/03/2027 |
| TOMASI ZUNINO ENRIQUE · Manuel Correa 3514 bis | Ídem (panificadora). | vigente hasta 04/08/2027 |
| BLARTIS S.A. · Ruta 1 8398 | Ídem (distribuidor sin depósito). | vigente hasta 06/02/2027 |
| GRUPO D ALIMENTOS · Núñez de Arce 5045 | Ídem (panificados). | vigente hasta 22/04/2028 |
| INTEGRO · Gral. Pagola 1765 | Ídem (congelados, comercio electrónico). | vigente hasta 10/07/2028 |
| VICTORIA · 26 de Marzo 3265 apto. 904 | Ídem (distribuidor sin depósito, un apartamento). | vigente hasta 01/12/2027 |
| ALBERTA · Gabriel A. Pereira 2820 | Ídem (comidas en bandejas, distribuidor). | vencida 24/01/2025 |

## Qué se escribió en producción

1. `db/fixes/2026-10-13-imm-admin-evidence.sql`: 7 filas en `place_evidence` (`source = 'admin'`): la habilitación IM de Helix, Ferniland,
   Me Gusta y Casa & Dispensa, y la revisión manual del admin de las tres primeras. `places` no cambió.
2. `aprobaciones_manuales.sh --apply`: tres `scripts.review_queue --approve … --level 100`.
3. `scripts.import_imm_source apply --apply --only 34 35`: 2 filas nuevas en `places` (`source = 'manual'`), 6 filas en `place_evidence`
   (habilitación IM + dos citas literales del sitio propio por local) y 2 registros `validate` en `agent_log` con la fuente, la fecha de
   captura y el vencimiento.

Totales: `places` 1385 → 1387; `place_evidence` 6 → 19; ninguna fila en `pending`.

## Hallazgos al margen

- **Goût (Paraguay 1962, `needs_review`)** no se tocó. Las citas que el buscador de evidencia le atribuía hablaban de otros negocios: como
  su `social_url` es un reel de Instagram, el buscador toma cualquier reel como «propio». Es un límite de `agents/evidence_finder.py` a corregir.
- Las tres filas aprobadas a mano no tenían ningún registro de una revisión anterior (`agent_log`, `place_evidence`, notas): si se habían
  revisado, quedó fuera del sistema. Regla nueva en `docs/DECISIONS.md`.
- Alárabi (0,82) y gluteno Sana Ingesta (0,72) siguen aprobados con el rubric binario de junio, por debajo del gate actual de 0,85.
