"""Perfiles de cumplimiento (eje proyecto/cliente · jurisdicción) — Fase 1, Paso 6.

Un **perfil** es un bundle reutilizable de normas/requisitos que un proyecto/cliente exige
(`knowledge/perfiles/<id>.yaml`). Las familias (o los casos) lo **referencian** (`revision.perfiles: [...]`)
y sus requisitos se suman al set de la familia. Resuelve el "depende del proyecto/jurisdicción" sin
forkear templates ni repetir normas.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "perfiles"


@lru_cache(maxsize=1)
def cargar_perfiles() -> dict[str, dict]:
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


def expandir_revision(revision: dict | None) -> dict:
    """Mergea los `perfiles` referenciados en el bloque `revision` (suma sus `normas`/`requisitos`).
    No-op si no hay `perfiles`. Lo llama el resolvedor de requisitos."""
    revision = dict(revision or {})
    ids = revision.get("perfiles") or []
    if not ids:
        return revision
    perfiles = cargar_perfiles()
    normas = list(revision.get("normas") or [])
    reqs = list(revision.get("requisitos") or [])
    for pid in ids:
        p = perfiles.get(pid) or {}
        normas += p.get("normas") or []
        reqs += p.get("requisitos") or []
    revision["normas"] = list(dict.fromkeys(normas))      # dedup, conserva orden
    revision["requisitos"] = list(dict.fromkeys(reqs))
    return revision


def requisitos_de_perfil(perfil: dict) -> list[str]:
    """req_ids globales que aporta un perfil (expandiendo sus normas/requisitos)."""
    from tools import normas

    rev = {"normas": perfil.get("normas") or [], "requisitos": perfil.get("requisitos") or []}
    return [r.get("req_id") for r in normas.resolver_requisitos(rev) if r.get("req_id")]
