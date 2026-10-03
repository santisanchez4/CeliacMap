# ADR-010 — Piloto móvil con PWA y Capacitor Android

## Estado

Aceptado el 2026-10-02 por el responsable. Implementación pendiente; no se publica una app con este ADR.

## Contexto

CeliacMap usa HTML/CSS/JavaScript, Leaflet y Supabase. Su responsable desarrolla como persona física y necesita demostrar paridad con la web ante la Intendencia y posibles financiadores, con mínimo costo y sin duplicar interfaces.

## Decisión

- PWA instalable primero, conservando carpetas; extraer únicamente lógica pura necesaria con tests. Después, Capacitor Android con assets locales y APK para demos; Play prueba interna es opcional.
- Paridad web más «Cerca mío»: ubicación puntual solo al tocar, en memoria, nunca enviada al backend/modelo ni persistida. Sin seguimiento, cuentas, fotos o push.
- Una rama por tarea, PR y CI obligatorios; Pages publica solo después de la suite completa aprobada. El responsable activa la protección de `main`.
- Publicación pública, iOS y cuenta de organización quedan para después de una posible financiación. No se exige un build iOS ahora.
- Auditoría Google solo documental: no bloquea el piloto por decisión de alcance; sí condiciona publicar en tiendas y no crea una excepción contractual. CARTO se presupone comercial por los aliados.

## Consecuencias positivas

Conserva web, backend, branding y gran parte de la UI; PWA/APK no exigen matrícula de tienda. Permite validar la demo antes de reorganizar el repo o invertir en iOS.

## Consecuencias negativas / trade-offs

Capacitor renderiza una WebView: mapa, teclado, permisos y clave de tiles necesitan QA físico. iOS sigue sin validación. La licencia de datos requiere decisión posterior; el servidor de tiles puede inferir la zona visualizada aunque no reciba el GPS explícito.

**Actualización 2026-10-03:** la fase Capacitor se implementó en `apps/mobile/` (no en la raíz), sin plugin de geolocalización y sin beacon de analítica; ver [decisión](../DECISIONS.md#android-demo-app-with-capacitor-2026-10-03) y [runbook del APK](../runbooks/apk-demo.md).

Detalle: [plan del piloto](../plans/PLAN-mobile-app.md). Diagramas: [evolución propuesta, no desplegada](C4-diagrams.md#evolución-propuesta--piloto-móvil-adr-010).
