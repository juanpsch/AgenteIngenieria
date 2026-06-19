"""Triage: admisibilidad + completitud (chequeo por TIPO de documento).

Para cada documento recibido: lo clasifica en un tipo conocido, lo chequea contra
el TEMPLATE de ese tipo (knowledge/tipos/*.yaml) aplicando sus reglas bloqueantes,
y resuelve completitud contra los tipos requeridos de la entrega.

Salida JSON con regex + fallback. Si no se puede evaluar, cae a un default
conservador (no admisible) para no dejar pasar basura.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_agents.provider import build_agent
from ai_agents.util import build_input, extract_json, load_prompt, run_agent
from tools.tipos import cargar_tipos, reglas_de, render_template

_PROMPT = load_prompt("triage")
_PROMPT_COTEJAR = load_prompt("cotejar")
_MAX_DOC_CHARS = 10_000


def _norm_bbox(raw: Any) -> dict[str, float] | None:
    """Coacciona el bbox del LLM a {x,y,w,h} floats en [0,1], o None si no es válido."""
    if not isinstance(raw, dict):
        return None
    try:
        bbox = {k: float(raw[k]) for k in ("x", "y", "w", "h")}
    except (KeyError, TypeError, ValueError):
        return None
    if bbox["w"] <= 0 or bbox["h"] <= 0:
        return None
    return {k: min(1.0, max(0.0, v)) for k, v in bbox.items()}


def run_cotejar(documento: dict[str, Any], tipo_objetivo: str) -> dict[str, Any]:
    """Cotejo single-doc: valida UN documento contra el TEMPLATE del tipo elegido.

    Devuelve `{es_el_tipo, checks[], cajetin_bbox, razonamiento, resumen}` (checks de
    Identidad + Completitud cualitativa). El cajetín se localiza en ESTA misma llamada
    (la imagen ya viaja al LLM): evita una 2ª llamada de visión. El score va aparte.
    """
    tpl = cargar_tipos().get(tipo_objetivo)
    template_txt = render_template(tpl) if tpl else f"(tipo '{tipo_objetivo}' no encontrado)"
    ext = Path(documento.get("filename", "")).suffix.lower().lstrip(".")
    contenido = (documento.get("contenido") or "")[:_MAX_DOC_CHARS]
    imagenes = documento.get("imagenes") or []

    # Campos que las reglas deterministas necesitan: el LLM SOLO los encuentra (extract);
    # la validación (regex / match-filename / presencia) la hace el motor determinista.
    campos = []
    if tpl:
        for r in reglas_de(tpl):
            c = r.get("campo")
            if c and c not in campos:
                campos.append(c)

    partes = [
        f"## Tipo elegido a validar: {tipo_objetivo}",
        "## Template del tipo",
        template_txt,
        "",
        f"## Documento recibido: {documento.get('filename')} (formato: .{ext})",
        contenido or "(sin texto extraído; ver imágenes)",
    ]
    if campos:
        partes += ["", "## Campos a EXTRAER (devolvé su valor textual exacto tal como aparece, "
                   "o null si no está; NO los valides vos):", ", ".join(campos)]
    texto = "\n".join(partes)

    default: dict[str, Any] = {
        "es_el_tipo": False,
        "checks": [],
        "campos": {},
        "cajetin_bbox": None,
        "razonamiento": "",
        "resumen": "no se pudo evaluar automáticamente",
    }
    agent = build_agent("cotejar-qa", instructions=_PROMPT_COTEJAR)
    out = run_agent(agent, build_input(texto, imagenes))
    res = extract_json(out, default)
    res["cajetin_bbox"] = _norm_bbox(res.get("cajetin_bbox"))
    if not isinstance(res.get("campos"), dict):
        res["campos"] = {}
    return res


def run_triage(
    tipo_entrega: str | None,
    disciplina: str | None,
    proyecto: str | None,
    documentos: list[dict[str, Any]],
    requeridos: list[str],
) -> dict[str, Any]:
    tipos = cargar_tipos()
    templates_txt = "\n\n".join(render_template(t) for t in tipos.values()) or "(no hay tipos definidos)"

    partes: list[str] = [
        "## Datos de la entrega",
        f"- tipo_entrega: {tipo_entrega}",
        f"- disciplina: {disciplina}",
        f"- proyecto: {proyecto}",
        "",
        "## Tipos de documento conocidos (sus templates)",
        templates_txt,
        "",
        f"## Documentos requeridos para esta entrega (por tipo_doc)\n{requeridos or '(no se pudieron resolver)'}",
        "",
        "## Documentos recibidos",
    ]
    imagenes: list[str] = []
    if not documentos:
        partes.append("(ningún documento adjunto)")
    for d in documentos:
        ext = Path(d.get("filename", "")).suffix.lower().lstrip(".")
        contenido = (d.get("contenido") or "")[:_MAX_DOC_CHARS]
        legible = d.get("legible", True)
        nota = "" if legible else "  [NO LEGIBLE: " + (d.get("motivo") or "") + "]"
        partes.append(f"### {d.get('filename')} (formato: .{ext}){nota}\n{contenido or '(sin texto extraído)'}")
        imagenes.extend(d.get("imagenes") or [])

    texto = "\n".join(partes)

    default: dict[str, Any] = {
        "es_admisible": False,
        "completa": False,
        "faltantes": list(requeridos),
        "irrelevantes": [],
        "documentos": [],
        "motivo": "no se pudo evaluar la entrega automáticamente",
    }

    agent = build_agent("triage-qa", instructions=_PROMPT)
    out = run_agent(agent, build_input(texto, imagenes))
    return extract_json(out, default)
