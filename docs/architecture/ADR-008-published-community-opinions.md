# ADR-008: Opiniones de la comunidad visibles en el sitio, solo con aprobación previa del administrador

**Estado:** Aceptado (2026-09-24) — implementado y verificado en producción (ver **Verificación**).

**Spec:** `docs/superpowers/specs/2026-09-24-community-opinions-design.md` · **Plan:** `docs/superpowers/plans/2026-09-24-community-opinions.md`

## Contexto

Cualquier persona puede recomendar un lugar del mapa (formulario "Recomendar / reportar" o chatbot) y el aporte queda
en `place_reports`. Esa tabla es **solo de escritura para el público** (INSERT-only, sin ninguna lectura), y por diseño
un reporte nunca modifica `places` (ADR-004): es evidencia para el Validator. El resultado es que las recomendaciones de
la comunidad **no se ven en ningún lado**. Peor: la sección "La voz de la comunidad" mostraba tres testimonios
**inventados** bajo el título "Experiencias reales".

Se quiere mostrar lo que escribe la gente, con el nombre que cada quien quiera poner ("Anónimo" si no pone ninguno).
Las restricciones: es una plataforma de salud, no hay cuentas (una persona es indistinguible de cinco y los límites
anti-spam viven en `localStorage`), y `place_reports` guarda datos que no deben salir (`owner_celiac`, la condición de
salud de un tercero; ver ADR-007).

## Decisión

1. **Solo se publican recomendaciones positivas.** Un reporte negativo sigue yendo al Validator (ADR-004) y nunca se
   muestra: publicar una acusación sobre un negocio es un riesgo legal y de salud.
2. **Aprobación previa del administrador.** Cada comentario entra como no publicado y solo aparece cuando el
   administrador lo aprueba. Sin cuentas, elogios falsos de un negocio propio serían fáciles de escribir; con el volumen
   actual la revisión es manejable. Se revisa si el volumen la supera o llegan cuentas verificadas.
3. **`place_reports` gana dos columnas:** `author_name` (nombre opcional, 1 a 40 caracteres tras `btrim`) y
   `published_at` (nulo = no publicada; es también el registro de cuándo se aprobó). Un CHECK impide que un reporte
   negativo tenga `published_at`.
4. **La política de inserción pública exige `published_at is null`.** El `grant insert` del público es de tabla
   completa; sin esa condición un cliente podría insertar un comentario ya publicado y saltarse la moderación.
5. **La lectura pública es una vista** (`community_opinions`) con una lista explícita de 8 columnas (`id`, `description`,
   `author_name`, `published_at`, `place_id`, `place_name`, `city`, `country`), filtrada a positivas publicadas de
   lugares `approved`. `place_reports` sigue cerrada. La vista corre con los permisos de su dueño (eso le permite leer
   la tabla cerrada), por lo que su `WHERE` es la única barrera; incluye `p.status = 'approved'`, así que una opinión
   desaparece sola si su lugar deja de estar publicado.
6. **El script `scripts/moderate_opinions.py` es la única vía de publicación.** Lista lo pendiente con el texto
   completo, `--approve` y `--hide`; dry-run por defecto, escribe solo con `--apply`; solo aprueba positivas pendientes
   de lugares aprobados.
7. **Las opiniones no cambian nada del mapa:** ni `places.status`, ni `safety_level`, ni el ranking. Mismo principio que
   ADR-002, ADR-004 y ADR-005.
8. **El chatbot no cambia.** Escribe en la misma tabla, así que sus recomendaciones se guardan sin nombre y, si se
   aprueban, salen como "Anónimo".
9. **En el sitio:** `js/opinions.js` dibuja la sección (nombre o "Anónimo", "sobre *Lugar* · *Ciudad*" que abre el
   lugar en el mapa, sin estrellas). El texto de las personas entra **solo con `textContent`**. Se eliminan los
   testimonios inventados; con menos de tres comentarios se agrega una tarjeta que invita a contar la experiencia.
10. **Formulario B:** campo opcional "Tu nombre" con `autocomplete="off"` y un aviso de que el comentario puede
    mostrarse (y de que los reportes no se publican). En modo "Reportar" el campo se oculta y no se envía.

## Alternativas descartadas

- **Publicación automática.** Cualquiera podría publicar elogios falsos de su propio negocio en una herramienta de
  salud. La aprobación previa cuesta poco con este volumen.
- **Moderación por IA.** Agrega costo, otra superficie de error y una decisión automática sobre texto público, para un
  volumen que una persona resuelve en minutos.
- **Una política de lectura sobre `place_reports`.** Habría expuesto la tabla entera (kitchen, `owner_celiac`, estado)
  a cualquier columna futura. La vista es un contrato explícito.
- **Una columna booleana `is_public`.** Pierde el registro de cuándo se aprobó y no aporta nada frente a `published_at`.
- **Pedir el nombre en el chatbot.** Más fricción en un flujo ya largo y otro cambio de prompt (que reinicia el conteo
  del soft-launch), para un beneficio menor.
- **Mostrar también los reportes negativos.** Ver decisión 1.

## Verificación

Todo en `db/checks/2026-09-24-opinions-live-run.md`. En resumen: la migración se ensayó en una transacción con
`ROLLBACK` y se aplicó (el check SQL falla sin ella y pasa con ella); la verificación en vivo pasó 6 de 6 (un anónimo no
puede publicarse, una recomendación con nombre no aparece hasta aprobarla, aparece con el nombre al aprobarla y
desaparece al retirarla); la lectura pública devuelve 200 por la vista, 401 por la tabla y 400 al pedir columnas
sensibles; la fila de prueba se revirtió contra la línea base. Se publicó el comentario de San Felipa como Anónimo.

**Hallazgo — privilegios de la vista.** Supabase otorga todos los privilegios a `anon`/`authenticated` sobre los objetos
nuevos, y un `grant select` solo suma: la vista quedó con `INSERT/UPDATE/DELETE/TRUNCATE` para `anon`. No había camino
explotable (una vista con `JOIN` no es actualizable), pero la vista corre con los permisos del dueño y se salta la RLS,
así que si se simplificara sería una vía de escritura a `place_reports`. Se corrigió con `revoke all` antes del `grant
select` (en `db/schema.sql` y en producción), con un test y una aserción en el check SQL que fallaba antes de la
corrección. Regla para el futuro: **toda vista u objeto nuevo expuesto al público lleva `revoke all` y después el
`grant` mínimo**, como las tablas.

## Consecuencias

- La comunidad ve lo que escribe, con su nombre si quiere; el administrador conserva el control de lo que se publica.
- Hay una tarea manual nueva y chica: revisar `moderate_opinions.py` cuando llegue un comentario.
- Una persona que puso su nombre y después quiere retirarlo pide por `hola@celiacmap.org` y se usa `--hide`; no hay
  edición ni borrado por parte de quien escribió (no hay cuentas).
- Los comentarios se recortan a ~280 caracteres en la tarjeta; el texto completo lo ve el administrador al aprobar.
- La vista es `security definer` de hecho (corre con los permisos de su dueño): el linter de Supabase lo señala y es
  intencional; el `WHERE` de la vista y el test de sus columnas son la protección.
