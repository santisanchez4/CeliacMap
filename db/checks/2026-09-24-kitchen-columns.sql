-- Verificación de la migración de columnas de cocina. Se corre DESPUÉS de aplicarla;
-- todo queda dentro de una transacción que termina en ROLLBACK (no deja filas).
-- Uso: node_modules/.bin/supabase db query --linked --file db/checks/2026-09-24-kitchen-columns.sql
-- Resultado esperado: termina sin error. Cualquier `expected ...` en un mensaje = FALLA.
begin;

-- 1) Filas válidas.
insert into public.suggestions (name, address, city, country, kitchen_exclusive, celiac_prep, owner_celiac)
values ('__chk_ok_1', 'Calle 1', 'Montevideo', 'Uruguay', false, 'separate_kitchen', true);
insert into public.suggestions (name, address, city, country, kitchen_exclusive, owner_celiac)
values ('__chk_ok_2', 'Calle 1', 'Montevideo', 'Uruguay', true, false);
insert into public.suggestions (name, address, city, country)
values ('__chk_ok_3', 'Calle 1', 'Montevideo', 'Uruguay');
insert into public.place_reports (place_name_text, report_type, description, kitchen_exclusive, celiac_prep)
values ('__chk_ok_4', 'positive', 'descripcion valida', false, 'shared_kitchen');

-- 2) Cada una de estas inserciones DEBE violar un CHECK.
do $$
begin
  begin
    insert into public.suggestions (name, address, city, country, kitchen_exclusive, celiac_prep)
    values ('__chk_bad_1', 'Calle 1', 'Montevideo', 'Uruguay', true, 'separate_kitchen');
    raise exception 'expected check violation: celiac_prep with kitchen_exclusive = true (suggestions)';
  exception when check_violation then null; end;

  begin
    insert into public.suggestions (name, address, city, country, celiac_prep)
    values ('__chk_bad_2', 'Calle 1', 'Montevideo', 'Uruguay', 'separate_kitchen');
    raise exception 'expected check violation: celiac_prep with kitchen_exclusive null (suggestions)';
  exception when check_violation then null; end;

  begin
    insert into public.suggestions (name, address, city, country, kitchen_exclusive, celiac_prep)
    values ('__chk_bad_3', 'Calle 1', 'Montevideo', 'Uruguay', false, 'hackeado');
    raise exception 'expected check violation: unknown celiac_prep value (suggestions)';
  exception when check_violation then null; end;

  begin
    insert into public.place_reports (place_name_text, report_type, description, kitchen_exclusive)
    values ('__chk_bad_4', 'negative', 'descripcion valida', true);
    raise exception 'expected check violation: kitchen data on a negative report';
  exception when check_violation then null; end;

  begin
    insert into public.place_reports (place_name_text, report_type, description, kitchen_exclusive, celiac_prep)
    values ('__chk_bad_5', 'positive', 'descripcion valida', true, 'separate_prep');
    raise exception 'expected check violation: celiac_prep with kitchen_exclusive = true (place_reports)';
  exception when check_violation then null; end;
end $$;

-- 3) El público (anon) sigue pudiendo insertar (los GRANT de tabla cubren las columnas nuevas).
set local role anon;
insert into public.place_reports (place_name_text, report_type, description, kitchen_exclusive, owner_celiac)
values ('__chk_anon', 'positive', 'descripcion valida', true, true);
reset role;

rollback;
