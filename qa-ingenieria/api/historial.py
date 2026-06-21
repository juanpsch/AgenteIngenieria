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
        # Migración para bases existentes: agrega `campos` / `requisitos` si faltan.
        cols = {r["name"] for r in c.execute("PRAGMA table_info(validaciones)").fetchall()}
        if "campos" not in cols:
            c.execute("ALTER TABLE validaciones ADD COLUMN campos TEXT")
        if "requisitos" not in cols:  # {req_id: estado} de la revisión (para el aprendedor)
            c.execute("ALTER TABLE validaciones ADD COLUMN requisitos TEXT")
        # Feedback humano POR REGLA (revisión de contenido): la etiqueta fina que alimenta la matriz.
        c.execute(
            """CREATE TABLE IF NOT EXISTS requisito_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT, tipo_doc TEXT, req_id TEXT,
                juicio TEXT, estado TEXT, nota TEXT, fecha TEXT,
                alcance TEXT DEFAULT 'familia'
            )"""
        )
        # Migración: `alcance` (familia | norma | global) — hasta dónde llega el juicio.
        if "alcance" not in {r["name"] for r in c.execute("PRAGMA table_info(requisito_feedback)").fetchall()}:
            c.execute("ALTER TABLE requisito_feedback ADD COLUMN alcance TEXT DEFAULT 'familia'")
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_req_fb ON requisito_feedback(thread_id, req_id)"
        )
        c.execute("CREATE INDEX IF NOT EXISTS ix_val_thread ON validaciones(thread_id)")
        c.commit()


def registrar_validacion(thread_id: str, doc: str, tipo_doc: str, status: str,
                         veredicto: str, score: Optional[float], operador: str, fecha: str,
                         campos: dict[str, Any] | None = None) -> int:
    with closing(_conn()) as c:
        # Una fila por thread_id: en un reenvío al mismo caso (ida-y-vuelta) se reemplaza la previa,
        # para no duplicar en métricas ni sesgar el corpus del aprendedor.
        c.execute("DELETE FROM validaciones WHERE thread_id=?", (thread_id,))
        cur = c.execute(
            """INSERT INTO validaciones (thread_id, doc, tipo_doc, status, veredicto, score, operador, fecha, campos)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (thread_id, doc, tipo_doc, status, veredicto, score, operador, fecha,
             json.dumps(campos or {}, ensure_ascii=False)),
        )
        c.commit()
        return int(cur.lastrowid)


def set_requisitos(thread_id: str, requisitos: dict[str, str]) -> None:
    """Guarda el resultado POR requisito {req_id: estado} de la revisión de un caso (para el aprendedor)."""
    if not requisitos:
        return
    with closing(_conn()) as c:
        c.execute("UPDATE validaciones SET requisitos=? WHERE thread_id=?",
                  (json.dumps(requisitos, ensure_ascii=False), thread_id))
        c.commit()


def corpus_requisitos(tipo_doc: str, limit: int = 5000) -> list[dict[str, Any]]:
    """Por familia: [{admitido: bool, requisitos: {req_id: estado}}] — base de la matriz de aprendizaje."""
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT veredicto, decision, requisitos FROM validaciones WHERE tipo_doc=? ORDER BY id DESC LIMIT ?",
            (tipo_doc, limit),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            reqs = json.loads(d.get("requisitos") or "{}")
        except Exception:
            reqs = {}
        if reqs:
            out.append({"admitido": _admitido(d), "requisitos": reqs})
    return out


def corpus_global(limit: int = 20000) -> list[dict[str, Any]]:
    """Todas las validaciones con requisitos (cualquier familia): [{tipo_doc, admitido, requisitos}].
    Base del observatorio de reglas (estadística de cumplimiento facetada)."""
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT tipo_doc, veredicto, decision, requisitos FROM validaciones ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            reqs = json.loads(d.get("requisitos") or "{}")
        except Exception:
            reqs = {}
        if reqs:
            out.append({"tipo_doc": d.get("tipo_doc"), "admitido": _admitido(d), "requisitos": reqs})
    return out


def feedback_global() -> list[dict[str, Any]]:
    """Juicios humanos por (familia, regla, alcance): [{tipo_doc, req_id, juicio, alcance, n}] — observatorio."""
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT tipo_doc, req_id, juicio, COALESCE(alcance,'familia') alcance, COUNT(*) n "
            "FROM requisito_feedback GROUP BY tipo_doc, req_id, juicio, alcance",
        ).fetchall()
    return [dict(r) for r in rows]


def feedback_agg(tipo_doc: str) -> dict[str, dict[str, int]]:
    """Conteo de juicios humanos por regla aplicables a una familia, RESUELTO por alcance:
    {req_id: {de_acuerdo, no_aplica, regla_mal}}. Suma el juicio de alcance `familia` de ESTA familia +
    el de alcance `norma`/`global` de cualquier caso (se reusa); si la familia tiene juicio propio sobre
    una regla, ese PISA al amplio (lo más específico gana)."""
    with closing(_conn()) as c:
        fam = c.execute(
            "SELECT req_id, juicio, COUNT(*) n FROM requisito_feedback WHERE tipo_doc=? AND COALESCE(alcance,'familia')='familia' GROUP BY req_id, juicio",
            (tipo_doc,),
        ).fetchall()
        amplio = c.execute(
            "SELECT req_id, juicio, COUNT(*) n FROM requisito_feedback WHERE alcance IN ('norma','global') GROUP BY req_id, juicio",
        ).fetchall()
    out: dict[str, dict[str, int]] = {}
    propios: set[str] = set()
    for r in fam:
        out.setdefault(r["req_id"], {})[r["juicio"]] = int(r["n"])
        propios.add(r["req_id"])
    for r in amplio:
        if r["req_id"] in propios:        # la familia tiene el suyo -> lo más específico gana
            continue
        d = out.setdefault(r["req_id"], {})
        d[r["juicio"]] = d.get(r["juicio"], 0) + int(r["n"])
    return out


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
                                 nota: str | None = None, alcance: str = "familia") -> None:
    """Guarda (o reemplaza) el juicio humano de UNA regla en un caso. `juicio` ∈ {de_acuerdo,
    no_aplica, regla_mal}; `estado` = resultado automático al momento (para la matriz de aprendizaje).
    `alcance` ∈ {familia, norma, global}: hasta dónde llega el juicio (familia = solo esta; norma/global =
    se reusa en todas las familias que usan la regla — lo más específico, la familia, gana en la resolución)."""
    with closing(_conn()) as c:
        c.execute("DELETE FROM requisito_feedback WHERE thread_id=? AND req_id=?", (thread_id, req_id))
        c.execute(
            """INSERT INTO requisito_feedback (thread_id, tipo_doc, req_id, juicio, estado, nota, fecha, alcance)
               VALUES (?,?,?,?,?,?,?,?)""",
            (thread_id, tipo_doc, req_id, juicio, estado, nota, fecha, alcance),
        )
        c.commit()


def feedback_de(thread_id: str) -> dict[str, dict[str, Any]]:
    """Juicios humanos por regla de un caso: {req_id: {juicio, nota, alcance}}."""
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT req_id, juicio, nota, alcance FROM requisito_feedback WHERE thread_id=?", (thread_id,)
        ).fetchall()
        return {r["req_id"]: {"juicio": r["juicio"], "nota": r["nota"], "alcance": r["alcance"] or "familia"} for r in rows}


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
