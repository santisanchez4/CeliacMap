-- PENDING: restoration requested by the admin; default is a rehearsal with ROLLBACK.
-- Apply only after explicit "dale", and after merging the Updater protection PR.
-- At that point replace ONLY the final rollback with commit in the reviewed execution copy.
-- No notes, safety labels, contacts or coordinates are changed.
begin;

create temp table _rikuras_before on commit drop as
select id, website, md5((to_jsonb(p) - 'website' - 'updated_at')::text) as other_fields
from public.places p;

do $$
declare n int;
begin
  update public.places
     set website = 'https://rikurassingluten.pidedirecto.uy/'
   where id = '339efc28-af19-4ce4-96ea-a9c1aa5176d4'
     and external_id = 'ChIJ64hoV1KHn5URvCEqq2PDcI4'
     and status = 'approved'
     and website = 'https://rikurassingluten.ambit.la/';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'Expected exactly one Rikuras Malvin row, got %', n; end if;

  if (select count(*) from public.places p join _rikuras_before b using (id)
      where p.website is distinct from b.website) <> 1 then
    raise exception 'Unexpected number of changed websites';
  end if;
  if exists (select 1 from public.places p join _rikuras_before b using (id)
             where md5((to_jsonb(p) - 'website' - 'updated_at')::text) <> b.other_fields) then
    raise exception 'Unexpected changes outside website/updated_at';
  end if;
  if (select count(*) from public.places) <> (select count(*) from _rikuras_before) then
    raise exception 'Unexpected place count change';
  end if;
end $$;

select id, name, website as rehearsed_website from public.places
where id = '339efc28-af19-4ce4-96ea-a9c1aa5176d4';

rollback;
