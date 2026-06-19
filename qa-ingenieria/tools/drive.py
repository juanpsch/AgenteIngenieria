"""Drive/Docs — stub (T0.9).

No se usa en Fase 0 (no se generan informes todavía). Existe para no romper
imports y para que el toggle real/fake del sandbox lo descubra como dependencia.
La generación de Doc/PDF (Markdown → formato, logo, export) se cablea en Fase 2/4.
Toggle `DRIVE_MODE=fake|real`.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _drive_mode() -> str:
    return (os.getenv("DRIVE_MODE") or "fake").strip().lower()


def generar_informe(markdown: str, nombre: str) -> dict:
    """Stub: en Fase 2 convierte Markdown → Google Doc → PDF. Por ahora loguea."""
    linea = f"[DRIVE generar_informe] {nombre} ({len(markdown)} chars de Markdown)"
    if _drive_mode() == "real":
        raise NotImplementedError("DRIVE_MODE=real se cablea en Fase 2/4 (Drive/Docs).")
    print(linea)
    return {"doc_id": None, "pdf_id": None, "accion": linea}
