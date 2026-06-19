"""Ensamblado del grafo + checkpointer (T0.14).

Entrada condicional (lección #8): trigger nuevo -> parser; respuesta sobre caso
existente -> clasificador (Fase 3). El checkpointer es SQLite local en Fase 0
(toggle DB_MODE; Neon en Fase 4), obtenido como singleton (lección #2).
"""

from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, StateGraph

from graph import edges, nodes
from graph.state import CasoState
from tools.db import get_checkpointer

_TERMINALES = (
    "pedir_datos",
    "reclamar_faltantes",
    "devolver_no_admisible",
    "requiere_decision",
)


def build_graph(checkpointer: Optional[Any] = None):
    g = StateGraph(CasoState)

    g.add_node("parser", nodes.parser_node)
    g.add_node("validacion", nodes.validacion_node)
    g.add_node("triage", nodes.triage_node)
    g.add_node("pedir_datos", nodes.pedir_datos_node)
    g.add_node("reclamar_faltantes", nodes.reclamar_faltantes_node)
    g.add_node("devolver_no_admisible", nodes.devolver_no_admisible_node)
    g.add_node("requiere_decision", nodes.requiere_decision_node)
    g.add_node("listo_para_revision", nodes.listo_para_revision_node)
    # Revisión de contenido (Fase 1) — corre tras la admisión
    g.add_node("extractor", nodes.extractor_node)
    g.add_node("revisor", nodes.revisor_node)

    # Entrada condicional. En Fase 0 el clasificador aún no existe -> ambas a parser.
    g.set_conditional_entry_point(
        edges.route_entry,
        {"parser": "parser", "clasificador": "parser"},
    )

    g.add_edge("parser", "validacion")
    g.add_conditional_edges(
        "validacion",
        edges.route_validation,
        {"ok": "triage", "faltan": "pedir_datos"},
    )
    g.add_conditional_edges(
        "triage",
        edges.route_post_triage,
        {
            "invalido": "devolver_no_admisible",
            "incompleta": "reclamar_faltantes",
            "revision_manual": "requiere_decision",
            "valido": "listo_para_revision",
        },
    )
    for terminal in _TERMINALES:
        g.add_edge(terminal, END)

    # Admitido -> (toggle) continúa a revisión de contenido, o termina en EN_REVISION (interrupt).
    g.add_conditional_edges(
        "listo_para_revision",
        edges.route_post_admision,
        {"revisar": "extractor", "fin": END},
    )
    g.add_edge("extractor", "revisor")
    g.add_edge("revisor", END)

    return g.compile(checkpointer=checkpointer)


def get_compiled_graph():
    """Grafo compilado con el checkpointer local (singleton)."""
    return build_graph(get_checkpointer())
