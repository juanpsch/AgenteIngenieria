"""Fakes del sandbox para el agente QA-Ingeniería.

- EmailUploadsFake: espeja tools/email (enviar_*) y además implementa `add_attachment`,
  que es lo que el endpoint /api/upload usa para persistir los archivos subidos.
  Guarda los bytes en sandbox/uploads/ y devuelve la RUTA como attachment_id, así
  build_trigger_state arma `documentos[{filename, path}]` y docs.py los lee del disco.
- SheetsFake: espeja tools/sheets.leer_catalogo (lee el mismo fixture local).

En Fase 0 los "reales" ya son locales/seguros (email loguea, sheets lee fixture),
así que real y fake se comportan igual; el toggle cobra sentido en Fase 4.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT") or "sandbox/uploads")

# Bandeja de archivos subidos desde la UI que aún no se consumieron en un turno.
# Permite adjuntar VARIOS archivos antes de enviar: el builder los drena todos.
_PENDING_UPLOADS: list[dict] = []


def drain_pending_uploads() -> list[dict]:
    """Devuelve y limpia los archivos subidos desde el último turno."""
    global _PENDING_UPLOADS
    files = list(_PENDING_UPLOADS)
    _PENDING_UPLOADS = []
    return files


class EmailUploadsFake:
    """Email en memoria + receptor de adjuntos del sandbox."""

    def __init__(self) -> None:
        self.outbox: list[dict] = []

    # --- envíos (lo que llaman los nodos vía graph.nodes.email) ---
    def _record(self, rol: str, to, asunto: str, cuerpo: str) -> str:
        linea = f"[EMAIL->{rol}] to={to or '-'} | {asunto}\n{cuerpo}"
        self.outbox.append({"rol": rol, "to": to, "asunto": asunto, "cuerpo": cuerpo})
        print(linea)
        return linea

    def enviar_emisor(self, to, asunto, cuerpo) -> str:
        return self._record("EMISOR", to, asunto, cuerpo)

    def enviar_senior(self, to, asunto, cuerpo) -> str:
        return self._record("SENIOR", to, asunto, cuerpo)

    def enviar_dueno(self, to, asunto, cuerpo) -> str:
        return self._record("DUEÑO", to, asunto, cuerpo)

    # --- adjuntos (lo que usa /api/upload) ---
    def add_attachment(self, data: bytes, filename: str, who: str = "") -> str:
        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        dest = UPLOAD_ROOT / f"{uuid.uuid4().hex[:8]}_{filename}"
        with open(dest, "wb") as fh:
            fh.write(data)
        _PENDING_UPLOADS.append({"filename": filename, "path": str(dest)})
        return str(dest)   # el attachment_id ES la ruta (la lee docs.py)

    def artifacts(self) -> list[dict]:
        return [{"type": "email", "title": f"{e['rol']}: {e['asunto']}", "body": e["cuerpo"]}
                for e in self.outbox]


class SheetsFake:
    """Catálogo de entregas (mismo fixture local que tools/sheets)."""

    def leer_catalogo(self, proyecto, tipo_entrega) -> list[str]:
        from tools.sheets import leer_catalogo as _real
        return _real(proyecto, tipo_entrega)

    def write_back(self, proyecto, fila) -> str:
        linea = f"[SHEET write_back] proyecto={proyecto} fila={fila}"
        print(linea)
        return linea
