# Diagramas de Arquitectura C4 — CeliacMap

## Nivel 1 — Contexto del sistema

```mermaid
flowchart TB
    usuario["👤 Persona celíaca<br/><i>Busca lugares sin TACC<br/>confiables en Argentina y Uruguay</i>"]
    colaborador["👤 Colaborador de la comunidad<br/><i>Sugiere nuevos lugares<br/>vía formulario público</i>"]

    celiacmap["🗺️ <b>CeliacMap</b><br/><i>Plataforma web que identifica, valida<br/>y muestra lugares sin TACC confiables</i>"]

    anthropic[["Anthropic API<br/><i>Claude Haiku (descubrimiento)<br/>y Sonnet (juicio de seguridad)</i>"]]
    google[["Google Places API<br/><i>Búsqueda determinística<br/>de comercios</i>"]]
    tavily[["Tavily API<br/><i>Descubrimiento de menciones<br/>en redes sociales</i>"]]
    resend[["Resend API<br/><i>Envío y recepción de<br/>email transaccional (Outreach)</i>"]]
    github_actions[["GitHub Actions<br/><i>Orquesta el pipeline<br/>de forma mensual</i>"]]

    usuario -->|"Consulta el mapa<br/>HTTPS"| celiacmap
    colaborador -->|"Sugiere un lugar<br/>HTTPS/Formulario"| celiacmap

    celiacmap -->|"Valida y clasifica<br/>candidatos"| anthropic
    celiacmap -->|"Busca comercios<br/>candidatos"| google
    celiacmap -->|"Busca menciones<br/>sociales"| tavily
    celiacmap -->|"Envía email de<br/>confirmación"| resend
    resend -->|"Notifica respuesta<br/>del comercio, webhook"| celiacmap
    github_actions -->|"Ejecuta el pipeline<br/>mensualmente"| celiacmap

    style celiacmap fill:#1168bd,color:#fff
    style usuario fill:#08427b,color:#fff
    style colaborador fill:#08427b,color:#fff
    style anthropic fill:#999,color:#fff
    style google fill:#999,color:#fff
    style tavily fill:#999,color:#fff
    style resend fill:#999,color:#fff
    style github_actions fill:#999,color:#fff
```

## Nivel 2 — Contenedores

```mermaid
flowchart TB
    usuario["👤 Persona celíaca"]

    anthropic[["Anthropic API"]]
    google[["Google Places API"]]
    tavily[["Tavily API"]]
    resend[["Resend API<br/><i>Envío y recepción de<br/>email transaccional</i>"]]
    github_actions[["GitHub Actions<br/><i>Cron mensual +<br/>repository_dispatch</i>"]]

    subgraph celiacmap["CeliacMap [SYSTEM]"]
        frontend["<b>Frontend estático</b><br/><i>HTML/CSS/JS + Leaflet.js</i><br/>Mapa interactivo + ranking<br/>comunitario, servido por<br/>GitHub Pages, sin build step"]
        pipeline["<b>Pipeline de agentes</b><br/><i>Python</i><br/>Search, Social, Web, Suggestion,<br/>Validator, Updater y Outreach<br/>(7 etapas) + Reply Handler<br/>(on-demand, vía dispatch)"]
        edge_function["<b>Edge Function</b><br/><i>Deno/TypeScript</i><br/>outreach-reply: recibe webhooks<br/>de Resend, dispara repository_dispatch"]
        mcp["<b>MCP Server</b><br/><i>Python/FastMCP</i><br/>Expone 6 tools para interactuar<br/>con los datos validados"]
        db[("<b>Base de datos</b><br/><i>Supabase (PostgreSQL)</i><br/>Lugares validados, sugerencias,<br/>reportes, votos comunitarios,<br/>estado del rubric de 3 niveles")]
    end

    usuario -->|"Navega el mapa<br/>HTTPS"| frontend
    usuario -->|"Envía sugerencia / reporte<br/>Formulario"| frontend
    usuario -->|"Vota un lugar<br/>1 click"| frontend
    frontend -->|"Lee/escribe<br/>REST"| db

    pipeline -->|"Lee/escribe lugares<br/>y estado, REST"| db
    pipeline -->|"Descubre (Haiku) y<br/>valida (Sonnet), API"| anthropic
    pipeline -->|"Busca candidatos<br/>API"| google
    pipeline -->|"Busca menciones<br/>sociales, API"| tavily
    pipeline -->|"Envía email de<br/>confirmación, API"| resend

    resend -->|"email.received<br/>webhook"| edge_function
    edge_function -->|"Persiste reply,<br/>flip outreach_status, REST"| db
    edge_function -->|"repository_dispatch<br/>(outreach_reply_received)"| github_actions
    github_actions -->|"Ejecuta<br/>outreach_reply_handler.py"| pipeline
    github_actions -->|"Orquesta mensualmente<br/>cron"| pipeline

    mcp -->|"Consulta datos<br/>validados, REST"| db

    style frontend fill:#1168bd,color:#fff
    style pipeline fill:#1168bd,color:#fff
    style edge_function fill:#1168bd,color:#fff
    style mcp fill:#1168bd,color:#fff
    style db fill:#1168bd,color:#fff
    style usuario fill:#08427b,color:#fff
    style anthropic fill:#999,color:#fff
    style google fill:#999,color:#fff
    style tavily fill:#999,color:#fff
    style resend fill:#999,color:#fff
    style github_actions fill:#999,color:#fff
```

**Nota — ranking comunitario (ADR-005).** El ranking "Los favoritos de la
comunidad" (`js/ranking.js`, dentro del contenedor *Frontend estático*) lee el
top-12 por país del **mismo endpoint anon de `places`** que ya usa el mapa
(vía la columna denormalizada `places.vote_count`) y escribe un voto como un
`POST` plano a la tabla `place_votes` (anon, INSERT-only). El contador se
mantiene con un trigger de base de datos (`sync_place_vote_count`,
`SECURITY DEFINER`) — **sin agente, sin LLM, sin GitHub Actions, sin Edge
Function**: en el diagrama, el borde `frontend → db` simplemente pasa a cubrir
también la escritura de votos.
