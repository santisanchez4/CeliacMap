# Deploy de `chat` v29: barrios por coordenadas (2026-11-21)

Con el «dale» del administrador, después del merge de los PR #64 (barrios) y #65 (Updater), `main` = `5d4e975`.

| Paso | Resultado |
|---|---|
| Antes | Corrección de ciudad de 10 filas aplicada (`db/fixes/2026-11-20-ciudades-pisadas-por-updater.sql`). El chequeo de solo lectura (aprobados con `city` de Montevideo o de la Capital y `region` vacía o distinta) dio 0. `chat` estaba en v28, con `verify_jwt=false` |
| Deploy | `node_modules/.bin/supabase functions deploy chat` desde `main`: sube `index.ts`, `barrios.ts`, `barrios_data.ts`, `regions.ts` y `prompts.ts` |
| Después | `chat` **v29**, `ACTIVE`, `verify_jwt=false` |
| Código desplegado | `supabase functions download chat --use-api`: los 5 archivos tienen el mismo SHA-256 que `main` (sin ``) |

`prompts.ts` no cambió, así que no reinicia el conteo del soft-launch.

## Turnos en vivo

`python db/checks/chat_barrios_live.py`, sesión `celiac-test-barrios-v29-20261121`, 20:01:32–20:01:55 UTC, 10 llamadas a
Haiku. Respuestas completas en `2026-11-21-chat-barrios-live-run.json`.

| Mensaje | Plan (`agent_log`) | Resultado |
|---|---|---|
| «dime un lugar para cenar en Ciudad Vieja Montevideo» | barrio Ciudad Vieja, restaurante | 1: Dalbertt (Mercedes 799, 100%) ✓ |
| «lugares sin gluten en Pocitos» | barrio Pocitos | 8: los 8 de adentro del polígono ✓ |
| «dónde comer en Palermo, Buenos Aires» | barrio Palermo, restaurante | 7 restaurantes del Palermo oficial ✓ |
| «un restaurante en Belgrano» | barrio Belgrano, restaurante | 0 adentro; «En Palermo hay 2», sin decir que están en Belgrano ✓ |
| «algo sin gluten en Malvín Alto» | ciudad, sin polígono | 0; «no encontré lugares para esa búsqueda en Malvín Alto» |

**Para la tanda de prompts:**
- El redactor repite «tengo confirmado» / «la comunidad tiene confirmados» / «opciones confirmadas»: es el punto 1.
- Con Malvín Alto no ofreció los lugares de Montevideo: el router no puso ciudad y no hubo `<datos_cercanos>`. Es el punto 4.
- Después de «En Palermo hay 2», un «sí, ¿cuáles?» listaría todos los restaurantes de Palermo, no solo los 2 cercanos.
  Queda anotado para la línea de cercanos (punto 3).

## Efectos en producción y limpieza

Línea base (20:00:32 UTC): 3 filas `chatbot` en `agent_log`, 3 filas `chat_usage` (todas del 2026-11-20), 2 `suggestions`,
2 `place_reports`. Los turnos escribieron 5 filas `agent_log` (`chat_turn`) y 3 contadores del 2026-11-21 (sesión, `ip:…` y
`global`, cada uno en 5); 0 lugares tocados. La limpieza `2026-11-21-chat-v29-test-cleanup.sql` tiene guardas de conteo
exacto. Con el «dale»: ensayo con ROLLBACK (1, 1, 1 y 5 filas, y vuelta a la línea base), después COMMIT. La lectura
posterior volvió a la línea base: 3 / 3 / 2 / 2, sin contadores del 2026-11-21.
