"""Smoke de ida y vuelta (multi-turno) sobre el mismo caso.

Turno 1: plano de fabricación -> INCOMPLETA (falta lista).
Turno 2: se adjunta la lista de materiales -> EN_REVISION (completa).
Mismo thread_id en ambos turnos, como hace el sandbox.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.graph import get_compiled_graph
from tools.email import build_trigger_state

FIX = Path("sandbox/test_fixtures")


def _resumen(titulo, res):
    adm = res.get("admisibilidad", {})
    print(f"\n--- {titulo} ---")
    print("status     :", res.get("status"))
    print("documentos :", [d.get("filename") for d in res.get("documentos", [])])
    print("faltantes  :", adm.get("faltantes"))
    print("respuesta  :", (res.get("respuesta") or "")[:120])


def main():
    graph = get_compiled_graph()

    # Turno 1: solo el plano
    s1 = build_trigger_state(
        [{"filename": "plano_P102.pdf", "path": str(FIX / "plano_P102.pdf")}],
        {"text": "Envio plano de fabricacion del proyecto P-102, disciplina estructural",
         "emisor": "emisor@test"},
    )
    cfg = {"configurable": {"thread_id": s1["thread_id"]}}
    r1 = graph.invoke(s1, cfg)
    _resumen("TURNO 1 (plano solo)", r1)

    # Turno 2: mismo hilo, adjunto la lista de materiales (delta)
    delta = {
        "trigger_text": "Ahi va la lista de materiales que faltaba",
        "nuevos_archivos": [{"filename": "lista_materiales_P102.xlsx",
                             "path": str(FIX / "lista_materiales_P102.xlsx"), "presente": True}],
    }
    r2 = graph.invoke(delta, cfg)
    _resumen("TURNO 2 (agrego lista)", r2)


if __name__ == "__main__":
    main()
