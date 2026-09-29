# ADR-009: Patrocinios: visibles y separados de la evaluación de seguridad

**Estado:** Aceptado (2026-09-28).

## Contexto

CeliacMap es una herramienta de salud: la gente celíaca decide dónde comer según lo que muestra el mapa. El proyecto
tiene su primer aliado, **Bienestar Gluten Free** (Fray Bentos, Uruguay; productos artesanales sin gluten, veganos, sin
lactosa y sin azúcar), que aprobó el uso de su logo.

El riesgo es que se mezcle el pago con la seguridad. Si un aliado aparece más arriba, con otro marcador o con otra
etiqueta, se pierde la confianza en el mapa, que es lo único que el proyecto tiene para ofrecer.

Bienestar ya estaba en el mapa antes de la alianza. Se aprobó a mano el 2026-09-01 (`APROBACIÓN MANUAL` por
conocimiento personal directo; el Validator había dicho `needs_review` @ 0.52). `safety_level` es `options_available`,
`validation_confidence` sigue en 0.52 y `verified` sigue en `false`.

## Decisión

1. **El patrocinio es solo frontend.** Hay una sección aparte, `<section id="aliados">`, antes del footer de
   `index.html`, con una tarjeta que lleva el logo, una línea sobre el negocio y enlaces a Instagram y WhatsApp. El
   footer y el nav del header suman un enlace "Aliados" (el del header se agregó el mismo día por decisión del dueño;
   primero había quedado solo en el footer). Debajo de la tarjeta, fuera de ella, una invitación a sumarse como aliado
   (`mailto:` a hola@celiacmap.org con asunto precargado).
2. **Rotulado claro y fijo.** Cada tarjeta dice "Aliado" / "Partner", y la sección lleva una sola vez, como bajada
   debajo del título y fuera de toda tarjeta, la frase fija "Los aliados apoyan el
   proyecto. No influyen en qué lugares aparecen en el mapa ni en su etiqueta." / "Partners support the project. They
   have no influence on which places appear on the map or on their label." El español está en el markup de
   `index.html` y el inglés en `js/main.js`.
3. **Enlaces marcados como patrocinados.** Llevan `rel="sponsored noopener"` y `target="_blank"`. No hay scripts de
   terceros, píxeles ni tracking.
4. **El logo es un archivo local optimizado** (WebP o PNG) de menos de 40 KB en `assets/images/`, con `alt`, `width`,
   `height` y `loading="lazy"`. Es la segunda excepción a la regla de no subir imágenes binarias al repo; la primera son
   los PNG del favicon.
5. **El patrocinio no toca nada de la evaluación:** ni `places` (`status`, `safety_level`, `validation_confidence`,
   `verified`), ni el Validator o el `RUBRIC`, ni el ranking (`place_votes` / `vote_count`), ni el chatbot (prompts,
   búsqueda u orden de resultados), ni el marcador o la ficha del lugar en el mapa. No hay columna `sponsored`, ni
   boost, ni pin.
6. **Bienestar no cambia de etiqueta ni de confianza.** Por transparencia se agrega una nota de alianza en su
   `validation_notes`, con el texto aprobado por el administrador y aplicada por separado.
7. **Reglas para futuros aliados:** usan la misma tarjeta y la misma frase. Un aliado que no está en el mapa no se
   agrega por ser aliado. Un aliado que está en el mapa pasa por las mismas reglas que cualquier otro lugar (Validator
   u override manual transparente). Terminar una alianza solo quita la tarjeta.

## Alternativas descartadas

- **Marcador "destacado" o boost en el ranking o el chatbot.** Mezcla el pago con la seguridad en una herramienta de
  salud. Es justo lo que este ADR evita.
- **Red de anuncios o afiliados.** Suma scripts de terceros y tracking a un sitio que hoy no tiene ninguno.
- **Mostrar al aliado sin rotular.** Quien visita no puede distinguir un patrocinio de una recomendación.

## Verificación

`tests/frontend_partners.test.js` es la guarda. Comprueba que:

- la sección `#aliados` existe, es la última de `<main>` y el footer la enlaza;
- el rótulo y la frase fija están en español y en inglés (se ejecuta `js/main.js` y se alterna el idioma);
- los enlaces llevan `rel="sponsored noopener"` y `target="_blank"`;
- el logo tiene `alt`, `width`, `height` y `loading="lazy"`, pesa menos de 40 KB, y la sección no tiene scripts ni
  iframes;
- ni `js/map.js`, ni `js/chat.js`, ni el código de la función `chat` (`index.ts`, `regions.ts`) mencionan al aliado.

**En producción (2026-09-28):** la sección está publicada en celiacmap.org (commit `8aa1f9c`, deploy de Pages en verde),
verificada en Chrome a 390 px y en desktop, en ES y EN, con 0 errores de consola y los dos enlaces abiertos. La nota de alianza
se aplicó después al `validation_notes` de Bienestar. `status`, `safety_level`, `validation_confidence`, `verified` y
`vote_count` no cambiaron (verificación de solo lectura).

**Hallazgo previo — el prompt del chatbot.** `supabase/functions/chat/prompts.ts` usa "Bienestar Gluten Free, Rivera
1967, Fray Bentos … 100% sin gluten" como ejemplo few-shot del flujo reportar/sugerir. El ejemplo se escribió antes de
la alianza. No se cambia acá, porque cambiar un prompt del chatbot exige la batería de jailbreak y reinicia el conteo
del soft-launch. El test excluye `prompts.ts` por ese motivo y lo deja documentado. **La próxima edición deliberada
del prompt debe reemplazar ese ejemplo por un nombre que no sea aliado.**

## Consecuencias

**Positivas:**

- El proyecto puede recibir apoyo sin tocar el mapa: el patrocinio y la seguridad quedan separados por diseño y un
  test lo vigila.
- Quien visita ve quién apoya el proyecto y sabe que eso no compra lugar ni etiqueta.
- No hay dependencias, scripts de terceros ni cambios de base de datos. `C4-diagrams.md` no cambia: la sección es
  contenido estático dentro del frontend, sin lectura ni escritura a la base.

**Negativas / trade-offs aceptados:**

- El aliado recibe poca visibilidad (una tarjeta al final de la página). Es intencional.
- Queda en `prompts.ts`, hasta la próxima edición del prompt, un ejemplo con el nombre del aliado y la frase "100% sin
  gluten". Es un ejemplo de formato y no busca lugares, pero es una deuda anotada.
- El repo tiene una imagen binaria más, acotada por el límite de 40 KB del test.
