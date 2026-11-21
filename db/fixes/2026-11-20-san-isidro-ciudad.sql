-- APLICADO en producción el 2026-11-20 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo
-- lectura): 1 fila; updated_at sin cambios; filas con city 'San Isidro' 35 -> 36; manual_override_marker -> None.
-- Registro de auditoría: no se vuelve a correr (su guarda de entrada fallaría con el estado actual).
-- ⚠️ El Updater la puede volver a pisar el próximo día 1 (ver docs/DECISIONS.md, entrada de barrios del chat).
-- 2026-11-20 · La Union Bakery Gluten Free San Isidro: city vuelve a «San Isidro».
-- Decisión del administrador (2026-11-20). El fix 2026-09-27-city-from-address.sql ya la había corregido; el Updater la
-- volvió a «Buenos Aires» el 2026-10-01 (agent_log: changes.city), porque toma la localidad de los address_components de
-- Google y Google dice «Buenos Aires» para «25 de Mayo 12, B1642». B1642 es el código postal de San Isidro, el nombre dice
-- San Isidro y region ya es «Buenos Aires» (la provincia). Con city «Buenos Aires» el lugar salía en las búsquedas de CABA.
-- La línea nueva es una corrección de DATOS («ciudad corregida», agents/manual_overrides.py): no protege el lugar, y
-- manual_override_marker de la nota completa sigue en None. Solo cambian city y validation_notes; el resto de la fila y
-- updated_at quedan igual (hash de las demás columnas, trigger apagado dentro de la transacción).
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-20-san-isidro-ciudad.sql
begin;

create temp table _snap on commit drop as
select id, city, validation_notes, md5((to_jsonb(p) - 'city' - 'validation_notes')::text) as h from public.places p;

create temp table _b on commit drop as
select (select count(*) from public.places) as places,
       (select count(*) from public.places where status = 'approved') as approved,
       (select count(*) from public.places where city = 'San Isidro') as san_isidro;

do $$
begin
  if (select count(*) from public.places
        where id = '3efed1b0-2161-4a0a-89a2-c5440ff94dc9' and status = 'approved' and city = 'Buenos Aires'
          and region = 'Buenos Aires' and address like '25 de Mayo 12, B1642 %'
          and validation_notes like 'CORRECCIÓN MANUAL (2026-11-06): la etiqueta baja%') <> 1 then
    raise exception 'guarda: La Union San Isidro no está como se leyó';
  end if;
end $$;

alter table public.places disable trigger places_set_updated_at;

do $$
declare n int;
begin
  update public.places
     set city = 'San Isidro',
         validation_notes = concat_ws(E'\n\n',
           'CORRECCIÓN MANUAL 2026-11-20: ciudad corregida de «Buenos Aires» a «San Isidro» (B1642 es San Isidro; el Updater la había vuelto a «Buenos Aires» el 2026-10-01)',
           validation_notes)
   where id = '3efed1b0-2161-4a0a-89a2-c5440ff94dc9' and city = 'Buenos Aires';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'esperaba 1 fila, actualizó %', n; end if;
end $$;

alter table public.places enable trigger places_set_updated_at;

do $$
declare bad int;
begin
  select count(*) into bad from public.places p join _snap s using (id)
   where p.city is distinct from s.city or p.validation_notes is distinct from s.validation_notes;
  if bad <> 1 then raise exception 'esperaba 1 fila con ciudad o nota nueva, hay %', bad; end if;
  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'city' - 'validation_notes')::text) <> s.h;
  if bad <> 0 then raise exception 'cambió algo más que city y validation_notes en % filas', bad; end if;
  if (select places from _b) <> (select count(*) from public.places)
     or (select approved from _b) <> (select count(*) from public.places where status = 'approved')
     or (select san_isidro from _b) + 1 <> (select count(*) from public.places where city = 'San Isidro') then
    raise exception 'cambiaron los conteos';
  end if;
  if not (select tgenabled <> 'D' from pg_trigger where tgname = 'places_set_updated_at') then
    raise exception 'el trigger places_set_updated_at quedó apagado';
  end if;
end $$;

select id, name, city, region, status, safety_level, validation_notes
  from public.places where id = '3efed1b0-2161-4a0a-89a2-c5440ff94dc9';

commit;
