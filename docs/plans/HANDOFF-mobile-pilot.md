# Punto de reanudación — piloto móvil CeliacMap

**Iniciado:** 2026-10-02. **Última actualización:** 2026-10-06. Bitácora de sesiones del piloto: las secciones viejas se
conservan como historia; el estado vigente es el de la **última «Actualización»**. Versionado desde el 2026-10-03.

## Contexto y autorizaciones

- Preparación del piloto completada y PR #2 mergeado: https://github.com/santisanchez4/CeliacMap/pull/2, commit main `23abe40e52d9aba416e6e71416e6bf929eee19a1`.
- Plan: `docs/plans/PLAN-mobile-app.md`; ADR-010; auditoría Google: `docs/legal/auditoria-datos-google.md`.
- Piloto PWA primero, después Capacitor Android. Sin cuentas/fotos/push; cercanía posterior solo al tocar, GPS en memoria y nunca enviado al backend/modelo.
- Usuario pidió una rama/PR del Updater y otra rama/PR PWA; no autorizó merge de esos PR ni despliegue.
- **SQL Rikuras: no aplicar hasta recibir «dale» explícito**, y después del merge de la protección del Updater. Ensayo con rollback sí autorizado y completado.
- Google Maps / datos propios / Places UI Kit: decisión del responsable más adelante. Riesgo abierto prioritario antes de tiendas o de presentación institucional; no bloquea desarrollo del piloto.

## Verificación de main

Se leyó la API, sin modificar configuración. Protección por ruleset (el endpoint clásico devuelve 404):

- Ruleset 24349101, «Proteger main», activo sobre rama predeterminada.
- PR obligatorio, 0 aprobaciones externas requeridas, check `CI required` de GitHub Actions (integration_id 15368).
- `bypass_actors: []`, bloqueados borrado y force-push.
- **Diferencia informada al usuario:** `strict_required_status_checks_policy: false`. La opción de exigir rama actualizada NO estaba activada al leerla, aunque el usuario creía que sí. No se cambió.

## Updater: implementado, PR abierto

**Rama local actual:** `fix/updater-manual-contact-fields`, basada en `origin/main`.
**Commit:** `0aae8b7` — `fix: preserve manually curated contact fields in updater`.
**PR #3:** https://github.com/santisanchez4/CeliacMap/pull/3 (abierto; sin merge).

- Tests primero: siete casos reprodujeron la sobrescritura antes de implementar.
- `agents/manual_overrides.py`: `protected_contact_fields()` protege website/phone/opening_hours solo por campo registrado en `config/manual_contact_fields.json`. Desde el 2026-10-06 una APROBACIÓN MANUAL protege la etiqueta de seguridad, no el contacto (`docs/DECISIONS.md`, "Contact data frozen only by the registry").
- `config/manual_contact_fields.json`: registro explícito UUID → campos + fuente SQL para correcciones históricas sin nota: Rikuras Malvín, Ramona Centro, Casa & Dispensa, La Commedia, Piu Cordón, ChocAra, NutriCiencia.
- `agents/updater_agent.py`: excluye esos campos del patch. Conserva valor actual incluso vacío; no restaura automáticamente datos. Rating, otros campos y cierres siguen igual.
- Nuevas correcciones deben registrarse por PR antes de aplicar datos. Limitación documentada: edición remota no registrada/sin aprobación no puede detectarse; coordinar cambios administrativos fuera de un Updater en ejecución.
- Documentado en `docs/runbooks/manual-contact-fields.md`, DECISIONS, índice/regla CLAUDE, README y prompts.md. Incluye Google como riesgo abierto y lectura del ruleset.
- Validación local final: **834 pytest + 268 Edge + 85 frontend = 1.187 tests aprobados**; diff check limpio.
- **Pendiente: consultar CI del PR #3.** Se abrió justo antes del pedido de detenerse; no se verificó el resultado remoto final.

## Rikuras: SQL ensayado, aplicación pendiente

Archivo `db/fixes/2026-10-02-rikuras-malvin-website.PENDING.sql`, termina en `rollback;`.

- UUID `339efc28-af19-4ce4-96ea-a9c1aa5176d4`, Place ID `ChIJ64hoV1KHn5URvCEqq2PDcI4`.
- Cambia solo website a `https://rikurassingluten.pidedirecto.uy/` si está approved y conserva URL anterior `https://rikurassingluten.ambit.la/`.
- Guardas: exactamente una fila; sin cambios fuera de website/updated_at; cantidad de lugares constante.
- Se leyeron triggers remotos: solo `places_set_updated_at` sobre places.
- Ensayo enlazado vía Supabase CLI completado: mostró URL nueva dentro de transacción, aserciones pasaron, terminó con ROLLBACK.
- SELECT posterior confirmó que la URL persistida sigue siendo ambit.la. **No se aplicó restauración.**
- Tras «dale» y merge protección: revisar estado, preparar copia del SQL cambiando solo rollback final por commit, ejecutar y verificar. Si guardas fallan, investigar sin quitarlas.

## Actualización 2026-10-02 (sesión siguiente)

- PR #3 (Updater) mergeado por el responsable (`76504df`); CI verde. **SQL Rikuras sigue sin aplicar**: espera el «dale».
- **PWA implementada y mergeada: PR #4** (`582c8b1`, merge `5698291`). Deploy de Pages exitoso.
- **Prueba en Android real (responsable):** instalación OK desde Chrome ("Install and create shortcut"), ícono verde, pantalla
  completa sin barra de Chrome. Mapa carga al abrir; la primera vez hubo que recargar una vez, después no (sin diagnóstico;
  observar en la QA del APK). Delay breve de tiles al expandir/moverse, igual que la web. Modo avión: aparece el aviso offline.
- Registro en DECISIONS: rama `docs/pwa-android-verified`.
- Lighthouse pendiente (no instalado). `adb` sigue sin estar en PATH.
- Próximo: fase 2 «Cerca mío» en rama/PR nuevos; el responsable pidió ver el plan antes de implementar.

## Actualización 2026-10-02 (fase 2)

- PR #5 (registro Android) y PR #6 (íconos = logo del header) mergeados por el responsable.
- **«Cerca mío»: PR #7** (`feat/nearby`, `9af1d51`), CI verde, sin merge. Local: 834 pytest + 268 Edge + 126 frontend.
  QA en Chrome con geolocalización simulada (pestaña oculta: visibilidad simulada). Pendiente: Android real (concedido,
  rechazado, aproximado). Política §3.10 en borrador.
- Rama local `claude/celiacmap-audit-agents-chatbot-0ohie6` conservada: tiene cambios que no están en su remota.

## Actualización 2026-10-03 (fase 2 cerrada)

- PR #7 («Cerca mío») mergeado por el responsable (`9ff567c`); deploy de Pages exitoso.
- **Prueba en Android real (responsable): los siete casos OK** — permiso concedido, distancia en la ficha, se borra al volver
  de otra app, permiso rechazado, ubicación aproximada, atajo del chat, inglés. El mapa no necesitó recarga (la recarga única
  de la primera apertura de la PWA no se repitió; sin diagnóstico, observar en la QA del APK).
- Registro en DECISIONS + índice de CLAUDE.md: PR #8 (`docs/nearby-android-verified`); lo mergea el responsable.
- **SQL Rikuras aplicado el 2026-10-03** con el «dale»: ensayo fresco con rollback aprobado, después la copia con `commit`.
  Lectura posterior: `website` = `https://rikurassingluten.pidedirecto.uy/`; 1 385 filas y 417 aprobadas, sin cambios.
  Archivo renombrado a `db/fixes/2026-10-02-rikuras-malvin-website.sql`; registro en PR #9 (sin merge).
- Pendientes del responsable: revisar §3.10 de la política de privacidad (borrador); decisión Google antes de mostrar en público.
- **Fase 3 aprobada (Capacitor Android, APK de demo).** Decisiones del responsable: appId `org.celiacmap.app`; Android SDK por
  línea de comandos (avisar antes de pasar a Android Studio); `https://localhost` en el CORS de `chat` en un PR aparte, con el
  comando de deploy mostrado y «dale» previo, y después verificar `verify_jwt=false` y fuente desplegada = `main`; sin beacon de
  Cloudflare en el APK; clave de firma fuera del repo, informando qué archivos respaldar y dónde están. Sin Play Store y sin
  cambios de datos. Rama `feat/capacitor-android` desde `main` actualizado, tests antes del push, PR sin merge. Al tener el
  APK: pasos de instalación y lista de pruebas.
  PC al 03-10: Node 22.20, JDK 21 en `C:\Program Files\Android\openjdk` (el `java` del PATH es 25), sin Android SDK ni `adb`.
  Capacitor vigente 8.5.2 (pide Node ≥ 22). CORS de `chat`: solo `celiacmap.org`, `www` y `http://localhost(:puerto)`.

## Actualización 2026-10-03 (fase 3 implementada)

- **PR #11** (`feat/capacitor-android`, `dfba2a6`), sin merge: `apps/mobile/` con Capacitor 8.5.2, `org.celiacmap.app`, sin
  beacon ni service worker en la app, geolocalización por la WebView (sin plugin), botón Atrás, runbook
  `docs/runbooks/apk-demo.md`. Incluye el commit del PR #8 para no chocar en DECISIONS. Local: 834 + 268 + 136.
- **PR #12** (`fix/chat-cors-capacitor`), sin merge: `https://localhost` exacto en el CORS de `chat`. **Deploy pendiente del
  «dale»**: `node_modules/.bin/supabase functions deploy chat` desde `main` ya mergeado; después `functions list`
  (`verify_jwt=false`) y `functions download chat --use-api` comparado contra `HEAD`. Hoy desplegada: chat v24.
- PC: Android SDK por línea de comandos en `%LOCALAPPDATA%/Android/Sdk` (cmdline-tools 19, platform-tools, plataforma 36,
  build-tools 35 y 36). El build usa `JAVA_HOME` = JDK 21 de `C:/Program Files/Android/openjdk`.
- Clave de firma generada en `%USERPROFILE%/celiacmap-signing/` (`celiacmap-release.jks` + `keystore.properties`), fuera del
  repo; el responsable debe respaldar los dos archivos. APK firmado 0.1.0 en `%USERPROFILE%/celiacmap-apk/`.
- **Pendiente: prueba en Android real** con la lista del runbook (no había teléfono conectado): CARTO en la WebView, teclado,
  enlaces externos, permiso de ubicación. El asistente no responde en la app hasta el deploy de `chat`.

## Actualización 2026-10-03 (chat v25 desplegado)

- PR #8, #9, #10, #11 y #12 mergeados por el responsable, en ese orden, con CI verde (`main` = `6b56d2d`).
- **`chat` v25 desplegado** con el «dale», desde `main`: `node_modules/.bin/supabase functions deploy chat`. Verificado en
  solo lectura: `verify_jwt=false`, versión 25, fuente descargada idéntica a `HEAD` (mismos hashes de `index.ts`, `prompts.ts`
  y `regions.ts`). Preflight `OPTIONS`: `https://localhost` y `https://celiacmap.org` reciben `Access-Control-Allow-Origin`;
  `https://localhost:8443` no. Sin llamadas al modelo. Los prompts no cambiaron: no reinicia el conteo del soft-launch.
- El responsable respaldó la carpeta de la clave de firma.
- **Pendiente: prueba del APK 0.1.0 en el Android del responsable** con la lista de `docs/runbooks/apk-demo.md`; pasa los
  resultados al terminar. Recién entonces registrar la verificación en DECISIONS.
- Pendientes del responsable sin cambios: §3.10 de la política de privacidad (borrador); decisión sobre los datos de Google
  antes de mostrar el piloto a instituciones.

## Actualización 2026-10-06 (revisión de la cola del 100%)

Decisiones del administrador sobre la cola «100% pendiente de confirmación del administrador», aplicadas en producción con
`scripts/review_queue.py --approve` (salvo Avanti) y verificadas en solo lectura. `validation_confidence` y `verified` no se
tocaron en ninguna fila. La cola quedó en **236** (201 Argentina, 35 Uruguay); el 2026-09-27 eran 271.

- **Confirmados en 100% (16):** Selkkis Gluten Free, Milena Gluten Free y Tu rincón de dulces gluten free by Flo Scalone
  (Montevideo, conocimiento directo); Local Celíacos (Montevideo, revisado por el administrador); TACCOFF (Buenos Aires, cita
  verificada de su sitio); las 11 sucursales de GOUT / Goût en Argentina (5 en CABA, 3 en Rosario, Vicente López, Nordelta y
  Pilar), con la frase «Todo 100% gluten free, todo Goût.» que el administrador verificó en el Instagram oficial. Las 11 figuran
  `OPERATIONAL` en Google Places.
- **Bajados a «Tiene opciones sin TACC» (3):** Vichenzo Sin Tacc Monserrat, Senza Tacc y Delimade Viandas (Buenos Aires): sin
  evidencia explícita de exclusividad; la nota dice que se pueden volver a subir si aparece evidencia.
- **Avanti Gluten Free (`25d351e9-a5d9-4425-970f-c9f5fb71997a`): descartado y cerrado.** Decisión del administrador, sin
  pendiente de verificación. Pasó a `discarded` por SQL con guardas (sin `DELETE`), con una `CORRECCIÓN MANUAL` arriba de las
  notas; ya no sale con la anon key. Es la única fila «Avanti» de la base. No reabrir ni volver a aprobar sin un pedido expreso.
- **Evidencia consultada:** `find_evidence` sobre 5 lugares de Buenos Aires (10 búsquedas de Tavily); reporte local en
  `db/checks/evidence-proposals/evidence-ba5-20261006T192437Z.*` (ignorado por git).
- **GOUT en Uruguay:** no se agregó nada. La única ficha de la cadena (Solano García 2496, Montevideo) figura
  `CLOSED_PERMANENTLY`. Deuda de datos: la fila descartada `3eb6707b-f311-4ab3-b402-0805531906e3` está en Chile con
  `country = 'Uruguay'`.
- **Contacto y Updater:** PR #17 mergeado: una `APROBACIÓN MANUAL` ya no congela `website` / `phone` / `opening_hours`; solo
  el registro `config/manual_contact_fields.json`. Local Celíacos queda sin registrar a propósito: el Updater le escribirá los
  datos de Google en su próxima corrida.
- **`CLAUDE.md`:** PR #18 mergeado: índice de decisiones agrupado por tema (44 359 caracteres en el checkout de Windows).

## PWA (sección original, ya resuelta: ver actualización arriba)

Se mostró el plan antes de implementar. No se creó su rama ni se modificó frontend por esta tarea. Usuario la llamó «Fase 2», aunque el documento enumera PWA como fase 1 y cercanía como fase 2: seguir el alcance PWA solicitado, sin geolocalización ahora.

Próximo trabajo autorizado al reanudar:

1. Crear rama independiente desde main actualizado; no incluir cambios del PR #3 si sigue sin merge.
2. Manifest con nombre, colores actuales (`theme-color #2d6a4f`), scope/start_url compatibles con raíz y GitHub Pages; iconos desde `assets/icons/favicon.svg`.
3. Service worker con lista explícita de interfaz HTML/CSS/JS/íconos. **Nunca cachear lugares, respuestas/chat, APIs, tiles ni GPS.** Considerar versión/actualización y evitar mezclas de assets. Sin cambios del comportamiento online.
4. Aviso accesible offline ES/EN. Sin colas de envíos offline ni promesa de mapa offline.
5. Actualizar staging/triggers de `.github/workflows/deploy-pages.yml` para manifest/SW; gate CI existente se conserva.
6. Tests de caché/allowlist, no cache de datos/chat y aviso online/offline; suite completa y QA navegador.
7. Medir Lighthouse, guardar evidencia y distinguir resultados de laboratorio de dispositivo real.
8. Probar instalación/apertura en Chrome Android real si hay dispositivo disponible; PR independiente sin merge ni despliegue automático.

Inspección útil:

- Web HTML/CSS/JS vanilla, Leaflet externo unpkg, fuentes externas; no build frontend.
- `scripts/gen_favicons.py`: render SVG con svglib/reportlab/rlPyCairo/Pillow; genera 48/96/180. Ampliar para iconos PWA, preservando los actuales; no ImageGen necesario para conversión de assets existentes.
- `js/main.js` maneja ES/EN y eventos a inspeccionar antes del aviso offline.
- Node/npm disponibles; `adb` y `lighthouse` no encontrados en PATH. No afirmar prueba Android realizada.
- Se preguntó al usuario mediante async si puede conectar Android por USB/depuración, si hará la prueba él o si no dispone. **No llegó respuesta antes de detenerse.**

## Estado local y precauciones al retomar

- `output/` es contenido ajeno preexistente no versionado: no agregar, borrar ni modificar.
- (Histórico, 02-10) El handoff se guardó sin commit; hoy está versionado. PWA, PR #3 y SQL Rikuras: ver las actualizaciones.
- PowerShell, repo `C:\Repos\CeliacMap`; `.git` requiere escalación para git write. CLI gh instalado en `C:\Program Files\GitHub CLI\gh.exe`; red restringida requiere escalación.
- No imprimir `.env` ni secretos. Para pytest local usar basetemp único en TEMP si el directorio compartido pytest-of-Santiago da PermissionError.
- Mantener actualizaciones breves al usuario; preguntó cuánto faltaba y se estimaron 30–60 minutos para PWA, antes de pedir detenerse.
