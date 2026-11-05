-- APLICADO en producción el 2026-11-05 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura).
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
insert into public.place_evidence (place_id, source, text, url) values ('a6a15ba0-eb8c-4579-8fba-7dd3a67e68ec', 'admin', 'El administrador confirma por conocimiento directo del lugar (2026-11-05) que GLUTENOFF es un establecimiento 100% sin gluten. Cita de su Instagram: «de productos artesanales ➡️ Apto celiaco.»', 'https://www.instagram.com/glutenoff.uy');
