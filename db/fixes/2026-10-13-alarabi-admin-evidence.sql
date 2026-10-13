-- Alárabi Cocina Inclusiva (09713c52...): the admin's own review of 2026-10-13, stored as evidence, plus its official account.
-- Step 1 of 2. This file does NOT approve anything: status, safety_level, validation_notes, validation_confidence and verified stay
-- as they are. The approval is the next, visible step (APROBACIÓN MANUAL header, earlier notes kept below):
--   bash db/fixes/2026-10-13-alarabi-manual-approval.sh --apply
--
-- Run:      node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-13-alarabi-admin-evidence.sql
-- Dry run:  the same statements with the final `commit;` replaced by `rollback;`.

begin;

create temp table _snap on commit drop as
select id, md5(to_jsonb(p)::text) as h, md5((to_jsonb(p) - 'social_url' - 'updated_at')::text) as h_rest
  from public.places p;
create temp table _ev on commit drop as select count(*) as total from public.place_evidence;

do $$
declare n int;
begin
  select count(*) into n from public.places
   where id = '09713c52-85d5-41ab-b746-6c1440996a48' and name = 'Alárabi Cocina Inclusiva'
     and status = 'needs_review' and social_url is null and validation_confidence = 0.82
     and validation_notes like 'OVERRIDE MANUAL (2026-10-13, Santiago Sánchez):%';
  if n <> 1 then raise exception 'guard: Alárabi is not in the expected state (needs_review, today''s override on top, no social_url)'; end if;

  select count(*) into n from public.place_evidence where place_id = '09713c52-85d5-41ab-b746-6c1440996a48';
  if n <> 1 then raise exception 'guard: expected 1 evidence row for Alárabi (the blog quote), found %', n; end if;
end $$;

update public.places
   set social_url = 'https://www.instagram.com/alarabi__glutenfree/'
 where id = '09713c52-85d5-41ab-b746-6c1440996a48' and status = 'needs_review' and social_url is null;

insert into public.place_evidence (place_id, source, text, url) values
  ('09713c52-85d5-41ab-b746-6c1440996a48'::uuid, 'admin',
   $t$Revisión manual del admin (Santiago Sánchez, 2026-10-13). Instagram @alarabi__glutenfree, bio: «Alarabi | Disfrutá sin preocupaciones 🌾 - Restaurante - Lunes a Domingo - Montevideo, Uruguay - Zona Cordón, Colonia 1779».$t$,
   'https://www.instagram.com/alarabi__glutenfree/'),
  ('09713c52-85d5-41ab-b746-6c1440996a48'::uuid, 'admin',
   $t$Carta online del local, referencia aportada por el admin (Santiago Sánchez, 2026-10-13).$t$,
   'https://alarabi.habitueonline.com/menu');

do $$
declare n int;
begin
  select count(*) into n from public.places p join _snap s using (id) where md5(to_jsonb(p)::text) <> s.h;
  if n <> 1 then raise exception 'expected exactly 1 row changed, found %', n; end if;
  select count(*) into n from public.places p join _snap s using (id)
   where p.id = '09713c52-85d5-41ab-b746-6c1440996a48' and md5((to_jsonb(p) - 'social_url' - 'updated_at')::text) = s.h_rest
     and p.social_url = 'https://www.instagram.com/alarabi__glutenfree/' and p.status = 'needs_review';
  if n <> 1 then raise exception 'Alárabi is not as intended (only social_url changed, still needs_review)'; end if;
  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'places row count changed'; end if;
  if (select count(*) from public.place_evidence) <> (select total from _ev) + 2 then raise exception 'expected exactly two new evidence rows'; end if;
end $$;

commit;
