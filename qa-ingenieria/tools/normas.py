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
            out.append({"norma_ref": v.get("norma_ref") or nid, "criterios": v.get("criterios"),
                        "referencia_imagen": v.get("referencia_imagen")})  # leyenda/estándar como ground-truth del VLM
    return out


_SEV_RANK = {"bloqueante": 3, "mayor": 2, "menor": 1, "observacion": 0}


def _aplicar_bundle(out: dict, excl: set, bundle: dict, origen: str, pol: str) -> None:
    """Suma las reglas de un bundle a `out` (id local -> regla), pisando lo previo (más específico gana).
    Cada regla queda anotada con `origen` (qué faceta/template la trajo) para explicabilidad."""
    def _set(rid, regla):
        prev = out.get(rid)
        nr = {**regla, "origen": origen}
        if prev and pol == "mas_restrictivo" and _SEV_RANK.get(prev.get("severidad"), 0) > _SEV_RANK.get(nr.get("severidad"), 0):
            nr["severidad"] = prev.get("severidad")   # conserva la severidad más alta
        out[rid] = nr

    for r in reglas_de_normas(bundle.get("normas") or []):
        _set(r.get("id"), r)
    for rid in bundle.get("requisitos") or []:
        q = requisito_por_id(rid)
        if q:
            _set(q.get("id"), q)
    for r in bundle.get("reglas") or []:
        _set(r.get("id"), {**r, "req_id": f"template:{r.get('id')}"})
    excl.update(e.split(":", 1)[-1] for e in (bundle.get("excluir") or []))


def resolver_requisitos(revision: dict | None) -> list[dict[str, Any]]:
    """Conjunto FINAL de requisitos a evaluar para una familia. Une, de MENOS a MÁS específico:
      facetas (`revision.facetas`, por precedencia de eje + ancestros) → `perfiles` → `normas`/`requisitos`/
      `reglas` propios del template. Mismo id local: gana lo más específico (override; con `origen`).
    `excluir` (id global o local) saca reglas. Todo configurable en knowledge/facetas.yaml."""
    try:
        from tools import perfiles  # import perezoso (evita circular)
        revision = perfiles.expandir_revision(revision or {})
    except Exception:
        revision = revision or {}

    out: dict[str, dict[str, Any]] = {}   # id local -> regla
    excl: set[str] = set()
    pol = "mas_especifico"

    facetas = revision.get("facetas") or {}
    if facetas:
        try:
            from tools import facetas as F  # import perezoso
            pol = (F.politica() or {}).get("conflicto_severidad", pol)
            for eje in sorted(facetas, key=F.precedencia, reverse=True):   # menos específico primero
                for v in F.cadena(eje, facetas[eje]):                      # ancestros primero
                    _aplicar_bundle(out, excl, F.bundle(eje, v), f"{eje}={v}", pol)
        except Exception:
            pass

    # Template propio = lo MÁS específico (último, pisa a las facetas).
    propio = {k: revision.get(k) for k in ("normas", "requisitos", "reglas", "excluir")}
    _aplicar_bundle(out, excl, propio, "template", pol)

    return [r for k, r in out.items() if k not in excl]
