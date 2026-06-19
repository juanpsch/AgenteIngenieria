"""Hace importable el paquete (graph, ai_agents, tools, api) al correr pytest."""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# El Tier 3 (VLM) hace una llamada LLM; en los tests va apagado por defecto (determinista, sin red).
os.environ.setdefault("REVISION_VLM", "0")
