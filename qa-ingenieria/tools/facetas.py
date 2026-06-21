"""Facetas (ejes ortogonales de clasificación) — el vínculo familia→reglas por composición.

Una familia declara coordenadas en `revision.facetas` (p.ej. {tipo: pid, organizacion: camuzzi}); cada
valor de faceta aporta normas/requisitos (un "mini-perfil" de un eje). El resolvedor (`tools/normas`) une
las contribuciones con precedencia "lo más específico gana". Todo configurable en `knowledge/facetas.yaml`
(precedencia de ejes, política de conflicto, jerarquía intra-eje vía `padre`). Ver docs/PLAN_Taxonomia_Facetas.md.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "facetas.yaml"


@lru_cache(maxsize=1)
def cargar_facetas() -> dict:
    """Registro de facetas. Degrada a {} si no hay archivo/yaml."""
    import yaml

    if not _PATH.exists():
        return {}
    try:
        return yaml.safe_load(_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def politica() -> dict:
    return cargar_facetas().get("politica") or {}


def precedencia(eje: str) -> int:
    """Precedencia del eje (menor = más específico). Ejes desconocidos van al final."""
    return ((cargar_facetas().get("ejes") or {}).get(eje) or {}).get("precedencia", 99)


def _valor(eje: str, v: str) -> dict:
    return ((cargar_facetas().get("valores") or {}).get(eje) or {}).get(v) or {}


def cadena(eje: str, valor: str) -> list[str]:
    """[ancestros..., valor] subiendo por `padre` dentro del eje (ancestros primero = menos específicos)."""
    out: list[str] = []
    v, seen = valor, set()
    while v and v not in seen:
        seen.add(v)
        out.append(v)
        v = _valor(eje, v).get("padre")
    return list(reversed(out))


def bundle(eje: str, v: str) -> dict[str, Any]:
    """Reglas que aporta un valor de faceta: {normas, requisitos, reglas, excluir}."""
    d = _valor(eje, v)
    return {"normas": d.get("normas"), "requisitos": d.get("requisitos"),
            "reglas": d.get("reglas"), "excluir": d.get("excluir")}


def nombre(eje: str, v: str) -> str:
    return _valor(eje, v).get("nombre") or v
