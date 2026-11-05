-- APLICADO en producción el 2026-11-05 (ensayo con ROLLBACK primero, después esta versión con COMMIT y verificación de solo lectura).
-- Registro de auditoría: no se vuelve a correr (sus guardas de entrada fallarían con el estado actual).
-- 2026-11-05 · Fila admin en place_evidence para los 16 lugares de la tanda del punto 4 (después de p4_batch.sh --apply).
-- Guarda: ninguno tiene ya evidencia admin de hoy. Termina en ROLLBACK en el ensayo; COMMIT al aplicar.
begin;
create temp table ev (place_id uuid primary key, text text not null, url text) on commit drop;
insert into ev values
('7aee1f3e-a2a0-4cee-8dae-cb18684c850a','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono igual al de la fila. Página de Facebook sin dirección (no se pudo confirmar que sea la del local): «Panificados y Delicatessen Sin Gluten Elaboración Artesanal.»','https://www.facebook.com/GiannasinGluten/about'),
('4d2aaac8-7dec-41bb-8488-a6399c83a6da','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono igual al de la fila; la búsqueda no encontró texto de su Instagram que diga que todo es sin gluten.','https://www.instagram.com/rinconceliacosalto'),
('815c3801-2ef0-4049-9d11-cfc13a69d0f1','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono igual al de la fila; la búsqueda no encontró texto de su Instagram que diga que todo es sin gluten.','https://www.instagram.com/flors.3325'),
('49e1e351-a926-433d-b9ea-c409c6af4000','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono igual al de la fila. Su Instagram (junio de 2025): «Seguí nuestra cuenta para enterarte del menú, promociones y fecha de apertura.»','https://www.instagram.com/abuelaelida.glutenfree'),
('eedc80b2-709b-436a-85d3-dadcef3f109f','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa; no se encontró ningún canal propio.',null),
('18cdf8a5-08a3-4c4d-973e-9655762fa828','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono igual al de la fila. Fuente de terceros (GlutenGo): «Emprendimiento de alimentos sin gluten listado en guías públicas de Tacuarembó.»','https://glutengo.com.uy/guias/sin-gluten-tacuarembo.html'),
('7212e339-5011-484e-92df-19e4caf4ebf0','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono y dirección iguales a los de la fila. Su Instagram: «Elaboramos alimentos SIN GLUTEN, APTOS PARA CELÍACOS (libre de contaminación). Estamos en Herrera Nº859 Entre Mata y Navarrete. Melo, Cerro Largo.»','https://www.instagram.com/empatia.glutenfree'),
('251571db-4a00-44c0-b4ce-1ad9d4eea7fb','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa; no se encontró ningún canal propio.',null),
('09be5ef2-ee1f-46c1-96e6-16a8a7b00e28','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa; no se encontró ningún canal propio.',null),
('a6493fc7-279c-4e30-81d3-d79a7e89cc9c','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono igual al de la fila; su Instagram da la misma dirección («📍Amilivia531(bis) Garibaldi y Av.Varela […] Minas») pero no dice que todo sea sin gluten. Fuente de terceros (GlutenGo): «Se presenta como cocina sin gluten en todo lo que ofrece, según lo que informa el propio local».','https://www.instagram.com/glutenoutminas'),
('cdffdec9-10f9-47f4-b148-848b2ac21ba5','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono igual al de la fila. Fuente de terceros (Guía Comercial): «este restaurante se presenta como una opción pensada para quienes buscan platos sin gluten».','https://guiacomercial.uy/ficha/lumiro-sin-gluten-trinidad'),
('75b1cdd9-22ff-4bdb-9bf7-ac4bca504d42','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono igual al de la fila; no se encontró ningún canal propio. Es un comercio distinto de Felices Celíacos y de Rico Rico (otra dirección y otro teléfono).',null),
('23776ff7-884d-49e6-9044-5e7860a95fdd','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa. Fuente de terceros (guiasingluten.uy en Instagram): «Felices Celíacos / @felicesceliacos 📍 Hipodromo, Mercedes, Soriano. […] ✅ Apto para celíacos».','https://www.instagram.com/p/CLwiex0MBR5'),
('df4a1078-15da-44d6-b275-6e1d26d1182a','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa, teléfono igual al de la fila. Fuente de terceros (guiasingluten.uy en Instagram): «Rico Rico Gluten Free […] 📍Mercedes , Soriano . Pedidos con anticipación. […] ✅ Apto para celíacos».','https://www.instagram.com/p/CLHatFnn_Rv'),
('0274deb6-ba10-43fc-b35c-411e871d7505','Revisión 2026-11-05 (admin): queda con opciones. Ficha de Google operativa. Fuente de terceros (GlutenGo): «Se presenta como cocina sin gluten en todo lo que ofrece, según lo que informa el propio local: no encontramos respaldo oficial que lo acompañe.»','https://glutengo.com.uy/lugar/mi-espacio-sin-tacc'),
('78c308ac-7936-4971-b550-b84a2ed3643f','Revisión 2026-11-05 (admin): descartado por cerrado. Google Places lo marca como cerrado temporalmente y su Facebook, el que enlaza su ficha de Google, anunció: «el cierre de nuestro local. Este viernes 3 será el último día».','https://www.facebook.com/simonconmama/photos/887397693174651');

do $$ begin
  if exists (select 1 from public.place_evidence e join ev using (place_id) where e.source = 'admin' and e.created_at::date = date '2026-11-05') then
    raise exception 'guarda: alguno ya tiene evidencia admin de hoy';
  end if;
end $$;
insert into public.place_evidence (place_id, source, text, url) select place_id, 'admin', text, url from ev;
select count(*) as filas_nuevas from public.place_evidence e join ev using (place_id) where e.source = 'admin';
commit;
