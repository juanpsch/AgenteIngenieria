"""Modelos Pydantic de request para la API Cotejar (las respuestas van como dicts)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TemplateIn(BaseModel):
    yaml: str  # contenido YAML del template (lo valida tools.tipos.guardar_template)


class ZonasIn(BaseModel):
    # zonas gráficas: [{nombre, bbox{x,y,w,h}, identidad?, campo?, patron?, tipo?, requerido?}]
    zonas: list[dict[str, Any]] | None = None


class EntregaTipoIn(BaseModel):
    documentos_requeridos: list[str]


class DisciplinaIn(BaseModel):
    nombre: str


class DecisionIn(BaseModel):
    decision: str  # "approved" | "rejected"


class RevisionDecisionIn(BaseModel):
    # veredicto humano de la revisión de contenido (Fase 1)
    decision: str  # "aprobado" | "aprobado_con_notas" | "observado" | "rechazado" | "escalar_senior"
    notas: str | None = None


class PromoverIn(BaseModel):
    thread_id: str
    promote: bool = True


class SugerirVarianteIn(BaseModel):
    campo: str
    valor: str  # el valor que el humano dice que SÍ debería pasar


class AplicarReglaIn(BaseModel):
    campo: str
    patron: str
