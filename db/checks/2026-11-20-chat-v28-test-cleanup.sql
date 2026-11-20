-- Limpieza del turno de prueba de chat v28 (2026-11-20 22:28:40–22:28:48 UTC: una búsqueda «¿Dónde puedo comer sin
-- gluten en Montevideo?», sesión celiac-test-deploy-v28-20261120). Línea base antes del turno (22:28:00 UTC): 0 filas
-- chatbot en agent_log, chat_usage vacía, 2 suggestions, 2 place_reports. Cada delete tiene guarda: si el conteo no es
-- el exacto (por ejemplo, tráfico real en el medio), se aborta y no se borra nada.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/checks/2026-11-20-chat-v28-test-cleanup.sql
begin;

do $$
declare n int;
begin
  delete from public.chat_usage
   where day = '2026-11-20' and bucket_key = 'session:celiac-test-deploy-v28-20261120' and count = 1;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'sesión de prueba: se esperaba 1 fila con count 1, hubo %', n; end if;

  delete from public.chat_usage where day = '2026-11-20' and bucket_key like 'ip:ddb7a461e%' and count = 1;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'bucket de IP: se esperaba 1 fila con count 1, hubo %', n; end if;

  delete from public.chat_usage where day = '2026-11-20' and bucket_key = 'global' and count = 1;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'global: se esperaba 1 fila con count 1, hubo %', n; end if;

  delete from public.agent_log
   where agent = 'chatbot' and action = 'chat_turn' and id = '97b5f58c-f92a-4126-88ce-5b3c6a276b73';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'agent_log: se esperaba 1 fila, hubo %', n; end if;

  if (select count(*) from public.agent_log where agent = 'chatbot') <> 0
     or (select count(*) from public.chat_usage) <> 0
     or (select count(*) from public.suggestions) <> 2
     or (select count(*) from public.place_reports) <> 2 then
    raise exception 'guarda: no se volvió a la línea base';
  end if;
end $$;

rollback;
