"""Hace importable el paquete (graph, ai_agents, tools, api) al correr pytest."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
