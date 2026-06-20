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
        det = n.get("deteccion") or {}
        declarada = any(_ancla_match(a, t) for a in det.get("anclas") or [])
        out.append({"id": nid, "nombre": n.get("nombre", nid), "declarada": declarada,
                    "norma_ref": _norma_ref(n), "version": n.get("version"),
                    "severidad": det.get("severidad", "mayor")})  # qué tan grave es NO declararla
    return out


def auto_detectar(texto: str) -> list[str]:
    """Barre TODO el catálogo y devuelve los ids cuyas anclas aparecen (sugerencia, aunque el
    template no las declare)."""
    return [d["id"] for d in detectar_normas(texto, None) if d.get("declarada")]


def reglas_de_normas(ids: list[str]) -> list[dict[str, Any]]:
    """Reglas Tier 2 de las normas dadas, cada una anotada con `norma_id`, `norma_ref` y el id global
    `req_id` = "<norma>:<id>" (la unidad asignable a una familia)."""
    normas = cargar_normas()
    out: list[dict[str, Any]] = []
    for nid in ids or []:
        n = normas.get(nid)
        if not n:
            continue
        ref = _norma_ref(n)
        for r in n.get("reglas") or []:
            out.append({**r, "norma_id": nid, "norma_ref": ref, "req_id": f"{nid}:{r.get('id')}"})
    return out


def catalogo_requisitos() -> list[dict[str, Any]]:
    """Vista PLANA de todos los requisitos (reglas) de todas las normas: la 'biblioteca' de elementos
    chequeables. Cada uno con `req_id` global + tags (norma, disciplina). Para asignar a las familias."""
    normas = cargar_normas()
    out: list[dict[str, Any]] = []
    for nid, n in normas.items():
        ref = _norma_ref(n)
        disc = (n.get("aplica_a") or {}).get("disciplinas")  # opcional (eje futuro)
        for r in n.get("reglas") or []:
            out.append({**r, "norma_id": nid, "norma_nombre": n.get("nombre"), "norma_ref": ref,
                        "req_id": f"{nid}:{r.get('id')}", "disciplinas": disc})
    return out


def requisito_por_id(req_id: str) -> dict[str, Any] | None:
    """Busca un requisito por su id global "<norma>:<id>" en el catálogo."""
    return next((q for q in catalogo_requisitos() if q.get("req_id") == req_id), None)


def vlm_de_normas(ids: list[str]) -> list[dict[str, Any]]:
    """Criterios interpretativos (bloque `vlm`) de las normas dadas, para el Tier 3 (observación VLM)."""
    cat = cargar_normas()
    out: list[dict[str, Any]] = []
    for nid in ids or []:
        v = (cat.get(nid) or {}).get("vlm")
        if v and v.get("criterios"):
            out.append({"norma_ref": v.get("norma_ref") or nid, "criterios": v.get("criterios")})
    return out


def resolver_requisitos(revision: dict | None) -> list[dict[str, Any]]:
    """Conjunto FINAL de requisitos (reglas) a evaluar para una familia, a partir de su bloque
    `revision`:  expand(`normas`) ∪ `requisitos`(por id global) ∪ `reglas`(inline del template) − `excluir`.

    Dedup/override por id LOCAL (el `reglas` inline del template pisa al de una norma con el mismo id;
    `requisitos` pisa al expandido). `excluir` acepta id global "<norma>:<id>" o id local.
    Antes de resolver, expande los `perfiles` referenciados (eje proyecto/cliente)."""
    try:
        from tools import perfiles  # import perezoso (evita circular)
        revision = perfiles.expandir_revision(revision or {})
    except Exception:
        revision = revision or {}
    out: dict[str, dict[str, Any]] = {}  # id local -> regla
    for r in reglas_de_normas(revision.get("normas") or []):   # atajo: norma entera
        out[r.get("id")] = r
    for rid in revision.get("requisitos") or []:               # granular por id global
        q = requisito_por_id(rid)
        if q:
            out[q.get("id")] = q
    for r in revision.get("reglas") or []:                     # reglas propias del template
        out[r.get("id")] = {**r, "req_id": f"template:{r.get('id')}"}
    excl = {e.split(":", 1)[-1] for e in (revision.get("excluir") or [])}  # por id local o global
    return [r for k, r in out.items() if k not in excl]
