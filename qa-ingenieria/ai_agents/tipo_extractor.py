"""Captura el template de un tipo de documento desde un EJEMPLO modelo.

Dado un documento bien hecho de un tipo, propone el template (mismos campos que
knowledge/tipos/*.yaml) para que el usuario lo revise y guarde.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ai_agents.provider import build_agent
from ai_agents.util import build_input, extract_json, load_prompt, run_agent

_PROMPT = load_prompt("tipo_extractor")
_CAMPOS = (
    "tipo_doc", "nombre", "disciplinas", "formatos_archivo", "cajetin", "zonas",
    "secciones_requeridas", "columnas_requeridas", "caracteristicas", "nomenclatura",
    "bloqueante", "senales_reconocimiento", "criterios_aceptacion", "no_corresponde",
)


_FRAMING = {
    "ejemplo": (
        "FUENTE: este documento es un EJEMPLO (instancia real) del tipo. Inferí el "
        "template observando su ESTRUCTURA REAL (lo que ves en el ejemplo)."
    ),
    "especificacion": (
        "FUENTE: este documento es una ESPECIFICACIÓN / INSTRUCTIVO que DEFINE cómo "
        "debe ser un tipo de documento (NO es una instancia). Enumerá las REGLAS que "
        "el documento ESTABLECE como obligatorias y convertilas en el template: "
        "secciones_requeridas (con su numeración/títulos tal como las define, p. ej. "
        "OBJETIVO, ALCANCE, REFERENCIAS, DESARROLLO, ANEXOS...), campos del cajetín, "
        "tabla de revisiones, roles de firma (preparó/revisó/aprobó) y nomenclatura/"
        "código. Tratá los placeholders (ej: 'CPAA-CRMXXX-DOC-NNNN-Rv', "
        "'(TIPO DE DOCUMENTO)', '(TITULO)') como PATRONES, no como valores reales."
    ),
}


def proponer_template(
    filename: str,
    contenido: str,
    imagenes: list[str] | None = None,
    tipo_doc_hint: str = "",
    nombre_hint: str = "",
    modo: str = "ejemplo",
) -> dict[str, Any]:
    ext = Path(filename).suffix.lower().lstrip(".")
    entrada = "\n".join([
        _FRAMING.get(modo, _FRAMING["ejemplo"]),
        "",
        f"Archivo: {filename} (formato .{ext})",
        f"Hint tipo_doc: {tipo_doc_hint or '(ninguno)'}",
        f"Hint nombre: {nombre_hint or '(ninguno)'}",
        "",
        "Contenido extraído:",
        (contenido or "(sin texto; ver imágenes)")[:12000],
    ])

    default: dict[str, Any] = {
        "tipo_doc": tipo_doc_hint or Path(filename).stem.lower(),
        "nombre": nombre_hint or "",
        "disciplinas": [],
        "formatos_archivo": [ext] if ext else [],
        "cajetin": {"requerido": False, "campos_requeridos": [], "logo_empresa": False},
        "zonas": [],
        "secciones_requeridas": [],
        "columnas_requeridas": [],
        "caracteristicas": [],
        "nomenclatura": "",
        "bloqueante": ["archivo fuera de formatos_archivo"],
        "senales_reconocimiento": "",
        "criterios_aceptacion": "",
        "no_corresponde": "",
    }

    agent = build_agent("tipo-extractor", instructions=_PROMPT)
    out = run_agent(agent, build_input(entrada, imagenes or []))
    data = extract_json(out, default)
    return _finalizar(data, default, [ext], imagenes or [])


def _finalizar(data: dict[str, Any], default: dict[str, Any], exts: list[str],
               imagenes: list[str]) -> dict[str, Any]:
    """Normaliza la propuesta del LLM: solo campos conocidos, asegura formatos, y propone la
    zona de identidad por visión si el LLM no marcó ninguna."""
    limpio = {k: data.get(k, default[k]) for k in _CAMPOS}
    formatos = list(limpio.get("formatos_archivo") or [])
    for e in exts:
        if e and e not in formatos:
            formatos.append(e)
    limpio["formatos_archivo"] = formatos
    if not limpio.get("tipo_doc"):
        limpio["tipo_doc"] = default["tipo_doc"]

    zonas = limpio.get("zonas") or []
    if imagenes and not any(isinstance(z, dict) and z.get("identidad") for z in zonas):
        try:
            from ai_agents import similarity

            z = similarity.detectar_zona_identidad(imagenes)
            if z:
                zonas = [{"nombre": "Identidad (sugerida)", "bbox": z, "identidad": True}, *zonas]
        except Exception:
            pass
    limpio["zonas"] = zonas
    return limpio


def proponer_template_multi(
    docs: list[dict[str, Any]],
    tipo_doc_hint: str = "",
    nombre_hint: str = "",
    modo: str = "ejemplo",
) -> dict[str, Any]:
    """Captura un template CONSOLIDADO a partir de VARIOS ejemplos del mismo tipo (mejor que uno
    solo: generaliza en vez de sobreajustar). `docs`: [{filename, contenido, imagenes}].
    Devuelve {"template": <dict>, "cobertura": [{campo, patron, n, total}]} donde la cobertura es
    DETERMINISTA: cuántos de los N ejemplos cumplen cada patrón propuesto."""
    docs = [d for d in docs if d]
    if not docs:
        return {"template": {}, "cobertura": []}

    exts = [Path(d.get("filename", "")).suffix.lower().lstrip(".") for d in docs]
    partes = [
        _FRAMING.get(modo, _FRAMING["ejemplo"]),
        "",
        f"Recibís {len(docs)} EJEMPLOS del MISMO tipo de documento. Proponé UN template "
        "CONSOLIDADO que valga para TODOS: marcá `requerido` solo lo que aparece en todos; en las "
        "reglas/patrones, GENERALIZÁ para que cubran a todos los ejemplos (no te ajustes a uno solo).",
        f"Hint tipo_doc: {tipo_doc_hint or '(ninguno)'} · Hint nombre: {nombre_hint or '(ninguno)'}",
    ]
    imagenes: list[str] = []
    for i, d in enumerate(docs, 1):
        partes += ["", f"### Ejemplo {i}: {d.get('filename')} (.{exts[i - 1]})",
                   (d.get("contenido") or "(sin texto; ver imágenes)")[:6000]]
        imagenes.extend((d.get("imagenes") or [])[:2])  # un par de páginas por doc (build_input capa en 8)

    default: dict[str, Any] = {
        "tipo_doc": tipo_doc_hint or Path(docs[0].get("filename", "tipo")).stem.lower(),
        "nombre": nombre_hint or "", "disciplinas": [], "formatos_archivo": [],
        "cajetin": {"requerido": False, "campos_requeridos": [], "logo_empresa": False},
        "zonas": [], "secciones_requeridas": [], "columnas_requeridas": [], "caracteristicas": [],
        "nomenclatura": "", "bloqueante": ["archivo fuera de formatos_archivo"],
        "senales_reconocimiento": "", "criterios_aceptacion": "", "no_corresponde": "",
    }
    agent = build_agent("tipo-extractor", instructions=_PROMPT)
    out = run_agent(agent, build_input("\n".join(partes), imagenes))
    data = extract_json(out, default)
    template = _finalizar(data, default, exts, docs[0].get("imagenes") or [])
    return {"template": template, "cobertura": cobertura_reglas(template, [d.get("contenido", "") for d in docs])}


_REGEX_PROMPT = (
    "Sos un asistente de expresiones regulares. Te doy valores que DEBEN matchear y (a veces) "
    "valores que NO deben. Devolvé UNA sola regex de Python para re.search (SIN anclas ^ ni $, "
    "SIN barras /.../, SIN explicación ni texto extra) que matchee TODOS los 'DEBEN' y NINGUNO "
    "de los 'NO'. Generalizá lo justo: ni demasiado amplia ni pegada a un solo valor."
)


def proponer_regex(deben: list[str], no_deben: list[str]) -> str:
    """Propone una regex que cubra los valores 'deben' y excluya los 'no_deben' (LLM). El llamador
    DEBE verificarla deterministamente (tools.reglas.verificar_variante) antes de ofrecerla."""
    deben = [str(v) for v in (deben or []) if v]
    no_deben = [str(v) for v in (no_deben or []) if v]
    if not deben:
        return ""
    entrada = "DEBEN matchear:\n" + "\n".join(f"- {v}" for v in deben)
    if no_deben:
        entrada += "\n\nNO deben matchear:\n" + "\n".join(f"- {v}" for v in no_deben)
    agent = build_agent("regex-sugeridor", instructions=_REGEX_PROMPT)
    out = run_agent(agent, entrada)
    linea = next((ln.strip().strip("`").strip() for ln in (out or "").splitlines() if ln.strip()), "")
    return linea


def cobertura_reglas(template: dict[str, Any], textos: list[str]) -> list[dict[str, Any]]:
    """Para cada regla con patrón, cuántos de los textos lo cumplen (evidencia DETERMINISTA)."""
    reglas: list[tuple[str, str]] = []
    for z in template.get("zonas") or []:
        if z.get("campo") and z.get("patron"):
            reglas.append((z["campo"], z["patron"]))
    for r in (template.get("cajetin") or {}).get("reglas") or []:
        if r.get("campo") and r.get("patron"):
            reglas.append((r["campo"], r["patron"]))

    total = len(textos)
    out: list[dict[str, Any]] = []
    for campo, patron in reglas:
        try:
            rx = re.compile(patron, re.IGNORECASE)
        except re.error:
            out.append({"campo": campo, "patron": patron, "n": 0, "total": total, "error": True})
            continue
        n = sum(1 for t in textos if rx.search(t or ""))
        out.append({"campo": campo, "patron": patron, "n": n, "total": total})
    return out
