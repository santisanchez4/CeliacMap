-- APLICADO en producción el 2026-11-23 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura).
-- Registro de auditoría: no se vuelve a correr (su guarda de entrada fallaría con el lugar ya creado).
-- 2026-11-23 · Ñam Ñam by Lindsay (Fray Bentos, Río Negro): alta manual pedida por el administrador.
-- Mismo camino que db/fixes/2026-09-24-fray-bentos-dispensario.sql: aprobación manual en el primer insert, nunca
-- pasa por el Validator; validation_confidence null, verified false, safety_level options_available («Tiene
-- opciones sin gluten»), no 100%.
-- Anclado a su ficha de Google: Find Place «Ñam Ñam by Lindsay Fray Bentos» del 2026-11-23 devolvió
-- ChIJ62XDOX1NpZURoYm5dY0AlUk (names_match = True, OPERATIONAL, types bakery/food/store -> category cafe),
-- geometry -33.127861, -58.309578. Place Details del mismo día: formatted_phone_number 099 122 402, igual al
-- teléfono que dio el administrador (+598 99 122 402), así que no hace falta congelarlo en
-- config/manual_contact_fields.json. Horario, rating y web los completa el Updater desde la ficha.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-23-fray-bentos-nam-nam-by-lindsay.sql
begin;

create temp table b on commit drop as
  select (select count(*) from public.places) as places,
         (select count(*) from public.place_evidence) as evidence;

do $$
begin
  if exists (select 1 from public.places
              where external_id = 'ChIJ62XDOX1NpZURoYm5dY0AlUk'
                 or social_url ilike '%namnam_lindsay%'
                 or name ilike '%lindsay%') then
    raise exception 'guarda: el lugar ya existe en places';
  end if;
end $$;

create temp table n on commit drop as
with p as (
  insert into public.places
    (name, lat, lng, category, country, city, region, safety_level, status, address,
     source, external_id, geocode_method, social_url, phone, verified, validation_confidence,
     validation_notes)
  values
    ('Ñam Ñam by Lindsay', -33.127861, -58.309578, 'cafe', 'Uruguay', 'Fray Bentos', 'Río Negro',
     'options_available', 'approved', 'Coviren viv 30, 65000 Fray Bentos',
     'manual', 'ChIJ62XDOX1NpZURoYm5dY0AlUk', 'find_place',
     'https://www.instagram.com/namnam_lindsay/', '099 122 402', false, null,
     'APROBACIÓN MANUAL (2026-11-23, Santiago Sánchez): el administrador conoce el emprendimiento y sabe que ofrece opciones sin gluten; la ubicación es la que publica su propia ficha de Google')
  returning id
)
select id from p;

insert into public.place_evidence (place_id, source, text, url)
select id, 'admin',
       'APROBACIÓN MANUAL (2026-11-23, Santiago Sánchez): el administrador conoce el emprendimiento y sabe que ofrece opciones sin gluten; la ubicación es la que publica su propia ficha de Google',
       'https://www.instagram.com/namnam_lindsay/'
  from n;

do $$
begin
  if (select count(*) from n) <> 1
     or (select count(*) from public.places) - (select places from b) <> 1
     or (select count(*) from public.place_evidence) - (select evidence from b) <> 1
     or (select count(*) from public.place_evidence e join n on n.id = e.place_id where e.source = 'admin') <> 1 then
    raise exception 'guarda: no se insertó exactamente una fila en places y una en place_evidence';
  end if;
end $$;

select p.id, p.name, p.category, p.safety_level, p.status, p.city, p.region, p.address, p.lat, p.lng,
       p.external_id, p.geocode_method, p.social_url, p.phone, p.verified, p.validation_confidence,
       p.validation_notes,
       (select count(*) from public.place_evidence e where e.place_id = p.id and e.source = 'admin') as admin_evidence
  from public.places p join n on n.id = p.id;

commit;
