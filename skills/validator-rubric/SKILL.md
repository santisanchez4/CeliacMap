---
name: validator-rubric
description: >
  Aplicar el rubric conservador del Validator Agent de CeliacMap para evaluar
  si un establecimiento puede clasificarse como gluten free / sin TACC.
  Usar siempre que se necesite evaluar evidencia sobre un lugar y decidir si
  aprobarlo, rechazarlo o escalarlo a revisión humana. La seguridad del
  usuario celíaco es la prioridad absoluta: nunca sobreestimar la seguridad.
---

# Validator Rubric — CeliacMap

## Propósito

Este skill encapsula el criterio de evaluación del Validator Agent de CeliacMap.
Su función es determinar si un establecimiento ofrece opciones **genuinamente seguras** para personas celíacas, basándose en evidencia pública recopilada.

**Principio rector:** ante la duda, nunca aprobar. La salud depende de este criterio.

> **Fuente de verdad:** el texto exacto del prompt vive en la constante `RUBRIC`
> de [`agents/validator_agent.py`](../../agents/validator_agent.py). Este documento
> describe el criterio; el código lo aplica. Mantener ambos en sincronía.

---

## Escala de confianza y mapeo de estado

El veredicto se mapea al estado en la base de datos de forma **aditiva** (sin
renombrar los estados existentes): `rejected` reutiliza `discarded`, y
`needs_review` es la cola de revisión humana (oculta del mapa).

| confidence_score | Veredicto | Estado en DB (`places.status`) | Acción |
|------------------|-----------|--------------------------------|--------|
| `>= 0.85` | `approved` | `approved` | Publicar en el mapa |
| `0.50 – 0.84` | `needs_review` | `needs_review` | Escalar a revisión humana |
| `< 0.50` | `rejected` | `discarded` | No publicar, registrar motivo |

> **Piso de seguridad (regla de oro):** cualquier `confidence_score < 0.7` se
> fuerza a `needs_review` en el código (`ValidatorAgent._decide_status`), sin
> importar el veredicto que devuelva el modelo. La aprobación automática exige
> `>= 0.85`. La salud del usuario celíaco es más importante que tener más lugares
> en el mapa.

---

## Criterios de aprobación (`confidence_score >= 0.85`)

Para llegar a este umbral, la evidencia debe incluir **al menos uno** de:

- ✅ Mención explícita de **"sin TACC"** (no solo "sin gluten", que puede ser marketing)
- ✅ Certificación reconocida por ACELA u organismo equivalente
- ✅ Descripción de protocolo anti-contaminación cruzada
- ✅ Menú dedicado sin TACC con descripción de preparación segura
- ✅ Múltiples reseñas positivas recientes de usuarios que se identifican como celíacos
- ✅ Comunicación oficial del establecimiento confirmando opciones sin TACC

---

## Flags de alerta — reducen la confianza

Cada flag detectado reduce el score y puede bajar el veredicto:

| Flag | Impacto |
|------|---------|
| Solo dice "sin gluten" sin "sin TACC" | Moderado — puede ser marketing sin respaldo médico |
| No menciona contaminación cruzada | Alto — riesgo real para celíacos severos |
| Solo tiene opciones veganas/vegetarianas | Bajo — no implica sin TACC necesariamente |
| Información con más de 12 meses de antigüedad | Moderado — puede haber cambiado |
| Reseñas negativas de celíacos | Alto — prioridad inmediata |
| Descripción ambigua ("apto para dietas especiales") | Moderado |
| Establecimiento sin presencia verificable online | Alto |

---

## Diferencia clave: "sin gluten" vs "sin TACC"

> **"Sin gluten"** puede referirse a cualquier preparación que no usa trigo como ingrediente principal.
> **"Sin TACC"** (Sin Trigo, Avena, Cebada, Centeno) es el estándar médico para celíacos en Argentina y Uruguay e implica control de contaminación cruzada.

Un lugar que solo usa la etiqueta "sin gluten" **no debe aprobarse automáticamente**.

---

## Salida estructurada

El Validator responde ÚNICAMENTE con un objeto JSON (sin prosa, sin markdown).
Además del veredicto del rubric, CeliacMap conserva `category` y `safety_level`
porque el esquema los requiere y el mapa los usa para los badges de seguridad:

```json
{
  "verdict": "approved" | "rejected" | "needs_review",
  "confidence_score": 0.0,
  "category": "restaurant" | "cafe" | "shop",
  "safety_level": "gluten_free_100" | "celiac_friendly" | "options_available",
  "reasoning": "<explicación en español>",
  "flags": ["<flag>"],
  "recommendation": "<acción sugerida>"
}
```

Persistencia: `confidence_score` → `validation_confidence`, `reasoning` →
`validation_notes`, y `flags` / `recommendation` en sus columnas propias.

---

## Modelo recomendado

- **Caso estándar:** `claude-sonnet-4-6` — balance costo/calidad óptimo
- **Caso de baja confianza (< 0.7):** escalar a `claude-opus-4-8` para revisión más profunda *(funcionalidad planificada)*

---

## Integración en el pipeline

El rubric se aplica en `agents/validator_agent.py` y se expone on-demand vía el
MCP server (`mcp_server/server.py`, tool `validate_place`). Ambos comparten la
**misma** constante `RUBRIC` y la misma normalización, así que el criterio es
idéntico en batch y on-demand:

```python
# agents/validator_agent.py — esquema del flujo
raw = llm.complete_json(RUBRIC, user_prompt, model="claude-sonnet-4-6")
v = self._normalize(raw, place)        # parsea + clamp + flags + decide estado

# _decide_status (defensa en profundidad, code-enforced):
#   verdict == "rejected" or confidence < 0.50  -> "discarded"
#   verdict == "approved" and confidence >= 0.85 -> "approved"
#   en cualquier otro caso (incl. < 0.70)        -> "needs_review"
self.db.update_place_validation(place_id, status=v["status"], ...)
```

---

## Por qué este rubric es el núcleo del proyecto

La automatización (búsqueda, scraping, pipelines) es infraestructura.
**El rubric es el juicio.** Es donde el proyecto toma una decisión que afecta a personas reales con una condición médica. Ahí está la contribución real de la IA: no en ejecutar tareas, sino en aplicar criterio con responsabilidad.
