# ADR-004: Reportes comunitarios como evidencia, no acción directa

**Estado:** Propuesto

## Contexto
El formulario de "Recomendar o reportar" permite que personas celíacas
recomienden lugares ya publicados en el mapa (experiencia positiva) o
reporten una mala experiencia en un lugar ya aprobado (experiencia
negativa). A diferencia del formulario de sugerencia de lugares nuevos
(que alimenta el pipeline de descubrimiento vía la tabla `suggestions`),
esto introduce una fuente de evidencia distinta sobre lugares que **ya
pasaron** por el Validator y están publicados — con el riesgo de que un
reporte mal intencionado, un error de tipeo, o una experiencia puntual y
no representativa degrade o eleve la confianza de un lugar sin el mismo
nivel de escrutinio que se aplicó originalmente.

## Decisión
Los reportes comunitarios (`place_reports`) nunca modifican directamente
el estado de un lugar. Se tratan como evidencia nueva que se reinyecta al
mismo flujo de decisión del Validator (rubric de tres niveles, ADR-001),
replicando el patrón ya usado en outreach (ADR-002):

1. **Registro en tabla intake** — cada reporte queda en `place_reports`
   (`report_type`: positive/negative, `place_id` o `place_name_text`,
   `status: new`), nunca escribe directo sobre `places`.
2. **Disparo de re-evaluación, no de acción** — un reporte `negative`
   sobre un lugar ya `approved` dispara automáticamente una
   re-evaluación vía el mismo rubric del Validator (`RUBRIC` y
   `_normalize` reusados sin duplicación, igual que
   `outreach_reply_handler.py`), no un downgrade automático. El Validator
   puede confirmar el estado actual, bajarlo a `needs_review`, o
   descartarlo — igual que decidiría ante cualquier otra evidencia nueva.
3. **Reportes `positive` no disparan automatismo** — quedan como
   evidencia acumulada visible para revisión manual y como señal
   cualitativa, pero no reevalúan por sí solos un lugar ya aprobado (un
   solo elogio no debe "reforzar" artificialmente la confianza sin
   nueva evidencia objetiva).
4. **Lugares sin match** (`place_id` nulo, solo `place_name_text`) no
   disparan nada automático — quedan en `new` para que un humano los
   vincule, o se deriven al flujo de sugerencia de lugar nuevo si
   corresponde.
5. **Sin límite de reportes por lugar todavía** — a diferencia de
   outreach (que tiene `OUTREACH_MONTHLY_LIMIT`), no se define un techo
   de volumen en esta primera versión, dado que el volumen esperado es
   bajo comparado con el pipeline de outreach.

## Consecuencias

**Positivas:**
- Los lugares ya publicados dejan de ser "estáticos" tras la aprobación
  — pueden degradarse si la realidad cambia (ej. un lugar deja de tener
  protocolo sin TACC real), sin que Santiago tenga que revisarlo
  manualmente cada vez.
- Mantiene el mismo principio de todo el proyecto: ninguna fuente
  externa (comercio, comunidad) tiene autoridad para aprobar o rechazar
  directamente — solo el rubric del Validator decide.
- Reusa código y criterio ya probado (`ValidatorAgent._normalize`),
  evitando una segunda implementación paralela de lógica de decisión.

**Negativas / trade-offs aceptados:**
- Un solo reporte negativo mal intencionado o erróneo puede disparar una
  re-evaluación innecesaria — mitigado porque el Validator, no el
  reporte, decide el resultado final, pero consume presupuesto de API
  igual.
- Reportes `positive` no generan ningún efecto automático — pueden
  sentirse "ignorados" por quien los envía, al no haber feedback visible
  inmediato.
- Sin techo de volumen definido, un pico de reportes contra un mismo
  lugar podría generar múltiples re-evaluaciones redundantes en poco
  tiempo — riesgo a monitorear una vez en producción, no bloqueante para
  esta versión.
- El autocomplete de lugares consulta la tabla `places` directamente
  desde el cliente — expone nombres/ciudades ya públicos en el mapa, sin
  dato sensible, pero es una superficie nueva de consulta directa a la
  base.
