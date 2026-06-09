# CeliacMap MCP Server

Servidor MCP (Model Context Protocol) propio del proyecto CeliacMap.
Permite que cualquier cliente compatible — Claude Desktop, Claude Code, agentes
externos — interactúe con la base de datos de lugares sin TACC / gluten free
mediante **herramientas declarativas**.

Reutiliza la lógica canónica del proyecto (no la duplica): el `RUBRIC` y la
normalización del `ValidatorAgent`, y los clientes `SupabaseClient` /
`GooglePlacesClient` / `LLMClient` de `agents/`. Así el MCP nunca se desincroniza
del pipeline diario, y usa el esquema real de `db/schema.sql`.

## Herramientas disponibles

| Tool | Descripción |
|------|-------------|
| `search_places` | Busca lugares **approved** por ciudad y término opcional |
| `get_place_detail` | Obtiene el detalle completo de un lugar por ID (UUID) |
| `validate_place` | Aplica el rubric del Validator sobre evidencia nueva (verdict + confidence_score + flags + recommendation; reporta el `db_status` resultante) |
| `suggest_place` | Sugiere un lugar nuevo: lo geocodifica con Find Place y lo inserta como `pending` (`source='user'`) |
| `get_map_stats` | Estadísticas del mapa (totales por estado y país) |
| `list_pending_reviews` | Lista lugares en `needs_review` (confianza < 0.7) esperando revisión humana |

## Esquema y rubric

- **Estados** (`places.status`): `pending` → `approved` / `discarded` / `needs_review`.
  El mapa muestra solo `approved`; `needs_review` es la cola de revisión humana.
- **Veredicto del Validator**: `approved` (confidence_score ≥ 0.85) /
  `needs_review` (0.5–0.85, o cualquier confianza < 0.7) / `rejected` (< 0.5).
  Ver el rubric completo en
  [`skills/validator-rubric/SKILL.md`](../skills/validator-rubric/SKILL.md) y en
  `agents/validator_agent.py` (`RUBRIC`).

## Instalación

```bash
pip install -r ../requirements.txt   # incluye fastmcp + supabase + anthropic + googlemaps
```

Variables de entorno requeridas (`.env` en la raíz del repo — las mismas que usan
los agentes, no hay variables nuevas):

```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
ANTHROPIC_API_KEY=...          # validate_place
GOOGLE_MAPS_API_KEY=...        # suggest_place (geocoding vía Find Place)
```

## Ejecutar en desarrollo

```bash
python mcp_server/server.py
```

## Conectar desde Claude Desktop

Agregar en `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "celiacmap": {
      "command": "python",
      "args": ["/ruta/absoluta/al/mcp_server/server.py"]
    }
  }
}
```

Reiniciar Claude Desktop. Las tools aparecen disponibles automáticamente en la
conversación.

## Conectar desde Claude Code

```bash
claude mcp add celiacmap python /ruta/al/mcp_server/server.py
```

## Patrón de implementación

Siguiendo el patrón FastMCP con decoradores Python:

```python
@mcp.tool()
def validate_place(name: str, address: str, city: str, evidence: str) -> str:
    """El docstring es la descripción del tool.
    Los type hints definen el schema de entrada.
    """
    ...
```

El docstring actúa como descripción del tool para el modelo de lenguaje.
Los type hints de Python se convierten automáticamente en el JSON Schema de entrada.

## Arquitectura en el pipeline

```
GitHub Actions (09:00 UTC)
    │
    ├── Search Agent      → Google Places (determinístico)
    ├── Social Agent      → Instagram/Facebook vía Tavily + Haiku
    ├── Web Agent (v3)    → Anthropic web search (autónomo)
    ├── Validator Agent   → rubric de salud (claude-sonnet-4-6)
    └── Updater Agent     → re-verifica lugares existentes
            │
            ▼
    Supabase (PostgreSQL + RLS)
            │
            ▼
    MCP Server  ←──── Claude Desktop / Claude Code / Agentes externos
            │
            ▼
    Frontend (Leaflet.js + GitHub Pages)
```
