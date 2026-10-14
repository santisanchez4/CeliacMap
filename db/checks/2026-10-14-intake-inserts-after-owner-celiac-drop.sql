-- After the owner_celiac drop (2026-10-14): do the three intake writers still insert? Ends in ROLLBACK: nothing stays.
-- Runs as the anon role, under the same RLS and grants as the browser forms and the chat (both write with the anon key).
-- The place_reports webhook (place-report-created) goes through pg_net, whose queue is transactional: a rolled-back insert
-- sends nothing.
--
--   node_modules/.bin/supabase db query --linked --file db/checks/2026-10-14-intake-inserts-after-owner-celiac-drop.sql

begin;

create temp table _before on commit drop as
select (select count(*) from public.suggestions) as suggestions, (select count(*) from public.place_reports) as place_reports;
grant select on _before to anon;

set local role anon;

-- 1. Form A (js/suggest.js): name, address, city, country, category, evidence_url, notes, origin + the kitchen answers (js/kitchen.js).
insert into public.suggestions (name, address, city, country, category, evidence_url, notes, origin, kitchen_exclusive, celiac_prep)
values ('PRUEBA ROLLBACK formulario', 'Calle de Prueba 123', 'Montevideo', 'Uruguay', 'cafe', null, 'fila de prueba, termina en rollback',
        'community', false, 'separate_prep');

-- 2. Form B (js/report.js): place_id, report_type, description, reporter_token (+ author_name on a positive report).
insert into public.place_reports (place_id, report_type, description, reporter_token, author_name)
values ('9dd64b4e-3e13-4d2d-88ea-931219dc5c2b', 'positive', 'fila de prueba del formulario, termina en rollback',
        'rollback-test-token-0001', 'Prueba');

-- 3. Chat, "recomendar un lugar" (buildSuggestionInsertPayload): the same columns as Form A, evidence_url null, origin community.
insert into public.suggestions (name, address, city, country, category, evidence_url, notes, origin, kitchen_exclusive)
values ('PRUEBA ROLLBACK chat', 'Avenida de Prueba 456', 'Fray Bentos', 'Uruguay', 'restaurant', null, 'fila de prueba del chat',
        'community', true);

-- 4. Chat, "reportar" (buildPlaceReportInsertPayload): place_id, place_name_text, report_type, description; no kitchen keys.
insert into public.place_reports (place_id, place_name_text, report_type, description)
values (null, 'Lugar de prueba del chat', 'negative', 'fila de prueba del chat, termina en rollback');

reset role;

do $$
begin
  if (select count(*) from public.suggestions) <> (select suggestions from _before) + 2
     or (select count(*) from public.place_reports) <> (select place_reports from _before) + 2
     then raise exception 'the four test rows were not all inserted'; end if;
end $$;

rollback;
