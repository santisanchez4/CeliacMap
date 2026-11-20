-- APLICADO en producción el 2026-11-20 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura): 7 filas a «Tiene opciones sin gluten» con la bandera; 100% de 66 a 58.
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-20 · Siete 100% manuales sin una cita del propio local pasan a «Tiene opciones sin gluten».
-- Decisión del administrador (2026-11-20): el 100% exige una afirmación explícita del propio comercio. Bajan los cinco
-- que se apoyaban en fuentes de terceros (Café Ramona Centro y WTC, La Panadería de Ramona, La Commedia, Un Lugar Sin
-- Gluten) y los dos Rikuras, cuyo Instagram dice «cocina apta para celíacos», que no es una afirmación de 100%. Se
-- suben de a uno cuando el administrador guarde la cita.
-- Igual que 2026-11-20-cien-automaticos-a-opciones.sql: safety_level -> celiac_friendly, bandera «100% pendiente de
-- confirmación del administrador», encabezado CORRECCIÓN MANUAL con «sin evidencia explícita de 100». status,
-- validation_confidence, verified y place_evidence no cambian.
-- Ojo: el OVERRIDE MANUAL / APROBACIÓN MANUAL anterior queda debajo como historial y sigue protegiendo la fila; para
-- volver a subir uno, SQL manual con «dale» (review_queue rechaza una fila con decisión manual).
-- Requiere 2026-11-20-marce-cakes-y-la-commedia.sql aplicado antes (La Commedia).
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-20-cien-sin-cita-propia-a-opciones.sql
begin;

create temp table d (id uuid primary key, motivo text not null) on commit drop;
insert into d values
('03ea2fae-834c-48c0-9f7e-b43b089dc4b4', 'el 100% se había asignado a mano el 2026-09-07 a partir de fuentes de terceros (guías y blogs), no de una afirmación del propio local'),  -- Café Ramona - Centro
('896d2aa6-50b3-4398-8399-6ed933344c94', 'el 100% se había asignado a mano el 2026-09-07 a partir de una fuente de terceros (una guía), no de una afirmación del propio local'),  -- Café Ramona - WTC
('0c8ed54c-b0ef-430d-aa99-1a05da52be19', 'el 100% se había asignado a mano el 2026-09-07 a partir de fuentes de terceros (guías y blogs), no de una afirmación del propio local'),  -- La Panadería de Ramona
('7363c257-9596-4aa1-a329-29d994d2eb65', 'el 100% se había asignado a mano el 2026-09-07 a partir de fuentes de terceros (guías y blogs), no de una afirmación del propio local'),  -- La Commedia
('fa317252-5123-4eb1-a60e-c7e5b79bff7d', 'el 100% se había asignado a mano el 2026-09-27 a partir de una nota de terceros (Superprof), no de una afirmación del propio local'),  -- Un Lugar Sin Gluten
('339efc28-af19-4ce4-96ea-a9c1aa5176d4', 'el 100% se había asignado a mano el 2026-09-27 a partir de su Instagram, que dice «cocina apta para celíacos»: no es una afirmación de 100%'),  -- Rikuras Sin Gluten
('4d290ca8-23bc-4485-8aea-a97692fc6db1', 'el 100% se había asignado a mano el 2026-09-27 a partir de su Instagram, que dice «cocina apta para celíacos»: no es una afirmación de 100%');  -- Rikuras Sin Gluten El Pinar

create temp table b on commit drop as
  select (select count(*) from public.places) as places,
         (select count(*) from public.places where status = 'approved') as approved,
         (select count(*) from public.places where status = 'approved' and safety_level = 'gluten_free_100') as cien,
         (select count(*) from public.place_evidence) as evidence;

do $$
begin
  if (select count(*) from d) <> 7 then raise exception 'guarda: la lista no tiene 7 filas'; end if;
  if (select count(*) from public.places p join d on d.id = p.id
        where p.status = 'approved' and p.safety_level = 'gluten_free_100'
          and p.validation_notes ~* '^(override manual|aprobaci[oóÓ]n manual) \(2026-09-(07|27)'
          and p.validation_notes not like '%dueño celíaco%'
          and not exists (select 1 from public.place_evidence e where e.place_id = p.id)) <> 7 then
    raise exception 'guarda: las 7 filas no están como se leyeron (o falta aplicar Marce Cakes y La Commedia)';
  end if;
end $$;

update public.places p
   set safety_level = 'celiac_friendly',
       flags = case when coalesce(p.flags, '[]'::jsonb) @> '["100% pendiente de confirmación del administrador"]'::jsonb
                    then p.flags
                    else coalesce(p.flags, '[]'::jsonb) || '["100% pendiente de confirmación del administrador"]'::jsonb end,
       validation_notes = concat_ws(E'\n\n',
         'CORRECCIÓN MANUAL (2026-11-20, Santiago Sánchez): sin evidencia explícita de 100 del propio local. La etiqueta pasa de «Espacio 100% sin gluten» a «Tiene opciones sin gluten» hasta que el administrador guarde una cita del propio local: '
           || d.motivo || '. No es evidencia en contra. Estado anterior: approved @ '
           || coalesce(p.validation_confidence::text, 's/d') || ', gluten_free_100.',
         nullif(btrim(p.validation_notes), ''))
  from d
 where p.id = d.id;

do $$
begin
  if (select count(*) from public.places p join d on d.id = p.id
        where p.status = 'approved' and p.safety_level = 'celiac_friendly'
          and p.flags @> '["100% pendiente de confirmación del administrador"]'::jsonb
          and p.validation_notes like 'CORRECCIÓN MANUAL (2026-11-20, Santiago Sánchez): sin evidencia explícita de 100 del propio local.%') <> 7 then
    raise exception 'guarda: no quedaron las 7 filas como se esperaba';
  end if;
  if (select places from b) <> (select count(*) from public.places)
     or (select approved from b) <> (select count(*) from public.places where status = 'approved')
     or (select cien from b) - 7 <> (select count(*) from public.places where status = 'approved' and safety_level = 'gluten_free_100')
     or (select evidence from b) <> (select count(*) from public.place_evidence) then
    raise exception 'guarda: cambió algo más que las 7 filas';
  end if;
end $$;

select p.id, p.name, p.city, p.status, p.safety_level, p.flags, left(p.validation_notes, 420) as nota
  from public.places p join d on d.id = p.id order by p.name;

commit;
