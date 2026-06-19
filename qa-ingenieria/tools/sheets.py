"""Sheets — catálogo de entregas (T0.7).

Fase 0: implementación **fake** que lee el catálogo desde `knowledge/catalogo.json`
(fixture local). En Fase 4 esto leerá el Sheet maestro real (Google Sheets API).
Toggle `SHEETS_MODE=fake|real`.

El catálogo resuelve, para un (proyecto, tipo_entrega), qué documentos se requieren.
`write_back` es no-op/log en Fase 0 (se usa recién en Fase 2 para volcar hallazgos).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

CATALOGO_PATH = Path(os.getenv("CATALOGO_PATH") or "knowledge/catalogo.json")


def _sheets_mode() -> str:
    return (os.getenv("SHEETS_MODE") or "fake").strip().lower()


def _catalogo() -> dict:
    # Sin caché: refleja ediciones a catalogo.json sin reiniciar el proceso.
    with open(CATALOGO_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def tipos_entrega() -> list[str]:
    """Lista de tipos de entrega conocidos (para el dropdown de la UI)."""
    if _sheets_mode() == "real":
        raise NotImplementedError("SHEETS_MODE=real se cablea en Fase 4 (Google Sheets).")
    cat = _catalogo()
    tipos = set(cat.get("_default_por_tipo_entrega", {}).keys())
    for p in cat.get("proyectos", {}).values():
        tipos.update((p.get("entregas") or {}).keys())
    return sorted(tipos)


def entregas_detalle() -> dict[str, list[str]]:
    """{tipo_entrega: [documentos_requeridos]} de los defaults (para ver/editar en la UI)."""
    return dict(_catalogo().get("_default_por_tipo_entrega", {}))


def eliminar_tipo_entrega(tipo_entrega: str) -> bool:
    """Borra un tipo de entrega del catálogo (defaults y por proyecto)."""
    import re

    tid = re.sub(r"[^a-z0-9_]+", "_", (tipo_entrega or "").strip().lower()).strip("_")
    cat = _catalogo()
    changed = False
    if tid in cat.get("_default_por_tipo_entrega", {}):
        del cat["_default_por_tipo_entrega"][tid]
        changed = True
    for p in cat.get("proyectos", {}).values():
        if tid in (p.get("entregas") or {}):
            del p["entregas"][tid]
            changed = True
    if changed:
        with open(CATALOGO_PATH, "w", encoding="utf-8") as fh:
            json.dump(cat, fh, ensure_ascii=False, indent=2)
    return changed


def guardar_tipo_entrega(tipo_entrega: str, documentos_requeridos: list[str]) -> str:
    """Crea/edita un tipo de entrega en catalogo.json (_default_por_tipo_entrega)."""
    import re

    tid = re.sub(r"[^a-z0-9_]+", "_", (tipo_entrega or "").strip().lower()).strip("_")
    if not tid:
        raise ValueError("falta un id de entrega válido")
    if not documentos_requeridos:
        raise ValueError("elegí al menos un documento requerido")
    cat = _catalogo()
    cat.setdefault("_default_por_tipo_entrega", {})[tid] = list(documentos_requeridos)
    with open(CATALOGO_PATH, "w", encoding="utf-8") as fh:
        json.dump(cat, fh, ensure_ascii=False, indent=2)
    return tid


def leer_catalogo(proyecto: Optional[str], tipo_entrega: Optional[str]) -> list[str]:
    """Devuelve la lista de `tipo_doc` requeridos para (proyecto, tipo_entrega).

    Orden de resolución:
    1. proyecto + tipo_entrega en el catálogo.
    2. default por tipo_entrega (si no hay proyecto o no está catalogado).
    3. [] si no se puede resolver (el triage lo trata como "no se puede validar completitud").
    """
    if _sheets_mode() == "real":
        raise NotImplementedError("SHEETS_MODE=real se cablea en Fase 4 (Google Sheets).")

    cat = _catalogo()
    if proyecto and tipo_entrega:
        entrega = (
            cat.get("proyectos", {})
            .get(proyecto, {})
            .get("entregas", {})
            .get(tipo_entrega)
        )
        if entrega and entrega.get("documentos_requeridos"):
            return list(entrega["documentos_requeridos"])

    if tipo_entrega:
        default = cat.get("_default_por_tipo_entrega", {}).get(tipo_entrega)
        if default:
            return list(default)

    return []


def write_back(proyecto: Optional[str], fila: dict) -> str:
    """No-op/log en Fase 0. Devuelve una línea de acción."""
    linea = f"[SHEET write_back] proyecto={proyecto} fila={fila}"
    if _sheets_mode() == "real":
        raise NotImplementedError("SHEETS_MODE=real se cablea en Fase 4.")
    print(linea)
    return linea
