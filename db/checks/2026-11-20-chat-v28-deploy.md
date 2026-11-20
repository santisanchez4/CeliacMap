# Deploy de `chat` v28 (2026-11-20)

Con el «dale» del administrador, después del merge del PR #61 (`main` = `319253d`).

| Paso | Resultado |
|---|---|
| Antes | `chat` v27, `verify_jwt=false` |
| Deploy | `node_modules/.bin/supabase functions deploy chat` desde `main`: sube `index.ts`, `regions.ts`, `prompts.ts` |
| Después | `chat` **v28**, `ACTIVE`, `verify_jwt=false` (sin tocar el toggle) |
| Código desplegado | `supabase functions download chat --use-api`: `index.ts`, `prompts.ts` y `regions.ts` con el mismo SHA-256 que `main` (sin `\r`). `index.ts` nombra `asociacionceliaca.org.ar` 4 veces y `celiaco.org.ar` 0 |
| Turno real | «¿Dónde puedo comer sin gluten en Montevideo?», sesión `celiac-test-deploy-v28-20261120`, 22:28:40–22:28:48 UTC: 8 lugares (4 en 100%, 4 con opciones; Rikuras, Un Lugar Sin Gluten y La Commedia ya como opciones) y `scope_note` «Las etiquetas salen de lo que declara cada local o cuentan sus clientes. CeliacMap no inspecciona ni certifica los lugares: confirmá siempre en el lugar.» Dos llamadas a Haiku |

`prompts.ts` no cambió: no reinicia el conteo del soft-launch.

**Observación para la tanda de prompts:** el redactor abrió con «la comunidad tiene confirmados varios lugares». «Confirmados»
promete más que lo que hacemos, igual que «verificado»: va con el cambio de nombre de la etiqueta y la batería.

## Efectos en producción y limpieza

Línea base (22:28:00 UTC): 0 filas `chatbot` en `agent_log`, `chat_usage` vacía, 2 `suggestions`, 2 `place_reports`. El turno
escribió 1 fila `agent_log` (`chat_turn`) y 3 contadores `chat_usage` (sesión, `ip:…`, `global`, cada uno en 1); 0 lugares
tocados. Limpieza: `2026-11-20-chat-v28-test-cleanup.sql` (guardas de conteo exacto y vuelta a la línea base), con el «dale»:
ensayo con ROLLBACK (cada borrado, exactamente 1 fila), después COMMIT. Lectura posterior: 0 filas `chatbot` en `agent_log`,
`chat_usage` vacía, 2 `suggestions`, 2 `place_reports`: la línea base.
