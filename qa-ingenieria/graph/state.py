"""Estado del caso QA-Ingeniería + enum Status.

Un "caso" es una **entrega** que puede exigir uno o varios documentos
(p. ej. Plano + Lista de materiales). El estado persiste en el checkpointer
(SQLite local en Fase 0; Neon en Fase 4).

Convención: los nodos son funciones puras `state -> state`; el IO vive en tools/.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, TypedDict


class Status(str, Enum):
    """Estados del ciclo de vida del caso.

    Fase 0 llega hasta el gate de triage (EN_TRIAGE / INCOMPLETA / NO_ADMISIBLE).
    El resto son placeholders para Fase 1+ (revisión de contenido y HITL).
    """

    # --- Fase 0 (frente del flujo) ---
    RECIBIDO = "RECIBIDO"
    FALTAN_DATOS = "FALTAN_DATOS"        # no se puede ni identificar la entrega
    EN_TRIAGE = "EN_TRIAGE"             # gate de admisibilidad + completitud
    INCOMPLETA = "INCOMPLETA"          # faltan documentos requeridos de la entrega
    NO_ADMISIBLE = "NO_ADMISIBLE"      # irrelevante / formato mal / archivo equivocado
    REQUIERE_DECISION = "REQUIERE_DECISION"  # admisión ambigua -> decide un humano (ámbar)

    # --- Fase 1+ (placeholders) ---
    EN_REVISION = "EN_REVISION"
    ESPERANDO_APROBACION_SENIOR = "ESPERANDO_APROBACION_SENIOR"
    OBSERVADO = "OBSERVADO"
    APROBADO = "APROBADO"
    APROBADO_CON_NOTAS = "APROBADO_CON_NOTAS"
    RECHAZADO = "RECHAZADO"


class Documento(TypedDict, total=False):
    """Un documento de la entrega (uno por archivo recibido o requerido)."""

    tipo_doc: str          # plano | lista_materiales | memoria_calculo | ...
    filename: str
    path: str              # ruta del archivo en disco (uploads del sandbox)
    presente: bool         # llegó un archivo para este requerido
    legible: bool          # docs.py pudo extraer contenido
    contenido: str         # texto/markdown extraído (lo que "lee" el agente)
    imagenes: list[str]    # páginas renderizadas (data-urls) para visión
    formato_ok: bool       # cumple la plantilla de formato
    relevante: bool        # corresponde a la entrega
    faltan: list[str]      # secciones/columnas/campos del cajetín ausentes
    motivo: str            # por qué no pasa (si aplica)
    razonamiento: str      # explicación de la decisión (explicabilidad)
    checks: list           # checks granulares del documento (ver Check)


class Admisibilidad(TypedDict, total=False):
    """Resultado del triage."""

    es_admisible: bool
    completa: bool
    faltantes: list[str]       # tipos de documento requeridos que no llegaron
    irrelevantes: list[str]    # archivos recibidos fuera de alcance
    motivo: str


class Check(TypedDict, total=False):
    """Un chequeo granular, agrupado por dimensión (Cotejar)."""

    dimension: str   # "identidad" | "completitud"
    label: str       # "Código de empresa coincide (ABC)"
    state: str       # "pass" | "fail" | "warn" | "info"
    detail: str      # "Falta el campo" | "87% · sobre umbral de revisión"
    requerido: bool  # un fail en un check requerido baja la dimensión


# Mapeo status backend -> veredicto de la UI Cotejar (verde/ámbar/rojo/info)
_VEREDICTO = {
    Status.EN_REVISION.value: "valido",
    Status.APROBADO.value: "valido",
    Status.APROBADO_CON_NOTAS.value: "valido",
    Status.REQUIERE_DECISION.value: "revision_manual",
    Status.OBSERVADO.value: "revision_manual",
    Status.ESPERANDO_APROBACION_SENIOR.value: "revision_manual",
    Status.NO_ADMISIBLE.value: "invalido",
    Status.RECHAZADO.value: "invalido",
    Status.FALTAN_DATOS.value: "faltan_datos",
    Status.INCOMPLETA.value: "faltan_datos",
}


def veredicto_ui(status: str) -> str:
    """Traduce el `Status` backend al veredicto de la UI (§4.3 del spec Cotejar)."""
    return _VEREDICTO.get(status, "faltan_datos")


def umbrales_score() -> tuple[float, float]:
    """(aprobación, revisión) leídos del entorno. Fuente única de los umbrales."""
    import os

    return float(os.getenv("APPROVAL_THRESHOLD", "96")), float(os.getenv("REVISION_THRESHOLD", "85"))


def clasificar_score(score: float, umbrales: tuple[float, float] | None = None) -> str:
    """Score de similitud (0–100) -> 'valido' | 'revision_manual' | 'invalido'.
    Única definición del umbralado. `umbrales` permite pasar los auto-calibrados por
    template; si es None usa los globales del entorno."""
    appr, rev = umbrales if umbrales else umbrales_score()
    if score >= appr:
        return "valido"
    if score >= rev:
        return "revision_manual"
    return "invalido"


class CasoState(TypedDict, total=False):
    """Estado persistente de un caso (una entrega)."""

    thread_id: str

    # Texto libre del trigger (email/chat) que lee el parser
    trigger_text: Optional[str]

    # Datos del trigger (parser)
    tipo_entrega: Optional[str]
    tipo_objetivo: Optional[str]   # Cotejar: template elegido a validar (modo single-doc)
    disciplina: Optional[str]
    proyecto: Optional[str]
    revision: Optional[str]
    emisor: Optional[str]
    norma_ref: Optional[str]

    # Documentos de la entrega
    documentos: list[Documento]        # acumulados del caso (ya leídos)
    nuevos_archivos: list[Documento]   # entrantes en este turno, sin procesar
    entrega_completa: bool
    admisibilidad: Admisibilidad

    # Control de flujo
    faltan_minimos: list[str]      # datos mínimos ausentes (lo llena validación)
    rebotes_admisibilidad: int     # veces que cayó en NO_ADMISIBLE (3º -> avisa dueño)
    ronda: int                     # vuelta de revisión
    status: str                    # valor de Status

    # Entrada condicional (trigger nuevo vs respuesta sobre caso existente)
    ref_thread_id: Optional[str]

    # Resultado de validación (Cotejar, modo single-doc)
    checks: list          # checks del documento elegido, por dimensión (ver Check)
    score: Optional[float]        # similitud por embeddings (Fase C); None si no concluyente
    no_concluyente: bool          # el score no es concluyente (template no calibrado)
    score_veredicto: Optional[str]  # veredicto del score decidido por el nodo (valido/revision_manual/invalido); lo lee el router
    score_detalle: Optional[dict]   # desglose observable del score (componentes, umbrales, ref más parecida)
    campos: dict                    # valores extraídos por el LLM para las reglas (extract-then-check / corpus)
    zonas_resultado: list           # resultado POR zona: [{nombre,pagina,bbox,clase,estado,detalle,score?}] (observabilidad)
    cajetin_bbox: Optional[dict]  # {x,y,w,h} relativo (Fase C)
    resumen: Optional[str]        # resumen del veredicto

    # Revisión de contenido (Fase 1) — corre tras la admisión sobre el doc admitido
    revisar_auto: bool                  # toggle: continuar a revisión en el mismo invoke (si no, queda EN_REVISION)
    revision_extracto: dict             # lo que extrajo el extractor (n_paginas, tablas, ...) para los tiers
    hallazgos: list                     # hallazgos de la revisión (ver graph/revision.Hallazgo)
    verdicto_revision: Optional[str]    # aprobado | aprobado_con_notas | observado | rechazado | pendiente_senior
    severidad_max: Optional[str]        # mayor severidad accionable encontrada
    revision_confiabilidad: Optional[str]  # completa | parcial (hay checks no_verificable)
    revision_resuelta: bool             # un humano fijó el veredicto de revisión
    revisor_notas: Optional[str]        # notas del humano al resolver

    # Salida visible en el sandbox
    respuesta: Optional[str]       # mensaje al usuario (burbuja del chat, ui.reply_field)
    documentos_panel: list[dict]   # tarjetas de los documentos acumulados (ui.files_field)
    acciones: list[str]            # log de envíos "fake" y avisos


def initial_state(thread_id: str, **kwargs) -> CasoState:
    """Estado inicial con defaults seguros. `kwargs` sobrescribe campos."""
    base: CasoState = {
        "thread_id": thread_id,
        "tipo_entrega": None,
        "tipo_objetivo": None,
        "disciplina": None,
        "proyecto": None,
        "revision": None,
        "emisor": None,
        "norma_ref": None,
        "documentos": [],
        "nuevos_archivos": [],
        "entrega_completa": False,
        "admisibilidad": {},
        "rebotes_admisibilidad": 0,
        "ronda": 1,
        "status": Status.RECIBIDO.value,
        "checks": [],
        "score": None,
        "no_concluyente": True,
        "cajetin_bbox": None,
        "resumen": None,
        "revisar_auto": True,
        "revision_extracto": {},
        "hallazgos": [],
        "verdicto_revision": None,
        "severidad_max": None,
        "revision_confiabilidad": None,
        "revision_resuelta": False,
        "revisor_notas": None,
        "ref_thread_id": None,
        "respuesta": None,
        "documentos_panel": [],
        "acciones": [],
    }
    base.update(kwargs)  # type: ignore[typeddict-item]
    return base
