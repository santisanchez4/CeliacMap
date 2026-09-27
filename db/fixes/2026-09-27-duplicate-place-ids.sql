-- One-off cleanup — the same Google place twice (24 place_ids with two rows), 21 of them resolved here. 2026-09-27.
--
-- Found while checking whether a manual place anchored to a Google place_id was safe from the Search agent: it never looked the place_id up, and the unique
-- index is on (source, external_id), so a candidate of another source became a second row (docs/DECISIONS.md, "One Google place, one row"; fixed for the future
-- in insert_place_candidate). This script cleans the ones that already exist:
--   * 13 pairs with BOTH rows approved (the same business twice on the map): the google_places row stays, the social one is discarded;
--   *  8 pairs with another status combination that still leave two live rows: same rule, except "Sin gluten Rosana", where the approved row (the social one)
--      stays because it is the public one and its google_places twin is only needs_review. The 8: one approved + one needs_review (Rosana, Harvest Punta del
--      Este, Sin Gluten Olivos) and five needs_review + needs_review (Il Porto, Niter, Mercado Natural, CAMPOBRAVO, Amayta);
--   *  3 pairs that need nothing because one side is already discarded (they are not touched):
--   Antojos café (needs_review / discarded)
--   Cafe de la Mansa Zunino (discarded / needs_review)
--   Carabele (approved / discarded)
--
-- The row that stays is the one with more information (in all 21 pairs the google_places row has the same or more panel fields, is anchored to the Google
-- listing and is the one the Updater refreshes) or, where a status differs, the approved one. None of the 42 rows carries an OVERRIDE or an APROBACIÓN MANUAL;
-- four discarded rows (Celihaus, Donato, Yoda, Sin Gluten Olivos) carry a data-only "ciudad corregida" header, which stays in their notes below the new header.
-- 11 of the 21 discarded rows are in the admin's 100% queue: the pending flag is removed with them (nothing of the queue is lost, the business keeps its own row).
-- What hangs from the discarded row moves to the kept one: votes (INSERT ... ON CONFLICT DO NOTHING, then DELETE, so the vote_count trigger, which only fires on
-- INSERT and DELETE, stays right), reports and published opinions, evidence, outreach messages and promoted suggestions. Today none of the 21 discarded rows has any
-- (the 15 votes of the 24 pairs, all of JANA, are already on the kept row), so the moves are safety nets; the assertions demand that nothing stays attached.
-- The kept row only gets its NULL panel fields (phone, website, social_url) filled from the discarded one: one case today (Minimarket La Isla, its Instagram).
-- The discarded row becomes status 'discarded' with the header "CORRECCIÓN MANUAL: duplicado de <id>" on top of its previous notes, and leaves the 100% queue
-- (its flag is removed, like review_queue --discard does). The header is a DATA correction (agents/manual_overrides.py, "duplicado de"): it protects nothing.
-- No row of `places` is deleted. Special case to review: CeliHaus, whose kept row is celiac_friendly ("Tiene opciones sin TACC") while the discarded one was
-- gluten_free_100 (in the admin's 100% queue): the business now shows the lower level until the admin confirms 100% with evidence.
--
-- Run (one transaction, all-or-nothing; any drift RAISES and nothing is written):
--   node_modules/.bin/supabase db query --linked --file db/fixes/2026-09-27-duplicate-place-ids.sql
-- Dry run: the same statements with the final `commit;` replaced by `rollback;`.

begin;

-- 0. The pairs: keep_id stays, drop_id is discarded; the statuses are the ones this script was written for.
create temp table _pairs (
  keep_id uuid primary key, drop_id uuid not null unique, external_id text not null,
  keep_status text not null, drop_status text not null
) on commit drop;
insert into _pairs (keep_id, drop_id, external_id, keep_status, drop_status) values
  ('4e944968-e0e5-49a7-9ca3-efef2de22971', 'f9325c8d-56ff-4fa5-a183-554db83d2ff6', 'ChIJn4ukAADLvJURzk5slx5hz5s', 'approved', 'approved'),  -- Alfin Pizzas Sin Gluten: keeps google_places (approved), discards social (approved)
  ('09713c52-85d5-41ab-b746-6c1440996a48', 'f6bc1d46-49ac-4d43-bda7-2c17f5c24953', 'ChIJUVFjFYaBn5URrkuPBgU5lBc', 'approved', 'approved'),  -- Alárabi Cocina Inclusiva: keeps google_places (approved), discards social (approved)
  ('102f1557-9d12-494d-bd4a-b4395c006b6d', 'f5222243-32b3-44dc-9adf-d90f279badd0', 'ChIJYyhy6Vxnt5URfoJPp2DOg-Y', 'approved', 'approved'),  -- Apto Libre de Gluten: keeps google_places (approved), discards social (approved)
  ('c302e82e-bfe7-4913-b3d1-193e1438b633', '27df16aa-bb57-430c-96cc-337a72fbd222', 'ChIJ3RdXVIa_vJURKeN7YnoaITA', 'approved', 'approved'),  -- Celiak2 gluten free: keeps google_places (approved), discards social (approved)
  ('4b6502d5-b044-4e58-8269-9abf39544679', '2c9bbad0-38b1-4f77-bfb3-dcfc17e58f18', 'ChIJpc6-XmKlvJURqixtKJ7TSKw', 'approved', 'approved'),  -- CeliHaus: keeps google_places (approved), discards social (approved)
  ('7222df03-c6ab-4c7c-8b87-a86750ce92cd', 'b8f1d744-a22a-4bb8-859b-d526066beafc', 'ChIJEQlThim1vJURIJjDt4qKIFk', 'approved', 'approved'),  -- Donato (sin tacc): keeps google_places (approved), discards social (approved)
  ('6797f10b-800e-4ce3-b070-b265894d1d27', '27e34f52-d319-47d9-9496-6cab2df6503e', 'ChIJ6QGSAL7JvJURZJeYyavD_A0', 'approved', 'approved'),  -- JANA GLUTEN FREE | Pizzeria: keeps google_places (approved), discards social (approved)
  ('22b104b1-f950-48fb-8deb-577985b51593', '756d0138-ffb2-47a9-b478-af675996c9ae', 'ChIJ2-t_mn0adZUR2Phhin9bLts', 'approved', 'approved'),  -- Minimarket La Isla 24 hours.: keeps google_places (approved), discards social (approved)
  ('a1a01324-3e7d-49af-ae7a-d26a7164b92c', '5b0f8fe5-2095-4dca-8317-333ac631f26e', 'ChIJt399yBWrt5URptiBiXLH9Es', 'approved', 'approved'),  -- Nana Gluten Free: keeps google_places (approved), discards social (approved)
  ('e01d9725-6a65-4e67-a05e-727268837f03', 'd39c13f0-e0a1-47ba-b43a-e20340186b97', 'ChIJr6esFT3mopURq5Aopxe5g7Q', 'approved', 'approved'),  -- Nature gluten free: keeps google_places (approved), discards social (approved)
  ('61c88bc0-04ba-46cb-a2e5-2879e2f51700', 'd4d77258-fa74-4107-b21e-9e12d1a4fdbf', 'ChIJ8RxtoJjnopURi8tM_eVK0Ts', 'approved', 'approved'),  -- Placeres sin gluten: keeps google_places (approved), discards social (approved)
  ('89b69ad7-0923-4f4f-b4d4-960072e56606', 'da15c446-b8b5-4955-823b-161a2dad894f', 'ChIJwS4P853fhJURVAwgIEhitMY', 'approved', 'approved'),  -- Yoda gluten free: keeps google_places (approved), discards social (approved)
  ('8a0e3a83-9b9b-46bc-87a5-f4ecdaa05a86', 'e4b6cc4c-b06e-4774-9b1f-d5fcc4e04dc5', 'ChIJ0XH-mdG1vJURbu0zS62b52w', 'approved', 'approved'),  -- Zero Gluten: keeps google_places (approved), discards social (approved)
  ('4058200c-8564-40a7-aab4-6f074e452de0', '92c4f36e-9667-40a2-a5d8-91a5d1f9f61e', 'ChIJXxWYFhnLvJURCEJETFMbIxg', 'needs_review', 'needs_review'),  -- Amayta: keeps google_places (needs_review), discards social (needs_review)
  ('772329b7-aa91-4169-b91c-6d985187d33e', 'e3be8652-d60a-478f-8124-a16442e731f3', 'ChIJvYZQPpM1o5UR4ve3tHL3lz8', 'needs_review', 'needs_review'),  -- CAMPOBRAVO Puerto Madero: keeps google_places (needs_review), discards social (needs_review)
  ('feac01c7-a1b6-4453-baba-e9a249201282', '6bc77ac8-4cea-48d7-ae9b-d688b0a0140d', 'ChIJkZ2S-3gFdZURjWZkrb3a73U', 'needs_review', 'needs_review'),  -- Gelatería Il Porto - Helados artesanales: keeps google_places (needs_review), discards social (needs_review)
  ('b64a4a15-e2a4-410a-9096-e4e7ca0461d0', '179211c3-252f-4943-a0d7-6224dab2b542', 'ChIJlZEG6xcFdZURD4AtEPrJw-M', 'approved', 'needs_review'),  -- Harvest Punta del Este: keeps google_places (approved), discards social (needs_review)
  ('e961bbf1-55ae-4b52-b6a5-2fe48bbb599e', 'ab1beb7d-d929-4358-8e03-82ee39c3e6e2', 'ChIJobPnrUCAn5UR19pT5jwRUHo', 'needs_review', 'needs_review'),  -- Mercado Natural: keeps google_places (needs_review), discards social (needs_review)
  ('4aba4cf6-f377-4c8f-9fe8-5c64a1cbe9c5', '456668cf-402d-427c-8408-c47b48caf653', 'ChIJmaf3r3yAn5URxzOvDEee5U8', 'needs_review', 'needs_review'),  -- Niter Alimentos Naturales: keeps google_places (needs_review), discards social (needs_review)
  ('a14e5e65-4071-4f9f-a241-92fe5e1bf25b', '435a6c9f-bbb9-4b87-85ea-75ead0123ebd', 'ChIJsWPoxBaxvJURD31L7Z1Pxv4', 'approved', 'needs_review'),  -- Sin Gluten Olivos: keeps google_places (approved), discards social (needs_review)
  ('88791fce-0f1a-4b9c-aedd-e0e322785656', 'ce65bf2b-fddc-46a6-a204-18eb90afd8b6', 'ChIJ-1Xica_HvJURfnXP7O66KIU', 'approved', 'needs_review');  -- Sin gluten Ro sana: keeps social (approved), discards google_places (needs_review)

-- 1. Snapshot (dropped at commit): a hash of every row, and of the discarded / kept rows without the columns this script may change.
create temp table _snap on commit drop as
select p.id, md5(to_jsonb(p)::text) as h,
       md5((to_jsonb(p) - 'status' - 'flags' - 'validation_notes' - 'updated_at')::text) as h_drop,
       md5((to_jsonb(p) - 'phone' - 'website' - 'social_url' - 'vote_count' - 'updated_at')::text) as h_keep,
       p.validation_notes as notes
  from public.places p;

-- 2. Guard: all 21 pairs exist, share the external_id and are in the expected statuses.
do $$
declare n int;
begin
  select count(*) into n from _pairs pr
    join public.places k on k.id = pr.keep_id and k.external_id = pr.external_id and k.status = pr.keep_status
    join public.places d on d.id = pr.drop_id and d.external_id = pr.external_id and d.status = pr.drop_status;
  if n <> 21 then raise exception 'guard: expected 21 pairs in their expected state, found %', n; end if;
end $$;

-- 3. Move what hangs from the discarded rows to the kept ones.
insert into public.place_votes (place_id, voter_token, source, created_at)
select pr.keep_id, v.voter_token, v.source, v.created_at
  from public.place_votes v join _pairs pr on v.place_id = pr.drop_id
on conflict (place_id, voter_token) do nothing;
delete from public.place_votes v using _pairs pr where v.place_id = pr.drop_id;

update public.place_reports r set place_id = pr.keep_id from _pairs pr where r.place_id = pr.drop_id;
update public.place_evidence e set place_id = pr.keep_id from _pairs pr where e.place_id = pr.drop_id;
update public.outreach_messages o set place_id = pr.keep_id from _pairs pr where o.place_id = pr.drop_id;
update public.suggestions s set promoted_place_id = pr.keep_id from _pairs pr where s.promoted_place_id = pr.drop_id;

-- 4. The kept row only fills its NULL panel fields from the discarded one.
update public.places k
   set phone = coalesce(k.phone, d.phone),
       website = coalesce(k.website, d.website),
       social_url = coalesce(k.social_url, d.social_url)
  from _pairs pr join public.places d on d.id = pr.drop_id
 where k.id = pr.keep_id
   and ((k.phone is null and d.phone is not null) or (k.website is null and d.website is not null) or (k.social_url is null and d.social_url is not null));

-- 5. Discard the duplicate, announce it, and take it out of the 100% queue.
do $$
declare n int;
begin
  update public.places p
     set status = 'discarded',
         flags = coalesce((select jsonb_agg(f) from jsonb_array_elements(coalesce(p.flags, '[]'::jsonb)) f
                            where f <> to_jsonb('100% pendiente de confirmación del administrador'::text)), '[]'::jsonb),
         validation_notes = concat_ws(E'\n\n', 'CORRECCIÓN MANUAL: duplicado de ' || pr.keep_id, nullif(p.validation_notes, ''))
    from _pairs pr where p.id = pr.drop_id and p.status = pr.drop_status;
  get diagnostics n = row_count;
  if n <> 21 then raise exception 'discard: expected 21 rows, updated %', n; end if;
end $$;

-- 6. Assertions: any drift RAISES and rolls the whole transaction back.
do $$
declare bad int;
begin
  -- rows outside the pairs did not change
  select count(*) into bad from public.places p join _snap s using (id)
   where p.id not in (select keep_id from _pairs) and p.id not in (select drop_id from _pairs) and md5(to_jsonb(p)::text) <> s.h;
  if bad <> 0 then raise exception 'a row outside the pairs changed (% rows)', bad; end if;

  if (select count(*) from public.places) <> (select count(*) from _snap) then raise exception 'the number of places changed'; end if;

  -- the 21 discarded rows: discarded, header on top and the previous notes kept below it, and nothing else changed
  select count(*) into bad from public.places p join _snap s using (id) join _pairs pr on p.id = pr.drop_id
   where p.status = 'discarded'
     and md5((to_jsonb(p) - 'status' - 'flags' - 'validation_notes' - 'updated_at')::text) = s.h_drop
     and p.validation_notes like 'CORRECCIÓN MANUAL: duplicado de ' || pr.keep_id::text || '%'
     and (s.notes is null or s.notes = '' or right(p.validation_notes, length(s.notes)) = s.notes)
     and not (p.flags @> jsonb_build_array('100% pendiente de confirmación del administrador'));
  if bad <> 21 then raise exception 'the discarded rows are not as intended: % of 21', bad; end if;

  -- the 21 kept rows: same status and same everything, except the NULL panel fields that were filled and the vote_count
  select count(*) into bad from public.places p join _snap s using (id) join _pairs pr on p.id = pr.keep_id
   where md5((to_jsonb(p) - 'phone' - 'website' - 'social_url' - 'vote_count' - 'updated_at')::text) = s.h_keep and p.status = pr.keep_status;
  if bad <> 21 then raise exception 'the kept rows changed something other than empty panel fields: % of 21 are intact', bad; end if;

  -- one live row per place_id in each pair
  select count(*) into bad from (
    select pr.external_id from _pairs pr join public.places p on p.external_id = pr.external_id
     group by pr.external_id having count(*) filter (where p.status <> 'discarded') <> 1
  ) x;
  if bad <> 0 then raise exception '% place_ids still have zero or two live rows', bad; end if;

  -- nothing is left attached to a discarded row
  select count(*) into bad from public.place_votes v join _pairs pr on v.place_id = pr.drop_id;
  if bad <> 0 then raise exception 'votes left on a discarded row: %', bad; end if;
  select count(*) into bad from public.place_reports r join _pairs pr on r.place_id = pr.drop_id;
  if bad <> 0 then raise exception 'reports left on a discarded row: %', bad; end if;
  select count(*) into bad from public.place_evidence e join _pairs pr on e.place_id = pr.drop_id;
  if bad <> 0 then raise exception 'evidence left on a discarded row: %', bad; end if;
  select count(*) into bad from public.reviews rv join _pairs pr on rv.place_id = pr.drop_id;
  if bad <> 0 then raise exception 'reviews left on a discarded row (move them by hand): %', bad; end if;
  select count(*) into bad from public.outreach_messages o join _pairs pr on o.place_id = pr.drop_id;
  if bad <> 0 then raise exception 'outreach messages left on a discarded row: %', bad; end if;
  select count(*) into bad from public.suggestions s join _pairs pr on s.promoted_place_id = pr.drop_id;
  if bad <> 0 then raise exception 'suggestions still promoted to a discarded row: %', bad; end if;

  -- the denormalised vote_count agrees with place_votes on every row of the pairs
  select count(*) into bad from public.places p
   where p.id in (select keep_id from _pairs union select drop_id from _pairs)
     and p.vote_count <> (select count(*) from public.place_votes v where v.place_id = p.id);
  if bad <> 0 then raise exception 'vote_count disagrees with place_votes on % rows', bad; end if;
end $$;

commit;
