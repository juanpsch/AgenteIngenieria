"""Catálogo de normas / códigos de diseño REUTILIZABLE (el vínculo doc↔norma).

Las normas viven en `knowledge/normas/<id>.yaml` y los templates las REFERENCIAN
(`revision.normas: [aea-90364, ...]`). El vínculo tiene dos direcciones:
  - DETECCIÓN (doc → norma): `detectar_normas` busca las `anclas` de cada norma en el texto del doc
    (¿lo declara? ¿qué versión?). Declarar la norma esperada es en sí un chequeo.
  - APLICACIÓN (norma → checks): `reglas_de_normas` trae las reglas Tier 2 de la norma; cada una se
    anota con `norma_ref` para que el hallazgo cite la cláusula incumplida.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "normas"


@lru_cache(maxsize=1)
def cargar_normas() -> dict[str, dict]:
    """Todas las normas del catálogo, indexadas por id. Degrada a {} si no hay carpeta/yaml."""
    import yaml

    out: dict[str, dict] = {}
    if not _DIR.exists():
        return out
    for p in sorted(_DIR.glob("*.yaml")):
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            out[d.get("id") or p.stem] = d
        except Exception:
            continue
    return out


def _norma_ref(n: dict) -> str:
    return (n.get("vlm") or {}).get("norma_ref") or n.get("nombre") or n.get("id") or "norma"


def _ancla_match(ancla: str, texto: str) -> bool:
    """Busca un ancla en el texto. Degrada con gracia si el regex es inválido (config de usuario)."""
    try:
        return re.search(ancla, texto, re.IGNORECASE) is not None
    except re.error:
        return re.search(re.escape(ancla), texto, re.IGNORECASE) is not None


def detectar_normas(texto: str, ids_esperados: list[str] | None = None) -> list[dict[str, Any]]:
    """¿Qué normas DECLARA el documento? Para las `ids_esperados` (o todas si None), busca sus anclas
    en el texto. Devuelve [{id, nombre, declarada, norma_ref, version}]."""
    normas = cargar_normas()
    ids = ids_esperados if ids_esperados is not None else list(normas)
    t = texto or ""
    out: list[dict[str, Any]] = []
    for nid in ids:
        n = normas.get(nid)
        if not n:
            out.append({"id": nid, "nombre": nid, "declarada": False, "desconocida": True})
            continue
        anclas = (n.get("deteccion") or {}).get("anclas") or []
        declarada = any(_ancla_match(a, t) for a in anclas)
        out.append({"id": nid, "nombre": n.get("nombre", nid), "declarada": declarada,
                    "norma_ref": _norma_ref(n), "version": n.get("version")})
    return out


def auto_detectar(texto: str) -> list[str]:
    """Barre TODO el catálogo y devuelve los ids cuyas anclas aparecen (sugerencia, aunque el
    template no las declare)."""
    return [d["id"] for d in detectar_normas(texto, None) if d.get("declarada")]


def reglas_de_normas(ids: list[str]) -> list[dict[str, Any]]:
    """Reglas Tier 2 de las normas dadas, cada una anotada con `norma_id` y `norma_ref`."""
    normas = cargar_normas()
    out: list[dict[str, Any]] = []
    for nid in ids or []:
        n = normas.get(nid)
        if not n:
            continue
        ref = _norma_ref(n)
        for r in n.get("reglas") or []:
            out.append({**r, "norma_id": nid, "norma_ref": ref})
    return out
