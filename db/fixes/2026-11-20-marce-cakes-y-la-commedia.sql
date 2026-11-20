-- APLICADO en producción el 2026-11-20 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura): Marce Cakes a «Tiene opciones» con la bandera; La Commedia sin el dato de salud; 0 notas con datos de salud.
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-20 · Marce Cakes baja a «Tiene opciones sin gluten» como los 23; La Commedia: se quita un dato de salud.
-- Decisión del administrador (2026-11-20).
-- * Marce Cakes® Gluten Free (Santa Fe): el 100% lo dejó el evaluador automático solo por el nombre; su única línea
--   manual es una corrección de ciudad. Mismo cambio que 2026-11-20-cien-automaticos-a-opciones.sql: safety_level ->
--   celiac_friendly, bandera «100% pendiente de confirmación del administrador», encabezado CORRECCIÓN MANUAL con
--   «sin evidencia explícita de 100». status, validation_confidence y verified no cambian.
-- * La Commedia (Montevideo): su nota de override nombraba la condición de salud de una persona (regla «No
--   third-party health data», también en validation_notes). Se quita solo esa frase; el resto de la nota queda igual.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-20-marce-cakes-y-la-commedia.sql
begin;

create temp table b on commit drop as
  select (select count(*) from public.places) as places,
         (select count(*) from public.places where status = 'approved') as approved,
         (select count(*) from public.places where status = 'approved' and safety_level = 'gluten_free_100') as cien,
         (select count(*) from public.place_evidence) as evidence;

do $$
begin
  if (select count(*) from public.places
        where id = 'c17a38ac-b398-458d-88fa-5d1b9c41ceb3' and status = 'approved' and safety_level = 'gluten_free_100'
          and updated_at = '2026-09-02 14:18:19.844782+00'
          and validation_notes like 'CORRECCIÓN MANUAL 2026-09-02: city reetiquetada%'
          and validation_notes !~* '(override|aprobaci[oó]n manual)'
          and not exists (select 1 from public.place_evidence e where e.place_id = 'c17a38ac-b398-458d-88fa-5d1b9c41ceb3')) <> 1 then
    raise exception 'guarda: Marce Cakes no está como se leyó';
  end if;
  if (select count(*) from public.places
        where id = '7363c257-9596-4aa1-a329-29d994d2eb65' and updated_at = '2026-09-07 13:39:32.954503+00'
          and validation_notes like '%cocina totalmente dedicada, dueño celíaco, sin contaminación cruzada%') <> 1 then
    raise exception 'guarda: La Commedia no está como se leyó';
  end if;
end $$;

update public.places
   set safety_level = 'celiac_friendly',
       flags = case when coalesce(flags, '[]'::jsonb) @> '["100% pendiente de confirmación del administrador"]'::jsonb
                    then flags
                    else coalesce(flags, '[]'::jsonb) || '["100% pendiente de confirmación del administrador"]'::jsonb end,
       validation_notes = concat_ws(E'\n\n',
         'CORRECCIÓN MANUAL (2026-11-20, Santiago Sánchez): sin evidencia explícita de 100 del propio local. La etiqueta pasa de «Espacio 100% sin gluten» a «Tiene opciones sin gluten» hasta que el administrador la revise: el 100% lo había dejado el evaluador automático a partir del nombre, sin revisión humana. No es evidencia en contra. El Validator había dejado: approved @ '
           || coalesce(validation_confidence::text, 's/d') || '.',
         nullif(btrim(validation_notes), ''))
 where id = 'c17a38ac-b398-458d-88fa-5d1b9c41ceb3';

update public.places
   set validation_notes = replace(validation_notes,
         'cocina totalmente dedicada, dueño celíaco, sin contaminación cruzada',
         'cocina totalmente dedicada, sin contaminación cruzada')
 where id = '7363c257-9596-4aa1-a329-29d994d2eb65';

do $$
begin
  if (select count(*) from public.places
        where id = 'c17a38ac-b398-458d-88fa-5d1b9c41ceb3' and status = 'approved' and safety_level = 'celiac_friendly'
          and flags @> '["100% pendiente de confirmación del administrador"]'::jsonb
          and validation_notes like 'CORRECCIÓN MANUAL (2026-11-20, Santiago Sánchez): sin evidencia explícita de 100 del propio local.%') <> 1 then
    raise exception 'guarda: Marce Cakes no quedó como se esperaba';
  end if;
  if exists (select 1 from public.places
               where validation_notes ilike '%dueño celíaco%' or validation_notes ilike '%dueña celíaca%') then
    raise exception 'guarda: queda una nota con la condición de salud de una persona';
  end if;
  if (select places from b) <> (select count(*) from public.places)
     or (select approved from b) <> (select count(*) from public.places where status = 'approved')
     or (select cien from b) - 1 <> (select count(*) from public.places where status = 'approved' and safety_level = 'gluten_free_100')
     or (select evidence from b) <> (select count(*) from public.place_evidence) then
    raise exception 'guarda: cambió algo más de lo previsto';
  end if;
end $$;

select id, name, status, safety_level, flags, left(validation_notes, 400) as nota
  from public.places
 where id in ('c17a38ac-b398-458d-88fa-5d1b9c41ceb3', '7363c257-9596-4aa1-a329-29d994d2eb65');

commit;
