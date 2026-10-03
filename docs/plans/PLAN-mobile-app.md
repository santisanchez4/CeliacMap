# CeliacMap — Plan del piloto móvil

**Decisión actualizada:** 02-10-2026. **Investigación y precios originales:** 01-10-2026.
**Estado:** estrategia aceptada, app todavía no implementada. Sustituye `docs/mobile-app-plan.md`.
**Decisión arquitectónica:** [ADR-010](../architecture/ADR-010-mobile-strategy.md).

## 1. Executive Summary

**PWA instalable primero; Capacitor Android y APK después.** El responsable desarrolla como persona física. El objetivo es una demostración para la Intendencia y posibles financiadores: paridad con la web más «Cerca mío». Play prueba interna es opcional. Publicación pública, iOS y cuenta de organización quedan después de una posible financiación.

La PWA se construirá sobre las carpetas actuales, antes de reorganizar nada. Solo se extraerá lógica pura necesaria, con tests. No se requiere React, Vite, monorepo, nueva API ni una segunda interfaz. Una rama por tarea, PR y CI serán obligatorios.

Ubicación solo al tocar: lectura puntual, memoria y cálculo local de distancias. Nunca se adjunta GPS del dispositivo a peticiones del backend, al modelo, logs o analytics. Sin seguimiento, cuentas, fotos ni push. La infraestructura de tiles puede inferir la zona visualizada; esa limitación debe informarse.

La auditoría Google no bloquea el piloto por decisión del responsable, pero sí debe resolverse antes de publicar en tiendas. Esta prioridad no concede una excepción contractual para demos ni autoriza modificar datos. CARTO se considera **comercial por los aliados: 1M requests/mes gratuitos agregados**, no 5M no comerciales.

Estimación de trabajo propio: **14–24 jornadas de 6 horas, 84–144 horas**, PWA y APK incluidos. Distribución obligatoria: **USD 0** con herramientas/equipos disponibles; servicios existentes según consumo. Play interno opcional: USD 25 una vez si no existe cuenta. No pagar Apple ahora.

## 2. Estado actual de CeliacMap

| Capa | Estado encontrado | Reutilización |
|---|---|---|
| Frontend | `index.html`, `css/styles.css`, `js/*.js`; JavaScript IIFE/DOM; sin React | Base completa del piloto |
| Tooling | Supabase CLI en `package.json`; sin build/lint frontend configurado | No agregar bundler como prerrequisito |
| Mapa | Leaflet 1.9.4, CARTO Positron raster; marcadores individuales | Mantener pines y filtros actuales |
| API/DB | Supabase Postgres/PostgREST, RLS y grants por columna | Mismo backend; no base móvil duplicada |
| Chat | UI `js/chat.js`; Edge Deno `chat`; Anthropic router/redactor | Mismo servicio y prompts; acción cerca mío local |
| Comunidad | Ranking/votos anónimos, opiniones moderadas, sugerencias/reportes | Paridad, sin crear cuentas |
| Agentes | Python: Google Places, Anthropic, Tavily, Resend | Operación compartida, no ejecutar desde app |
| Auth | No hay login implementado; anon key no identifica personas | Tokens locales no son autenticación |
| Idiomas | ES/EN distribuidos entre módulos/atributos HTML | Mantener sin consolidación masiva previa |
| Infraestructura | GitHub Pages `celiacmap.org`; Actions; Supabase Edge separado | Web sigue funcionando |
| Tests | Pytest, Deno Edge Functions y frontend/linkedom | Suite completa en PR; pruebas móviles futuras |

El mapa descarga aprobados en páginas de 500 y filtra en cliente; no tiene clustering/PostGIS. La UI agrupa tres valores de seguridad de base en dos etiquetas públicas. Votos/rating no certifican seguridad. Solo datos aprobados y columnas autorizadas salen al cliente; evidencia/logs/reviews internas siguen en servidor.

### Actualización operativa al 02-10

Fuente: [Decisions Log](../DECISIONS.md), entradas Privacy phase 1/2 y A social profile is not a website.

- **HMAC configurado:** `CHAT_IP_HASH_SECRET` se creó y verificó en chat v23 el 30-09 mediante un bucket IP HMAC real. No es un secreto pendiente ni se publica su valor. Chat v24 conserva el control.
- **Privacidad 05-10:** nuevas retenciones implementadas y ensayadas en dry run; primera ejecución prevista el 05-10, todavía futura hoy. Documentos legales v1.0 pendientes de revisión/publicación del responsable. No confundir esa fecha con evidencia de publicación ni de ejecución.
- **`owner_celiac`:** etapa 1 desplegada; pregunta/recolección retiradas. Drop pendiente **no antes del 07-10**, según migración `.PENDING.sql`. No ejecutarlo en este trabajo ni recuperarlo en mobile.
- **Perfiles sociales:** corrección aplicada a 190 filas; `social_url` separado de `website`. Corte documentado 01-10: 417 públicos, 117 con `social_url`, 73 con sitio propio; no son los conteos actualizados de la nueva auditoría.
- **MOOY:** Instagram en `social_url`; confirmación manual y frase de nota corregidas, sin cambiar nivel/confianza. La sucursal City Bell no se agrega.
- **Correcciones manuales:** ChocAra/NutriCiencia tienen contactos/horarios corregidos; Updater puede sobrescribir `website`/`opening_hours`. Aprobación manual no prueba procedencia manual de todas las columnas.
- **CARTO:** decisión comercial por aliados, aun siendo persona física; sumar tráfico web + PWA + APK bajo la misma cuota.

Limitaciones: fuerte acoplamiento al DOM, controles antiabuso de formularios parcialmente locales, riesgo conocido de duplicar envío si falla el redactor después del insert, CORS pendiente para origen Android y falta de PWA actual. La base de `deploy-pages` no tenía gate de tests; el punto CI de esta tarea lo incorpora. El estado real de facturación/consumo no se deduce del repo.

Validación local de esta preparación (02-10): **821 tests Python, 268 Edge y 85 frontend aprobados**. La [guía de CI y protección de main](../runbooks/pr-ci-main.md) documenta los comandos y el check obligatorio; GitHub vuelve a ejecutarlos en el PR. Todavía no hay tests móviles porque la app no se implementó.

## 3. Opciones tecnológicas

PWA conserva HTML/CSS/JS y se distribuye por URL. Capacitor empaqueta esos assets y agrega plugins nativos; sí utiliza WebView, con QA de teclado, gestos y mapa. RN/Expo y RN bare reutilizan backend y algo de JS puro, pero rehacen el DOM. Flutter usa Dart/widgets; Android/iOS nativos exigen más interfaces. TWA reutiliza una PWA solo para Android, sin el camino de plugins/iOS de Capacitor.

No elegir RN automáticamente: el repo no tiene React. No se necesita Ionic UI para Capacitor. EAS es opcional para RN/Expo y no se presupone como builder de Capacitor. [Capacitor](https://capacitorjs.com/docs), [RN](https://reactnative.dev/docs/environment-setup), [Flutter](https://docs.flutter.dev/resources/faq), [TWA](https://developer.chrome.com/docs/android/trusted-web-activity).

## 4. Tabla comparativa

Estimaciones de ingeniería, no mediciones/cotizaciones. Reutilización del frontend aplicable, sin inflar porcentajes contando Python/SQL. Los tiempos siguientes son referencias del análisis original para una salida más amplia; el piloto reducido se estima en §13.

| Opción | Frontend reutilizable | Esfuerzo orientativo | Mantenimiento/UX | Riesgo de dos interfaces |
|---|---:|---|---|---|
| PWA | 80–90% | 15–25 jornadas versión amplia | Bajo; límites navegador | Bajo |
| Capacitor | 70–85% | 35–55 Android público completo | Medio; WebView + plugins | Bajo |
| RN + Expo | 15–30%; UI 0–10% | 50–80 Android | Medio–alto; UI nativa | Medio–alto |
| RN bare | 15–30%; UI 0–10% | 65–100 Android | Alto; gestión nativa propia | Medio–alto |
| Flutter | 0–10%, assets aparte | 55–90 Android | Dart adicional; buena UX | Alto |
| Kotlin/Swift | 0–5%, assets aparte | 90–150 ambas plataformas | Máximo control y costo | Muy alto |
| PWA + TWA | 80–90% | 20–35 Android | Web; Android específico | Bajo al inicio |

| Capacidad | PWA | Capacitor | RN/Expo y bare | Flutter | Nativo | TWA |
|---|---|---|---|---|---|---|
| Android/iOS | Navegador ambos | Ambos; iOS futuro | Ambos | Ambos | Un proyecto por OS | Android |
| Mapa | Leaflet actual | Leaflet actual | Nuevo componente nativo | Nuevo plugin | SDK por OS | Leaflet |
| Geo | API web foreground | Plugin + adaptador web | API/plugin nativo | Plugin | API OS | Web |
| Chat | UI/API actuales | UI/API actuales | API igual, UI nueva | API igual, UI nueva | API igual, dos UI | Actual |
| Push/cámara futuros | Límites navegador/OS | Plugins | Plugins; Expo simplifica | Plugins | APIs OS | Web |
| Deep links | URLs | App/Universal Links | Linking/asociaciones | Asociaciones | Por OS | Android |
| Tiendas | No directamente | Ambas | Ambas | Ambas | Por OS | Play |
| CI | Estático simple | Gradle; Xcode futuro | EAS opcional o Gradle/Xcode | Toolchain Dart | Dos pipelines | Web + Android |
| Lógica compartida | Directa | Directa | JS puro, no DOM | Contratos API | Contratos API | Directa |

Todas conservan el backend. Ninguna resuelve licencias, abuso o idempotencia por cambiar framework. Web Push iOS requiere instalación y soporte de plataforma; no está en el piloto. [WebKit](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).

## 5. Tecnología recomendada

**PWA sobre estructura actual → Capacitor Android con assets locales.** Evitar `server.url` remoto como app de producción y no duplicar `map.js`/`chat.js`. No introducir React, monorepo, TypeScript masivo o un bundler antes de demostrar que hacen falta. [Configuración Capacitor](https://capacitorjs.com/docs/config).

Validar Android físico: clave CARTO restringida, CORS, permisos, teclado, atrás y navegación externa. Si falla una clave, resolver restricción/proveedor, no abrirla indiscriminadamente. Si falla rendimiento, medir y optimizar antes de cambiar mapa. RN + Expo es alternativa futura si la WebView no cumple, no desarrollo paralelo.

## 6. Arquitectura propuesta

```text
CeliacMap/
├── index.html, css/, js/, assets/  # se conservan; una implementación
├── manifest.webmanifest          # futuro: fase PWA
├── service-worker.js             # futuro: shell/versionado, no API/chat/tiles
├── js/shared/                    # solo funciones puras necesarias + tests
├── capacitor.config.*            # futuro: después de PWA
├── android/                      # futuro: APK, todavía no generado
├── supabase/functions/, db/      # mismo backend y políticas
├── agents/, scripts/             # misma operación
├── tests/
└── .github/workflows/            # PR + suite completa + deploy condicionado
```

Árbol propuesto. **Implementado distinto el 03-10:** Capacitor vive en `apps/mobile/` (config, scripts, `native.js`, `android/`) y la web sigue en la raíz; sin `js/shared/` ni adaptador de ubicación, porque la WebView usa la geolocalización web ([decisión](../DECISIONS.md#android-demo-app-with-capacitor-2026-10-03)). Primeras extracciones: normalización/filtros cuando haga falta, etiqueta conservadora de seguridad, Haversine/formato de distancias. Funciones sin DOM, red ni almacenamiento, con pruebas antes/después. No separar API/estado/i18n completos como prerrequisito de PWA.

Adaptador mínimo de ubicación web/nativa cuando se integre Capacitor. Mismos endpoints/columnas y traducciones; validar en servidor y RLS. No importar prompts privados, credenciales o servicios Python al bundle. Compatibilidad aditiva: apps instaladas pueden quedar atrás del servidor. `apps/web`, `apps/mobile`, paquetes y workspaces se evaluarán después si simplifican dependencias reales.

## 7. Estrategia Web + Android + iOS

1. Rama por tarea, PR y suite completa. Responsable activa protección de main.
2. PWA mínima sobre archivos actuales; definir scope/start URL de demo para no interceptar rutas ajenas. No pedir ubicación al abrir ni cambiar silenciosamente la landing pública.
3. Cercanía local con lógica pura probada, sin reestructuración general.
4. Capacitor Android y APK firmado; assets locales, permisos, enlaces y CORS exacto.
5. Play interno solo si aporta a las demos; cuenta personal/verificación/costo/requisitos correspondientes. No es publicación pública.
6. Financiación y decisión posterior para tiendas públicas, organización e iOS. Compatibilidad iOS es intención todavía sin validar; no requiere Mac/Apple Developer ahora.

No añadir OTA JS. El APK se actualiza por instalación firmada compatible o Play interno; datos mediante API. PWA puede ser suficiente si las demos no justifican avanzar.

## 8. Geolocation

**Solo por toque** en «Cerca mío»/centrar. Explicar antes del permiso que se usa una lectura para calcular distancias localmente y que se puede buscar por ciudad. Denegarlo no impide mapa/chat/búsqueda. No `watchPosition`, background location, refresco al volver a foreground ni solicitudes repetidas automáticas.

Mantener `{lat,lng,accuracy,timestamp}` solo en memoria; descartar al cerrar/suspender sesión y al revocar permiso. Cancelar callbacks obsoletos. Parámetros iniciales a calibrar: timeout 10 segundos, reutilización máxima 60 segundos dentro de la sesión tras un toque. No persistir posición, rumbo/velocidad, historial ni último radio centrado en GPS.

Android: foreground, soportar aproximada y precisa/solo una vez, `COARSE`/`FINE` según plugin; sin `ACCESS_BACKGROUND_LOCATION`, servicio persistente ni GPS obligatorio para instalar. iOS futuro: When In Use, sin Always/background. El plugin Capacitor puede requerir descripciones iOS adicionales por su dependencia; verificarlas en la versión fijada, sin confundir descripción con solicitar Always. [Android](https://developer.android.com/develop/sensors-and-location/location/permissions/runtime), [Capacitor Geolocation](https://capacitorjs.com/docs/apis/geolocation), [Core Location](https://developer.apple.com/documentation/corelocation/requesting-authorization-to-use-location-services).

Marcador distinto «Tu ubicación», círculo de precisión y estado de lectura. No garantizar exactitud: depende de señal, hardware y permiso. Haversine local = línea recta, no distancia caminando. Redondear según precisión («A 250 m», «A 1,2 km»); si precisión es kilométrica, no mostrar falsa exactitud. Radio propuesto 5 km, ampliable manualmente; ranking conserva criterio propio.

| Destino | Tratamiento del piloto |
|---|---|
| Memoria | Posición temporal, distancia y selección local |
| Backend/modelo | Nunca recibe GPS del dispositivo, distancias ni resultados cercanos automáticamente |
| Logs/analytics/disco | Sin GPS, historial o breadcrumbs geográficos |
| Tiles | Recibe IP y tiles visualizados; puede inferir la zona al centrar |
| Maps externo | Solo destino; la otra app decide origen bajo sus permisos |

No prometer «ninguna información de ubicación sale del teléfono» por la inferencia de tiles. No cachear ni precargar tiles centrados en GPS. Pruebas deben capturar tráfico y separar coordenadas públicas de negocios del GPS del usuario.

## 9. Map architecture

Mantener Leaflet/Positron, pines aceptados y expandir mapa; no «Buscar en esta zona». Cercanía calcula sobre catálogo aprobado descargado, sin RPC espacial ni geocoding por usuario. Sincronizar selección existente de ranking/chat con detalle y revisar `invalidateSize()` al cambiar viewport.

Cientos: medir implementación actual. Miles: clustering/carga por bloques si la medición lo pide; decenas de miles: regiones/celdas/PostGIS con índices y límites. No introducir todo eso en la demo. Fixtures 500/2.000/10.000 permiten decidir; umbrales propuestos p95 filtro <150 ms y mapa útil ~3 s en red/dispositivo definidos, no resultados garantizados. [Leaflet.markercluster](https://leaflet.github.io/Leaflet.markercluster/).

**CARTO comercial:** 1M requests/mes gratis agregados, cuenta completa; plan comercial publicado USD 500/mes hasta 10M o USD 5.000 prepago anual. Confirmar restricción compatible con WebView, no reutilizar ciegamente una clave restringida a dominio web. [CARTO](https://carto.com/basemaps/).

**Google:** [auditoría específica](../legal/auditoria-datos-google.md), solo lectura. Fuente por fila no demuestra procedencia de cada columna; manual approval no equivale a datos propios. Purga de reviews a 30 días no resuelve el resto. Opciones a decidir: fuente independiente documentada, retirar/reemplazar campos, o mapa Google donde lo exijan las condiciones. No cambiar datos en esta fase.

Alternativas: raster MapTiler (Flex publicado USD 30/mes + exceso, unidades distintas); MapLibre motor abierto pero tiles/hosting pagos según proveedor; Google SDK nativo con mapa base gratuito publicado, JS y otros SKU aparte. OSM público no es CDN ilimitada ni permite descarga masiva/offline. [MapTiler](https://www.maptiler.com/cloud/pricing/), [MapLibre](https://maplibre.org/), [Google precios](https://developers.google.com/maps/billing-and-pricing/pricing), [OSM](https://operations.osmfoundation.org/policies/tiles/).

Navegación: conservar Google Maps URL con destino y no origen; Apple Maps al incorporar iOS. No API de rutas ni pago por GPS. Geocoding sigue en agentes para nuevas direcciones. Nominatim público tiene restricciones, no es reemplazo libre para autocomplete. [Google URLs](https://developers.google.com/maps/documentation/urls/get-started), [Apple links](https://developer.apple.com/library/archive/featuredarticles/iPhoneURLScheme_Reference/MapLinks/MapLinks.html), [Nominatim](https://operations.osmfoundation.org/policies/nominatim/).

## 10. Chatbot mobile

Reusar UI y endpoint; adaptar tamaño/teclado, sin cambiar rubric/prompts ni extraer toda la arquitectura. Mantener historial en memoria, confirmaciones y errores. Botón «Cerca mío» consulta dispositivo y renderiza tarjetas localmente: no llama al modelo ni añade resultados/distancias al historial enviado después. Conservar acciones actuales.

Texto libre geográfico avanzado queda después: una acción estructurada del router podría disparar flujo local, pero requiere cambio aprobado/pruebas y no está en el piloto. No enviar IDs cercanos automáticamente: también revelan una zona. Texto que el usuario escriba sí sigue el flujo actual del chat; avisar, no autocompletar GPS.

CORS Android esperado se confirma con configuración fijada; añadir origen exacto, no wildcard. HMAC ya configurado/verificado; preservar límites sesión/IP/global y no exponer secretos. Dos llamadas Haiku por turno no equivalen a tarifa fija. Evitar reintento automático de writes; riesgo existente de insert exitoso/redactor fallido se trata en tarea de idempotencia, sin fingir que ya está resuelto. Conservar render seguro y validar protocolos de links.

## 11. UX/navigation propuesta

Piloto = experiencia actual adaptada, instalable y usable con touch/teclado. No rediseño obligatorio ni nuevas tabs antes de la demo. Mantener branding, aliados separados de seguridad, ES/EN, focus visible y reduced-motion.

Wireframe conceptual de evolución: **Mapa** (buscar, filtros, cerca mío, detalle) → **Comunidad** (ranking/opiniones/sugerir/reportar) → **Asistente** → **Más** (idioma, explicación, privacidad, contacto, aliados). No tab Perfil vacía. Se puede alcanzar primero con navegación existente.

Mapa: búsqueda arriba, botón cercano accesible, mapa, detalle sin tapar atribución. Detalle: nombre, etiqueta/aviso, dirección/distancia aproximada, contacto/horario disponible, votos separados de rating, cómo llegar. Chat: campo encima del teclado, quick actions, estado de red. Targets 44–48 unidades, contraste y texto grande; Atrás cierra teclado/detalle antes de salir.

## 12. MVP

**Incluye:** instalación/loading; mapa actual y expandir; búsqueda/filtros; detalle/seguridad; ranking/votos/opiniones moderadas; sugerencias/reportes; chatbot; idiomas/branding/aliados; links externos; cerca mío puntual con precisión visible y fallback manual.

**No incluye:** cuentas, fotos, push, tracking, rutas internas, nuevos perfiles, gamificación, iOS nativo, publicación pública, monorepo ni refactor general. No exigir nuevas pantallas para conservar paridad.

Offline: shell/assets versionados y aviso sin conexión; deshabilitar envíos/chat/votos offline sin cola silenciosa. **No cachear catálogo, tiles, conversaciones ni GPS durante el piloto.** Últimos lugares/favoritos después de resolver licencias, retención, timestamp y retiro de aprobaciones. TTL no sustituye derechos ni garantiza seguridad. Estimación posterior: favoritos locales 1–2 jornadas, caché de datos robusta 2–4, mapas offline 10–20+ y proveedor específico.

## 13. Roadmap

Una rama y PR por tarea, cambios pequeños reversibles. Jornadas de 6 horas; no cotización.

| Fase | Tareas/componentes | Dependencias/riesgos | Esfuerzo | Resultado |
|---|---|---|---:|---|
| 0 — Preparación | Plan/ADR, auditoría documental, workflows/tests, protección main | Responsable activa protección; no alterar datos | 1–2 días | Base de trabajo revisada |
| 1 — PWA primero | Manifest/iconos, scope, SW shell, instalación/actualización, paridad | Caché obsoleta y rutas; conservar carpetas | 3–5 | PWA instalable y web intacta |
| 2 — Cerca mío | Funciones puras + tests, permiso/botón/precisión/distancia local | Denegación, precisión, fugas GPS | 3–5 | Cercanía solo por toque, sin red de ubicación |
| 3 — APK | Capacitor/assets, plugin Android, CORS/tiles, firma, teclado/atrás | Claves/orígenes/WebView/dispositivo | 4–7 | APK instalable y actualizable |
| 4 — Demo | QA ES/EN/paridad/red/permisos, guion y evidencia commit/build | No crear contribuciones de prueba públicas | 3–5 | Piloto presentable |
| Opcional — Play interno | Cuenta personal/requisitos/AAB/testers privados | USD 25 si falta cuenta; condiciones del canal | +1–3 + trámites | Distribución interna, no pública |
| Tras financiación | Resolver datos/proveedor, hardening, tiendas, organización si corresponde, iOS | Revisión/legal/recursos/operación | Reestimar | Release separado autorizado |

**PWA + APK: 14–24 jornadas (84–144 horas), unas 3–5 semanas** a cinco jornadas por semana. No incluye cambio sustancial de proveedor ni iOS. Auditoría no bloquea piloto, pero un eventual uso de Play debe cumplir sus requisitos aplicables; no usar internal testing para eludirlos.

## 14. Testing

CI inmediata: pytest completo y Deno completo de Edge Functions/frontend, con fixtures/mocks, sin APIs pagas ni escrituras productivas. Conservar regresiones de etiquetas, prompts, grants, ranking, formularios y chat.

Piloto: unit Haversine/precisión/formato/filtros; integración selección/chat/mapa; captura de requests sin GPS; permisos concedidos/denegados/aproximados, timeout y revocación; cierre/background sin nueva lectura; fallos 429/red y no duplicar submits. API/RLS en Supabase local o staging aislado. Fixtures del mapa, ES/EN, accesibilidad, teclado/Atrás/rotación y actualización PWA/APK.

Playwright para PWA, geolocation mocks y red interceptada; aún no instalado. WebKit no prueba un iPhone nativo. Android/WebView de Playwright es experimental. Appium con contextos native/webview para pocos journeys APK si automatizar compensa; no duplicar toda la suite. [Playwright](https://playwright.dev/docs/api/class-android), [Appium](https://appium.io/docs/en/latest/guides/context/).

Android físico económico/medio y emulador reciente; permiso/precisión real no se valida solo con mocks. iPhone/simuladores/Xcode quedan después; PWA en iPhone prestado es prueba útil, no gate del piloto Android. Salida: sin secretos/GPS en requests propios, sin safety más permisivo, paridad y cero bloqueantes de demo.

## 15. CI/CD

```text
tarea → rama → PR → pytest + Deno Edge + Deno frontend → revisión/merge
main → tests del mismo commit → deploy Pages
futuro piloto → build trazable → prueba Android física → APK de demo
                                      └→ Play interno opcional
tras financiación → beta → revisión → producción; iOS separado
```

GitHub Actions existente, Linux para checks/Android. Job de agentes separado; no agentes pagos en PR ni secrets de producción a forks. La protección requerida se configura en GitHub por el responsable: PR obligatoria, check estable de suite completa, sin force-push/borrado. No exigir aprobaciones imposibles para un mantenedor individual; sí revisión explícita del diff. La regla escrita no sustituye activar el ruleset.

`deploy-pages` solo publica tras tests exitosos del mismo commit, también en ejecución manual. No filtros de paths que dejen un check requerido pendiente. Lint/build frontend se añadirán cuando existan; hoy no se afirma un comando inexistente. Edge y migraciones mantienen despliegue aparte.

APK firmado, clave fuera del repo y copia de recuperación; PR sin firma de distribución. Versionado monotónico y commit identificable. Play App Signing/upload key solo si se elige ese canal. Fastlane, EAS, Azure y Appflow no son necesarios para la demo. macOS/Apple/CI iOS después.

Rollback PWA por assets/SW versionados; APK por nuevo build firmado, no revert remoto. Deep links nativos y `.well-known` después, sin perder links web actuales. Nunca publicar un APK o tienda automáticamente por merge.

## 16. Seguridad y privacidad

Cliente puede contener anon key y clave pública restringida de tiles; nunca service_role, Anthropic, Google de agentes, Resend, Tavily, HMAC o firma. Revisar bundle/requests. HTTPS y enlaces permitidos; no abrir URLs arbitrarias del modelo dentro de WebView con plugins. RLS/grants y validaciones servidor se conservan.

No cuentas ni tokens auth nuevos. Tokens anónimos no impiden abuso por sí solos. Rate limit autoritativo/idempotencia de intake son hardening posterior o tarea separada si las pruebas demuestran necesidad. No habilitar publicación automática de UGC. HMAC IP ya funciona; mantenerlo y límites.

Coordinar privacidad 05-10 con responsable: job previsto no equivale a ejecución exitosa ni política publicada. No ejecutar drop `owner_celiac` antes del 07-10 ni como parte del piloto. Inventario/legales existentes se actualizan, no se escriben versiones contradictorias. Logs de chat marcados pueden guardar texto 30 días, contadores 7; nuevas retenciones siguen su cron documentado. No decir «no recolectamos datos» porque no hay cuentas.

Informar permisos puntuales, GPS solo memoria, inferencia por tiles, tratamiento de mensajes por Anthropic y terceros. No session replay ni eventos con formularios/texto/GPS. Crash reporting opcional con scrubbing; actual Cloudflare Analytics no habilita eventos sensibles.

**Antes de tiendas públicas:** resolver auditoría Google, políticas publicadas y declaración de datos; moderación/reportar contenido IA/UGC; controles y soporte; revisión de SDK/permissions y salud/claims. Play interno tiene sus requisitos específicos y no una dispensa universal. iOS requerirá revisar privacidad/manifests y funcionalidad suficiente; login futuro añade borrado/OAuth y reglas Apple. [Play Data safety](https://support.google.com/googleplay/android-developer/answer/10787469), [IA](https://support.google.com/googleplay/android-developer/answer/14094294), [Apple review](https://developer.apple.com/app-store/review/guidelines/).

## 17. Costos

USD sin impuestos/cambio bancario. Precios consultados originalmente el 01-10; revalidar antes de contratar. Factura/plan real, registrar y hardware no verificados. No duplicar costos backend ni renovar free tiers por cada cliente. «Obligatorio» significa servicio necesario, no plan pago.

### Obligatorios o compartidos con la web

| Servicio | Para qué | Free tier | Costo inicial | Mensual | Anual | Obligatorio MVP |
|---|---|---|---:|---|---|---|
| Capacitor/Leaflet | Runtime/mapa | Licencia abierta | 0 | 0 | 0 | Sí, sin matrícula |
| Supabase | DB/API/Edge actuales | 500 MB DB, 1 GB files, 5 GB egress +5 cached, 500k Edge/mes | 0 | Free 0; Pro desde 25 | 0 o desde 300 | Backend sí, Pro no |
| CARTO comercial | Tiles web/piloto | 1M requests/mes agregado | 0 | 0 en cuota; 500 hasta 10M | 5.000 prepago o 6.000 mensualizado | Tiles sí, plan pago no |
| Anthropic Haiku 4.5 | Chat/agentes | Sin free tier estable asumido | Según cuenta/crédito | 1 input /5 output por millón tokens | Según consumo | Sí chatbot |
| Sonnet 4.6 | Validador compartido | Igual criterio | Según cuenta | 3 input /15 output por millón | Según consumo | Operación actual |
| Google Places Legacy | Agentes actuales | 5k/mes por Text Search/Find Place/Details | Billing | Después 32/17/17 por mil; campos extra aparte | Variable | No por apertura app |
| Google Geocoding | Direcciones en agentes | 10k/mes | 0 | Después 5/mil primer tramo | Variable | GPS local no lo necesita |
| GitHub Pages | Web/PWA | Plan/repositorio elegible; límite suave 100 GB/mes | 0 adicional | 0 bajo condiciones | 0 adicional | Hosting sí |
| GitHub Actions | Checks/agentes | Runners estándar repo público; privado Free 2k min/500 MB | 0 | Exceso según OS/plan | Variable | CI sí |
| Dominio existente | `celiacmap.org` | No | No comprar otro | Factura no verificada | D: renovación real | Sí conservar |
| HTTPS/firma Android | TLS/keystore | Herramientas/hosting sin cargo extra | 0 | 0 | 0 | Sí |

Supabase Pro incluye primer Micro por crédito compute, 8 GB DB, 100 GB files, 250 GB egress +250 cached, 2M Edge/mes y backups diarios 7 días. Free puede pausarse por inactividad; confirmar conveniencia antes de demos. Google Legacy Contact/Atmosphere tienen 1k gratis por SKU y luego 3/5 por mil; no aplicar tarifas New ni crédito histórico global 200. [Supabase](https://supabase.com/pricing), [Google SKU](https://developers.google.com/maps/billing-and-pricing/pricing).

### Opcionales o posteriores

| Servicio | Para qué | Free tier | Costo inicial | Mensual | Anual | Obligatorio MVP |
|---|---|---|---:|---|---|---|
| Play Console | Play interno opcional | No | 25 una vez si falta cuenta | 0 | Sin renovación | No para PWA/APK |
| Apple Developer | iOS posterior | No para distribuir | 99 anual | — | 99 | No |
| Expo/EAS | Alternativa RN | 15 Android+15 iOS builds/mes; límites | 0 | Starter 19 + uso, Production 199 + uso | 228/2.388 + uso | No Capacitor |
| FCM/Crashlytics | Push/crashes futuro | Productos sin cargo | 0 | 0, integración aparte | 0 | No; no fotos/push ahora |
| Cloudflare Analytics | Métrica web actual | Sin cargo | 0 | 0 | 0 | No SDK nuevo |
| Resend | Email agentes | 3k/mes, 100/día | 0 | Pro 20/50k + exceso | Desde 240 pago | Servicio compartido, no alta mobile |
| Tavily | Búsqueda agentes | 1k créditos/mes | 0 | PAYG 0,008/crédito | Uso | No consultas de usuario |
| MapTiler | Alternativa raster | Free con restricciones no comerciales | 0 | Flex 30 + exceso | 360 + exceso | Solo si se decide |
| Google Maps SDK/JS | Alternativa mapa | SDK nativo base gratis; JS 10k/mes | 0 | JS después 7/mil primer tramo | Uso | Solo si se decide |
| Storage fotos | Futuro | Incluido según backend | 0 ahora | Según volumen | Según uso | No fotos piloto |
| Fastlane | Automatizar tiendas | Abierto | 0 licencia | Runner aparte | Variable | No |
| Hardware/legal/trabajo | QA/asesoría/desarrollo | Propios/prestados si disponibles | H/L/T sin cotización | Variable | Variable | No inventar tarifa |

Fuentes directas en §23. No contratar Apple/EAS/organización por anticipación. Play interno paga al registrar, APIs según consumo, tiles al superar cuota/cambiar licencia, dominio al renovar. La licencia de datos puede alterar presupuesto; elegir después de auditoría. Revisar condiciones de Pages si evoluciona a negocio comercial/SaaS; migrar hosting no obliga a cambiar backend/dominio.

## 18. Costo estimado del MVP

Supuestos ilustrativos, no métricas: turno router+redactor = 8.000 tokens input +800 output Haiku = **0,012 USD**; validación 8.000+600 Sonnet = **0,033**; otra operación agentes 3.000+500 Haiku = **0,0055**. Contexto/reintentos cambian consumo, caché puede reducirlo. [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).

| Supuesto | Ultra low cost | Recomendado | Escalable, posterior |
|---|---:|---:|---:|
| Distribución | PWA/APK | PWA/APK | Android+iOS públicos |
| Supabase | Free | Pro Micro | Pro Micro inicial + excesos |
| Turnos chat/mes | 100 | 1.000 | 10.000 |
| Validaciones/mes | 50 | 200 | 1.000 |
| Otras operaciones Haiku | 25 | 100 | 500 |
| IA total/mes | 2,9875 | 19,15 | 155,75 |
| DB/API/mes | 0 | 25 | 25 + escala |
| **Servicios/mes** | **≈2,99** | **44,15** | **180,75 + exceso** |
| Distribución primer año | 0; Play interno +25 opcional | 0; Play interno +25 opcional | 124 |
| **Primer año constante** | **35,85** | **529,80** | **2.293 + exceso** |
| Año siguiente | 35,85 | 529,80 | 2.268 + exceso |

Sumar dominio D, hardware H, legal L, desarrollo T e impuestos. Precios de servicios compartidos web/app/agentes, **no costo incremental íntegro del móvil**. Supuestos: cuotas de Google/CARTO/Resend/Tavily/CI cubiertas; licencias sin contratar una alternativa adicional. Escalable no significa capacidad garantizada. Actualizar con mediciones del piloto y facturas.

Sensibilidad: 10.000 usuarios × 4 sesiones × 20 tiles = 800.000 requests; a 40 tiles supera 1M comercial. 40.000 descargas × 0,35 MB de catálogo supuesto = 14 GB de egress. Cada 1.000 turnos del ejemplo suma USD 12; un contador de turnos no limita dólares. CARTO pago agregaría USD 500/mes salvo alternativa decidida.

Piloto: 84–144 horas; `T = horas × tarifa acordada` si se contrata, sin inventar tarifa. Trabajo propio puede no tener factura pero consume tiempo. Play interno suma 6–18 horas y registro opcional. No pagar Apple ahora. Referencia anterior Android público: 210–330 horas, no se suma íntegra al piloto, pues hay trabajo compartido; iOS: 48–90 horas futuras a reestimar.

## 19. Android vs iOS

Base compatible con Capacitor, **PWA y APK Android primero**, sin publicación pública. Windows/equipo Android permiten demo sin Mac ni membresía Apple. Mantener lógica independiente ayuda a iOS posterior, pero no afirmar soporte verificado sin compilar/probarlo.

Cuenta personal si se elige Play interno; organización después de financiación. Nuevas cuentas personales sujetas a la política requieren 12 testers continuos durante 14 días para solicitar producción, no para convertir una demo APK en piloto. Internal testing no sustituye esa futura prueba cerrada. [Play pruebas](https://support.google.com/googleplay/android-developer/answer/14151465), [registro](https://support.google.com/googleplay/android-developer/answer/6112435).

Antes de cualquier envío verificar SDK/target vigentes, identidad y requisitos del canal; no fijar una fecha futura de aprobación. iOS necesitará macOS/Xcode, físico y revisión propia. Apple individual/organización se decide entonces, con D-U-N-S si corresponde a organización. [Apple enrollment](https://developer.apple.com/programs/enroll/), [target Play](https://support.google.com/googleplay/android-developer/answer/11926878).

## 20. Riesgos técnicos

| Riesgo | Respuesta |
|---|---|
| Google/licencias por campo | Auditoría paralela documental; responsable decide antes de tiendas; demo no exime contratos |
| CARTO comercial/clave móvil | Cuota de 1M agregada, restricciones reales y medición; alternativa si falla |
| Refactor rompe web | PWA antes de mover carpetas, solo lógica pura con tests |
| Caché PWA vieja | Shell versionado y actualización segura; no API/chat/tiles |
| WebView/teclado/permisos | Android físico y criterios de demo, no mera pantalla remota |
| Precisión GPS | Círculo/aviso, distancia aproximada, fallback manual |
| Spam o duplicados | Conservar límites/moderación y evitar reintento automático; hardening separado |
| Backend y APK antiguo | Contratos aditivos, pruebas de compatibilidad |
| Costos/pausa Free | Medir consumo y continuidad, alertas/topes; factura real |
| iOS pendiente | No prometer compatibilidad probada; financiar QA después |

## 21. Futuras funcionalidades

Favoritos/historial opt-in local; luego cuentas Supabase Auth con RLS, tokens OS seguros, OAuth PKCE y borrado. Fotos mediante plugin/Storage privado, EXIF GPS eliminado y moderación. Push FCM/APNs por ciudad elegida, sin background tracking. Navegación interna con servicio/licencia propia. Gamificación no altera seguridad. Recomendaciones geográficas primero locales, cualquier transmisión nueva requiere otra decisión de privacidad.

No implementar nada de esto ahora. Mantener fronteras de plataforma/API permite evolucionar sin RN. Si cambia el núcleo del producto, reabrir ADR con métricas.

## 22. Próximos pasos

1. Revisar esta PR de plan/ADR/auditoría/CI; responsable protege main. Rama por tarea desde ahora.
2. PWA mínima sobre carpeta actual: definir scope/start URL, iconos, shell y actualización, verificar paridad.
3. Cercanía local mediante funciones puras probadas y captura de requests sin GPS. Sin watch ni refresco automático.
4. Capacitor Android/APK; elegir teléfono demo, custodia de firma y guion para Intendencia/financiadores.
5. Decidir si basta APK o se necesita Play interno y sus requisitos adicionales.
6. Responsable revisa auditoría y decide datos/proveedor más adelante; no cambiar columnas ni ocultarlas automáticamente.
7. Verificar hito privacidad 05-10/publicación legal y drop owner no antes del 07-10 en tareas operativas separadas, no confundir previsión con ejecución.

Ya decididos tecnología, persona física, alcance, Android y ausencia de cuentas/fotos/push. Pendientes prácticos: URL/scope, teléfono/fecha demo, plan real Free/Pro/techo consumo, Play interno sí/no. Tiendas públicas/iOS/organización requieren financiación y una nueva decisión.

## 23. Fuentes oficiales utilizadas para costos y requisitos

Base consultada el 01-10-2026; este documento actualiza alcance el 02-10 sin afirmar nuevas verificaciones de tarifas. Revalidar antes de contratar.

- Costos backend/IA: [Supabase](https://supabase.com/pricing), [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing), [Sonnet configurado](https://platform.claude.com/docs/en/models/sonnet-4-6/overview).
- Mapas/licencias: [CARTO](https://carto.com/basemaps/), [Google precios](https://developers.google.com/maps/billing-and-pricing/pricing), [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies), [Google términos](https://cloud.google.com/maps-platform/terms), [MapTiler](https://www.maptiler.com/cloud/pricing/), [OSM tiles](https://operations.osmfoundation.org/policies/tiles/).
- Servicios: [Expo/EAS](https://expo.dev/pricing), [Firebase](https://firebase.google.com/pricing), [Resend](https://resend.com/pricing), [Tavily](https://www.tavily.com/pricing), [Cloudflare Analytics](https://www.cloudflare.com/web-analytics/).
- Hosting/CI: [Pages límites](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits), [Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Cloudflare Pages alternativa](https://developers.cloudflare.com/pages/platform/limits/).
- Distribución/requisitos: [Play registro](https://support.google.com/googleplay/android-developer/answer/6112435), [pruebas](https://support.google.com/googleplay/android-developer/answer/14151465), [Data safety](https://support.google.com/googleplay/android-developer/answer/10787469), [Apple enrollment](https://developer.apple.com/programs/enroll/), [App review](https://developer.apple.com/app-store/review/guidelines/), [App privacy](https://developer.apple.com/app-store/app-privacy-details/).

## Recommended CeliacMap Mobile Strategy

**PWA instalable primero, Capacitor Android/APK después, para demostrar paridad web más «Cerca mío».** Una implementación y mismo backend; 70–85% de frontend aplicable reutilizable, estimación no ahorro de horas garantizado. Mantener carpetas, extraer solo lógica pura con tests. Rama+PR+CI obligatorios.

Persona física, sin publicación pública/iOS/organización ahora. Distribución PWA/APK: USD 0 obligatorio; Play interno opcional: USD 25. Piloto: 84–144 horas, servicios compartidos ilustrativos de USD 2,99/44,15 mensuales según carga/plan, más costos reales no verificados. No hay segundo backend ni Apple/EAS obligatorio.

Ubicación solo al tocar, en memoria y sin GPS al servidor/modelo; terceros de tiles pueden inferir área. Auditoría Google documental no bloquea piloto por decisión de alcance, pero sí publicación en tiendas; ninguna excepción contractual implícita. CARTO comercial por aliados.

**Primer trabajo tras esta PR: PWA mínima instalable sobre la estructura actual, con paridad comprobada.** Después cercanía local probada y APK. La financiación y evidencia de uso determinarán hardening, tiendas, organización e iOS.
