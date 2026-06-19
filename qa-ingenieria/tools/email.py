"""Email + armado del estado inicial (T0.6).

Fase 0: implementación **fake** — los envíos se loguean (no se mandan) y el
trigger se arma desde **archivos subidos** en el sandbox (no desde un email real).
Toggle `EMAIL_MODE=fake|real`; el modo real se cablea en Fase 4 (Resend + Svix).

Regla de oro sandbox-able: `build_trigger_state` es el **único** armador de estado
inicial; el server real (Fase 4) y el manifest del sandbox lo espejan, sin duplicar.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

from dotenv import load_dotenv

from graph.state import CasoState, initial_state

load_dotenv()

UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT") or "sandbox/uploads")


def _email_mode() -> str:
    return (os.getenv("EMAIL_MODE") or "fake").strip().lower()


def _new_thread_id() -> str:
    return uuid.uuid4().hex[:12]


def build_trigger_state(
    files: Iterable[dict[str, Any]],
    meta: Optional[dict[str, Any]] = None,
    thread_id: Optional[str] = None,
) -> CasoState:
    """Arma el `CasoState` inicial desde archivos + metadata del trigger.

    `files`: iterable de dicts. Cada uno con `filename` y **o bien** `path`
    (archivo ya en disco) **o bien** `bytes` (se persiste en UPLOAD_ROOT/<thread>/).
    `meta`: dict opcional con `text` (texto libre del trigger), `tipo_entrega`,
    `disciplina`, `proyecto`, `revision`, `emisor`, `ref_thread_id`.
    """
    meta = dict(meta or {})
    thread_id = thread_id or meta.get("thread_id") or _new_thread_id()

    nuevos: list[dict[str, Any]] = []
    for f in files:
        filename = f["filename"]
        path = f.get("path")
        if not path:
            dest_dir = UPLOAD_ROOT / thread_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            path = str(dest_dir / filename)
            with open(path, "wb") as out:
                out.write(f["bytes"])
        nuevos.append({"filename": filename, "path": str(path), "presente": True})

    return initial_state(
        thread_id,
        trigger_text=meta.get("text", ""),
        tipo_entrega=meta.get("tipo_entrega"),
        tipo_objetivo=meta.get("tipo_doc") or meta.get("tipo_objetivo"),
        disciplina=meta.get("disciplina"),
        proyecto=meta.get("proyecto"),
        revision=meta.get("revision"),
        emisor=meta.get("emisor"),
        ref_thread_id=meta.get("ref_thread_id"),
        nuevos_archivos=nuevos,
    )


# --- Envíos (fake en Fase 0) -------------------------------------------------

def _send(rol: str, to: Optional[str], asunto: str, cuerpo: str) -> str:
    """Envía (o loguea) un email. Devuelve una línea de acción para el estado/sandbox."""
    linea = f"[EMAIL->{rol}] to={to or '-'} | asunto: {asunto}\n{cuerpo}"
    if _email_mode() == "real":
        # Fase 4: aquí va Resend Send API (From con nombre + Reply-To al inbound).
        raise NotImplementedError("EMAIL_MODE=real se cablea en Fase 4 (Resend).")
    print(linea)  # visible en el log/chat del sandbox
    return linea


def enviar_emisor(to: Optional[str], asunto: str, cuerpo: str) -> str:
    return _send("EMISOR", to, asunto, cuerpo)


def enviar_senior(to: Optional[str], asunto: str, cuerpo: str) -> str:
    return _send("SENIOR", to, asunto, cuerpo)


def enviar_dueno(to: Optional[str], asunto: str, cuerpo: str) -> str:
    return _send("DUEÑO", to, asunto, cuerpo)
