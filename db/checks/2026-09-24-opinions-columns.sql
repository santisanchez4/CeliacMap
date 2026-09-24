-- Verificación de la migración de opiniones de la comunidad. Se corre DESPUÉS de aplicarla;
-- todo queda dentro de una transacción que termina en ROLLBACK (no deja filas).
-- Uso: node_modules/.bin/supabase db query --linked --file db/checks/2026-09-24-opinions-columns.sql
-- Resultado esperado: termina sin error. Cualquier `expected ...` en un mensaje = FALLA.
begin;

-- Como dueño (postgres): estructura, CHECKs y qué muestra la vista.
do $$
declare
  ok_place  uuid;
  bad_place uuid;
  r_pub     uuid;
  n         int;
  cols      text;
begin
  select id into ok_place  from public.places where status = 'approved'  limit 1;
  select id into bad_place from public.places where status <> 'approved' limit 1;
  if ok_place is null or bad_place is null then
    raise exception 'need one approved and one non-approved place to run this check';
  end if;

  -- 1) una positiva publicada de un lugar aprobado aparece en la vista
  insert into public.place_reports (place_id, report_type, description, author_name, published_at)
  values (ok_place, 'positive', '__chk_opinion_1', 'Prueba', now()) returning id into r_pub;
  select count(*) into n from public.community_opinions where id = r_pub;
  if n <> 1 then raise exception 'expected the published positive report in the view'; end if;

  -- 2) sin publicar, no aparece
  insert into public.place_reports (place_id, report_type, description)
  values (ok_place, 'positive', '__chk_opinion_2');
  select count(*) into n from public.community_opinions where description = '__chk_opinion_2';
  if n <> 0 then raise exception 'expected an unpublished report to stay out of the view'; end if;

  -- 3) publicada, pero el lugar NO está aprobado -> no aparece
  insert into public.place_reports (place_id, report_type, description, published_at)
  values (bad_place, 'positive', '__chk_opinion_3', now());
  select count(*) into n from public.community_opinions where description = '__chk_opinion_3';
  if n <> 0 then raise exception 'expected a non-approved place to hide its opinion'; end if;

  -- 4) un lugar que deja de estar aprobado se lleva su opinión
  update public.places set status = 'needs_review' where id = ok_place;
  select count(*) into n from public.community_opinions where id = r_pub;
  if n <> 0 then raise exception 'expected the opinion to vanish when its place stops being approved'; end if;
  update public.places set status = 'approved' where id = ok_place;

  -- 5) columnas exactas de la vista
  select string_agg(column_name, ',' order by column_name) into cols
  from information_schema.columns where table_schema = 'public' and table_name = 'community_opinions';
  if cols <> 'author_name,city,country,description,id,place_id,place_name,published_at' then
    raise exception 'expected the public view columns, got %', cols;
  end if;

  -- 6) violaciones de CHECK
  begin
    insert into public.place_reports (place_id, report_type, description, published_at)
    values (ok_place, 'negative', '__chk_bad_1', now());
    raise exception 'expected check violation: a negative report cannot be published';
  exception when check_violation then null; end;

  begin
    insert into public.place_reports (place_id, report_type, description, author_name)
    values (ok_place, 'positive', '__chk_bad_2', '   ');
    raise exception 'expected check violation: a name of only spaces';
  exception when check_violation then null; end;

  begin
    insert into public.place_reports (place_id, report_type, description, author_name)
    values (ok_place, 'positive', '__chk_bad_3', repeat('x', 41));
    raise exception 'expected check violation: a name longer than 40';
  exception when check_violation then null; end;
end $$;

-- Como anónimo (la clave pública): no se puede auto-publicar, se puede escribir, la tabla sigue cerrada.
do $$
declare
  ok_place uuid;
  n        int;
begin
  select id into ok_place from public.places where status = 'approved' limit 1;
  set local role anon;

  begin
    insert into public.place_reports (place_id, report_type, description, published_at)
    values (ok_place, 'positive', '__chk_anon_1', now());
    raise exception 'expected RLS rejection: anon inserting an already published row';
  exception when insufficient_privilege then null; end;

  insert into public.place_reports (place_id, report_type, description, author_name)
  values (ok_place, 'positive', '__chk_anon_2', 'Ana');

  begin
    perform 1 from public.place_reports limit 1;
    raise exception 'expected permission denied: anon reading place_reports';
  exception when insufficient_privilege then null; end;

  select count(*) into n from public.community_opinions where description = '__chk_opinion_1';
  if n <> 1 then raise exception 'expected anon to read the published opinion through the view'; end if;
  select count(*) into n from public.community_opinions where description = '__chk_anon_2';
  if n <> 0 then raise exception 'expected anon to NOT see an unpublished opinion'; end if;

  reset role;
end $$;

rollback;
