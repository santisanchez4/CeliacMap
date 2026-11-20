-- APLICADO en producción el 2026-11-20 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura): 15 filas admin en place_evidence; 42 de los 58 lugares en 100% con cita guardada.
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-20 · Las citas del propio local que ya estaban transcriptas en las notas pasan a place_evidence (filas admin).
-- Decisión del administrador (2026-11-20). Quince lugares en 100% por revisión manual (2026-09-27 a 2026-10-06), de
-- antes de que review_queue guardara la fila admin (desde el 2026-10-13): Goût ×11 (Instagram oficial de la cadena),
-- TACCOFF, Alimentos NutriCiencia, ChocAra y RecoBeco (sitio propio). El texto es la cita literal que ya figura en
-- validation_notes, con la fecha de esa revisión y su URL. Una guarda exige que cada cita esté, tal cual, en la nota.
-- No cambia ningún lugar (places queda igual).
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-11-20-citas-admin-en-place-evidence.sql
begin;

create temp table c (place_id uuid primary key, fecha date not null, fuente text not null, cita text not null,
                     url text not null) on commit drop;
insert into c values
('96367d15-2f6e-4f0a-ac2c-0019615189ae', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- GOUT CAFE GLUTEN FREE · Buenos Aires
('a93fdbd6-49d2-4eb2-bd52-44fbe6086829', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- GOUT GLUTEN FREE · Buenos Aires
('e4f4f299-05e3-4ee2-82df-78e18e228fc9', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- GOUT GLUTEN FREE BELGRANO · Buenos Aires
('f48ede75-aa4c-4a7e-948e-77c38b3d186d', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- GOUT Gluten Free Palermo · Buenos Aires
('0ad32fd2-75f9-4d13-9bb2-d9db78d8fd06', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- GOUT GLUTEN FREE BARRACAS · CABA
('4d843d7a-d6ed-4856-ba23-9c197775a471', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- Goût Gluten Free Pilar
('93ad145b-6713-4536-9561-24047e9c44da', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- Gout Gluten Free Alto Rosario
('2746bc7e-03f2-400a-bece-1a7770f45f97', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- Goût Gluten Free Monumento · Rosario
('37c9c336-b0f4-4e16-9a14-76cd56d64a26', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- Goût Gluten Free Rosario Italia
('83da9b31-9414-4457-83d3-25a57fc9ce68', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- Gout Cafe Gluten Free Nordelta · Tigre
('f6594a62-a387-44d5-b468-574782851418', '2026-10-06', 'el Instagram oficial de la cadena (@goutglutenfree)', 'Todo 100% gluten free, todo Goût.', 'https://www.instagram.com/goutglutenfree/'),  -- GOUT CAFE GLUTEN FREE · Vicente López
('0ae93217-7bbe-4d54-b971-8c1a221d02fd', '2026-10-06', 'su sitio propio (taccoff.com.ar)', '¡Todo lo que hacemos es 100% Gluten Free y está pensado para vos!', 'https://www.taccoff.com.ar/'),  -- TACCOFF
('7f145df1-b613-470b-8748-b5ee19d383ad', '2026-10-01', 'su sitio propio (cerogluten.uy)', 'Primera empresa Uruguaya de dedicación exclusiva a alimentos certificados Aptos para Celíacos', 'https://cerogluten.uy/'),  -- Alimentos NutriCiencia
('1becc778-212c-49ac-b2de-7e6417265385', '2026-10-01', 'su sitio propio (chocara.com)', 'Nuestra cocina es 100% libre de gluten', 'https://chocara.com/'),  -- ChocAra
('6967a6a5-abc4-4066-99c2-a92638b913a4', '2026-09-27', 'su sitio propio (recobeco.com.uy)', 'Elaboramos nuestros productos en una cocina 100 % libre de gluten, con atención a cada detalle.', 'http://www.recobeco.com.uy/');  -- RecoBeco

create temp table b on commit drop as
  select (select count(*) from public.place_evidence) as evidence,
         (select count(*) from public.place_evidence where source = 'admin') as admin_rows,
         (select max(updated_at) from public.places) as places_last_update;

do $$
begin
  if (select count(*) from c) <> 15 then raise exception 'guarda: la lista no tiene 15 filas'; end if;
  if (select count(*) from public.places p join c on c.place_id = p.id
        where p.status = 'approved' and p.safety_level = 'gluten_free_100'
          and position(c.cita in p.validation_notes) > 0
          and position(to_char(c.fecha, 'YYYY-MM-DD') in p.validation_notes) > 0
          and not exists (select 1 from public.place_evidence e where e.place_id = p.id and e.source = 'admin')) <> 15 then
    raise exception 'guarda: los 15 lugares no están como se leyeron (o la cita no está tal cual en la nota)';
  end if;
end $$;

insert into public.place_evidence (place_id, source, text, url)
select c.place_id, 'admin',
       'Revisión manual (' || to_char(c.fecha, 'YYYY-MM-DD') || ', Santiago Sánchez): el administrador revisó '
         || c.fuente || '. Cita: «' || c.cita || '». Guardada en place_evidence el 2026-11-20 desde la nota de esa revisión.',
       c.url
  from c;

do $$
begin
  if (select count(*) from public.place_evidence) - (select evidence from b) <> 15
     or (select count(*) from public.place_evidence where source = 'admin') - (select admin_rows from b) <> 15
     or (select count(*) from public.place_evidence e join c on c.place_id = e.place_id and e.source = 'admin') <> 15
     or (select max(updated_at) from public.places) is distinct from (select places_last_update from b) then
    raise exception 'guarda: no se insertaron exactamente 15 filas admin, o cambió un lugar';
  end if;
end $$;

select p.name, p.city, e.text, e.url
  from public.place_evidence e join public.places p on p.id = e.place_id join c on c.place_id = e.place_id
 where e.source = 'admin' order by p.name;

commit;
