"""
CeliacMap MCP Server
====================
Servidor MCP propio del proyecto CeliacMap.
Expone herramientas (tools) que permiten a cualquier cliente MCP compatible
(Claude Desktop, Claude Code, agentes externos) interactuar con la base de
datos de lugares sin TACC / gluten free.

Diseño:
  * Reutiliza la lógica canónica del proyecto en lugar de duplicarla: el rubric
    del Validator (``agents.validator_agent.RUBRIC``), la normalización de
    veredictos (``ValidatorAgent._normalize`` / ``_decide_status``) y los clientes
    ``SupabaseClient`` / ``GooglePlacesClient`` / ``LLMClient``. Así el MCP nunca
    se desincroniza del pipeline diario.
  * Usa el esquema real de ``db/schema.sql`` (``category``, ``safety_level``,
    ``validation_confidence``, ``status`` in pending/approved/discarded/needs_review).

Ejecutar en modo desarrollo:
    pip install fastmcp supabase anthropic googlemaps python-dotenv PyYAML
    python mcp_server/server.py

Conectar desde Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "celiacmap": {
          "command": "python",
          "args": ["/ruta/absoluta/a/mcp_server/server.py"]
        }
      }
    }
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Allow `from agents...` / `from config...` when launched as a standalone script
# (Claude Desktop runs it by absolute path, so the repo root is not on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP

from agents.clients.google_places import GooglePlacesClient
from agents.clients.llm import LLMClient
from agents.clients.supabase_client import SupabaseClient
from agents.validator_agent import RUBRIC, ValidatorAgent
from config.settings import get_settings

# ── Inicialización ──────────────────────────────────────────────────────────
mcp = FastMCP(
    name="celiacmap",
    instructions=(
        "Servidor MCP de CeliacMap. "
        "Permite buscar, validar y gestionar lugares gluten free / sin TACC "
        "en Uruguay y Argentina. "
        "Úsalo para consultar la base de datos, validar evidencia con el rubric "
        "conservador del Validator, enviar lugares a revisión y obtener "
        "estadísticas del mapa."
    ),
)


# ── Fábricas perezosas (no construir clientes en import) ────────────────────
@lru_cache(maxsize=1)
def _settings():
    return get_settings()


@lru_cache(maxsize=1)
def _db() -> SupabaseClient:
    s = _settings()
    s.require("supabase_url", "supabase_service_role_key")
    return SupabaseClient(s.supabase_url, s.supabase_service_role_key)


@lru_cache(maxsize=1)
def _validator() -> ValidatorAgent:
    s = _settings()
    s.require("anthropic_api_key")
    llm = LLMClient(s.anthropic_api_key, s.validator_model)
    return ValidatorAgent(_db(), llm)


@lru_cache(maxsize=1)
def _places() -> GooglePlacesClient:
    s = _settings()
    s.require("google_maps_api_key")
    return GooglePlacesClient(s.google_maps_api_key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── TOOL 1: Buscar lugares ──────────────────────────────────────────────────
@mcp.tool()
def search_places(
    city: str,
    query: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Busca lugares gluten free / sin TACC publicados en una ciudad.

    Solo devuelve lugares con status 'approved' (los que se muestran en el mapa).

    Args:
        city: Ciudad a buscar (ej: "Montevideo", "Buenos Aires").
        query: Término adicional de búsqueda por nombre (ej: "pizza", "panadería").
        limit: Cantidad máxima de resultados (máximo 50).

    Returns:
        JSON con lista de lugares: nombre, dirección, coordenadas, categoría,
        safety_level, confianza de validación y estado.
    """
    q = (
        _db()._db.table("places")
        .select(
            "id, name, address, city, country, lat, lng, category, "
            "safety_level, validation_confidence, status, updated_at"
        )
        .eq("status", "approved")
        .ilike("city", f"%{city}%")
        .limit(min(limit, 50))
    )
    if query:
        q = q.ilike("name", f"%{query}%")

    places = q.execute().data or []
    return json.dumps(
        {"count": len(places), "city": city, "places": places},
        ensure_ascii=False,
        indent=2,
        default=str,
    )


# ── TOOL 2: Obtener detalle de un lugar ────────────────────────────────────
@mcp.tool()
def get_place_detail(place_id: str) -> str:
    """Obtiene el detalle completo de un lugar específico por su ID.

    Args:
        place_id: ID único del lugar en la base de datos de CeliacMap (UUID).

    Returns:
        JSON con todos los campos del lugar: fuentes, evidencia de validación
        (validation_confidence / validation_notes / flags / recommendation),
        provenance e historial.
    """
    result = (
        _db()._db.table("places").select("*").eq("id", place_id).single().execute()
    )
    if not result.data:
        return json.dumps({"error": f"Lugar con id '{place_id}' no encontrado."})
    return json.dumps(result.data, ensure_ascii=False, indent=2, default=str)


# ── TOOL 3: Validar un lugar con el rubric del Validator Agent ─────────────
@mcp.tool()
def validate_place(
    name: str,
    address: str,
    city: str,
    evidence: str,
) -> str:
    """Valida si un lugar puede considerarse gluten free / sin TACC.

    Aplica el rubric conservador del Validator Agent de CeliacMap (el mismo que
    usa el pipeline diario). Nunca sobreestima la seguridad: la aprobación
    automática exige confidence_score >= 0.85; por debajo de 0.7 el resultado es
    siempre 'needs_review' en lugar de aprobar.

    Args:
        name: Nombre del establecimiento.
        address: Dirección completa.
        city: Ciudad donde se encuentra.
        evidence: Texto con la evidencia recopilada (posts, sitio web,
                  descripciones de Google Maps, reseñas, etc.).

    Returns:
        JSON con: verdict (approved | rejected | needs_review), confidence_score,
        category, safety_level, reasoning, flags, recommendation, y db_status
        (el estado al que se mapearía en la base de datos).
    """
    agent = _validator()
    place = {"name": name, "address": address, "city": city, "category": None}

    user_prompt = (
        f"Valida el siguiente lugar:\n\n"
        f"Nombre: {name}\n"
        f"Dirección: {address}\n"
        f"Ciudad: {city}\n\n"
        f"Evidencia recopilada:\n{evidence}"
    )

    raw = agent.llm.complete_json(RUBRIC, user_prompt)
    v = agent._normalize(raw, place)

    result = {
        "verdict": v["verdict"],
        "confidence_score": v["confidence"],
        "category": v["category"],
        "safety_level": v["safety_level"],
        "reasoning": v["reason"],
        "flags": v["flags"],
        "recommendation": v["recommendation"],
        "db_status": v["status"],
        "validated_at": _now_iso(),
        "place_name": name,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── TOOL 4: Sugerir un lugar nuevo ─────────────────────────────────────────
@mcp.tool()
def suggest_place(
    name: str,
    city: str,
    country: str,
    evidence_url: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """Envía una sugerencia de nuevo lugar gluten free para revisión.

    El lugar se geocodifica con Google Find Place (para obtener coordenadas reales
    y un place_id canónico, igual que los agentes Social/Web), entra como
    status 'pending' con source 'user', y será evaluado por el Validator en el
    próximo pipeline diario antes de publicarse en el mapa.

    Args:
        name: Nombre del establecimiento.
        city: Ciudad.
        country: País ("Uruguay" o "Argentina").
        evidence_url: URL de referencia (Instagram, Google Maps, sitio web).
        notes: Notas adicionales del usuario que sugiere el lugar.

    Returns:
        JSON con el ID de la sugerencia y el estado de la operación.
    """
    resolved = _places().find_place(f"{name} {city}")
    if not resolved or not resolved.get("place_id"):
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"No se pudo geocodificar '{name}' en {city}. "
                    "No se registró (el mapa requiere coordenadas reales)."
                ),
            },
            ensure_ascii=False,
        )

    external_id = resolved["place_id"]
    if _db().place_exists_by_external_id(external_id):
        return json.dumps(
            {
                "success": True,
                "message": f"'{name}' ya está en la base de datos (no duplicado).",
                "status": "already_known",
                "external_id": external_id,
            },
            ensure_ascii=False,
        )

    candidate = GooglePlacesClient.to_candidate(resolved, country=country, city=city)
    candidate.update(
        {
            "source": "user",
            "category": "restaurant",          # provisional; el Validator lo corrige
            "safety_level": "options_available",  # piso conservador por defecto
            "social_url": evidence_url,
            "validation_notes": notes,
        }
    )

    inserted = _db().insert_place_candidate(candidate)
    if inserted:
        return json.dumps(
            {
                "success": True,
                "message": f"Sugerencia recibida. '{name}' será revisado en el próximo pipeline diario.",
                "suggestion_id": inserted.get("id"),
                "status": "pending",
                "external_id": external_id,
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {"success": False, "error": "No se pudo registrar la sugerencia."},
        ensure_ascii=False,
    )


# ── TOOL 5: Estadísticas del mapa ──────────────────────────────────────────
@mcp.tool()
def get_map_stats() -> str:
    """Retorna estadísticas generales del mapa de CeliacMap.

    No requiere argumentos.

    Returns:
        JSON con totales de lugares desglosados por estado (pending / approved /
        discarded / needs_review) y por país.
    """
    places = _db()._db.table("places").select("status, country, city").execute().data or []

    stats: dict = {"total": len(places), "by_status": {}, "by_country": {}}
    for p in places:
        status = p.get("status", "unknown")
        country = p.get("country", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        stats["by_country"][country] = stats["by_country"].get(country, 0) + 1

    return json.dumps(stats, ensure_ascii=False, indent=2)


# ── TOOL 6: Listar lugares pendientes de revisión humana ───────────────────
@mcp.tool()
def list_pending_reviews(limit: int = 20) -> str:
    """Lista lugares con status 'needs_review' que esperan revisión humana.

    Son los casos donde el Validator no tuvo suficiente confianza (< 0.7) para
    aprobar o rechazar automáticamente.

    Args:
        limit: Máximo de lugares a retornar (máximo 50).

    Returns:
        JSON con lista de lugares pendientes, ordenados por validation_confidence
        ascendente (los más dudosos primero), con sus flags y recommendation.
    """
    places = (
        _db()._db.table("places")
        .select(
            "id, name, address, city, country, validation_confidence, "
            "validation_notes, flags, recommendation, updated_at"
        )
        .eq("status", "needs_review")
        .order("validation_confidence", desc=False)
        .limit(min(limit, 50))
        .execute()
        .data
        or []
    )
    return json.dumps(
        {
            "count": len(places),
            "message": "Lugares ordenados por confianza ascendente (más dudosos primero).",
            "places": places,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
