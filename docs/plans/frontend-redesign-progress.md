# Rediseño del explorador: implementación y verificación

## Comportamiento implementado

- El mapa precede al contenido informativo en el DOM y en pantalla.
- Búsqueda permanente; filtros de categoría, ciudad y nivel en un panel desplegable. Se actualizan inmediatamente; «Ver resultados» cierra el panel y encuadra los lugares. «Restablecer» limpia los filtros.
- La card junto al mapa (desde 1000 px) es solo el Top 3 de la comunidad, con selector Argentina / Uruguay compartido con el ranking completo. No hay lista de «lugares encontrados»: los lugares se exploran con los marcadores, la búsqueda, los filtros y las recomendaciones del chat. En pantallas angostas el detalle comienza como resumen y permite expandir la información.
- Seleccionar una recomendación con filtros incompatibles restablece esos filtros antes de mostrar el lugar. El autocomplete respeta todos los filtros activos.
- Cambiar selección, paginar cards o traducir no reconstruye la capa de marcadores. Los cambios de filtros agregan o eliminan únicamente los marcadores afectados.
- A petición del usuario, se retiraron la geolocalización, las distancias y los grupos numerados. Cada lugar se muestra con un marcador individual; la ciudad se selecciona manualmente.
- El chat móvil ocupa temporalmente la pantalla y adapta su altura a VisualViewport. Conserva la conversación en memoria; abrirlo no activa el teclado. Abre solo con el saludo (sin preguntas sugeridas), con foco contenido y fondo inerte mientras funciona como diálogo modal.
- Se conservan el stack estático, Leaflet y las reglas de publicación de lugares aprobados. No hay migraciones ni cambios en prompts del modelo.

## Contrato del chatbot

La respuesta añade `places`, una lista de hasta ocho referencias públicas derivadas de la consulta de lugares aprobados: `id`, `name`, `city`, `category`, `safety_level`. El `id` no se envía al redactor: su allowlist no cambia. El frontend tolera respuestas antiguas sin `places`.

Para activar recomendaciones navegables en producción debe desplegarse también la Edge Function `chat`; publicar GitHub Pages por sí solo no actualiza esa función. Esta implementación no realiza despliegues.

## Verificación

```text
node --check js/map.js
node --check js/chat.js
deno test supabase/functions/chat/index.test.ts
deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_explorer.test.js
git diff --check
```

Los tests de frontend ejecutan los módulos reales con un DOM de LinkeDOM y una capa Leaflet simulada. LinkeDOM se descarga en la caché de Deno, no se incorpora al sitio ni a sus dependencias de producción. Cubren apertura de detalle mediante el chatbot, conflicto de filtros, autocomplete, traducción, orden del DOM, la card del Top 3 (selector de país compartido, país sin votos, error de carga) y que el chat abra sin preguntas sugeridas.

## Simplificación posterior (2026-09-20)

A pedido del dueño del producto: se quitó la lista «Lugares encontrados» (cards, paginación, contador y el botón móvil «Lugares / mapa») y la card junto al mapa volvió a ser solo el Top 3, ahora con selector Argentina / Uruguay. También se quitaron las preguntas sugeridas del chat, que lo cargaban de información al abrirlo. Solo frontend: sin cambios en la Edge Function, el esquema ni los prompts. Al quitar la lista salió a la luz un bug del rediseño: un clic real sobre un marcador abría el detalle y lo cerraba en el mismo clic (el ícono se reemplaza con `setIcon` y el handler de «clic afuera» veía un target ya desconectado); se corrigió con un guard `isConnected` en `js/map.js` y un test de regresión. El breakpoint de dos columnas vuelve a 1000 px (coincide con el que oculta la card por debajo y con el corrimiento de la atribución del mapa frente al FAB del chat).

## Verificación de publicación y navegador

El frontend del commit `d1ffa19` se publicó mediante GitHub Pages. La función `chat` se desplegó como versión 12 y se verificó `ACTIVE`, conservando `verify_jwt=false`.

Una búsqueda real desde el chat en producción devolvió referencias estructuradas. Se verificaron sus IDs contra `places.status=approved` y se abrió una recomendación en el mapa desde el widget mobile.

Se habilitó una instalación temporal de Playwright fuera de las dependencias de producción, en `supabase/.temp/visual-qa`, para ejecutar Chrome real en modo headless. Se comprobaron vistas de 360, 390, 768, 1024 y 1440 px: mapa primero, selección desde cards, expansión del detalle mobile, cierre, filtros y apertura del chat. Se inspeccionaron capturas. La prueba encontró un desbordamiento horizontal causado por el panel de detalle cerrado desde 768 px; se corrigió conteniendo ese panel dentro del mapa y se repitieron satisfactoriamente los cinco tamaños sobre el código corregido, sin errores JavaScript.

Esto valida Chromium con emulación de viewport/touch, no hardware móvil. Quedan fuera de esta verificación el teclado nativo de iOS/Android, Safari, lectores de pantalla y pruebas con personas usuarias.
