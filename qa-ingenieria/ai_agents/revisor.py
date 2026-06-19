"""Orquestador de la revisión de contenido (Fase 1).

Corre los tiers de barato a caro y ensambla `hallazgos[]` (ver `graph/revision.py`). Esta rebanada
implementa el **Tier 1** (determinístico: legibilidad + presencia de secciones, `tools/legibilidad`).
Los Tier 2 (reglas/tablas) y Tier 3 (VLM) se enchufan acá más adelante sin tocar el grafo.
"""

from __future__ import annotations

import os
from typing import Any

from graph.revision import Hallazgo, mk
from tools import docs, legibilidad, normas, reglas_revision


_BLANK_VAR = 10.0  # varianza Laplaciano por debajo de esto = hoja en blanco/casi vacía (no "borrosa")


def _leg_dpi() -> int:
    try:
        return int(os.getenv("OCR_DPI", "220"))
    except ValueError:
        return 220


def _indices_muestra(n: int, k: int) -> list[int]:
    """Índices 0-based de páginas a muestrear: portada + equiespaciadas + última (k como máx).
    Robusto a k=1 (sin división por cero) y a n pequeño."""
    if n <= 0:
        return []
    if n <= k:
        return list(range(n))
    return sorted({round(i * (n - 1) / max(1, k - 1)) for i in range(k)})


def _muestras_legibilidad(doc: dict) -> list[tuple[int, Any]]:
    """Páginas a muestrear para legibilidad. Cubre TODO el documento sin renderizar cada hoja.
    [(pagina_1indexed, img_data_url)]."""
    path = doc.get("path")
    if path and str(path).lower().endswith(".pdf"):
        n = docs.contar_paginas(path) or 1
        try:
            k = max(1, int(os.getenv("REVISION_LEG_SAMPLES", "6")))
        except ValueError:
            k = 6
        dpi = _leg_dpi()
        out = [(i + 1, docs.render_pdf_page(path, page=i + 1, dpi=dpi)) for i in _indices_muestra(n, k)]
        out = [(pg, im) for pg, im in out if im]
        if out:
            return out
    imgs = doc.get("imagenes") or []
    return [(1, imgs[0])] if imgs else []


def _tier1_legibilidad(doc: dict, cfg: dict) -> list[Hallazgo]:
    """Métricas físicas de la hoja: nitidez, confianza de OCR (muestreadas en TODO el doc), DPI.
    Reporta la PEOR página (la más borrosa / de menor confianza)."""
    out: list[Hallazgo] = []
    path = doc.get("path")
    leg = cfg.get("legibilidad") or {}
    muestras = _muestras_legibilidad(doc)

    # Nitidez: varianza Laplaciano por página muestreada -> la peor (mínima). Se ignoran las hojas
    # EN BLANCO (var≈0): no son "borrosas", y reportarlas daría falsos negativos.
    thr_blur = float(leg.get("blur_var_min", 120))
    vals = [(pg, legibilidad.varianza_laplaciano(im)) for pg, im in muestras]
    vals = [(pg, v) for pg, v in vals if v is not None and v > _BLANK_VAR]
    if not vals:
        out.append(mk("nitidez", "legibilidad", "mayor", "no_verificable", fuente="deterministico",
                      razonamiento="No hay páginas con contenido para medir nitidez (en blanco o sin render).",
                      ubicacion={"pagina": 1}))
    else:
        peor_pg, peor = min(vals, key=lambda x: x[1])
        ok = peor >= thr_blur
        out.append(mk("nitidez", "legibilidad", "mayor", "ok" if ok else "fallo", fuente="deterministico",
                      evidencia=f"varianza Laplaciano mínima {peor:.0f} en pág {peor_pg} (de {len(vals)} muestreadas, mínimo {thr_blur:.0f})",
                      razonamiento="Líneas/textos borrosos dificultan la revisión y la lectura de cotas.",
                      sugerencia="" if ok else "Re-exportar/re-escanear esa(s) hoja(s) en mayor calidad.",
                      ubicacion={"pagina": peor_pg}))

    # Confianza media de OCR: robusta por MAYORÍA (una hoja-diagrama suelta de baja confianza NO
    # reprueba el doc; sí lo hace si la mayoría de las hojas con texto está por debajo del umbral).
    thr_ocr = float(leg.get("ocr_conf_min", 0.70))
    confs = [(pg, legibilidad.confianza_ocr(im)) for pg, im in muestras]
    confs = [(pg, c) for pg, c in confs if c is not None]
    if not confs:
        out.append(mk("ocr_confianza", "legibilidad", "mayor", "no_verificable", fuente="deterministico",
                      razonamiento="OCR no disponible o sin texto legible para medir confianza.", ubicacion={"pagina": 1}))
    else:
        bajos = [(pg, c) for pg, c in confs if c < thr_ocr]
        peor_pg, peor = min(confs, key=lambda x: x[1])
        mayoria_baja = len(bajos) * 2 > len(confs)
        out.append(mk("ocr_confianza", "legibilidad", "mayor", "fallo" if mayoria_baja else "ok", fuente="deterministico",
                      evidencia=(f"{len(bajos)}/{len(confs)} hojas con confianza OCR < {thr_ocr:.0%} (mínima {peor:.0%} en pág {peor_pg})"
                                 if mayoria_baja else
                                 f"confianza OCR aceptable en {len(confs)} hojas (mínima {peor:.0%} en pág {peor_pg}, umbral {thr_ocr:.0%})"),
                      razonamiento="Mucho texto de baja confianza sugiere hojas poco legibles.",
                      sugerencia="" if not mayoria_baja else "Mejorar resolución/contraste del documento.",
                      ubicacion={"pagina": peor_pg}))

    # Resolución efectiva (DPI) — solo si la hoja es raster (escaneo)
    if leg.get("dpi_min"):
        thr_dpi = float(leg["dpi_min"])
        dpi = legibilidad.dpi_efectivo(path, 0)
        if dpi is None:
            out.append(mk("dpi", "legibilidad", "menor", "no_verificable", fuente="deterministico",
                          razonamiento="Página vectorial o DPI no determinable (no aplica el mínimo de escaneo).",
                          ubicacion={"pagina": 1}))
        else:
            ok = dpi >= thr_dpi
            out.append(mk("dpi", "legibilidad", "menor", "ok" if ok else "fallo", fuente="deterministico",
                          evidencia=f"{dpi:.0f} DPI (mínimo {thr_dpi:.0f})",
                          razonamiento="Resolución baja pierde detalle de símbolos y anotaciones.",
                          sugerencia="" if ok else "Re-escanear a mayor DPI.", ubicacion={"pagina": 1}))
    return out


def _tier1_presencia(doc: dict, cfg: dict) -> list[Hallazgo]:
    """Presencia de las secciones que el template marca obligatorias (por texto/OCR del doc)."""
    out: list[Hallazgo] = []
    texto = doc.get("contenido") or ""
    path = doc.get("path")
    for s in cfg.get("contenido_requerido") or []:
        cid = s.get("id") or "seccion"
        frase = s.get("detectar") or cid
        sev = s.get("severidad_si_falta", "menor")
        hay = legibilidad.contiene_seccion(texto, frase)
        ubic = legibilidad.ubicacion_seccion(path, frase, 0) if hay else {"pagina": 1}
        out.append(mk(cid, "contenido", sev, "ok" if hay else "fallo", fuente="deterministico",
                      evidencia=(f"se encontró «{frase}»" if hay else f"no se encontró «{frase}» en el documento"),
                      razonamiento=f"El template marca «{frase}» como sección obligatoria del tipo.",
                      sugerencia="" if hay else f"Incluir la sección «{frase}».", ubicacion=ubic))
    return out


def _tier2_reglas(doc: dict, cfg: dict, extracto: dict) -> list[Hallazgo]:
    """Tier 2 (determinista): vínculo doc↔norma + reglas sobre texto/tablas.
    1) Detección: ¿el doc DECLARA las normas que el template espera? (declarar la norma es un check).
    2) Aplicación: reglas del template + reglas de las normas (merge; el template pisa por id)."""
    out: list[Hallazgo] = []
    texto = doc.get("contenido") or ""
    tablas = (extracto or {}).get("tablas") or []

    # Conjunto final de requisitos (atajo `normas` + granular `requisitos` + inline − `excluir`).
    reglas = normas.resolver_requisitos(cfg)

    # 1) Detección del vínculo: normas esperadas = las listadas + las que están detrás de los requisitos.
    esperadas = sorted({*(cfg.get("normas") or []), *(r.get("norma_id") for r in reglas if r.get("norma_id"))})
    for det in normas.detectar_normas(texto, esperadas):
        declarada = det.get("declarada")
        out.append(mk(f"norma_declarada:{det['id']}", "norma", "mayor",
                      "ok" if declarada else "fallo", fuente="reglas",
                      evidencia=(f"el documento declara «{det['nombre']}»" if declarada
                                 else f"no se declara la norma esperada «{det['nombre']}»"),
                      razonamiento="El documento debe citar la norma/código de diseño aplicable.",
                      sugerencia="" if declarada else f"Citar «{det['nombre']}» en la sección de normas o el cajetín.",
                      norma_ref=det.get("norma_ref")))

    # 2) Aplicación de los requisitos resueltos (cada hallazgo cita su norma_ref).
    for r in reglas:
        out.append(reglas_revision.evaluar_regla(r, texto, tablas))
    return out


_DIMS = ("legibilidad", "norma", "contenido", "consistencia")
_SEVS = ("bloqueante", "mayor", "menor", "observacion")


def _a_hallazgos_vlm(observaciones: list) -> list[Hallazgo]:
    """Convierte las observaciones del VLM en hallazgos. estado='advertencia' + fuente='vlm' →
    la agregación nunca las deja bloquear por sí solas (§2.2). Pura (testeable)."""
    out: list[Hallazgo] = []
    for i, o in enumerate(observaciones or []):
        if not isinstance(o, dict):
            continue
        desc = (o.get("observacion") or o.get("descripcion") or "").strip()
        if not desc:
            continue
        sev = o.get("severidad") if o.get("severidad") in _SEVS else "observacion"
        dim = o.get("dimension") if o.get("dimension") in _DIMS else "norma"
        pag = o.get("pagina")
        ubic = {"pagina": int(pag)} if isinstance(pag, (int, float)) else None
        out.append(mk(f"vlm:{o.get('id') or i + 1}", dim, sev, "advertencia", fuente="vlm",
                      evidencia=desc[:300], razonamiento=(o.get("razonamiento") or "Observación del revisor (visión)."),
                      sugerencia=(o.get("sugerencia") or ""), ubicacion=ubic, norma_ref=o.get("norma_ref")))
    return out


def _tier3_vlm(doc: dict, cfg: dict) -> list[Hallazgo]:
    """Tier 3 (cualitativo): un VLM observa lo interpretativo con los criterios de la(s) norma(s) +
    `observacion_vlm.instrucciones`. Observaciones no bloqueantes. Degrada con gracia (LLM no disponible
    o `REVISION_VLM=0` → [])."""
    if (os.getenv("REVISION_VLM", "1") or "1").strip() == "0":
        return []
    instrucciones = ((cfg.get("observacion_vlm") or {}).get("instrucciones") or "").strip()
    norma_ids = sorted({r.get("norma_id") for r in normas.resolver_requisitos(cfg) if r.get("norma_id")}
                       | set(cfg.get("normas") or []))
    criterios = normas.vlm_de_normas(norma_ids)
    if not instrucciones and not criterios:
        return []
    try:
        from ai_agents.provider import build_agent
        from ai_agents.util import build_input, extract_json, load_prompt, run_agent

        partes = ["## Instrucciones de revisión (observación, NO bloqueante)"]
        if instrucciones:
            partes.append(instrucciones)
        for v in criterios:
            partes.append(f"### Criterios — {v['norma_ref']}\n{v['criterios']}")
        partes += ["", "## Texto del documento", (doc.get("contenido") or "")[:8000] or "(ver imágenes)"]
        agent = build_agent("revisor-qa", instructions=load_prompt("revisor"))
        out = run_agent(agent, build_input("\n".join(partes), doc.get("imagenes") or []))
        return _a_hallazgos_vlm(extract_json(out, {"observaciones": []}).get("observaciones") or [])
    except Exception:
        return []


def revisar(doc: dict, cfg: dict, extracto: dict | None = None) -> list[Hallazgo]:
    """Corre los tiers disponibles sobre un documento admitido y devuelve los hallazgos.
    `cfg` = bloque `revision:` del template; `extracto` = lo que dejó el extractor (tablas, etc.).
    Tier 1 (legibilidad/presencia) + Tier 2 (reglas/normas) + Tier 3 (observación VLM, no bloqueante)."""
    if not cfg:
        return []
    hallazgos: list[Hallazgo] = []
    hallazgos += _tier1_legibilidad(doc, cfg)
    hallazgos += _tier1_presencia(doc, cfg)
    hallazgos += _tier2_reglas(doc, cfg, extracto or {})
    hallazgos += _tier3_vlm(doc, cfg)
    return hallazgos
