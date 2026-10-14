-- Admin decisions (Santiago Sánchez, 2026-10-13) on four places approved in June 2026 under the old binary rubric, below today's 0.85
-- gate. Dry run of the current Validator, with its quotes: db/checks/2026-10-13-reevaluate-below-gate-dry-run.md.
--
--   1. Géant Fresh Market (9f9abf53...):        approved -> discarded. A supermarket chain, general retail: not a place of this map.
--   2. By Gessi Cocina Inclusiva (d6a3edb8...): approved -> discarded. A cooking school, no food or products sold to the public.
--   3. Alárabi Cocina Inclusiva (09713c52...):  approved -> needs_review, for the admin to verify himself. The note says what to
--      check. The two Google reviews are summarised, not quoted: review text is server-only and purged after 30 days (Google ToS),
--      and validation_notes is permanent. The blog quote is literal (checked on its page) and also goes to place_evidence.
--   4. gluteno Sana Ingesta (e3e6dd26...):      stays approved, same level. Only social_url is set, to the account its own site
--      (glutenouy.com) links to: http://instagram.com/glutenosanaingesta/ (read on 2026-10-13), stored in the usual form.
--
-- In every case the earlier Validator note stays below the new header, and validation_confidence / verified are not touched.
-- One transaction: it aborts if a row is not the expected one, is not approved, changed its confidence or carries a manual decision.
--
-- Run:      node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-13-below-gate-admin-decisions.sql
-- Dry run:  the same statements with the final `commit;` replaced by `rollback;`.

begin;

create temp table _snap on commit drop as
select id, md5(to_jsonb(p)::text) as h,
       md5((to_jsonb(p) - 'status' - 'validation_notes' - 'updated_at')::text) as h_decision,
       md5((to_jsonb(p) - 'social_url' - 'updated_at')::text) as h_social
  from public.places p;
create temp table _ev on commit drop as select count(*) as total from public.place_evidence;

-- 0. Guards.
do $$
declare n int;
begin
  select count(*) into n from public.places
   where status = 'approved'
     and coalesce(validation_notes, '') !~* '(override|aprobaci[oó]n manual|correcci[oó]n manual|revisi[oó]n manual)'
     and (   (id = '9f9abf53-67fa-44ad-9594-e42aa1959ecb' and name = 'Géant Fresh Market'        and validation_confidence = 0.7)
          or (id = 'd6a3edb8-b393-469f-ae93-6c105b951494' and name = 'By Gessi Cocina Inclusiva' and validation_confidence = 0.82)
          or (id = '09713c52-85d5-41ab-b746-6c1440996a48' and name = 'Alárabi Cocina Inclusiva'  and validation_confidence = 0.82)
          or (id = 'e3e6dd26-2b4b-49b9-885e-ab56d0cfdf56' and name = 'gluteno Sana Ingesta'      and validation_confidence = 0.72
              and social_url is null));
  if n <> 4 then raise exception 'guard: expected the 4 rows approved, unchanged and without a manual decision; found %', n; end if;

  select count(*) into n from public.place_evidence where place_id = '09713c52-85d5-41ab-b746-6c1440996a48';
  if n <> 0 then raise exception 'guard: Alárabi already has evidence rows (%)', n; end if;
end $$;

-- 1. Géant Fresh Market: discarded.
update public.places
   set status = 'discarded',
       validation_notes = concat_ws(E'\n\n',
         'CORRECCIÓN MANUAL 2026-10-13: no aplica al mapa: cadena de supermercados, comercio general; descartado por decisión del admin.',
         nullif(validation_notes, ''))
 where id = '9f9abf53-67fa-44ad-9594-e42aa1959ecb' and status = 'approved';

-- 2. By Gessi Cocina Inclusiva: discarded.
update public.places
   set status = 'discarded',
       validation_notes = concat_ws(E'\n\n',
         'CORRECCIÓN MANUAL 2026-10-13: no es un comercio: escuela de cocina de productos aptos para celíacos, sin venta de comida ni productos al público; no corresponde a este mapa; descartado por decisión del admin.',
         nullif(validation_notes, ''))
 where id = 'd6a3edb8-b393-469f-ae93-6c105b951494' and status = 'approved';

-- 3. Alárabi Cocina Inclusiva: needs_review, with what the admin has to verify.
update public.places
   set status = 'needs_review',
       validation_notes = concat_ws(E'\n\n',
         'OVERRIDE MANUAL (2026-10-13, Santiago Sánchez): bajado de approved a needs_review por decisión del admin, para verificarlo él mismo. '
         || 'El Validator lo había aprobado el 2026-06-04 con el rubric binario anterior (0.82, celiac_friendly), solo por el nombre; en el dry-run del 2026-10-13 con el rubric vigente dio needs_review 0.52 en 3 de 3 corridas. '
         || 'A verificar: (1) En su ficha de Google hay dos reseñas con mención de gluten, las dos negativas (leídas el 2026-10-13; su texto no se guarda): una dice que no recomienda la comida para celíacos y que la elaboración le parece peligrosa para quien es sensible al gluten; la otra supone que la comida está contaminada y cuenta que recibió un producto distinto del pedido. '
         || '(2) A favor, un blog de viajes: «El otro restaurante al que fuimos, es el restaurante Alárabi, Cocina Inclusiva, que es 100% sin gluten y que cuenta con variedad opciones para comer.» (https://pajaritosviajeros.com/america/viaje-sin-gluten-uruguay). '
         || '(3) Figura en IM Montevideo - Locales_Gluten_Free con la habilitación vencida el 30/11/2025.',
         nullif(validation_notes, ''))
 where id = '09713c52-85d5-41ab-b746-6c1440996a48' and status = 'approved';

insert into public.place_evidence (place_id, source, text, url) values
  ('09713c52-85d5-41ab-b746-6c1440996a48'::uuid, 'web',
   $t$El otro restaurante al que fuimos, es el restaurante Alárabi, Cocina Inclusiva, que es 100% sin gluten y que cuenta con variedad opciones para comer.$t$,
   'https://pajaritosviajeros.com/america/viaje-sin-gluten-uruguay');

-- 4. gluteno Sana Ingesta: only its official account.
update public.places
   set social_url = 'https://www.instagram.com/glutenosanaingesta'
 where id = 'e3e6dd26-2b4b-49b9-885e-ab56d0cfdf56' and status = 'approved' and social_url is null;

-- 5. Assertions: any drift RAISES and rolls everything back.
do $$
declare n int;
begin
  select count(*) into n from public.places p join _snap s using (id) where md5(to_jsonb(p)::text) <> s.h;
  if n <> 4 then raise exception 'expected exactly 4 rows changed, found %', n; end if;

  -- the three decisions: only status, validation_notes (and updated_at) changed; confidence, verified, level, flags... are intact
  select count(*) into n from public.places p join _snap s using (id)
   where md5((to_jsonb(p) - 'status' - 'validation_notes' - 'updated_at')::text) = s.h_decision
     and (   (p.id = '9f9abf53-67fa-44ad-9594-e42aa1959ecb' and p.status = 'discarded'
              and p.validation_notes like 'CORRECCIÓN MANUAL 2026-10-13: no aplica al mapa:%' || E'\n\n' || 'Géant Fresh Market is a large supermarket chain%')
          or (p.id = 'd6a3edb8-b393-469f-ae93-6c105b951494' and p.status = 'discarded'
              and p.validation_notes like 'CORRECCIÓN MANUAL 2026-10-13: no es un comercio:%' || E'\n\n' || 'The term ''Cocina Inclusiva''%')
          or (p.id = '09713c52-85d5-41ab-b746-6c1440996a48' and p.status = 'needs_review'
              and p.validation_notes like 'OVERRIDE MANUAL (2026-10-13, Santiago Sánchez):%' || E'\n\n' || 'The name ''Cocina Inclusiva''%'));
  if n <> 3 then raise exception 'the three decisions are not as intended (status, header, earlier note below, nothing else); ok = %', n; end if;

  -- gluteno: only social_url (and updated_at) changed; still approved, same level
  select count(*) into n from public.places p join _snap s using (id)
   where p.id = 'e3e6dd26-2b4b-49b9-885e-ab56d0cfdf56' and md5((to_jsonb(p) - 'social_url' - 'updated_at')::text) = s.h_social
     and p.status = 'approved' and p.safety_level = 'celiac_friendly' and p.social_url = 'https://www.instagram.com/glutenosanaingesta';
  if n <> 1 then raise exception 'gluteno Sana Ingesta is not as intended (only social_url changed, still approved)'; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'places row count changed'; end if;
  if (select count(*) from public.place_evidence) <> (select total from _ev) + 1 then raise exception 'expected exactly one new evidence row'; end if;
end $$;

commit;
