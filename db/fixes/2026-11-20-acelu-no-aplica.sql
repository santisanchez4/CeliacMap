-- APLICADO en producción el 2026-11-20 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura): 1 fila (ACELU) a discarded; publicados 377 -> 376.
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-20 · ACELU sale del mapa: asociación de pacientes, no un lugar del mapa.
-- Decisión del administrador (2026-11-20): sale venda o no en su sede. Una asociación de pacientes como lugar del
-- mapa mezcla la organización de referencia con los lugares publicados. Reemplaza la decisión del 2026-09-21 (100%
-- por conocimiento directo), que queda debajo como historial.
-- status -> discarded, con CORRECCIÓN MANUAL «no aplica al mapa» (frase de corrección de datos). No se tocan:
-- safety_level, validation_confidence, verified, flags, place_evidence (no tiene filas).
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-20-acelu-no-aplica.sql
begin;

create temp table b on commit drop as
  select (select count(*) from public.places) as places,
         (select count(*) from public.places where status = 'approved') as approved,
         (select count(*) from public.places where status = 'discarded') as discarded;

do $$
begin
  if (select count(*) from public.places
        where id = 'd6d5375b-7ceb-44dc-9c3a-dac847f4a670' and name = 'ACELU' and status = 'approved'
          and safety_level = 'gluten_free_100' and updated_at = '2026-09-21 18:00:21.932267+00') <> 1 then
    raise exception 'guarda: ACELU no está como se leyó';
  end if;
end $$;

update public.places
   set status = 'discarded',
       validation_notes = concat_ws(E'\n\n',
         'CORRECCIÓN MANUAL (2026-11-20, Santiago Sánchez): no aplica al mapa: asociación de pacientes; se menciona como organización de referencia, no como lugar del mapa. Estado anterior: approved, gluten_free_100 (decisión del 2026-09-21, abajo).',
         nullif(btrim(validation_notes), ''))
 where id = 'd6d5375b-7ceb-44dc-9c3a-dac847f4a670';

do $$
begin
  if (select count(*) from public.places
        where id = 'd6d5375b-7ceb-44dc-9c3a-dac847f4a670' and status = 'discarded'
          and validation_notes like 'CORRECCIÓN MANUAL (2026-11-20, Santiago Sánchez): no aplica al mapa: asociación de pacientes;%') <> 1
     or (select places from b) <> (select count(*) from public.places)
     or (select approved from b) - 1 <> (select count(*) from public.places where status = 'approved')
     or (select discarded from b) + 1 <> (select count(*) from public.places where status = 'discarded') then
    raise exception 'guarda: cambió algo más que la fila de ACELU';
  end if;
end $$;

select id, name, status, safety_level, validation_confidence, left(validation_notes, 260) as nota
  from public.places where id = 'd6d5375b-7ceb-44dc-9c3a-dac847f4a670';

commit;
