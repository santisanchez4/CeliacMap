# Cambios de frontend para publicar la política y los términos

> Lista para cuando se publique (2026-09-29). **Nada de esto está implementado.** Condición previa: los pendientes que
> la política marca como **[PENDIENTE DE IMPLEMENTAR]** ya están resueltos o se sacaron del texto, y la revisión legal
> está hecha.

## 1. Páginas nuevas

- `privacidad.html` y `terminos.html` en la raíz, servidas por GitHub Pages como `/privacidad` y `/terminos` (Pages
  resuelve `/privacidad` a `privacidad.html`). Rutas relativas, igual que `index.html` (la decisión del deploy en
  Pages).
- **ES + EN en la misma página**, con el sistema i18n actual (`data-i18n` + `js/main.js`, clave `celiacmap-lang`), así
  el idioma elegido en la landing se mantiene. Alternativa más simple, si el texto largo complica el diccionario de
  `main.js`: dos bloques `<article lang="es">` y `<article lang="en">`, y mostrar el del idioma activo.
- Estructura semántica: `header` con la marca y un link de vuelta a la landing, `main > article`, títulos `h1`/`h2`,
  la tabla de retención y la de proveedores como `<table>` con `<caption>`, y el mismo `footer` que la landing.
- Reusar `css/styles.css` (tipografías, colores y contenedor). Solo hace falta una clase para texto largo (ancho de
  línea de unos 70 caracteres).
- Sin scripts de terceros nuevos. La baliza de Cloudflare se agrega igual que en `index.html`, para que las páginas
  cuenten visitas.
- Fecha de “Última actualización” visible arriba.
- La versión en inglés es una traducción. **[A CONFIRMAR EN LA REVISIÓN LEGAL]** Qué versión prevalece si difieren
  (propuesta: la española).

## 2. Footer

- Agregar en el footer de `index.html` (y de las páginas nuevas) dos links: “Privacidad” → `privacidad.html` y
  “Términos” → `terminos.html` (EN: “Privacy”, “Terms”), en el grupo de links del footer o en una línea propia debajo
  del contacto.

## 3. Aviso en cada formulario y en el chat

Una línea corta, siempre visible, **arriba del botón de envío** y asociada con `aria-describedby`:

| Lugar | Archivo | Texto ES | Texto EN |
|---|---|---|---|
| Form A “Agregalo” | `index.html` (`#suggest`, cerca de la nota de validación actual) + `js/suggest.js` sin cambios | Al enviar aceptás la [política de privacidad](privacidad.html). | By sending, you accept the [privacy policy](privacidad.html). |
| Form B “Contanos” | `index.html` (`#rp-*`, debajo de los avisos de autor) | Idem | Idem |
| Voto (ranking) | `js/ranking.js` / su contenedor | **[A DECIDIR]** Un voto no lleva texto: alcanza con el link del footer, o una línea en la sección del ranking | — |
| Chat | `js/chat.js`: diccionario `MSG`, junto a `disclaimer` y `logNotice` | Al escribir aceptás la [política de privacidad](privacidad.html). No compartas datos de salud tuyos ni de otras personas. | By writing, you accept the [privacy policy](privacidad.html). Don't share health data about yourself or others. |

Notas:
- El `logNotice` del chat (“…hasta 30 días…”) se queda y tiene que seguir coincidiendo con la política.
- El link del chat abre en una pestaña nueva (`target="_blank" rel="noopener"`) para no perder la conversación.
- Las claves i18n nuevas van en ES y EN. `tests/frontend_*.test.js` puede afirmar que los tres avisos existen y apuntan
  a `privacidad.html`.
- Estos avisos son **informativos**, sin casilla para tildar. **[A CONFIRMAR EN LA REVISIÓN LEGAL]** Si para los datos
  sensibles (un texto donde alguien cuenta su salud) hace falta una casilla de consentimiento expreso.

## 4. Otros cambios que dependen de los pendientes

- ~~Sacar la pregunta “¿El dueño o la dueña es celíaco/a?”~~ Hecho en la fase 1 (2026-09-29).
- El aviso de publicación de las recomendaciones que llegan por el chat va en la tanda de prompts, no en el frontend
  (`docs/plans/next-prompt-batch.md`, punto 2).
- Actualizar `README.md` y `docs/DECISIONS.md` (entrada nueva + línea en el índice de `CLAUDE.md`) cuando se publique.

## 5. Verificación antes de dar por hecho

- Abrir `/privacidad` y `/terminos` en el deploy real, en ES y EN, en celular y en escritorio.
- Hacer click de verdad en los links del footer, de los formularios y del chat (regla vigente: verificar en un
  navegador real).
- Correr los tests del frontend.
