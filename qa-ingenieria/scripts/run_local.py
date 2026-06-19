"""Runner local de smoke (Fase 0).

Corre el grafo sobre archivos reales desde la CLI, sin sandbox ni email.
Espeja `build_trigger_state` (mismo armador de estado que usará el sandbox/server).

Uso:
  uv run python scripts/run_local.py ruta1.pdf ruta2.xlsx \
      --text "Entrega de fabricación, proyecto P-102" \
      --proyecto P-102 --tipo-entrega fabricacion --disciplina estructural

Requiere una API key del proveedor LLM configurado (.env): OPENAI_API_KEY o
ANTHROPIC_API_KEY según LLM_PROVIDER.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permitir imports del paquete al correr el script directamente
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.graph import get_compiled_graph  # noqa: E402
from tools.email import build_trigger_state  # noqa: E402


def run(paths: list[str], meta: dict) -> dict:
    files = [{"filename": Path(p).name, "path": p} for p in paths]
    state = build_trigger_state(files, meta)
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": state["thread_id"]}}
    return graph.invoke(state, config)


def _print_resumen(result: dict) -> None:
    print("\n================ RESULTADO ================")
    print(f"thread_id : {result.get('thread_id')}")
    print(f"status    : {result.get('status')}")
    print(f"entrega   : tipo={result.get('tipo_entrega')} disciplina={result.get('disciplina')} proyecto={result.get('proyecto')}")
    adm = result.get("admisibilidad", {})
    if adm:
        print(f"admisible : {adm.get('es_admisible')} | completa: {adm.get('completa')}")
        if adm.get("faltantes"):
            print(f"faltantes : {adm.get('faltantes')}")
        if adm.get("irrelevantes"):
            print(f"irrelev.  : {adm.get('irrelevantes')}")
        print(f"motivo    : {adm.get('motivo')}")
    print("\n--- acciones (envíos fake) ---")
    for a in result.get("acciones", []):
        print(a)
    print("===========================================\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Smoke runner local del agente QA-Ingeniería (Fase 0)")
    ap.add_argument("paths", nargs="*", help="rutas de archivos de la entrega")
    ap.add_argument("--text", default="", help="texto libre del trigger")
    ap.add_argument("--proyecto", default=None)
    ap.add_argument("--tipo-entrega", dest="tipo_entrega", default=None)
    ap.add_argument("--disciplina", default=None)
    ap.add_argument("--emisor", default="emisor@ejemplo.com")
    args = ap.parse_args()

    meta = {
        "text": args.text,
        "proyecto": args.proyecto,
        "tipo_entrega": args.tipo_entrega,
        "disciplina": args.disciplina,
        "emisor": args.emisor,
    }
    result = run(args.paths, meta)
    _print_resumen(result)


if __name__ == "__main__":
    main()
