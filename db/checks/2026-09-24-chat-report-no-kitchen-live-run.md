# Chatbot: una reseña de un lugar ya mapeado no pregunta ni guarda cocina (2026-09-24)

Cambio de solo código (los prompts no cambian, no se reinicia el conteo del soft-launch): un borrador `report` —una
recomendación o un reporte sobre un lugar que ya está en el mapa— **nunca** pregunta por la cocina ni lleva datos de
cocina. La cocina se pregunta solo al **agregar un comercio** (borradores `suggestion`) y en el Módulo 4 (confirmar un
lugar en revisión). Es la misma decisión del dueño que en el formulario "¿Ya fuiste a un lugar del mapa?".

Evidencia cruda: `2026-09-24-chat-report-no-kitchen-live-run.json` (9 turnos). Script: `chat_kitchen_live.py`
(`--only S1 S4 S5 S11`).

## Despliegue

| | |
|---|---|
| `chat` v16 → v17 | `supabase functions deploy chat --use-api`; código descargado **idéntico a `HEAD`** (0 líneas de diferencia en `index.ts` y `prompts.ts`) |
| `verify_jwt` | sigue en `false`: un POST sin `Authorization` responde 400 (no 401) |
| Tests | chat 201 → 202 (`deno check` limpio); 6 tests reescritos primero en rojo |

## Escenarios en vivo

| # | Qué prueba | Resultado |
|---|---|---|
| S1 | comercio **nuevo**: dirección → pregunta de cocina (una vez) → respuesta con datos → confirmar | ✅ igual que antes: pregunta una sola vez y termina con "¿Lo envío así?"; la sugerencia quedó con `kitchen_exclusive=true`, `owner_celiac=true` |
| S4 | recomendar un lugar **ya en el mapa** | ✅ el borrador no pregunta por la cocina ni resume datos de cocina; "dale" escribe un reporte positivo con `kitchen_*` nulos |
| S11 | lo mismo, diciendo además "tienen cocina separada para celíacos" | ✅ el dato de cocina **se ignora**: el borrador no lo repite ni pregunta, y el reporte quedó con `kitchen_exclusive`, `celiac_prep` y `owner_celiac` nulos (la frase queda solo como texto del comentario) |
| S5 | reporte **negativo** | ✅ sin pregunta, sin escritura |

Sin marcas de fuga (`<envio>`, `<datos>`, tablas, "system prompt") en ningún turno. No se corrió la batería de
jailbreak: el cambio no toca prompts, alcance ni guardianes, solo dónde se aplica el paso de cocina.

## Reversión

Todo lo del test era propio: el contador global (9) coincidía con la suma de las sesiones `celiac-test-kitchen-…` (4 + 2
+ 2 + 1), y los 9 registros del log estaban dentro de la ventana del test. Se borraron en **una** transacción con
guardas de cantidad (1 sugerencia, 2 reportes, 9 filas del log, 6 contadores; si alguna cantidad no coincidía, abortaba
todo), con el SQL mostrado antes. Verificación contra la línea base: `suggestions` 2 filas (huella `b021476b…`),
`place_reports` 2 filas (huella `b1b3087c…`), log del chatbot 95, contadores de hoy 0, `places` 1311, 0 sobrantes.
