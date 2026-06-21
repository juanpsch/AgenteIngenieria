"""Routers condicionales (T0.13).

- route_entry: punto de entrada condicional (lección #8). Trigger nuevo -> parser;
  respuesta sobre caso existente (ref_thread_id) -> clasificador (Fase 3).
- route_validation: datos mínimos ok -> triage; faltan -> pedir_datos.
- route_triage: no admisible -> devolver; incompleta -> reclamar; ok -> revisión.
"""

from __future__ import annotations

from graph.state import CasoState


def route_entry(state: CasoState) -> str:
    # Fase 0: el clasificador (Fase 3) aún no existe; ambas ramas van al parser.
    if state.get("ref_thread_id"):
        return "clasificador"
    return "parser"


def route_validation(state: CasoState) -> str:
    return "faltan" if state.get("faltan_minimos") else "ok"


def route_triage(state: CasoState) -> str:
    """Decide por señales concretas, no por el flag `es_admisible` (ambiguo en el LLM):

    - hay archivos irrelevantes o con formato malo -> NO_ADMISIBLE (devuelve).
    - lo recibido está bien pero faltan requeridos   -> INCOMPLETA (reclama).
    - completa y sin problemas                        -> revisión (Fase 1).

    Un caso meramente incompleto NO es 'no admisible': lo recibido es válido.
    """
    adm = state.get("admisibilidad", {})
    irrelevantes = adm.get("irrelevantes") or []
    faltantes = adm.get("faltantes") or []
    docs_mal = any(
        d.get("relevante") is False or d.get("formato_ok") is False
        for d in state.get("documentos", [])
    )

    if irrelevantes or docs_mal:
        return "no_admisible"
    if faltantes:
        return "incompleta"
    return "revision"


def _dim_pasa(checks: list, dim: str) -> bool:
    return not any(
        c.get("state") == "fail" and c.get("requerido")
        for c in (checks or []) if c.get("dimension") == dim
    )


def route_post_triage(state: CasoState) -> str:
    """Router unificado del veredicto (Cotejar single-doc + entrega multi-doc).

    Devuelve: valido | revision_manual | invalido | incompleta.
    - Cotejar (hay tipo_objetivo): Identidad falla -> invalido; Completitud falla
      (requerido) -> revision_manual (ámbar); ambas pasan -> valido.
    - Entrega: irrelevante/formato malo -> invalido; faltan docs -> incompleta;
      todo OK -> valido. (No usa revision_manual.)
    """
    if state.get("tipo_objetivo"):
        checks = state.get("checks", [])
        if not _dim_pasa(checks, "identidad"):
            return "invalido"
        # Veredicto del score (lo decidió el nodo con los umbrales del template):
        sv = state.get("score_veredicto")
        if sv in ("invalido", "revision_manual"):
            return sv
        if not _dim_pasa(checks, "completitud"):
            return "revision_manual"
        return "valido"

    adm = state.get("admisibilidad", {})
    irrelevantes = adm.get("irrelevantes") or []
    faltantes = adm.get("faltantes") or []
    docs_mal = any(
        d.get("relevante") is False or d.get("formato_ok") is False
        for d in state.get("documentos", [])
    )
    if irrelevantes or docs_mal:
        return "invalido"
    if faltantes:
        return "incompleta"
    return "valido"


def route_post_admision(state: CasoState) -> str:
    """Tras admitir (EN_REVISION): ¿se continúa a la revisión de contenido en el mismo invoke?

    Sí solo si el toggle `revisar_auto` está on, es un cotejo single-doc (`tipo_objetivo`) y el
    template declara un bloque `revision:`. Si el toggle está off (interrupt), el caso queda
    EN_REVISION y la revisión se dispara a mano (`POST /casos/{id}/revisar`). El multi-doc no
    entra a revisión en esta fase.
    """
    from tools.tipos import cargar_tipos
    from tools import normas

    tipo = state.get("tipo_objetivo")
    if not state.get("revisar_auto", True) or not tipo:
        return "fin"
    tpl = cargar_tipos().get(tipo) or {}
    return "revisar" if normas.tiene_revision(tpl.get("revision")) else "fin"
