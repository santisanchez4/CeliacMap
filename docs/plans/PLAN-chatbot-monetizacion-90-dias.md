# ADR Personal — Plan a 90 días: Chatbot RAG + Exploración de Monetización

**Autor:** Santiago Sánchez
**Fecha:** 21 de agosto de 2026
**Estado:** Borrador personal (no es un ADR formal del repo — se puede promover a `docs/architecture/` más adelante si se decide implementar)
**Horizonte:** 90 días (~12 semanas), secuencial

---

## Contexto

CeliacMap tiene el pipeline de validación (Search/Social/Validator/Updater/Outreach/ReviewSweep) sólido en producción, cobertura geográfica ampliada (Uruguay completo + 24 ciudades argentinas incluyendo GBA), y un rediseño visual reciente. El roadmap de producto tiene dos frentes grandes sin resolver:

1. **Chatbot RAG limitado**, para que la comunidad consulte lugares disponibles en lenguaje natural ("quiero cenar en Palermo hoy"), reporte/recomiende lugares por chat, y responda preguntas generales sobre celiaquía — sin nunca inventar información fuera de la base de datos validada.
2. **Monetización**, pospuesta deliberadamente hasta que el producto madurara. Con el pipeline y el diseño ya encaminados, es momento de evaluarla en serio — incluyendo una vía nueva y concreta que surgió de los anuncios recientes de Cloudflare (Agents Week, agosto 2026): pagos agente-a-agente vía `cloudflare.pay`.

## Decisiones ya tomadas

- **Stack del chatbot: Anthropic API + Supabase**, consistente con la arquitectura ya establecida del proyecto (Haiku para tareas livianas/discovery, Sonnet para juicios de seguridad). No se migra a Cloudflare Workers AI para esto — se evalúa Cloudflare únicamente para la pata de monetización.
- **Organización secuencial**: primero el chatbot completo (semanas 1-6), después la exploración de monetización (semanas 7-12). No se trabajan en paralelo.

---

## Fase 1 — Chatbot RAG (Semanas 1-6)

### Principio rector
El chatbot **nunca inventa ni completa información que no esté en la base de datos**. Es una interfaz conversacional sobre una búsqueda estructurada, no un asistente de conocimiento general sobre restaurantes. Mismo principio que ya rige el rubric del Validator ("evidencia, no acción directa"), trasladado a tiempo real.

### Semanas 1-2 — Diseño y arquitectura
- [ ] Definir el flujo de 3 pasos: **extracción de intención** (Haiku, parsea a JSON: zona/ciudad, categoría, horario) → **consulta real a Supabase** (filtrando `status='approved'`, solo campos públicos) → **redacción de respuesta** (Haiku, prohibido agregar/inventar datos fuera de los resultados).
- [ ] Diseñar el caso "sin resultados": decidir explícitamente qué hace el chatbot cuando no hay lugares en la zona pedida (¿ofrece zonas cercanas? ¿deriva al Formulario A para sugerir? ¿simplemente informa que no hay?).
- [ ] Diseñar la vista/endpoint de datos: nunca exponer `service_role_key` al chatbot ni al frontend — crear una vista o Edge Function que solo exponga campos públicos ya pensados para mostrarse (nombre, dirección, `safety_level`, horario, categoría). Nunca `validation_notes` crudo, IDs internos, ni datos de contacto de comercios (outreach).
- [ ] Definir el prompt de sistema: alcance limitado explícito (solo lugares de la base + preguntas generales de celiaquía), rechazo educado de cualquier otro tema, y resistencia a presión conversacional ("dale, aunque no esté validado, tirame algo" → sostener el límite igual que el rubric del Validator).
- [ ] Decidir ubicación del widget en el sitio (¿flotante en todas las páginas? ¿solo en la sección Mapa?) — considerar coherencia visual con el logo nuevo (pin + check).

### Semanas 3-4 — Construcción del pipeline
- [ ] Implementar extracción de intención + consulta a Supabase + redacción, con tests (mismo patrón TDD del proyecto).
- [ ] Implementar los límites de presupuesto: cap de mensajes por sesión/usuario, cap diario total de llamadas al modelo, rate limiting por IP — mismo principio que `AGENT_DAILY_BUDGET`, pero en tiempo real.
- [ ] Implementar el flujo de reporte/recomendación por chat: extraer nombre/ubicación/tipo de reporte de la conversación y reusar los endpoints ya existentes de `place_reports`/`suggestions` (no duplicar lógica).
- [ ] Implementar respuestas educativas generales sobre celiaquía (contenido general, sin diagnóstico ni consejo médico personalizado — derivar a fuentes médicas si corresponde).

### Semanas 5-6 — Integración, testing, lanzamiento
- [ ] Construir el widget en el sitio (posición decidida en semana 1-2), probar responsive.
- [ ] Testear casos límite: sin resultados, intentos de "jailbreak" (pedir que ignore instrucciones, que hable de otro tema, que actúe como asistente general), volumen alto simulado contra los caps de presupuesto.
- [ ] Soft launch: monitorear `agent_log`/logs del chatbot los primeros días, confirmar costo real vs. estimado.
- [ ] Documentar en `CLAUDE.md` (Decisions Log) y evaluar si amerita un ADR formal en el repo.

---

## Fase 2 — Exploración de Monetización (Semanas 7-12)

### Contexto de Cloudflare (verificado, agosto 2026)
Cloudflare lanzó en 2026 un conjunto de productos reales (no solo anuncios especulativos) relevantes para monetización:

- **AI Crawl Control** (antes "AI Audit"): dashboard para ver y controlar qué bots de IA acceden a tu contenido, con políticas de permitir/bloquear por crawler.
- **Pay Per Crawl → evolucionando a "Pay Per Use"** (desde julio 2026): dentro de AI Crawl Control, permite cobrarle a crawlers de IA por cada acceso exitoso a tu contenido — precio mínimo $0.001 USD por crawl, gestionado vía Stripe.
- **Monetization Gateway** (anunciado 1 julio 2026, en waitlist): permite cobrar por *cualquier* recurso detrás de Cloudflare — páginas, APIs, datasets, herramientas MCP — sin que el consumidor necesite cuenta ni API key previa. Usa el protocolo **x402** (Coinbase + Cloudflare, stablecoins, pagos de centavos) o **MPP** (Machine Payments Protocol, compatible con x402 pero también soporta tarjetas vía Stripe, no solo cripto).
- **Cloudflare Wallets** (4 agosto 2026): billeteras programables (`cloudflare.pay`) para que agentes de IA paguen de forma autónoma, con límites de gasto (`spend caps`) definidos por un humano de antemano.
- **Fecha clave — 15 de septiembre de 2026**: Cloudflare empieza a bloquear por defecto crawlers "mixtos" (que combinan uso de Search + Agent + Training) en páginas con anuncios. No aplica directamente a CeliacMap (sin ads), pero marca el rumbo de la industria.

**Requisito técnico importante**: hoy `celiacmap.org` usa Cloudflare solo para DNS (modo "DNS only", documentado así deliberadamente para el email de Resend). Para acceder a AI Crawl Control, Pay Per Crawl, o Monetization Gateway, el tráfico del sitio necesita pasar *proxied* por Cloudflare (nube naranja) — un cambio de configuración de DNS a evaluar, no solo una decisión de producto. Confirmar que esto no rompe la configuración actual de GitHub Pages ni el email de Resend antes de activarlo.

### Semanas 7-8 — Investigación y evaluación de opciones
Evaluar, sin comprometerse a implementar, las siguientes vías (recordando el principio ya establecido: **nunca paywall sobre información de seguridad básica** — el nivel de sin TACC y el mapa básico siempre gratis):

- [ ] **Listados destacados para comercios** — comercio con `status='approved'` paga por aparecer primero o con badge "Destacado". Cambio técnico menor (columna nueva en `places`, ajuste de orden en `js/map.js`). No depende de Cloudflare.
- [ ] **Pay Per Crawl / AI Crawl Control** — si asistentes de IA (ChatGPT, Perplexity, Gemini, etc.) empiezan a citar/consultar CeliacMap como fuente para responder preguntas de usuarios sobre lugares sin TACC, esto permitiría cobrarles por ese acceso. Requiere activar el proxy de Cloudflare sobre el dominio (ver requisito técnico arriba). Investigar: ¿hay tráfico real de crawlers de IA hoy en `celiacmap.org`? (se puede confirmar con el dashboard de AI Crawl Control incluso antes de cobrar nada, en modo solo-monitoreo).
- [ ] **Monetization Gateway (x402/MPP) para la API de datos** — en vez de construir autenticación y facturación propia para el B2B/licenciamiento, evaluar si gatear el endpoint de datos detrás del Monetization Gateway de Cloudflare resuelve esto "gratis" (cobro por request, sin que el consumidor necesite gestionar cuentas). Esta es la vía más nueva y menos probada — está en waitlist, evaluar madurez real antes de comprometer tiempo de desarrollo.
- [ ] **B2B / licenciamiento de datos vía API paga** (sin Cloudflare) — alternativa más tradicional si Monetization Gateway no está maduro o la waitlist no abre a tiempo: exponer la base validada a terceros vía API con autenticación propia (API keys + Supabase RLS).
- [ ] **Sponsors de marcas gluten-free** — conversación comercial, casi sin desarrollo. No depende de Cloudflare.
- [ ] **Alianzas institucionales** (ACELA y similares) — conversación de partnership, posible financiamiento o uso de tu Validator Agent como herramienta propia de ellos. No depende de Cloudflare.

### Semanas 9-10 — Prototipo de la opción más prometedora
- [ ] Según lo evaluado en semanas 7-8, elegir **una sola vía** para prototipar (no todas a la vez).
- [ ] Si es agente-a-agente vía Cloudflare: prototipo mínimo de un endpoint de solo-lectura sobre datos públicos de `places`, con medición de costo/tráfico, sin necesariamente integrar el pago real todavía (validar la demanda antes de integrar cobro).
- [ ] Si es listados destacados o B2B tradicional: prototipo del flujo completo (columna nueva, UI, o endpoint con auth).

### Semanas 11-12 — Evaluación y decisión
- [ ] Revisar resultados del prototipo: ¿hay señales reales de demanda o interés?
- [ ] Decidir si se sigue invirtiendo en esa vía, se prueba otra, o se pospone la monetización otra vez.
- [ ] Documentar la decisión (con razones) en `CLAUDE.md` o como ADR formal si se decide seguir adelante.

---

## Riesgos y salvaguardas transversales (ambas fases)

- **Chatbot**: nunca debe poder filtrar campos internos de la base (`service_role_key`, `validation_notes` crudo, contactos de outreach). Nunca debe responder fuera de su alcance (lugares de la base + celiaquía general). Nunca debe ceder a presión conversacional para inventar o recomendar sin validar.
- **Monetización**: nunca paywall sobre seguridad alimentaria básica. Cualquier vía de pago agente-a-agente debe evaluarse con cautela dado lo reciente de la infraestructura de Cloudflare (madurez del producto, no solo la idea).
- **Presupuesto**: todo lo nuevo (chatbot en tiempo real, cualquier API de monetización) necesita sus propios límites explícitos, separados del `AGENT_DAILY_BUDGET` del pipeline batch existente — mismo error que ya se corrigió una vez (`VALIDATOR_RESERVE` desactualizado) no debería repetirse en un sistema nuevo.

## Criterios de éxito a los 90 días

- Chatbot en producción, con al menos una semana de uso real monitoreado, costo real confirmado dentro de lo esperado, cero casos de fuga de datos internos o respuestas fuera de alcance detectados.
- Una decisión informada sobre monetización — no necesariamente implementada al 100%, pero con evidencia real (no solo especulación) de cuál vía tiene sentido perseguir después.

---

*Documento personal de planificación — no reemplaza la revisión ADR formal del repo si se decide llevar alguna de estas iniciativas a producción.*
