"""Checkpointer del grafo (T0.3).

Toggle por env `DB_MODE`:
- local  -> AsyncSqliteSaver sobre un archivo SQLite (Fase 0). Persiste entre reinicios.
- neon   -> AsyncPostgresSaver (Fase 4; aún no cableado).

Lección #2: el saver se mantiene **vivo como singleton** (no se abre/cierra por
invocación). Para SQLite no hay pooler, pero igual evitamos reconstruirlo.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

_saver: Optional[Any] = None


def _db_mode() -> str:
    return (os.getenv("DB_MODE") or "local").strip().lower()


def _local_db_path() -> Path:
    raw = os.getenv("LOCAL_DB_PATH") or "local_state/qa_ingenieria.sqlite"
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_checkpointer() -> Any:
    """Devuelve el checkpointer (singleton). Síncrono: el grafo corre con `invoke`/`stream`."""
    global _saver
    if _saver is not None:
        return _saver

    mode = _db_mode()
    if mode == "local":
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(str(_local_db_path()), check_same_thread=False)
        _saver = SqliteSaver(conn)  # no se cierra: vive lo que vive el proceso
        _saver.setup()
        return _saver

    if mode == "neon":
        raise NotImplementedError(
            "DB_MODE=neon se cablea en Fase 4 (PostgresSaver con pool singleton). "
            "En Fase 0 usá DB_MODE=local."
        )

    raise ValueError(f"DB_MODE desconocido: {mode!r} (esperado: local | neon)")
