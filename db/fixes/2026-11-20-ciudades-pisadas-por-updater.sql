-- APLICADO en producción el 2026-11-21 (ensayo con ROLLBACK dos veces, después esta versión con COMMIT y verificación de
-- solo lectura): 10 filas; manual_override_marker de cada una igual antes y después; quedan 0 filas con esas ciudades.
-- Registro de auditoría: no se vuelve a correr (su guarda de entrada fallaría con el estado actual).
-- 2026-11-20 · city de 10 lugares (7 aprobados + 3 no publicados) con la localidad de Google en vez del pueblo.
-- Decisión del administrador (2026-11-20), después del PR que impide que el Updater vuelva a escribir city / country /
-- region (docs/DECISIONS.md, «El Updater no reescribe ciudad, país ni región»):
--   Kanu Sushi - Delivery Vicente Lopez   'buenos aires' -> 'Vicente López'  (la dirección dice «vicente lopez»; ya corregida
--                                          el 2026-09-27, el Updater la volvió atrás)
--   5 lugares de CABA                      'Ciudad Autónoma de Buenos Aires' -> 'Buenos Aires' (regla «CABA es Buenos Aires»;
--                                          los escribió el Updater el 2026-11-01)
--   Ríccoli                                'Uruguay' -> 'Montevideo' (Cuaro 3151, 11800 Montevideo)
--   No publicados, mismas ciudades (pedido del administrador 2026-11-21): La Cocina de Matías (needs_review, CABA),
--   Instituto Savez y San Francisco C.I.S.A. (discarded, Montevideo, 'Uruguay').
-- Cada línea nueva es una corrección de DATOS («ciudad corregida», agents/manual_overrides.py): no protege el lugar. Dos de
-- las filas (GOUT Barracas, Ríccoli) ya tienen una APROBACIÓN MANUAL anterior que las protege; eso no cambia. Lo que se
-- verifica es que manual_override_marker de cada nota quede igual que antes.
-- Solo cambian city y validation_notes; el resto de cada fila y updated_at quedan igual (hash de las demás columnas,
-- trigger apagado dentro de la transacción).
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-20-ciudades-pisadas-por-updater.sql
begin;

create temp table _snap on commit drop as
select id, city, validation_notes, md5((to_jsonb(p) - 'city' - 'validation_notes')::text) as h from public.places p;

create temp table _fix (
  id uuid primary key, old_city text not null, new_city text not null, status text not null, region text not null
) on commit drop;
insert into _fix (id, old_city, new_city, status, region) values
  ('ad0ee75e-2026-45ef-9cc4-bb45edf20441', 'buenos aires', 'Vicente López', 'approved', 'Buenos Aires'),
  ('cc171911-7afd-4c53-a107-c633aae45b1f', 'Ciudad Autónoma de Buenos Aires', 'Buenos Aires', 'approved', 'Ciudad Autónoma de Buenos Aires'),
  ('0ad32fd2-75f9-4d13-9bb2-d9db78d8fd06', 'Ciudad Autónoma de Buenos Aires', 'Buenos Aires', 'approved', 'Ciudad Autónoma de Buenos Aires'),
  ('18a05b0b-a0e8-4141-a517-38f5344af1e7', 'Ciudad Autónoma de Buenos Aires', 'Buenos Aires', 'approved', 'Ciudad Autónoma de Buenos Aires'),
  ('02359bc6-b895-4313-9f1f-07234c6f1a6a', 'Ciudad Autónoma de Buenos Aires', 'Buenos Aires', 'approved', 'Ciudad Autónoma de Buenos Aires'),
  ('ae9293eb-271d-4d08-a719-2d917965c288', 'Ciudad Autónoma de Buenos Aires', 'Buenos Aires', 'approved', 'Ciudad Autónoma de Buenos Aires'),
  ('378e84a5-8ab7-44a1-953a-c940112f0575', 'Uruguay', 'Montevideo', 'approved', 'Montevideo'),
  ('29e8f921-b428-4e49-b7ed-5be86650b62e', 'Ciudad Autónoma de Buenos Aires', 'Buenos Aires', 'needs_review', 'Ciudad Autónoma de Buenos Aires'),
  ('0cb69c96-eb24-4725-b78f-a1bfc5f30e75', 'Uruguay', 'Montevideo', 'discarded', 'Montevideo'),
  ('be6d68f1-401d-46fa-919e-eebdc55e7378', 'Uruguay', 'Montevideo', 'discarded', 'Montevideo');

do $$
declare n int;
begin
  select count(*) into n from _fix f join public.places p on p.id = f.id
   where p.city = f.old_city and p.status = f.status and p.region = f.region;
  if n <> 10 then raise exception 'guarda: se esperaban 10 filas como se leyeron, hay %', n; end if;
end $$;

alter table public.places disable trigger places_set_updated_at;

do $$
declare n int;
begin
  update public.places p
     set city = f.new_city,
         validation_notes = concat_ws(E'\n\n',
           'CORRECCIÓN MANUAL 2026-11-21: ciudad corregida de «' || f.old_city || '» a «' || f.new_city
             || '» (la había escrito el Updater desde la localidad de Google)',
           nullif(p.validation_notes, ''))
    from _fix f
   where p.id = f.id and p.city = f.old_city and p.status = f.status;
  get diagnostics n = row_count;
  if n <> 10 then raise exception 'esperaba 10 filas, actualizó %', n; end if;
end $$;

alter table public.places enable trigger places_set_updated_at;

do $$
declare bad int;
begin
  select count(*) into bad from public.places p join _snap s using (id)
   where p.city is distinct from s.city or p.validation_notes is distinct from s.validation_notes;
  if bad <> 10 then raise exception 'esperaba 10 filas con ciudad o nota nueva, hay %', bad; end if;
  select count(*) into bad from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'city' - 'validation_notes')::text) <> s.h;
  if bad <> 0 then raise exception 'cambió algo más que city y validation_notes en % filas', bad; end if;
  if (select count(*) from public.places) <> (select count(*) from _snap)
     or (select count(*) from public.places where status = 'approved')
        <> (select count(*) from _snap s join public.places p using (id) where p.status = 'approved') then
    raise exception 'cambiaron los conteos';
  end if;
  if (select count(*) from public.places
        where city in ('Ciudad Autónoma de Buenos Aires', 'Uruguay', 'buenos aires')) <> 0 then
    raise exception 'quedó alguna de las ciudades a corregir';
  end if;
  if not (select tgenabled <> 'D' from pg_trigger where tgname = 'places_set_updated_at') then
    raise exception 'el trigger places_set_updated_at quedó apagado';
  end if;
end $$;

select p.id, p.name, s.city as antes, p.city as despues, s.validation_notes as notas_antes, p.validation_notes as notas_despues
  from public.places p join _snap s using (id) join _fix f using (id) order by p.name;

commit;
