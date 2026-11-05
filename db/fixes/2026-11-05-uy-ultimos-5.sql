-- APLICADO en producción el 2026-11-05 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura).
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-05 · Los últimos 5 lugares de Uruguay de la cola «100% pendiente»: Monik (retirado del mapa) y las 4 decisiones del admin.
-- validation_confidence y verified no se tocan. Ensayo: termina en ROLLBACK; la versión que se aplica cambia solo la última línea por COMMIT.
begin;

create temp table d (
  id uuid primary key, expected_updated_at timestamptz not null, old_social text, new_social text,
  new_status text not null check (new_status in ('approved','discarded','needs_review')),
  level text check (level in ('gluten_free_100','options_available')),   -- null = no cambia
  header text not null, ev_text text not null, ev_url text
) on commit drop;

insert into d values
-- Monik: fuera del mapa, sigue en needs_review.
('b4d78166-3af7-4182-b929-362e238b5366','2026-10-01 20:55:15.924144+00','http://www.facebook.com/Monik-sin-gluten-200303317091903/?ref=ts&fref=ts', null,
 'needs_review', null,
 'RETIRADO DEL MAPA (2026-11-05): ficha de Google no encontrada y sin actividad pública; se revisa si reaparece.',
 'Revisión 2026-11-05 (admin): retirado del mapa. Google Places ya no encuentra su ficha (place_id NOT_FOUND); no se encontró un canal propio con actividad.', null),
-- Sin Gluten Colonia: 100%, cuenta oficial confirmada.
('06065939-2465-466a-a751-041a6abe0bb4','2026-11-01 15:55:37.808045+00', null, 'https://www.instagram.com/singluten_colonia',
 'approved', 'gluten_free_100',
 'APROBACIÓN MANUAL (2026-11-05, fix SQL): El administrador revisó su cuenta oficial (@singluten_colonia) y confirma que es un establecimiento 100% sin gluten.',
 'El administrador revisó la cuenta oficial (@singluten_colonia) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «Empresa dedicada a la elaboración y venta de productos 100% libres de gluten, apto celíacos»',
 'https://www.instagram.com/singluten_colonia'),
-- Celilife: fábrica que vende por terceros, sin local propio de venta al público.
('8e0758b6-7568-4c2e-973d-adefefec45c2','2026-09-25 03:49:02.868024+00','https://www.instagram.com/reel/DO6lYCAj-7B', null,
 'discarded', null,
 'DESCARTE MANUAL (2026-11-05, fix SQL): No es un comercio: Celilife es una fábrica de alimentos sin gluten que vende a través de otros comercios; su ficha de Google no tiene horarios y su Instagram no ofrece local ni retiro.',
 'Revisión 2026-11-05 (admin): descartado, no es un comercio. Su Instagram se presenta como «CELILIFE | FABRICA DE ALIMENTOS LIBRE DE GLUTEN» y dice: «¡Estamos en todo Montevideo! 🤩 Deslizá y conocé todos puntos de ventas en los que podés encontrar nuestros productos libres de gluten». La ficha de Google no tiene horarios.',
 'https://www.instagram.com/p/DIG4s7Agmf-'),
-- 0%Gluten: opciones, sin evidencia propia.
('e4b7d8eb-365a-4116-a321-cc8132da1211','2026-09-25 03:48:58.448302+00', null, null,
 'approved', 'options_available',
 'APROBACIÓN MANUAL (2026-11-05, fix SQL): Revisión del 2026-11-05 aprobada por el administrador: ningún canal propio del lugar dice que todo lo que vende o cocina es sin gluten; queda con opciones sin TACC hasta que el administrador confirme el 100%.',
 'Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa (venta por pedido, dirección sin número); no se encontró ningún canal propio.', null),
-- GLUTEN FREE Y JUGOS: opciones; la cuenta @glutenfree.mvd era de otro negocio.
('599fd49d-85c9-4e98-a950-8d3ab0ec6722','2026-09-25 03:48:48.381786+00', null, null,
 'approved', 'options_available',
 'APROBACIÓN MANUAL (2026-11-05, fix SQL): Revisión del 2026-11-05 aprobada por el administrador: ningún canal propio del lugar dice que todo lo que vende o cocina es sin gluten (la cuenta @glutenfree.mvd, con dirección en Herrera, era de otro negocio); queda con opciones sin TACC hasta que el administrador confirme el 100%.',
 'Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa en José Germán Araújo 1206, teléfono igual al de la fila. La cuenta @glutenfree.mvd (sin publicaciones desde 2021, dirección en Luis Alberto de Herrera) es de otro negocio y no se usa como evidencia.', null);

create temp table baseline on commit drop as
  select (select count(*) from public.places) as places,
         (select count(*) from public.places where status = 'approved') as approved,
         (select count(*) from public.place_evidence) as evidence;

do $$
begin
  if (select count(*) from public.places p join d on d.id = p.id
        where p.status = 'approved' and p.country = 'Uruguay' and p.updated_at = d.expected_updated_at
          and p.social_url is not distinct from d.old_social
          and p.flags @> '["100% pendiente de confirmación del administrador"]'::jsonb) <> 5 then
    raise exception 'guarda: las 5 filas no están como se leyeron';
  end if;
  if exists (select 1 from public.place_evidence e join d on d.id = e.place_id) then
    raise exception 'guarda: alguna fila ya tiene place_evidence';
  end if;
end $$;

update public.places p
   set social_url = coalesce(d.new_social, p.social_url),
       status = d.new_status,
       safety_level = coalesce(d.level, p.safety_level),
       flags = coalesce((select jsonb_agg(f) from jsonb_array_elements(p.flags) f
                          where f <> to_jsonb('100% pendiente de confirmación del administrador'::text)), '[]'::jsonb),
       validation_notes = concat_ws(E'\n\n',
         case when d.header like 'RETIRADO DEL MAPA%' then d.header
              else d.header || ' El Validator había dejado: ' || p.status || coalesce(' @ ' || p.validation_confidence::text, '') || '.' end,
         case when d.new_social is not null then
           'CORRECCIÓN MANUAL (2026-11-05): cuenta oficial confirmada por el administrador: ' || d.new_social
             || '. social_url anterior: ' || coalesce(d.old_social, 'vacío') || '.' end,
         nullif(btrim(p.validation_notes), ''))
  from d
 where p.id = d.id;

insert into public.place_evidence (place_id, source, text, url)
select id, 'admin', ev_text, ev_url from d;

do $$
begin
  if (select count(*) from public.places p join d on d.id = p.id
        where p.status = d.new_status and p.safety_level = coalesce(d.level, 'gluten_free_100')
          and not p.flags @> '["100% pendiente de confirmación del administrador"]'::jsonb
          and p.validation_notes like left(d.header, 30) || '%') <> 5 then
    raise exception 'guarda: no quedaron las 5 filas como se esperaba';
  end if;
  if (select places from baseline) <> (select count(*) from public.places)
     or (select approved from baseline) - 2 <> (select count(*) from public.places where status = 'approved')
     or (select evidence from baseline) + 5 <> (select count(*) from public.place_evidence) then
    raise exception 'guarda: cambió la cantidad de lugares, de aprobados (−2) o de evidencia (+5) más de lo previsto';
  end if;
end $$;

select p.name, p.status, p.safety_level, p.flags, p.social_url, p.validation_confidence, p.verified,
       left(p.validation_notes, 260) as nota,
       (select count(*) from public.place_evidence e where e.place_id = p.id and e.source = 'admin') as ev_admin
  from public.places p join d on d.id = p.id order by p.status, p.name;

commit;
