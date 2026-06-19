"""Smoke single-doc (Cotejar): valida UN documento contra un template ELEGIDO.

Uso:
  uv run python scripts/run_cotejar.py <archivo> --tipo-doc <id> [--proyecto P] [--disciplina d]

Requiere una API key (.env) y que exista knowledge/tipos/<id>.yaml.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.graph import get_compiled_graph  # noqa: E402
from graph.state import veredicto_ui  # noqa: E402
from tools.email import build_trigger_state  # noqa: E402


def run(path: str, tipo_doc: str, meta_extra: dict) -> dict:
    files = [{"filename": Path(path).name, "path": path}]
    meta = {"text": f"Validar este documento como '{tipo_doc}'", "tipo_doc": tipo_doc, **meta_extra}
    state = build_trigger_state(files, meta)
    graph = get_compiled_graph()
    cfg = {"configurable": {"thread_id": state["thread_id"]}}
    return graph.invoke(state, cfg)


def main() -> None:
    ap = argparse.ArgumentParser(description="Cotejo single-doc contra un template")
    ap.add_argument("path")
    ap.add_argument("--tipo-doc", dest="tipo_doc", required=True)
    ap.add_argument("--proyecto", default=None)
    ap.add_argument("--disciplina", default=None)
    args = ap.parse_args()

    r = run(args.path, args.tipo_doc,
            {"proyecto": args.proyecto, "disciplina": args.disciplina, "emisor": "cotejar@test"})

    print("\n================ COTEJO ================")
    print(f"status     : {r.get('status')}  ->  veredicto: {veredicto_ui(r.get('status', ''))}")
    print(f"resumen    : {r.get('resumen')}")
    print(f"score      : {r.get('score')} | no_concluyente: {r.get('no_concluyente')}")
    print("\n-- checks --")
    for c in r.get("checks", []):
        req = "*" if c.get("requerido") else " "
        print(f"  {req}[{(c.get('dimension') or '')[:11]:11}] {str(c.get('state')):4} · {c.get('label')} — {c.get('detail')}")
    print("\n-- respuesta --")
    print(r.get("respuesta"))
    print("========================================\n")


if __name__ == "__main__":
    main()
