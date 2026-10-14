-- IM Montevideo source (2026-10-13): evidence rows for four existing places. Only place_evidence is written; `places` is not touched.
--
--   * Cooperativa Helix, Ferniland and Me Gusta: the IM licence (source "IM Montevideo - Locales_Gluten_Free", capture and expiry dates) and the
--     admin's own review of 2026-10-13 with its literal quotes. The approval itself is a separate, visible step:
--     `scripts/review_queue.py --approve <id> --level 100 --note ... --apply` (APROBACIÓN MANUAL header, earlier note kept below).
--   * Casa & Dispensa (Solano García 2496, approved by manual override on 2026-09-07): the IM licence of that address is registered
--     under its former name, "GOÛT GLUTEN FREE" (expired 30/11/2025). Complementary evidence only: status and level stay as they are.
--
-- Run (one transaction; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-10-13-imm-admin-evidence.sql

begin;

create temp table _snap on commit drop as
select id, md5(to_jsonb(p)::text) as h from public.places p;

do $$
declare n int;
begin
  select count(*) into n from public.places where id = '1e21c93a-0030-4c99-8ef1-eab8d487130f' and name = $t$Casa & Dispensa$t$;
  if n <> 1 then raise exception 'guard: 1e21c93a is not the expected place'; end if;
  select count(*) into n from public.places where id = '61fa7e8b-3366-4724-b09c-fb7150e35653' and name = $t$FERNILAND S.A.$t$;
  if n <> 1 then raise exception 'guard: 61fa7e8b is not the expected place'; end if;
  select count(*) into n from public.places where id = '7362c23b-b02d-4930-9dba-8e00a9fc6bf6' and name = $t$Cooperativa de Trabajo Helix Uruguay$t$;
  if n <> 1 then raise exception 'guard: 7362c23b is not the expected place'; end if;
  select count(*) into n from public.places where id = 'dbc2db5e-3078-44a3-9e03-f0cbcf19d07d' and name = $t$Me Gusta$t$;
  if n <> 1 then raise exception 'guard: dbc2db5e is not the expected place'; end if;
  select count(*) into n from public.place_evidence
   where place_id in ('1e21c93a-0030-4c99-8ef1-eab8d487130f', '61fa7e8b-3366-4724-b09c-fb7150e35653', '7362c23b-b02d-4930-9dba-8e00a9fc6bf6', 'dbc2db5e-3078-44a3-9e03-f0cbcf19d07d');
  if n <> 0 then raise exception 'guard: these places already have evidence rows (%), review before inserting', n; end if;
end $$;

insert into public.place_evidence (place_id, source, text, url) values
  ('7362c23b-b02d-4930-9dba-8e00a9fc6bf6'::uuid, 'admin', $t$Fuente: IM Montevideo - Locales_Gluten_Free (Servicio de Regulación Alimentaria, capturada 2026-10-13). Registro: HELIX, JOFFRE Nº: 1005. Habilitación 28/05/2019 a 28/05/2024 (figura vencida en la fuente). Rubro Elab. Giros: Elaboración de productos de rotiseria congelados- Panificadora- Libre de gluten- Elaboración de productos de rotiseria$t$, null),
  ('7362c23b-b02d-4930-9dba-8e00a9fc6bf6'::uuid, 'admin', $t$Revisión manual del admin (Santiago Sánchez, 2026-10-13). Revisó redes y web del local. Sitio https://www.cooperativahelix.com.uy/index.html y WhatsApp 092 410 428.$t$, $t$https://www.cooperativahelix.com.uy/index.html$t$),
  ('61fa7e8b-3366-4724-b09c-fb7150e35653'::uuid, 'admin', $t$Fuente: IM Montevideo - Locales_Gluten_Free (Servicio de Regulación Alimentaria, capturada 2026-10-13). Registro: FERNILAND, COCHABAMBA Nº: 2949. Habilitación 21/10/2022 a 21/10/2027 (vigente). Rubro Elab. Giros: Libre de gluten- Elaboración de productos de rotiseria- Fraccionamiento de alimentos en general- Importador- Depósito$t$, null),
  ('61fa7e8b-3366-4724-b09c-fb7150e35653'::uuid, 'admin', $t$Revisión manual del admin (Santiago Sánchez, 2026-10-13). Instagram @fernilanduy, bio: "Somos una empresa dedicada a alimentos sin gluten. Industria Uruguaya. Aptos celiacos. Aptos Veganos". Tel 092921922. Sitio www.ferniland.com.uy.$t$, $t$https://www.instagram.com/fernilanduy$t$),
  ('dbc2db5e-3078-44a3-9e03-f0cbcf19d07d'::uuid, 'admin', $t$Fuente: IM Montevideo - Locales_Gluten_Free (Servicio de Regulación Alimentaria, capturada 2026-10-13). Registro: ME GUSTA, CARLOS ROXLO Nº: 1374. Habilitación 04/08/2023 a 04/08/2028 (vigente). Rubro Exp-elab. Giros: Elaborador y fraccionador de alimentos libres de gluten- Libre de gluten$t$, null),
  ('dbc2db5e-3078-44a3-9e03-f0cbcf19d07d'::uuid, 'admin', $t$Revisión manual del admin (Santiago Sánchez, 2026-10-13). Instagram @megusta_uy, bio: "Restaurante - Comida Saludable GLUTEN FREE - Productos congelados - Servicio de catering". Tel +598 2402 77 54 y +598 092056917.$t$, $t$https://www.instagram.com/megusta_uy$t$),
  ('1e21c93a-0030-4c99-8ef1-eab8d487130f'::uuid, 'admin', $t$Fuente: IM Montevideo - Locales_Gluten_Free (Servicio de Regulación Alimentaria, capturada 2026-10-13). Registro: GOÛT GLUTEN FREE, SOLANO GARCIA Nº: 2496 (nombre anterior del local de esta dirección, según la revisión manual del 2026-09-07). Habilitación 30/11/2020 a 30/11/2025 (figura vencida en la fuente). Rubro Exp-elab. Giros: Libre de gluten- Reposteria$t$, null);

do $$
declare n int;
begin
  select count(*) into n from public.place_evidence
   where place_id in ('1e21c93a-0030-4c99-8ef1-eab8d487130f', '61fa7e8b-3366-4724-b09c-fb7150e35653', '7362c23b-b02d-4930-9dba-8e00a9fc6bf6', 'dbc2db5e-3078-44a3-9e03-f0cbcf19d07d') and source = 'admin';
  if n <> 7 then raise exception 'expected 7 evidence rows, found %', n; end if;
  select count(*) into n from public.places p join _snap s using (id) where md5(to_jsonb(p)::text) <> s.h;
  if n <> 0 then raise exception 'places changed (% rows): this script must not touch it', n; end if;
  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'places row count changed'; end if;
end $$;

commit;
