-- APLICADO en producción el 2026-11-20 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura): 1 fila; manual_override_marker de Marce Cakes pasa a None.
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-20 · Marce Cakes: su línea de corrección de ciudad se reescribe con la frase de datos «ciudad corregida».
-- Decisión del administrador (2026-11-20), tras la auditoría de líneas CORRECCIÓN MANUAL que solo corrigen datos.
-- «city reetiquetada» no está en DATA_CORRECTION_PHRASES, así que esa línea protegía el lugar como si fuera una
-- decisión de seguridad. Con «ciudad corregida» deja de protegerlo, igual que a los 23 (manual_override_marker -> None).
-- No se suma «reetiquetada» a la lista: una línea de seguridad («reetiquetada a 100%») quedaría liberada.
-- Solo cambia esas palabras de la nota; nada más de la fila.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-20-marce-cakes-linea-de-ciudad.sql
begin;

create temp table b on commit drop as
  select (select count(*) from public.places) as places,
         (select count(*) from public.places where status = 'approved') as approved,
         (select count(*) from public.places where validation_notes like '%city reetiquetada%') as con_frase;

do $$
begin
  if (select count(*) from public.places
        where id = 'c17a38ac-b398-458d-88fa-5d1b9c41ceb3' and status = 'approved' and safety_level = 'celiac_friendly'
          and validation_notes like '%CORRECCIÓN MANUAL 2026-09-02: city reetiquetada de "Paraná" a "Santa Fe"%') <> 1
     or (select con_frase from b) <> 1 then
    raise exception 'guarda: Marce Cakes no está como se leyó';
  end if;
end $$;

update public.places
   set validation_notes = replace(validation_notes,
         'CORRECCIÓN MANUAL 2026-09-02: city reetiquetada de "Paraná" a "Santa Fe"',
         'CORRECCIÓN MANUAL 2026-09-02: ciudad corregida de "Paraná" a "Santa Fe"')
 where id = 'c17a38ac-b398-458d-88fa-5d1b9c41ceb3';

do $$
begin
  if (select count(*) from public.places where validation_notes like '%city reetiquetada%') <> 0
     or (select count(*) from public.places
           where id = 'c17a38ac-b398-458d-88fa-5d1b9c41ceb3'
             and validation_notes like '%CORRECCIÓN MANUAL 2026-09-02: ciudad corregida de "Paraná" a "Santa Fe"%') <> 1
     or (select places from b) <> (select count(*) from public.places)
     or (select approved from b) <> (select count(*) from public.places where status = 'approved') then
    raise exception 'guarda: cambió algo más que la línea de Marce Cakes';
  end if;
end $$;

select id, name, status, safety_level, validation_notes
  from public.places where id = 'c17a38ac-b398-458d-88fa-5d1b9c41ceb3';

commit;
