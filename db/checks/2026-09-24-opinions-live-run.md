# Verificación en vivo de las opiniones de la comunidad (2026-09-24)

Contra producción, con `db/checks/opinions_live.py` (clave pública para la parte anónima; la clave de servicio, por el
mismo camino que `scripts/moderate_opinions.py`, para moderar) y `db/checks/2026-09-24-opinions-columns.sql`.

## Despliegue, en el orden fijado

| Paso | Resultado |
|---|---|
| Ensayo: migración + checks en **una** transacción con `ROLLBACK` | sin errores; verificación posterior: sin columnas nuevas, sin vista, misma huella (`edd36c07162b97246a738000aab31373`) |
| Control negativo: los checks **sin** la migración | fallan (`column "author_name" ... does not exist`): el ejecutor de verdad los evalúa |
| Migración aplicada (`begin; … commit;`) | 2 columnas, 2 CHECKs, vista con sus 8 columnas, política con `published_at is null`; `place_reports` y `places` sin cambios |
| **Hallazgo:** privilegios de la vista | `anon` tenía **todos** los privilegios sobre `community_opinions` (Supabase los otorga por defecto a objetos nuevos y mi `grant select` solo sumó). La vista con `JOIN` no es actualizable (medido: `is_updatable = NO`), así que no había camino explotable, pero corre con los permisos del dueño y se salta la RLS: si se simplificara, `anon` habría podido escribir en `place_reports` a través de ella |
| Corrección | `revoke all … from anon, authenticated; grant select …` (también en `db/schema.sql`), con un test y una aserción nueva en el check SQL; el check **falló** contra producción antes de la corrección y **pasó** después. Privilegios finales: vista `anon:SELECT, authenticated:SELECT`; tabla `anon:INSERT, authenticated:INSERT` |
| Lectura pública con la anon key | vista → 200; tabla `place_reports` → 401 `permission denied`; `owner_celiac` / `kitchen_exclusive` por la vista → 400 `column ... does not exist` |
| Merge a `main` + push | `deploy-pages.yml` en verde |

## Escenarios (`opinions_live.py`) — 6/6

| # | Qué prueba | Resultado |
|---|---|---|
| a | un anónimo inserta con `published_at` ya cargado | ✅ HTTP 401, 0 filas |
| b | recomendación normal con el nombre "Prueba" | ✅ 201, una fila, `published_at` vacío |
| c | vista pública antes de aprobar | ✅ no aparece |
| d | listado de moderación (service role) | ✅ aparece con su lugar (la consulta con `JOIN` embebido funciona en producción) |
| e | `--approve --apply` | ✅ la vista la muestra con `author_name = 'Prueba'` |
| f | `--hide --apply` | ✅ la vista ya no la muestra |

## Reversión

Una sola fila de prueba (la del paso b; la del paso a nunca llegó a existir). `DELETE` por `id` **y** marcador exacto,
mostrado antes de ejecutar. Verificación contra la línea base: `place_reports` n = 2, huella `edd36c07162b97246a738000aab31373`,
0 filas sobrantes, 0 publicadas.

## Publicación de San Felipa

El comentario positivo del 2026-09-23 sobre *San Felipa - Sin gluten* (Gualeguaychú) —sin nombre, sin datos
personales— se publicó con `python -m scripts.moderate_opinions --approve <id> --apply`. En https://celiacmap.org
aparece como **Anónimo**, con la tarjeta de invitación al lado (es un solo comentario) y el enlace "sobre San Felipa -
Sin gluten · Gualeguaychú" abre el lugar en el mapa (clic real verificado). Los testimonios inventados ya no están y
"Acerca" ya no dice "académico".

## Lo que la verificación en el navegador encontró y el resto no

Un bug de CSS: `.field { display: flex }` le ganaba al atributo `hidden`, y en modo "Reportar" el campo de nombre
seguía visible. Los tests de DOM simulado solo miran la propiedad `.hidden`; se vio en Chrome real y quedó cubierto con
`.field[hidden]` más un test sobre el CSS.
