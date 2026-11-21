-- APLICADO en producción el 2026-11-21 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de
-- solo lectura): línea base recuperada. Registro de auditoría: no se vuelve a correr.
-- Limpieza de los 5 turnos de prueba de chat v29 (2026-11-21 20:01:32–20:01:55 UTC, sesión
-- celiac-test-barrios-v29-20261121, db/checks/chat_barrios_live.py). Línea base antes de los turnos (20:00:32 UTC):
-- 3 filas chatbot en agent_log, 3 filas chat_usage (todas del 2026-11-20, count 3), 2 suggestions, 2 place_reports.
-- Cada delete tiene guarda: si el conteo no es el exacto (por ejemplo, tráfico real en el medio), se aborta y no se borra nada.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/checks/2026-11-21-chat-v29-test-cleanup.sql
begin;

do $$
declare n int;
begin
  delete from public.chat_usage
   where day = '2026-11-21' and bucket_key = 'session:celiac-test-barrios-v29-20261121' and count = 5;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'sesión de prueba: se esperaba 1 fila con count 5, hubo %', n; end if;

  delete from public.chat_usage
   where day = '2026-11-21' and bucket_key = 'ip:1e57aca43d0d3e0dd5b5439cf94eed601dd17457914b3e3a2d49c8c11f8009ef' and count = 5;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'bucket de IP: se esperaba 1 fila con count 5, hubo %', n; end if;

  delete from public.chat_usage where day = '2026-11-21' and bucket_key = 'global' and count = 5;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'global: se esperaba 1 fila con count 5, hubo %', n; end if;

  delete from public.agent_log
   where agent = 'chatbot' and action = 'chat_turn' and id in (
     '54e90be7-bd25-4867-83f0-60cb162f551d', 'b0a2434e-4216-456f-bd1e-4c1f3c90173a',
     '022eb554-748a-44c2-96b5-0f6eee26c35d', '272b293d-7ef8-4884-aa8f-7fd99485760b',
     'e97c3d97-cdf6-4bae-883e-b7c7edc9e787');
  get diagnostics n = row_count;
  if n <> 5 then raise exception 'agent_log: se esperaban 5 filas, hubo %', n; end if;

  if (select count(*) from public.agent_log where agent = 'chatbot') <> 3
     or (select count(*) from public.chat_usage) <> 3
     or (select count(*) from public.chat_usage where day <> '2026-11-20' or count <> 3) <> 0
     or (select count(*) from public.suggestions) <> 2
     or (select count(*) from public.place_reports) <> 2 then
    raise exception 'guarda: no se volvió a la línea base';
  end if;
end $$;

select (select count(*) from public.agent_log where agent = 'chatbot') as chat_log,
       (select count(*) from public.chat_usage) as chat_usage,
       (select count(*) from public.suggestions) as suggestions,
       (select count(*) from public.place_reports) as place_reports;

commit;
