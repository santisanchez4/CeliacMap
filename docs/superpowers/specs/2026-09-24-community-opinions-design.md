# Opiniones de la comunidad visibles en el sitio — diseño

**Fecha:** 2026-09-24 · **Estado:** aprobado por Santiago (2026-09-24); plan en `docs/superpowers/plans/2026-09-24-community-opinions.md`.
**Origen:** pieza 3 de 3 de la sesión de diseño del 2026-09-24 (la 1, títulos de `#suggest`, y la 2, información de cocina, ya están en producción).

## 1. Propósito

Hoy una persona puede dejar una recomendación de un lugar (formulario B o chatbot) y **nunca se ve en ningún lado**: `place_reports` es solo de escritura para el público (INSERT-only, sin ninguna lectura). Además, "La voz de la comunidad" (`#reviews`) muestra tres testimonios **inventados** bajo el título "Experiencias reales".

Este diseño hace que las recomendaciones **positivas** de la comunidad se muestren en esa sección, con el nombre que la persona quiera poner (o **"Anónimo"** si no pone ninguno), **solo después de que el administrador las apruebe**, y saca los testimonios inventados.

## 2. Decisiones ya tomadas

- **Nombre opcional**, en el formulario B. Sin nombre → "Anónimo".
- **Solo positivas.** Los reportes negativos no se muestran nunca: siguen yendo al Validator (ADR-004) y publicar una acusación sobre un negocio es un riesgo legal y de salud.
- **Aprobación previa del administrador.** Es una plataforma de salud y no hay cuentas: alguien podría escribir elogios falsos de su propio negocio. El volumen actual (1 comentario real) lo permite; se revisa si crece.
- **El chatbot no se toca.** Escribe en la misma tabla, así que sus recomendaciones se guardan sin nombre y, si se aprueban, salen como "Anónimo". Que el chatbot pregunte el nombre queda fuera.
- **Las opiniones no cambian nada del mapa.** Una recomendación publicada no modifica `places.status`, `safety_level` ni el ranking (mismo principio que ADR-002 / ADR-004 / ADR-005).

## 3. Alcance

**Dentro:** dos columnas en `place_reports`, política de inserción endurecida, vista pública, campo de nombre + aviso en el formulario B, sección `#reviews` con datos reales, script de moderación, tests, ADR-008, documentación.

**Fuera:** mostrar opiniones en el panel de cada lugar (siguiente paso natural, la misma vista alcanza); puntaje con estrellas; que la persona edite o borre su comentario (se quita por pedido a `hola@celiacmap.org` con `--hide`); moderación automática; panel de administración; que el chatbot pregunte el nombre.

## 4. Modelo de datos

```sql
alter table public.place_reports add column if not exists author_name  text;
alter table public.place_reports add column if not exists published_at timestamptz;

-- nombre: opcional, acotado, sin espacios de sobra
alter table public.place_reports add constraint place_reports_author_name_check
  check (author_name is null or char_length(btrim(author_name)) between 1 and 40);

-- solo una recomendación positiva puede publicarse (defensa en profundidad:
-- aunque alguien la marque por error, un reporte negativo nunca sale)
alter table public.place_reports add constraint place_reports_publish_positive_only_check
  check (published_at is null or report_type = 'positive');
```

`published_at` nulo = no publicada. Es también el registro de cuándo se aprobó. No se agrega ninguna columna de "moderador": hay un solo administrador.

**La política de inserción pública se endurece** (hoy el `grant insert` es de tabla completa, así que sin esto un cliente malicioso podría insertar `published_at` ya cargado y publicarse solo):

```sql
drop policy if exists "public can submit place reports" on public.place_reports;
create policy "public can submit place reports"
  on public.place_reports for insert to anon, authenticated
  with check (
    status = 'new'
    and published_at is null
    and (place_id is not null or place_name_text is not null)
    and char_length(description) between 5 and 2000
  );
```

**Lectura pública: una vista con las únicas columnas que se exponen.** `place_reports` sigue sin lectura para anon.

```sql
create or replace view public.community_opinions as
select r.id,
       r.description,
       r.author_name,
       r.published_at,
       p.id      as place_id,
       p.name    as place_name,
       p.city,
       p.country
from public.place_reports r
join public.places p on p.id = r.place_id
where r.report_type = 'positive'
  and r.published_at is not null
  and p.status = 'approved';

grant select on public.community_opinions to anon, authenticated;
```

Por qué una vista y no una política de lectura sobre la tabla: la vista es el contrato explícito de qué es público. **`kitchen_exclusive`, `celiac_prep`, `owner_celiac`, `status` y `place_name_text` nunca salen** (`owner_celiac` es la condición de salud de un tercero, ver ADR-007), y una columna agregada mañana a `place_reports` no se filtra por accidente. La vista corre con los permisos de su dueño (es lo que permite leer la tabla cerrada); por eso el `where` es la única barrera y lleva la condición `p.status = 'approved'`: si el lugar deja de estar publicado, su opinión desaparece sola.

## 5. Frontend

**Formulario B (`js/report.js`, `index.html`):**
- Campo nuevo `#rp-author` ("Tu nombre (opcional)"), `maxlength=40`, dentro de `#rp-details` debajo de la descripción.
- Un aviso debajo del campo, según el tipo elegido. Recomendar: "Tu comentario puede mostrarse en el sitio después de que lo revisemos. Sin nombre, aparece como Anónimo." Reportar: "Los reportes no se publican: los revisamos internamente."
- Al elegir "Reportar" el campo de nombre se oculta y no se envía (mismo criterio que el bloque de cocina). Al elegir "Recomendar" se muestra.
- El envío agrega `author_name` (con `trim`) **solo** si el tipo es positivo y el campo no quedó vacío.

**Sección `#reviews` (`js/opinions.js`, nuevo):**
- Lee `community_opinions?select=id,description,author_name,place_id,place_name,city,country&order=published_at.desc&limit=6` con la clave anon, igual que `ranking.js`.
- Cada tarjeta muestra el comentario, el autor (`author_name` o **Anónimo / Anonymous**), y "sobre *Lugar* · *Ciudad*", que abre el lugar en el mapa con el evento `celiacmap:open-place` que ya usa el chat. Inicial del autor en el avatar, o un ícono neutro si es anónimo. **Sin estrellas.**
- **El texto de las personas se inserta solo con `textContent`, nunca como HTML.** Los comentarios largos se recortan a ~280 caracteres en una palabra completa, con "…" (el administrador ve el texto completo al aprobar).
- **Sin opiniones publicadas:** una tarjeta vacía que dice "Todavía no hay comentarios publicados" y un botón "Contanos tu experiencia" que lleva al formulario. **Con menos de tres:** se muestran las que haya, más esa misma tarjeta al final.
- **Se eliminan** las tres tarjetas inventadas del HTML y sus claves de traducción (`reviews.r1/r2/r3.*`). La sección conserva el título "La voz de la comunidad"; el subtítulo "Experiencias reales que generan confianza." pasa a "Lo que cuentan quienes ya fueron a estos lugares." (ES y EN).
- Etiquetas fijas (Anónimo, "sobre", estado vacío) en un `MSG = {es, en}` dentro de `opinions.js`, que se vuelve a dibujar con `celiacmap:lang`; mismo patrón que `chat.js` y `ranking.js`. Si la carga falla, la sección muestra el estado vacío, sin error visible.

## 6. Moderación (`scripts/moderate_opinions.py`)

Con la clave de servicio (server-only), estilo de `revalidate_low_confidence.py`: **listar por defecto, escribir solo con `--apply`**.
- Sin argumentos: lista las recomendaciones **positivas, no publicadas, de lugares aprobados**, con id, lugar, ciudad, autor y **texto completo**.
- `--approve ID [ID…]`: pone `published_at = now()` en esos ids (y solo si son positivas de un lugar aprobado).
- `--hide ID [ID…]`: pone `published_at = null` (para retirar una ya publicada, por ejemplo a pedido de la persona).
- Sin `--apply` muestra qué haría y no escribe.

El administrador lee el texto y el nombre antes de aprobar: es la barrera contra datos personales, spam y elogios falsos. **La recomendación de San Felipa (23/09) se cargó antes de que existiera el aviso de publicación**; queda en la lista como cualquier otra y decide el administrador si se publica (sin nombre, saldría como Anónimo).

## 7. Riesgos y cómo se acotan

| Riesgo | Mitigación |
|---|---|
| Texto malicioso (HTML/script) en un comentario | Solo `textContent`; además el administrador aprueba cada uno |
| Alguien se auto-publica insertando `published_at` | `with check ... published_at is null` en la política + test de la política |
| Exponer datos internos (cocina, `owner_celiac`, estado) | La vista lista columnas explícitas; test que verifica la lista exacta |
| Un reporte negativo termina publicado | CHECK `publish_positive_only` + filtro de la vista + el script solo aprueba positivas |
| Elogio falso de un negocio | Aprobación previa; los comentarios no cambian el mapa ni el ranking |
| Nombre real de una persona publicado sin querer | Aviso explícito en el formulario; nombre opcional; retiro con `--hide` |
| Comentario largo que rompe el diseño | Recorte a ~280 caracteres en la tarjeta |

## 8. Pruebas

- **SQL** (`db/checks/2026-09-24-opinions-columns.sql`, en `begin; … rollback;`): columnas y CHECKs presentes; como `anon`, insertar con `published_at` cargado **falla**, insertar normal **funciona**, la vista no devuelve nada hasta que se publica, una positiva de lugar aprobado publicada **aparece**, una negativa **no puede** publicarse, y la vista expone exactamente las 8 columnas previstas.
- **Python:** `tests/test_schema_opinions.py` (los CHECKs y la política en `db/schema.sql`, más validación de sintaxis con `pglast`) y tests del script de moderación con un cliente falso (lista, `--approve` solo a positivas, `--hide`, dry-run que no escribe).
- **Frontend:** `tests/frontend_opinions.test.js` (nombre vs. Anónimo, estado vacío, menos de tres, recorte, **un comentario con HTML se muestra como texto**, EN/ES, falla de carga) y ampliación de los tests de `report.js` (`author_name` solo en positivo y recortado, ausente si está vacío, campo oculto en negativo).
- **En vivo, después de aplicar:** una recomendación de prueba con nombre "Prueba" sobre un lugar real → no aparece hasta aprobarla → aparece con el nombre → se **revierte** con el SQL mostrado antes y verificación contra la línea base (mismo protocolo de las fases anteriores).

## 9. Orden de despliegue

1. **Migración** en Supabase (SQL a la vista antes de ejecutar; es aditiva, las columnas son nulas, el sitio actual no se rompe).
2. **Frontend** (merge a `main` → GitHub Pages).
3. **Verificación en vivo** y reversión de la fila de prueba.
4. El administrador revisa la lista y aprueba lo que quiera con `moderate_opinions.py --approve … --apply`.

El frontend nunca va antes que la migración: el formulario mandaría `author_name` a una tabla que todavía no tiene la columna y fallaría el envío.

## 10. Documentación

ADR-008 (opiniones publicadas solo con aprobación, vista como contrato público), entrada en el Decisions Log y Fase 26 en `CLAUDE.md`, `README.md`, diagrama C4 (nivel 2: `js/opinions.js`, la vista, el script), y la línea de "Schema refinements" sobre lo que es público en `place_reports`.
