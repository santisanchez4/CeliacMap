-- APLICADO en producción el 2026-11-21 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de
-- solo lectura): línea base recuperada. Registro de auditoría: no se vuelve a correr.
-- Limpieza de los 2 turnos en vivo de chat v30 (2026-11-21 20:49:47–20:49:57 UTC, sesión celiac-test-tanda-v30-20261121,
-- db/checks/2026-11-21-chat-v30-live-run.json), después de limpiar la batería. Línea base: 3 filas chatbot en agent_log,
-- 3 filas chat_usage (todas del 2026-11-20, count 3), 2 suggestions, 2 place_reports.
-- Los turnos escribieron 2 filas chatbot en agent_log y 3 contadores del 2026-11-21 (sesión, IP y global, cada uno en 2).
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/checks/2026-11-21-chat-v30-live-cleanup.sql
begin;

do $$
declare n int;
begin
  delete from public.chat_usage
   where day = '2026-11-21' and bucket_key = 'session:celiac-test-tanda-v30-20261121' and count = 2;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'sesión de prueba: se esperaba 1 fila con count 2, hubo %', n; end if;

  delete from public.chat_usage
   where day = '2026-11-21' and bucket_key = 'ip:1e57aca43d0d3e0dd5b5439cf94eed601dd17457914b3e3a2d49c8c11f8009ef' and count = 2;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'bucket de IP: se esperaba 1 fila con count 2, hubo %', n; end if;

  delete from public.chat_usage where day = '2026-11-21' and bucket_key = 'global' and count = 2;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'global: se esperaba 1 fila con count 2, hubo %', n; end if;

  delete from public.agent_log
   where agent = 'chatbot' and action = 'chat_turn'
     and id in ('a1ad7052-6b16-48b6-9215-fd0ca8ca66fb', '2894f2e2-780e-4743-84ec-ed05db9b69ef');
  get diagnostics n = row_count;
  if n <> 2 then raise exception 'agent_log: se esperaban 2 filas, hubo %', n; end if;

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
