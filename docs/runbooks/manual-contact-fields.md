# Protección de datos de contacto manuales

El Updater conserva solo los campos (`website`, `phone`, `opening_hours`) registrados por UUID en `config/manual_contact_fields.json`. Una `APROBACIÓN MANUAL` protege la decisión de seguridad, no el contacto: desde el 2026-10-06 ya no congela ningún campo ([decisión](../DECISIONS.md#contact-data-frozen-only-by-the-registry-2026-10-06)). Un valor vacío registrado tampoco se rellena automáticamente.

El registro contiene correcciones verificadas de Rikuras Malvín, Café Ramona Centro, Casa & Dispensa, La Commedia, Piu Cordón, ChocAra y NutriCiencia. Cada entrada enlaza el SQL de origen. No almacena valores alternativos: evita sobrescribir el valor actual, sin restaurarlo ni copiar datos de otra sucursal. Los lugares `source=manual` ya quedan fuera del Updater.

Para una nueva corrección de estos campos: agregar el UUID/campos/fuente al registro, una regresión y un PR; hacer merge antes de aplicar el cambio de datos aprobado. Para permitir de nuevo la actualización Google, quitar el campo del registro. No inferir campos corregidos de prosa arbitraria ni cambiar las reglas del Validator sobre seguridad.

Trade-off: registro versionado pequeño, sin migración ni nueva columna pública. Si aumentan las ediciones, convendrá metadata de procedencia/overrides en servidor. Ediciones remotas no registradas no pueden detectarse automáticamente. La protección actúa sobre la fila leída al comenzar el check; coordinar correcciones administrativas fuera de un Updater en ejecución.

Rating, cantidad de reseñas, nombre, dirección, categoría y tratamiento de cierres mantienen su lógica actual. `social_url` mantiene su política de solo rellenar si está vacío. Una protección de contacto no certifica la licencia de los datos.

## Restauración de Rikuras Malvín — aplicada el 03-10-2026

[SQL](../../db/fixes/2026-10-02-rikuras-malvin-website.sql), con final `ROLLBACK` (el archivo versionado es siempre un ensayo). Verifica UUID, Place ID, estado aprobado y URL anterior; exige exactamente una fila y comprueba que solo cambien `website`/`updated_at`.

Ensayo 02-10-2026: trigger de `places` inspeccionado (solo `set_updated_at`); ejecución enlazada completada, todas las aserciones pasaron y mostró `https://rikurassingluten.pidedirecto.uy/` dentro de la transacción. Terminó con rollback. La lectura posterior confirmó que sigue `https://rikurassingluten.ambit.la/`.

Aplicación 03-10-2026, con el «dale» del responsable y la protección ya en `main`: ensayo fresco con rollback (aserciones aprobadas; la lectura posterior seguía en `ambit.la`), luego la copia de ejecución, que difería solo en el `rollback` final cambiado por `commit`. Lectura posterior: `website` = `https://rikurassingluten.pidedirecto.uy/`, `updated_at` 2026-10-03 21:09 UTC; 1 385 filas y 417 aprobadas, igual que antes; estado, etiqueta, confianza y `verified` sin cambios. El archivo ya no se puede reaplicar: su guarda exige la URL anterior. No volver a ejecutar el script histórico del 27-09.
