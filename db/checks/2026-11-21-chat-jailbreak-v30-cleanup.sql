-- APLICADO en producción el 2026-11-21 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de
-- solo lectura): línea base recuperada. Registro de auditoría: no se vuelve a correr.
-- Limpieza de la batería de jailbreak contra chat v30 (2026-11-21 20:44:15–20:47:28 UTC, 37 turnos, sesiones
-- celiac-test-v13-*, db/checks/2026-11-21-chat-jailbreak-v30.json). Veredicto: 37/37 se sostuvieron, 0 rupturas.
-- Línea base antes de la batería (20:43:30 UTC): 3 filas chatbot en agent_log, 3 filas chat_usage (todas del 2026-11-20,
-- count 3), 2 suggestions, 2 place_reports.
-- La batería escribió: 37 filas chatbot en agent_log; en chat_usage del 2026-11-21, 12 contadores de sesión (suman 37), el
-- de IP (37) y el global (37); y 1 place_report (turno #37, Módulo 4, place_id null). No 4: el #36 quedó en borrador y el #14
-- cayó en fuera_de_alcance. Ninguna otra fila de agent_log ni corrida de place-report-review.
-- Cada delete tiene guarda de conteo exacto: si algo no coincide, se aborta y no se borra nada.
-- Ensayo: termina en ROLLBACK. La versión que se aplica cambia solo la última línea por COMMIT.
--   node_modules/.bin/supabase db query --linked --file db/checks/2026-11-21-chat-jailbreak-v30-cleanup.sql
begin;

do $$
declare n int; s int;
begin
  select count(*), coalesce(sum(count), 0) into n, s from public.chat_usage
   where day = '2026-11-21' and bucket_key like 'session:celiac-test-v13-%';
  if n <> 12 or s <> 37 then raise exception 'sesiones: se esperaban 12 filas que suman 37, hay % que suman %', n, s; end if;
  delete from public.chat_usage where day = '2026-11-21' and bucket_key like 'session:celiac-test-v13-%';
  get diagnostics n = row_count;
  if n <> 12 then raise exception 'sesiones: se borraron % filas', n; end if;

  delete from public.chat_usage
   where day = '2026-11-21' and bucket_key = 'ip:1e57aca43d0d3e0dd5b5439cf94eed601dd17457914b3e3a2d49c8c11f8009ef' and count = 37;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'bucket de IP: se esperaba 1 fila con count 37, hubo %', n; end if;

  delete from public.chat_usage where day = '2026-11-21' and bucket_key = 'global' and count = 37;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'global: se esperaba 1 fila con count 37, hubo %', n; end if;

  delete from public.agent_log
   where agent = 'chatbot' and action = 'chat_turn'
     and created_at between '2026-11-21 20:44:00+00' and '2026-11-21 20:48:00+00';
  get diagnostics n = row_count;
  if n <> 37 then raise exception 'agent_log: se esperaban 37 filas, hubo %', n; end if;

  delete from public.place_reports
   where id = '8c6e09cd-9950-47f8-8daf-2252137bad39' and place_id is null and report_type = 'positive'
     and created_at between '2026-11-21 20:47:00+00' and '2026-11-21 20:48:00+00';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'place_reports: se esperaba 1 fila, hubo %', n; end if;

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
