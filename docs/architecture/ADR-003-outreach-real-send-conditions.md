# ADR-003: Condiciones para habilitar envío real de outreach a comercios

**Estado:** Aceptado

## Contexto
El Outreach Agent (Etapa 1 y 2) está implementado y verificado end-to-end,
pero desde su construcción todo envío fue dirigido únicamente a
`OUTREACH_TEST_RECIPIENT` — nunca a un comercio real. Activar el
destinatario real (`contact_email` en vez del test recipient) introduce
riesgos que no existían en el resto del proyecto: reputación de dominio
(spam/bounce), consentimiento implícito (se contacta a comercios que nunca
pidieron ser contactados), y volumen (más de 40 lugares ya elegibles, con
más sumándose cada corrida mensual).

## Decisión
Antes de activar el destinatario real, se establecen tres condiciones,
todas resueltas antes de este ADR ser aceptado:

1. **Dominio propio verificado en Resend** (`celiacmap.org`) — requisito
   técnico duro, el sandbox de Resend no puede entregar a destinatarios
   externos. Verificado (DKIM, SPF, MX de envío y recepción) el 4 de
   agosto de 2026.
2. **Mecanismo de opt-out explícito** — cada email de outreach incluye una
   línea fija, no generada por IA, indicando cómo pedir no ser contactado
   de nuevo. Las respuestas se clasifican con un paso barato de Haiku
   antes de la re-evaluación completa del rubric (Sonnet); un opt-out
   detectado marca `places.outreach_opt_out = true` de forma permanente y
   excluye el lugar de toda futura selección, sin excepción. La
   clasificación falla hacia "no es opt-out" en caso de error, nunca al
   revés, para evitar bloquear un comercio legítimo por un falso positivo.
3. **Volumen inicial acotado** — primer envío real limitado a
   `OUTREACH_MONTHLY_LIMIT=3`, no el default de 20, para observar tasa de
   respuesta y de rebote antes de escalar.

## Consecuencias

**Positivas:**
- Cierra el propósito real del Outreach Agent: reduce la cola de
  `needs_review` con evidencia directa del comercio, no solo
  hipotéticamente.
- El opt-out protege la reputación del dominio a largo plazo y respeta la
  voluntad del comercio contactado.
- El volumen acotado permite detectar problemas (bounces, quejas, baja
  tasa de respuesta) con bajo costo antes de escalar.

**Negativas / trade-offs aceptados:**
- Mayor complejidad operativa: hay que monitorear respuestas, rebotes y
  opt-outs manualmente al principio, no hay dashboard dedicado todavía.
- Un comercio puede percibir el email como spam pese al opt-out, con
  impacto reputacional imposible de controlar del todo.
- El volumen acotado inicial retrasa el objetivo de "vaciar" la cola de
  `needs_review` — es una decisión consciente de ir despacio primero.
- `OUTREACH_TEST_RECIPIENT` sigue siendo el único destinatario hasta que
  se aplique un cambio de código explícito y revisado que use
  `contact_email` como destino real — este ADR documenta las condiciones
  cumplidas, no activa el envío por sí solo.
