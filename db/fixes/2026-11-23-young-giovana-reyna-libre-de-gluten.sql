-- APLICADO en producción el 2026-11-23 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura).
-- Registro de auditoría: no se vuelve a correr (su guarda de entrada fallaría con el lugar ya creado).
-- 2026-11-23 · Giovana Reyna libre de gluten (Young, Río Negro): alta manual pedida por el administrador.
-- Emprendimiento de dulces y salados por encargo, con retiro en Treinta y Tres 3070 (entre Hervidero y Piedra Alta).
-- El emprendimiento pasó la dirección de retiro y confirmó al administrador que está de acuerdo en figurar en el mapa.
-- 100% asignado por el administrador (regla «el 100% lo asigna solo una persona»): cita fechada de la bio de su cuenta
-- oficial en place_evidence (fila admin) + lo que el emprendimiento le confirmó al administrador. Nunca pasa por el
-- Validator; validation_confidence null, verified false.
-- Sin ficha de Google propia: Find Place «Giovana Reyna libre de gluten Young» (2026-11-23) devolvió «Rikuras Sin
-- Gluten» (Montevideo), names_match = False. Ubicación por Geocoding API, solo la dirección (geocode_method
-- address_only, external_id null, como Ta Bacana): «Treinta y Tres 3070, 65100 Young» ROOFTOP, sin partial_match,
-- -32.7059424, -57.6273396. Cuadra comprobada con las dos esquinas (intersecciones Treinta y Tres & Hervidero
-- -32.7055495, -57.6279155 y Piedra Alta & Treinta y Tres -32.7064034, -57.6271879): el punto queda al 57 % del tramo
-- de ~116 m y a ~18 m del eje de la calle.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-23-young-giovana-reyna-libre-de-gluten.sql
begin;

create temp table b on commit drop as
  select (select count(*) from public.places) as places,
         (select count(*) from public.place_evidence) as evidence;

do $$
begin
  if exists (select 1 from public.places
              where name ilike '%giovan%reyna%'
                 or social_url ilike '%giovanareyna%'
                 or regexp_replace(coalesce(phone, ''), '[^0-9]', '', 'g') like '%98299755') then
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
    ('Giovana Reyna libre de gluten', -32.7059424, -57.6273396, 'cafe', 'Uruguay', 'Young', 'Río Negro',
     'gluten_free_100', 'approved', 'Treinta y Tres 3070, entre Hervidero y Piedra Alta, Young',
     'manual', null, 'address_only',
     'https://www.instagram.com/giovanareynalibredegluten/', '098 299 755', false, null,
     'APROBACIÓN MANUAL (2026-11-23, Santiago Sánchez): su cuenta oficial dice «Productos 100% libre de gluten»; el administrador habló con el emprendimiento, que confirmó que elabora solo con productos libres de gluten en una cocina exclusiva y que está de acuerdo en figurar en el mapa con su dirección de retiro')
  returning id
)
select id from p;

insert into public.place_evidence (place_id, source, text, url)
select id, 'admin',
       'Revisión manual (2026-11-23, Santiago Sánchez): bio de su cuenta oficial de Instagram (@giovanareynalibredegluten), transcripta por el administrador. Cita: «Productos 100% libre de gluten. Dulces y salados. Por encargues con 48 hrs de anticipación. Contacto MD o Wpp 098299755».',
       'https://www.instagram.com/giovanareynalibredegluten/'
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

select p.id, p.name, p.category, p.safety_level, p.status, p.city, p.region, p.country, p.address, p.lat, p.lng,
       p.external_id, p.geocode_method, p.social_url, p.phone, p.verified, p.validation_confidence,
       p.validation_notes,
       (select e.text from public.place_evidence e where e.place_id = p.id and e.source = 'admin') as admin_evidence
  from public.places p join n on n.id = p.id;

commit;
