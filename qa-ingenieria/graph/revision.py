"""Revisión de contenido (Fase 1) — schema de hallazgos + agregación de veredicto.

Complementa el gate de admisión (Fase 0): un doc YA admitido pasa por la revisión, que mide/chequea
su CALIDAD y produce un veredicto propio (aprobado / con notas / observado / rechazado). Ver
`docs/spec/SPEC_Cotejar_Fase1_Revision.md`. La agregación es DETERMINISTA (el LLM/VLM nunca decide
un bloqueante solo): la severidad de los hallazgos deriva el veredicto.
"""

from __future__ import annotations

from typing import Any, Optional, TypedDict

# Catálogos (str literales para serializar directo a JSON / YAML del template)
DIMENSIONES = ("legibilidad", "norma", "contenido", "consistencia")
SEVERIDADES = ("bloqueante", "mayor", "menor", "observacion")
ESTADOS = ("ok", "advertencia", "fallo", "no_verificable")
FUENTES = ("deterministico", "reglas", "vlm")

_SEV_RANK = {"bloqueante": 3, "mayor": 2, "menor": 1, "observacion": 0}


class Hallazgo(TypedDict, total=False):
    check_id: str
    dimension: str          # legibilidad | norma | contenido | consistencia
    severidad: str          # bloqueante | mayor | menor | observacion
    estado: str             # ok | advertencia | fallo | no_verificable
    ubicacion: dict         # {pagina, bbox?}
    evidencia: str          # qué se encontró / no se encontró
    razonamiento: str       # por qué
    sugerencia: str         # cómo corregir
    fuente: str             # deterministico | reglas | vlm
    norma_ref: str          # norma/cláusula que origina el chequeo (trazabilidad del vínculo)
    req_id: str             # id global del requisito "<norma>:<id>" (para el feedback por regla)
    estado_previo: str      # estado por TEXTO antes de que el VLM verificara la regla (marca el cambio)
    nota_vlm: str           # qué concluyó el VLM al verificar la regla (trazabilidad del override)


def mk(check_id: str, dimension: str, severidad: str, estado: str, *,
       razonamiento: str, fuente: str, evidencia: str = "", sugerencia: str = "",
       ubicacion: Optional[dict] = None, norma_ref: Optional[str] = None,
       req_id: Optional[str] = None) -> Hallazgo:
    """Construye un hallazgo normalizado (campos vacíos se omiten)."""
    h: Hallazgo = {"check_id": check_id, "dimension": dimension, "severidad": severidad,
                   "estado": estado, "razonamiento": razonamiento, "fuente": fuente}
    if evidencia:
        h["evidencia"] = evidencia
    if sugerencia:
        h["sugerencia"] = sugerencia
    if ubicacion:
        h["ubicacion"] = ubicacion
    if norma_ref:
        h["norma_ref"] = norma_ref
    if req_id:
        h["req_id"] = req_id
    return h


def agregar_revision(hallazgos: list[Hallazgo]) -> dict[str, Any]:
    """Severidad agregada -> veredicto (regla determinista, §5.3 del spec).

    - accionable DURO bloqueante           -> rechazado
    - accionable DURO mayor (sin bloqueante)-> observado
    - resto de accionables                  -> aprobado_con_notas
    - sin hallazgos accionables             -> aprobado

    "Accionable" = `estado` en (fallo, advertencia). "Duro" = fuente determinística/reglas (NO `vlm`):
    el VLM nunca bloquea por sí solo (§2.2), sus señales son a lo sumo "con notas" sin importar la
    severidad sugerida. `no_verificable` no es accionable, pero baja la confianza del dictamen.
    """
    accionables = [h for h in hallazgos if h.get("estado") in ("fallo", "advertencia")]
    duros = [h for h in accionables if h.get("fuente") != "vlm"]
    no_verif = [h for h in hallazgos if h.get("estado") == "no_verificable"]

    if any(h.get("severidad") == "bloqueante" for h in duros):
        verdicto = "rechazado"
    elif any(h.get("severidad") == "mayor" for h in duros):
        verdicto = "observado"
    elif accionables:
        verdicto = "aprobado_con_notas"
    else:
        verdicto = "aprobado"

    sev_max = max((h.get("severidad") for h in accionables),
                  key=lambda s: _SEV_RANK.get(s, 0), default=None)
    return {
        "verdicto": verdicto,
        "severidad_max": sev_max,
        "confiabilidad": "parcial" if no_verif else "completa",
        "no_verificables": len(no_verif),
    }
