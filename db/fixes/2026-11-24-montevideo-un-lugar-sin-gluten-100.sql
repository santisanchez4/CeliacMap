-- APLICADO en producción el 2026-11-24 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura).
-- Registro de auditoría: no se vuelve a correr (su guarda de entrada fallaría con la fila ya cambiada).
-- 2026-11-24 · Un Lugar Sin Gluten (Montevideo): dirección corregida y vuelve a «Espacio 100% sin gluten».
-- Era una de las 7 filas bajadas a opciones el 2026-11-20 por no tener una cita del propio local. El administrador revisó a mano
-- su cuenta oficial (@unlugarsingluten): la bio dice «Productos artesanales 100% Gluten Free» y da Dr. Martín García 2351.
-- Mudanza: Place Details de su ficha (ChIJdVY2fC6Bn5URWKgl5_rraOI, 2026-11-24) está OPERATIONAL y ya dice «C. Martín García
-- 2351, 11800 Montevideo», con geometry -34.886918, -56.1670383 y teléfono 091 431 900 (igual al de la fila, sin entrada en
-- config/manual_contact_fields.json); Find Place «Un Lugar Sin Gluten Dr. Martín García 2351 Montevideo» devuelve el mismo
-- place_id (names_match = True).
-- Cruce con el listado de la Intendencia (db/checks/2026-10-13-imm/imm_locales_libres_de_gluten.csv, fila 17): «UN LUGAR SIN
-- GLUTEN», Dr Duvimioso Terra Nº 2148, habilitado del 30/10/2022 al 30/10/2027; el listado no publica el número de habilitación,
-- así que el 36038 no se coteja. Su punto queda a ~32 m del de Google.
-- No cambian status, validation_confidence ni verified.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-24-montevideo-un-lugar-sin-gluten-100.sql
begin;

create temp table b on commit drop as
  select status, validation_confidence, verified, updated_at,
         (select count(*) from public.place_evidence) as evidence
    from public.places where id = 'fa317252-5123-4eb1-a60e-c7e5b79bff7d';

do $$
begin
  if (select count(*) from public.places
       where id = 'fa317252-5123-4eb1-a60e-c7e5b79bff7d'
         and name = 'Un Lugar Sin Gluten'
         and external_id = 'ChIJdVY2fC6Bn5URWKgl5_rraOI'
         and address like 'Dr. Duvimioso Terra 2148%'
         and safety_level = 'celiac_friendly'
         and status = 'approved'
         and flags ? '100% pendiente de confirmación del administrador'
         and updated_at = '2026-11-20 21:53:43.027539+00') <> 1 then
    raise exception 'guarda: la fila no está como se leyó';
  end if;
  if (select count(*) from public.places
       where name ilike '%lugar%sin%gluten%' or social_url ilike '%unlugarsingluten%') <> 1 then
    raise exception 'guarda: hay más de una fila de este local';
  end if;
end $$;

create temp table u on commit drop as
with p as (
  update public.places
     set safety_level = 'gluten_free_100',
         flags = flags - '100% pendiente de confirmación del administrador',
         social_url = 'https://www.instagram.com/unlugarsingluten/',
         address = 'C. Martín García 2351, 11800 Montevideo, Departamento de Montevideo, Uruguay',
         lat = -34.886918,
         lng = -56.1670383,
         validation_notes =
           'APROBACIÓN MANUAL (2026-11-24, Santiago Sánchez): vuelve a «Espacio 100% sin gluten»: su cuenta oficial dice «Productos artesanales 100% Gluten Free»; revisada por el administrador. Declara habilitación IMM 36038' || E'\n'
           || 'CORRECCIÓN MANUAL (2026-11-24, Santiago Sánchez): dirección corregida: de Dr. Duvimioso Terra 2148 a C. Martín García 2351 (la dirección y las coordenadas que hoy publica su ficha de Google, que es la misma; su cuenta oficial da Dr. Martín García 2351).' || E'\n\n'
           || validation_notes
   where id = 'fa317252-5123-4eb1-a60e-c7e5b79bff7d'
  returning id
)
select id from p;

insert into public.place_evidence (place_id, source, text, url)
select id, 'admin',
       'Revisión manual (2026-11-24, Santiago Sánchez): bio de su cuenta oficial de Instagram (@unlugarsingluten), revisada a mano por el administrador. Cita: «✨Productos artesanales 100% Gluten Free ✨Habilitación IMM 36038 ⌚Lunes 10 a 19hrs ⌚️Mar a Sab 10 a 22hrs 👇🏼Hace tu pedido por Whatsapp Dr. Martín García 2351, Montevideo, Uruguay». Cruce con el listado de locales habilitados de la Intendencia de Montevideo (capa Locales_Gluten_Free, copia del 2026-10-13): figura «UN LUGAR SIN GLUTEN» en Dr Duvimioso Terra Nº 2148 (elaboración de productos panificados, rotisería, libre de gluten), habilitado del 30/10/2022 al 30/10/2027; el listado no publica el número de habilitación, así que el 36038 no se pudo cotejar.',
       'https://www.instagram.com/unlugarsingluten/'
  from u;

do $$
begin
  if (select count(*) from u) <> 1
     or (select count(*) from public.place_evidence) - (select evidence from b) <> 1
     or (select count(*) from public.place_evidence e join u on u.id = e.place_id where e.source = 'admin') <> 1
     or (select count(*) from public.places p, b
          where p.id = 'fa317252-5123-4eb1-a60e-c7e5b79bff7d'
            and p.status = b.status
            and p.validation_confidence is not distinct from b.validation_confidence
            and p.verified = b.verified
            and p.safety_level = 'gluten_free_100'
            and not coalesce(p.flags ? '100% pendiente de confirmación del administrador', false)) <> 1 then
    raise exception 'guarda: no se actualizó exactamente una fila y se insertó una de evidencia, o cambió status/confianza/verified';
  end if;
end $$;

select p.id, p.name, p.address, p.lat, p.lng, p.safety_level, p.status, p.validation_confidence, p.verified, p.flags,
       p.social_url, p.phone, left(p.validation_notes, 520) as notes_start,
       (select e.text from public.place_evidence e where e.place_id = p.id and e.source = 'admin') as admin_evidence
  from public.places p join u on u.id = p.id;

commit;
