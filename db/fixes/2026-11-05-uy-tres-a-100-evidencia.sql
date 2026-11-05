-- APLICADO en producción el 2026-11-05 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura).
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-05 · EMPATIA, Gluten Out y Mi espacio sin TACC: el admin averiguó directamente que son 100% sin gluten.
-- Paso 1 de 2: social_url (EMPATIA y Gluten Out) con CORRECCIÓN MANUAL y una fila admin en place_evidence por lugar.
-- El paso 2 es review_queue --approve ID --level 100 (pone el nivel y la APROBACIÓN MANUAL encima).
-- No toca status, safety_level, flags, validation_confidence ni verified. Ensayo: termina en ROLLBACK.
begin;

create temp table d (id uuid primary key, expected_updated_at timestamptz not null, new_social text, ev_text text not null, ev_url text) on commit drop;
insert into d values
('7212e339-5011-484e-92df-19e4caf4ebf0','2026-11-05 22:09:15.600777+00','https://www.instagram.com/empatia.glutenfree',
 'El administrador averiguó directamente (2026-11-05) y confirma que EMPATIA es un establecimiento 100% sin gluten. Cita de su Instagram: «Elaboramos alimentos SIN GLUTEN, APTOS PARA CELÍACOS (libre de contaminación)»',
 'https://www.instagram.com/empatia.glutenfree'),
('a6493fc7-279c-4e30-81d3-d79a7e89cc9c','2026-11-05 22:09:23.409021+00','https://www.instagram.com/glutenoutminas',
 'El administrador averiguó directamente (2026-11-05) y confirma que Gluten Out es un establecimiento 100% sin gluten. Su Instagram da la misma dirección que la fila: «📍Amilivia531(bis) Garibaldi y Av.Varela […] Minas»',
 'https://www.instagram.com/glutenoutminas'),
('0274deb6-ba10-43fc-b35c-411e871d7505','2026-11-05 22:09:36.824602+00', null,
 'El administrador averiguó directamente (2026-11-05) y confirma que Mi espacio sin TACC es un establecimiento 100% sin gluten.',
 null);

create temp table baseline on commit drop as
  select (select count(*) from public.places) as places, (select count(*) from public.place_evidence) as evidence;

do $$ begin
  if (select count(*) from public.places p join d on d.id = p.id
        where p.status = 'approved' and p.country = 'Uruguay' and p.safety_level = 'options_available'
          and p.updated_at = d.expected_updated_at and p.social_url is null) <> 3 then
    raise exception 'guarda: las 3 filas no están como se leyeron';
  end if;
end $$;

update public.places p
   set social_url = d.new_social,
       validation_notes = concat_ws(E'\n\n',
         'CORRECCIÓN MANUAL (2026-11-05): cuenta oficial confirmada por el administrador: ' || d.new_social || '. social_url anterior: vacío.',
         nullif(btrim(p.validation_notes), ''))
  from d
 where p.id = d.id and d.new_social is not null;

insert into public.place_evidence (place_id, source, text, url) select id, 'admin', ev_text, ev_url from d;

do $$ begin
  if (select count(*) from public.places p join d on d.id = p.id where p.social_url is not distinct from d.new_social) <> 3
     or (select places from baseline) <> (select count(*) from public.places)
     or (select evidence from baseline) + 3 <> (select count(*) from public.place_evidence) then
    raise exception 'guarda: el resultado no es el esperado';
  end if;
end $$;

select p.name, p.status, p.safety_level, p.social_url, left(p.validation_notes, 120) as nota,
       (select count(*) from public.place_evidence e where e.place_id = p.id and e.source = 'admin') as ev_admin
  from public.places p join d on d.id = p.id order by p.name;

commit;
