-- APLICADO en producción el 2026-11-20 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura): 23 filas a «Tiene opciones sin gluten» con la bandera; 100% de 90 a 67.
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-20 · Los 23 lugares que el evaluador automático dejó como «Espacio 100% sin gluten» sin revisión humana
-- pasan a «Tiene opciones sin gluten» con la bandera «100% pendiente de confirmación del administrador».
-- Decisión del administrador (2026-11-20): el 100% lo asigna solo una persona, con una cita del propio local guardada
-- y fechada. Estos 23 no tienen decisión manual (`manual_override_marker` = None), ninguno tiene `place_evidence`, y el
-- 100% salió de reseñas de Google y del nombre del local. No es evidencia en contra.
-- La línea CORRECCIÓN MANUAL contiene «sin evidencia explícita de 100» (DATA_CORRECTION_PHRASES): NO protege el lugar,
-- así que el Validator y el administrador pueden volver a evaluarlo.
-- No se tocan: status (sigue approved), validation_confidence, verified, category, ni place_evidence.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-20-cien-automaticos-a-opciones.sql
begin;

create temp table d (id uuid primary key, expected_updated_at timestamptz not null) on commit drop;

insert into d values
('117e8f23-f799-441d-a98b-8e64e56657c0','2026-11-01 15:55:47.48591+00'),  -- Despensa del Celíaco · Beccar, Argentina
('723f1da2-9c5c-477d-9393-c0bccd198c56','2026-08-19 20:02:06.645666+00'),  -- TaccFree - Casero. Rico. Sin Gluten · Beccar, Argentina
('f73250fb-21b3-4cea-9f88-a2a1f6354092','2026-08-08 15:35:29.901165+00'),  -- Sapori Gluten Free · Concepción del Uruguay, Argentina
('d7e973e5-f038-4983-8016-d72ec9369617','2026-10-01 20:55:15.924144+00'),  -- Lo de Pauli Gluten Free · Concordia, Argentina
('dfdbd5ff-cb05-42b3-b466-574cc55a43bb','2026-10-01 20:55:15.924144+00'),  -- Celisano comidas sin TACC · Córdoba, Argentina
('6e7ad8e6-c38a-43d5-9be7-01b2bca190da','2026-10-01 20:55:15.924144+00'),  -- Deligood · Córdoba, Argentina
('26507986-8a9b-4722-bfee-985ca7ef07b6','2026-11-01 15:55:58.870781+00'),  -- lüben – ꜱɪɴ ɢʟᴜᴛᴇɴ [Av. Nores Martínez] · Córdoba, Argentina
('cb82d45a-90cc-4303-b84b-c222e63a9c80','2026-10-01 20:55:15.924144+00'),  -- lüben – ꜱɪɴ ɢʟᴜᴛᴇɴ [Valle Escondido] · Córdoba, Argentina
('56fb6f14-de4e-4371-b3a5-88bc428127ff','2026-09-02 14:19:14.429034+00'),  -- Alaia Sin Tacc-Tienda & Café · Morón, Argentina
('d1a04190-f93f-4907-b482-7d475c6aa5bc','2026-08-19 18:06:01.769576+00'),  -- La Unión Gluten Free Bakery · Rincón de Milberg, Argentina
('160c24ea-3595-4f37-a621-510a72983f4f','2026-11-01 15:55:50.052947+00'),  -- Eliseo Chocolate gluten free. · San Isidro, Argentina
('4eae7e88-eeb9-42cc-90fe-5893a3f635a5','2026-09-02 14:19:14.429034+00'),  -- Fiambrería y Almacén Sin Gluten Martínez · San Isidro, Argentina
('0bf9809c-a36e-4cad-886d-64d6bb161475','2026-11-01 15:55:41.221458+00'),  -- Hache Homebaked gluten free Acassuso · San Isidro, Argentina
('2f715145-e1cb-4664-90f3-8f71781a02cf','2026-11-01 15:56:03.846939+00'),  -- Hache Homebaked gluten free Las Lomas · San Isidro, Argentina
('500fe9ca-c8f9-42c0-817c-2dcc012c0f9d','2026-08-19 18:04:42.861106+00'),  -- La Chiperia, Gastronomía casera libre de gluten · Tigre, Argentina
('23a3eb38-752d-41c9-9afb-a8c4405132fb','2026-11-01 15:55:55.977549+00'),  -- Hoy Café · La Barra, Uruguay
('337adfb3-c2aa-4ad5-bb29-23a6ed52d7b8','2026-10-01 20:55:15.924144+00'),  -- Chivas Resto Ciclyng · Minas, Uruguay
('3067f321-3e35-4803-9d1f-3c851da46fbc','2026-11-01 15:56:04.622387+00'),  -- Treat - Minas Shopping · Minas, Uruguay
('ccc37788-fcd6-4c9f-9c7d-cc19f8b3b809','2026-06-05 02:44:26.995159+00'),  -- La Casita by Cari · Punta del Este, Uruguay
('977642b3-e7fc-4f02-910a-b7369e764a5b','2026-07-06 12:41:55.061796+00'),  -- Crisálida Alimentos sin gluten Veganos & Vegetariano · Rocha, Uruguay
('671e5846-8c82-47b9-8bb5-be28589e1c96','2026-10-01 20:55:15.924144+00'),  -- La Alacena Salto, almacén saludable · Salto, Uruguay
('d64cf81d-2d96-4ffd-b273-c1f24a73aa19','2026-06-05 02:46:03.56301+00'),  -- La Casona del Celiaco · Salto, Uruguay
('c14c866a-f12a-4768-b7b2-fbcd87c38369','2026-06-05 02:46:06.842857+00');  -- Oliva y Romero · Salto, Uruguay

create temp table baseline on commit drop as
  select (select count(*) from public.places) as places,
         (select count(*) from public.places where status = 'approved') as approved,
         (select count(*) from public.places where status = 'approved' and safety_level = 'gluten_free_100') as approved_100,
         (select count(*) from public.place_evidence) as evidence;

do $$
begin
  if (select count(*) from d) <> 23 then raise exception 'guarda: la lista no tiene 23 ids'; end if;
  if (select count(*) from public.places p join d on d.id = p.id
        where p.status = 'approved' and p.safety_level = 'gluten_free_100'
          and p.updated_at = d.expected_updated_at
          and coalesce(p.validation_notes, '') !~* '(override|aprobaci[oó]n manual|correcci[oó]n manual)') <> 23 then
    raise exception 'guarda: las 23 filas no están como se leyeron (approved, 100%%, updated_at, sin encabezado manual)';
  end if;
  if exists (select 1 from public.place_evidence e join d on d.id = e.place_id) then
    raise exception 'guarda: alguna fila tiene place_evidence (no debería)';
  end if;
end $$;

update public.places p
   set safety_level = 'celiac_friendly',
       flags = case
         when coalesce(p.flags, '[]'::jsonb) @> '["100% pendiente de confirmación del administrador"]'::jsonb then p.flags
         else coalesce(p.flags, '[]'::jsonb) || '["100% pendiente de confirmación del administrador"]'::jsonb end,
       validation_notes = concat_ws(E'

',
         'CORRECCIÓN MANUAL (2026-11-20, Santiago Sánchez): sin evidencia explícita de 100 del propio local. '
           || 'La etiqueta pasa de «Espacio 100% sin gluten» a «Tiene opciones sin gluten» hasta que el administrador '
           || 'la revise: el 100% lo había dejado el evaluador automático a partir de reseñas de clientes y del nombre, '
           || 'sin revisión humana. No es evidencia en contra. El Validator había dejado: '
           || p.status || coalesce(' @ ' || p.validation_confidence::text, '') || '.',
         nullif(btrim(p.validation_notes), ''))
  from d
 where p.id = d.id;

do $$
begin
  if (select count(*) from public.places p join d on d.id = p.id
        where p.status = 'approved' and p.safety_level = 'celiac_friendly'
          and p.flags @> '["100% pendiente de confirmación del administrador"]'::jsonb
          and p.validation_notes like 'CORRECCIÓN MANUAL (2026-11-20, Santiago Sánchez): sin evidencia explícita de 100 del propio local.%') <> 23 then
    raise exception 'guarda: no quedaron las 23 filas como se esperaba';
  end if;
  if (select places from baseline) <> (select count(*) from public.places)
     or (select approved from baseline) <> (select count(*) from public.places where status = 'approved')
     or (select approved_100 from baseline) - 23 <> (select count(*) from public.places where status = 'approved' and safety_level = 'gluten_free_100')
     or (select evidence from baseline) <> (select count(*) from public.place_evidence) then
    raise exception 'guarda: cambió algo más de lo previsto (lugares, aprobados, 100%% o evidencia)';
  end if;
end $$;

select p.id, p.name, p.city, p.country, p.status, p.safety_level, p.flags, p.validation_confidence, p.verified,
       p.validation_notes as nota
  from public.places p join d on d.id = p.id order by p.country, p.city, p.name;

commit;
