# Rediseño del explorador: implementación y verificación

## Comportamiento implementado

- El mapa precede al contenido informativo en el DOM y en pantalla.
- Búsqueda permanente; filtros de categoría, ciudad y nivel en un panel desplegable. Se actualizan inmediatamente; «Ver resultados» cierra el panel y encuadra los lugares. «Restablecer» limpia los filtros.
- En desktop los resultados acompañan al mapa. Hasta 767 px se abren como un panel inferior colapsable; el detalle comienza como resumen y permite expandir la información.
- Seleccionar una recomendación con filtros incompatibles restablece esos filtros antes de mostrar el lugar. El autocomplete respeta todos los filtros activos.
- Cambiar selección, paginar cards o traducir no reconstruye la capa de marcadores. Los cambios de filtros agregan o eliminan únicamente los marcadores afectados.
- Geolocalización solicitada mediante botón, guardada solo en memoria. Las distancias se presentan explícitamente como línea recta, sin inferir tiempos de viaje.
- El chat móvil ocupa temporalmente la pantalla y adapta su altura a VisualViewport. Conserva la conversación en memoria; abrirlo no activa el teclado. Incluye prompts editables, foco contenido y fondo inerte mientras funciona como diálogo modal.
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

Los tests de frontend ejecutan los módulos reales con un DOM de LinkeDOM y una capa Leaflet simulada. LinkeDOM se descarga en la caché de Deno, no se incorpora al sitio ni a sus dependencias de producción. Cubren apertura de detalle mediante cards y chatbot, conflicto de filtros, autocomplete, paginación, traducción y orden del DOM.

## Validación pendiente en dispositivos reales

No se dispone de navegador automatizable en esta sesión. Los tests DOM no comprueban la composición visual de Leaflet, gestos, agrupación real, teclado iOS/Android ni lectores de pantalla. Verificar a 360, 390, 768, 1024 y 1440 px los tres recorridos del plan, con zoom del navegador, teclado y movimiento reducido, antes de publicar.
