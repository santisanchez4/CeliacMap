-- APLICADO en producción el 2026-11-05 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura).
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-05 · Decisiones del administrador sobre 12 lugares de Uruguay de la cola «100% pendiente».
-- Por lugar: social_url con la cuenta oficial (CORRECCIÓN MANUAL), el nivel con APROBACIÓN MANUAL (igual que
-- review_queue --approve: status approved, safety_level, flag de pendiente fuera, encabezado delante de las notas;
-- validation_confidence y verified no se tocan) y una fila admin en place_evidence con la cita literal.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
begin;

create temp table d (
  id uuid primary key, expected_updated_at timestamptz not null,
  old_social text, new_social text,           -- new_social null = no se cambia
  level text not null check (level in ('gluten_free_100','options_available')),
  approval_note text not null, ev_text text not null, ev_url text
) on commit drop;

insert into d values
('a03020bf-b13c-4a5c-afca-0dd66888c1dc','2026-09-25 03:48:49.805379+00', null, 'https://www.instagram.com/alapalaglutenfree', 'gluten_free_100',
 'El administrador revisó su cuenta oficial (@alapalaglutenfree) y confirma que es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@alapalaglutenfree) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «🍕Pizzas Sin Gluten / Pizzas Sin Lactosa»',
 'https://www.instagram.com/alapalaglutenfree'),
('3a3f5470-fee4-4d7f-959f-f01e8d8d5f2e','2026-09-25 03:48:52.067936+00', null, 'https://www.instagram.com/locosuelto_uy', 'gluten_free_100',
 'El administrador revisó su cuenta oficial (@locosuelto_uy) y confirma que es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@locosuelto_uy) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «Productos 100% aptos para celíacos»',
 'https://www.instagram.com/locosuelto_uy'),
('62619f79-3636-43d2-ab7a-fa6fc662f48d','2026-09-25 03:48:52.386107+00', null, 'https://www.instagram.com/delacasa_singluten', 'gluten_free_100',
 'El administrador revisó su cuenta oficial (@delacasa_singluten) y confirma que es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@delacasa_singluten) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «Elaboramos exclusivos productos sin gluten.»',
 'https://www.instagram.com/delacasa_singluten'),
('9748f698-dfcf-483c-bb75-eebd7457db5f','2026-09-25 03:48:52.760379+00', null, 'https://www.instagram.com/celiacos33', 'gluten_free_100',
 'El administrador revisó su cuenta oficial (@celiacos33) y confirma que es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@celiacos33) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «Somos de Treinta y tres. […] Nuestro local❤ · #singluten #glutenfree #celíacos»',
 'https://www.instagram.com/celiacos33'),
('51ab73ce-8ff4-41dd-a724-76b375d863ed','2026-10-01 20:55:15.924144+00', 'https://www.instagram.com/quiero_singluten/', null, 'gluten_free_100',
 'El administrador revisó su cuenta oficial (@quiero_singluten) y confirma que es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@quiero_singluten) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «Elaboración 100% artesanal de Comida sin Gluten»',
 'https://www.instagram.com/quiero_singluten'),
('77ef6ceb-08ac-4b34-b4cf-598331869bef','2026-09-25 03:49:03.620088+00', 'https://www.instagram.com/paganaglutenfree', null, 'gluten_free_100',
 'El administrador revisó su cuenta oficial (@paganaglutenfree) y confirma que es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@paganaglutenfree) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «Cafetería Gluten Free»',
 'https://www.instagram.com/paganaglutenfree'),
('49a9b63f-24a4-4b0d-b74f-9f94c3f64f4a','2026-09-25 03:48:58.518642+00', null, 'https://www.instagram.com/granjalemuria', 'gluten_free_100',
 'El administrador revisó su cuenta oficial (@granjalemuria) y confirma que es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@granjalemuria) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «Comida sin gluten congelada o pronta para llevar»',
 'https://www.instagram.com/granjalemuria'),
('9a32f415-7186-43f9-96be-8c61b16d2f01','2026-09-25 03:49:03.467242+00', null, 'https://www.instagram.com/beulacoffee', 'gluten_free_100',
 'El administrador revisó su cuenta oficial (@beulacoffee) y confirma que es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@beulacoffee) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «Todo 100% sin gluten, hecho para disfrutar sin pensarlo demasiado.»',
 'https://www.instagram.com/beulacoffee'),
('c94f0b1a-205a-47bf-b486-5356df1ae974','2026-09-25 03:49:04.070412+00', null, 'https://www.instagram.com/celisanosalto', 'gluten_free_100',
 'El administrador revisó su cuenta oficial (@celisanosalto) y confirma que es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@celisanosalto) el 2026-11-05 y confirma que es un establecimiento 100% sin gluten. Cita de su bio: «Todo 100% libre de gluten Comidas, meriendas, y más»',
 'https://www.instagram.com/celisanosalto'),
('28b73dab-e1e3-4f76-b3ec-ba9ad231601d','2026-09-25 03:48:58.602541+00', null, null, 'gluten_free_100',
 'El administrador confirma por conocimiento directo que todo lo que elabora La Juana es sin gluten: es un establecimiento 100% sin gluten',
 'El administrador confirma por conocimiento directo (2026-11-05) que todo lo que elabora La Juana es sin gluten. No hay cita de una cuenta propia: la búsqueda del 2026-11-05 solo encontró una guía de terceros (glutengo.com.uy) que la lista como cafetería con opciones.',
 null),
('f91f627a-2cc1-4fcf-b6eb-aaa08b04656a','2026-10-01 20:55:15.924144+00', 'https://www.facebook.com/v%C3%ADaSana-1681312118763035/', 'https://www.instagram.com/viasana_tiendadealimentos', 'options_available',
 'El administrador revisó su cuenta oficial (@viasana_tiendadealimentos): vende productos para celíacos junto con productos para otras dietas, así que tiene opciones sin TACC y no es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@viasana_tiendadealimentos) el 2026-11-05: vende productos para celíacos junto con productos para otras dietas; tiene opciones, no es 100%. Cita de su bio: «Alimentos aptos celíacos. F. Carámbula 1121 - Rivera»',
 'https://www.instagram.com/viasana_tiendadealimentos'),
('3909ce8b-bf75-4859-9a04-56eb3f374103','2026-09-25 03:48:58.748141+00', null, 'https://www.instagram.com/almacen_gelpi', 'options_available',
 'El administrador revisó su cuenta oficial (@almacen_gelpi): es un almacén con productos sin gluten, así que tiene opciones sin TACC y no es un establecimiento 100% sin gluten',
 'El administrador revisó la cuenta oficial (@almacen_gelpi) el 2026-11-05: es un almacén con productos sin gluten; tiene opciones, no es 100%. Cita de su bio: «Productos sin gluten. Provision de bebidas y comestibles»',
 'https://www.instagram.com/almacen_gelpi');

create temp table baseline on commit drop as
  select (select count(*) from public.places) as places,
         (select count(*) from public.places where status = 'approved') as approved,
         (select count(*) from public.place_evidence) as evidence;

do $$
begin
  if (select count(*) from public.places p join d on d.id = p.id
        where p.status = 'approved' and p.country = 'Uruguay' and p.updated_at = d.expected_updated_at
          and p.social_url is not distinct from d.old_social
          and p.flags @> '["100% pendiente de confirmación del administrador"]'::jsonb) <> 12 then
    raise exception 'guarda: las 12 filas no están como se leyeron (approved, Uruguay, updated_at, social_url, flag de pendiente)';
  end if;
  if exists (select 1 from public.place_evidence e join d on d.id = e.place_id) then
    raise exception 'guarda: alguna fila ya tiene place_evidence';
  end if;
end $$;

update public.places p
   set social_url = coalesce(d.new_social, p.social_url),
       status = 'approved',
       safety_level = d.level,
       flags = coalesce((select jsonb_agg(f) from jsonb_array_elements(p.flags) f
                          where f <> to_jsonb('100% pendiente de confirmación del administrador'::text)), '[]'::jsonb),
       validation_notes = concat_ws(E'\n\n',
         'APROBACIÓN MANUAL (2026-11-05, fix SQL): ' || d.approval_note || '. El Validator había dejado: '
           || p.status || coalesce(' @ ' || p.validation_confidence::text, '') || '.',
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
        where p.status = 'approved' and p.safety_level = d.level
          and p.social_url is not distinct from coalesce(d.new_social, d.old_social)
          and not p.flags @> '["100% pendiente de confirmación del administrador"]'::jsonb
          and p.validation_notes like 'APROBACIÓN MANUAL (2026-11-05, fix SQL): %') <> 12 then
    raise exception 'guarda: no quedaron las 12 filas como se esperaba';
  end if;
  if (select places from baseline) <> (select count(*) from public.places)
     or (select approved from baseline) <> (select count(*) from public.places where status = 'approved')
     or (select evidence from baseline) + 12 <> (select count(*) from public.place_evidence) then
    raise exception 'guarda: cambió la cantidad de lugares, de aprobados o de evidencia más de lo previsto';
  end if;
end $$;

select p.name, p.safety_level, p.flags, p.social_url, p.validation_confidence, p.verified,
       left(p.validation_notes, 400) as nota,
       (select count(*) from public.place_evidence e where e.place_id = p.id and e.source = 'admin') as ev_admin
  from public.places p join d on d.id = p.id order by p.safety_level, p.name;

commit;
