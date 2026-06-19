"""Historial de validaciones en SQLite local (Cotejar §7.5).

Registra cada validación (doc, template, veredicto, score, operador, fecha) y las
decisiones humanas + promociones. Alimenta GET /api/historial y el strip de métricas.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

_DB = Path(os.getenv("HISTORIAL_DB_PATH") or "local_state/historial.sqlite")


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB))
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with closing(_conn()) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS validaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT, doc TEXT, tipo_doc TEXT,
                status TEXT, veredicto TEXT, score REAL,
                operador TEXT, fecha TEXT,
                decision TEXT, promovido_a_ref INTEGER DEFAULT 0,
                campos TEXT
            )"""
        )
        # Migración para bases existentes: agrega `campos` si falta.
        cols = {r["name"] for r in c.execute("PRAGMA table_info(validaciones)").fetchall()}
        if "campos" not in cols:
            c.execute("ALTER TABLE validaciones ADD COLUMN campos TEXT")
        # Feedback humano POR REGLA (revisión de contenido): la etiqueta fina que alimenta la matriz.
        c.execute(
            """CREATE TABLE IF NOT EXISTS requisito_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT, tipo_doc TEXT, req_id TEXT,
                juicio TEXT, estado TEXT, nota TEXT, fecha TEXT
            )"""
        )
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_req_fb ON requisito_feedback(thread_id, req_id)"
        )
        c.commit()


def registrar_validacion(thread_id: str, doc: str, tipo_doc: str, status: str,
                         veredicto: str, score: Optional[float], operador: str, fecha: str,
                         campos: dict[str, Any] | None = None) -> int:
    with closing(_conn()) as c:
        cur = c.execute(
            """INSERT INTO validaciones (thread_id, doc, tipo_doc, status, veredicto, score, operador, fecha, campos)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (thread_id, doc, tipo_doc, status, veredicto, score, operador, fecha,
             json.dumps(campos or {}, ensure_ascii=False)),
        )
        c.commit()
        return int(cur.lastrowid)


def registrar_decision(thread_id: str, decision: str) -> None:
    with closing(_conn()) as c:
        c.execute("UPDATE validaciones SET decision=? WHERE thread_id=?", (decision, thread_id))
        c.commit()


def marcar_promovido(thread_id: str) -> None:
    with closing(_conn()) as c:
        c.execute("UPDATE validaciones SET promovido_a_ref=1 WHERE thread_id=?", (thread_id,))
        c.commit()


def decision_de(thread_id: str) -> Optional[str]:
    with closing(_conn()) as c:
        row = c.execute(
            "SELECT decision FROM validaciones WHERE thread_id=? ORDER BY id DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        return row["decision"] if row else None


def registrar_requisito_feedback(thread_id: str, req_id: str, juicio: str, fecha: str,
                                 tipo_doc: str | None = None, estado: str | None = None,
                                 nota: str | None = None) -> None:
    """Guarda (o reemplaza) el juicio humano de UNA regla en un caso. `juicio` ∈ {de_acuerdo,
    no_aplica, regla_mal}; `estado` = resultado automático al momento (para la matriz de aprendizaje)."""
    with closing(_conn()) as c:
        c.execute("DELETE FROM requisito_feedback WHERE thread_id=? AND req_id=?", (thread_id, req_id))
        c.execute(
            """INSERT INTO requisito_feedback (thread_id, tipo_doc, req_id, juicio, estado, nota, fecha)
               VALUES (?,?,?,?,?,?,?)""",
            (thread_id, tipo_doc, req_id, juicio, estado, nota, fecha),
        )
        c.commit()


def feedback_de(thread_id: str) -> dict[str, dict[str, Any]]:
    """Juicios humanos por regla de un caso: {req_id: {juicio, nota}}."""
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT req_id, juicio, nota FROM requisito_feedback WHERE thread_id=?", (thread_id,)
        ).fetchall()
        return {r["req_id"]: {"juicio": r["juicio"], "nota": r["nota"]} for r in rows}


def listar(limit: int = 200) -> list[dict[str, Any]]:
    with closing(_conn()) as c:
        rows = c.execute("SELECT * FROM validaciones ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def corpus(tipo_doc: str, limit: int = 5000) -> list[dict[str, Any]]:
    """Evidencia etiquetada de un tipo: cada validación con sus `campos` extraídos + la decisión
    humana (label). Base para sugerir/ajustar reglas. `campos` ya viene parseado a dict."""
    with closing(_conn()) as c:
        rows = c.execute(
            """SELECT thread_id, doc, veredicto, decision, fecha, campos
               FROM validaciones WHERE tipo_doc=? ORDER BY id DESC LIMIT ?""",
            (tipo_doc, limit),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["campos"] = json.loads(d.get("campos") or "{}")
        except Exception:
            d["campos"] = {}
        out.append(d)
    return out


def _admitido(i: dict[str, Any]) -> bool:
    """Admitido = el humano lo aprobó; o, sin decisión humana, el veredicto fue 'valido'.
    Una decisión humana (approved/rejected) SIEMPRE prevalece sobre el veredicto automático."""
    dec = i.get("decision")
    if dec == "approved":
        return True
    if dec == "rejected":
        return False
    return i.get("veredicto") == "valido"


def metricas() -> dict[str, Any]:
    items = listar(10000)
    total = len(items)
    aprob = sum(1 for i in items if _admitido(i))
    pend = sum(1 for i in items if i.get("veredicto") == "revision_manual" and not i.get("decision"))
    prom = sum(1 for i in items if i.get("promovido_a_ref"))
    return {
        "validados": total,
        "aprobacion_pct": round(100 * aprob / total) if total else 0,
        "pendientes": pend,
        "promovidos": prom,
    }
