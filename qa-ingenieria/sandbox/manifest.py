"""Manifest del sandbox — Agente QA-Ingeniería (Fase 0).

Declara el grafo, las dependencias fakeables (email, sheets), los nodos y los
armadores de estado. `build_trigger_state` espeja tools.email.build_trigger_state
(mismo armador único) tomando el archivo subido en el chat.

LLM siempre real (provider configurable). preset_inicial="all-real": en Fase 0 los
reales ya son locales/seguros; el upload de adjuntos funciona en cualquier toggle.
"""

from __future__ import annotations

from agent_sandbox.manifest import Dependency, FakeTarget, Manifest, Node, UI

from sandbox.fakes import drain_pending_uploads
from tools.email import build_trigger_state as _build_state

MANIFEST = Manifest(
    graph_factory="graph.graph:build_graph",
    dependencies=[
        Dependency(
            name="email",
            fake="sandbox.fakes:EmailUploadsFake",
            targets=[
                FakeTarget("graph.nodes", "enviar_emisor"),
                FakeTarget("graph.nodes", "enviar_dueno"),
            ],
        ),
        Dependency(
            name="sheets",
            fake="sandbox.fakes:SheetsFake",
            targets=[FakeTarget("graph.nodes", "leer_catalogo")],
        ),
    ],
    nodes=[
        Node("graph.nodes", "parser_node"),
        Node("graph.nodes", "validacion_node"),
        Node("graph.nodes", "triage_node"),
        Node("graph.nodes", "pedir_datos_node"),
        Node("graph.nodes", "reclamar_faltantes_node"),
        Node("graph.nodes", "devolver_no_admisible_node"),
        Node("graph.nodes", "listo_para_revision_node"),
    ],
    entry={
        "trigger_builder": "sandbox.manifest:build_trigger_state",
        "client_builder": "sandbox.manifest:build_client_input",
        "thread_id_prefix": "qa",
    },
    ui=UI(
        product="QA-Ingeniería",
        vendor="Agencia",
        agent_name="QA",
        agent_subtitle="Admisibilidad + completitud de entregas (Fase 0)",
        attachments=True,           # habilita subir archivos en el chat
        reply_field="respuesta",     # muestra state["respuesta"] como burbuja del agente
        files_field="documentos_panel",  # documentos acumulados del caso en el panel Archivos
    ),
    preset_inicial="all-real",
    schema_version="1.0",
)


def _files_from_attachment(attachment: "dict | None") -> list[dict]:
    """Fallback: el attachment_id que devuelve add_attachment ES la ruta en disco."""
    if not attachment:
        return []
    path = attachment.get("id")
    filename = attachment.get("filename") or "adjunto"
    return [{"filename": filename, "path": path}] if path else []


def _incoming_files(attachment: "dict | None") -> list[dict]:
    """Todos los archivos subidos en este turno (drena la bandeja del fake).
    Esto permite adjuntar VARIOS antes de enviar y que entren todos juntos.
    Si la bandeja viene vacía (p. ej. infra real), cae al attachment único.
    """
    files = drain_pending_uploads()
    return files if files else _files_from_attachment(attachment)


def build_trigger_state(text: str, attachment: "dict | None" = None):
    """Trigger nuevo desde el chat: texto + los archivos adjuntados en este turno."""
    return _build_state(_incoming_files(attachment), {"text": text or "", "emisor": "emisor@sandbox"})


def build_client_input(text: str, attachment: "dict | None" = None):
    """Turno siguiente sobre el MISMO caso (ida y vuelta): devuelve solo el delta.
    LangGraph lo mergea al estado del hilo y re-corre parser -> validación -> triage,
    así el caso acumula los documentos que el emisor va mandando hasta completarse.
    """
    delta: dict = {"trigger_text": text or ""}
    nuevos = _incoming_files(attachment)
    if nuevos:
        delta["nuevos_archivos"] = [
            {"filename": n["filename"], "path": n["path"], "presente": True} for n in nuevos
        ]
    return delta
