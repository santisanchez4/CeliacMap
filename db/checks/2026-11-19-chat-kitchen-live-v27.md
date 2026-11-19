# S1 y S2 en vivo — chat v27 (2026-11-19)

Verificación del arreglo de `decideDraftAmendment` / `isBareConfirmation` / lugar nuevo sin comentario (PR #57) contra
`chat` **v27** (deploy desde `main` `e12028b`, `verify_jwt=false`, código descargado = `HEAD`), con el «dale» del
administrador. `python db/checks/chat_kitchen_live.py --send --only S1 S2`, 8 turnos, ventana 2026-11-19 03:22:58Z –
03:23:45Z. Respuestas crudas: `2026-11-19-chat-kitchen-live-v27.json`.

| Escenario | Resultado |
|---|---|
| S1 dato + dueño después del borrador | **PASA.** El turno 3 vuelve a mostrar el mismo borrador con la dirección y «contás que la cocina es exclusivamente sin gluten»; no repite al dueño ni pregunta por la cocina. «dale, mandalo» envía: fila con la dirección, `kitchen_exclusive=true`, sin clave del dueño. |
| S2 «lugar nuevo que no está en el mapa» | **PASA.** Pide nombre y lugar, después la dirección; muestra el borrador (nombre + dirección) sin exigir comentario; «dale» envía: fila con dirección, `notes` null, sin datos de cocina. |

**Observación:** en S1.3 el redactor sumó el aviso «Anónimo» a una sugerencia de lugar nuevo (el aviso es para comentarios
sobre lugares del mapa; el texto de una sugerencia no se publica como opinión). Dice «puede publicarse»: queda del lado
prudente. Anotado en `docs/plans/next-prompt-batch.md` (ítem 10), porque corregirlo es un cambio de prompt.

## Efectos en producción y limpieza

Línea base: `place_reports` 2, `suggestions` 2, `agent_log` chatbot 0, `chat_usage` vacía. Escrito: 2 `suggestions`, 8 filas
`agent_log` (`chatbot`), 4 contadores `chat_usage` (2 sesiones + `global` 8 + `ip:…` 8, sin tráfico ajeno), 0 lugares tocados.
**Revertido** con el SQL mostrado y aprobado antes (bloque `do`, conteo exacto 2 / 8 / 2 / 2, línea base comprobada al
final). Lectura posterior: `place_reports` 2, `suggestions` 2, `agent_log` chatbot 0, `chat_usage` vacía, 0 lugares tocados.
