"""Catálogo de disciplinas (editable). Fuente: knowledge/disciplinas.json.

Lista de disciplinas que se ofrecen al clasificar una entrega y al definir tipos.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_PATH = Path(os.getenv("DISCIPLINAS_PATH") or "knowledge/disciplinas.json")
_DEFAULT = ["estructural", "electrica", "electronica", "sanitaria", "mecanica"]


def cargar_disciplinas() -> list[str]:
    if _PATH.exists():
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(d) for d in data]
        except Exception:
            pass
    return list(_DEFAULT)


def guardar_disciplinas(lista: list[str]) -> list[str]:
    """Normaliza (minúsculas, sin duplicados ni vacíos) y persiste."""
    out: list[str] = []
    seen: set[str] = set()
    for d in lista:
        d = (d or "").strip().lower()
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def agregar_disciplina(nombre: str) -> list[str]:
    return guardar_disciplinas([*cargar_disciplinas(), nombre])


def eliminar_disciplina(nombre: str) -> list[str]:
    n = (nombre or "").strip().lower()
    return guardar_disciplinas([d for d in cargar_disciplinas() if d != n])
