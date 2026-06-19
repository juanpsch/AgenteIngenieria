"""Orquestador de la revisión de contenido (Fase 1).

Corre los tiers de barato a caro y ensambla `hallazgos[]` (ver `graph/revision.py`). Esta rebanada
implementa el **Tier 1** (determinístico: legibilidad + presencia de secciones, `tools/legibilidad`).
Los Tier 2 (reglas/tablas) y Tier 3 (VLM) se enchufan acá más adelante sin tocar el grafo.
"""

from __future__ import annotations

from typing import Any

from graph.revision import Hallazgo, mk
from tools import legibilidad


def _tier1_legibilidad(doc: dict, cfg: dict) -> list[Hallazgo]:
    """Métricas físicas de la hoja: nitidez, confianza de OCR, resolución (DPI)."""
    out: list[Hallazgo] = []
    imgs = doc.get("imagenes") or []
    path = doc.get("path")
    leg = cfg.get("legibilidad") or {}
    img0 = imgs[0] if imgs else None

    # Nitidez (varianza Laplaciano sobre la 1ª página)
    thr_blur = float(leg.get("blur_var_min", 120))
    var = legibilidad.varianza_laplaciano(img0) if img0 else None
    if var is None:
        out.append(mk("nitidez", "legibilidad", "mayor", "no_verificable", fuente="deterministico",
                      razonamiento="No se pudo medir la nitidez (sin render de página).", ubicacion={"pagina": 1}))
    else:
        ok = var >= thr_blur
        out.append(mk("nitidez", "legibilidad", "mayor", "ok" if ok else "fallo", fuente="deterministico",
                      evidencia=f"varianza Laplaciano {var:.0f} (mínimo {thr_blur:.0f})",
                      razonamiento="Líneas/textos borrosos dificultan la revisión y la lectura de cotas.",
                      sugerencia="" if ok else "Re-exportar el plano en mayor calidad o re-escanear sin compresión.",
                      ubicacion={"pagina": 1}))

    # Confianza media de OCR
    thr_ocr = float(leg.get("ocr_conf_min", 0.70))
    conf = legibilidad.confianza_ocr(img0) if img0 else None
    if conf is None:
        out.append(mk("ocr_confianza", "legibilidad", "mayor", "no_verificable", fuente="deterministico",
                      razonamiento="OCR no disponible o sin texto legible para medir confianza.", ubicacion={"pagina": 1}))
    else:
        ok = conf >= thr_ocr
        out.append(mk("ocr_confianza", "legibilidad", "mayor", "ok" if ok else "fallo", fuente="deterministico",
                      evidencia=f"confianza media OCR {conf:.0%} (mínimo {thr_ocr:.0%})",
                      razonamiento="Mucho texto de baja confianza sugiere una hoja poco legible.",
                      sugerencia="" if ok else "Mejorar resolución/contraste del escaneo.", ubicacion={"pagina": 1}))

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


def revisar(doc: dict, cfg: dict) -> list[Hallazgo]:
    """Corre los tiers disponibles sobre un documento admitido y devuelve los hallazgos.
    `cfg` = bloque `revision:` del template. Tier 1 implementado; 2 y 3 se agregan acá."""
    if not cfg:
        return []
    hallazgos: list[Hallazgo] = []
    hallazgos += _tier1_legibilidad(doc, cfg)
    hallazgos += _tier1_presencia(doc, cfg)
    # Tier 2 (reglas/tablas) y Tier 3 (VLM): se enchufan aquí en próximos incrementos.
    return hallazgos
