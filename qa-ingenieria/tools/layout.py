"""Localización de regiones por TEXTO — zonas 'ancladas' a palabras/regex.

Resuelve el bbox de una zona dinámicamente en CADA documento a partir de anclas (regex que
marcan el inicio y/o el fin). Usa las cajas de palabras de PyMuPDF (PDFs con capa de texto),
así la zona *sigue* al contenido aunque su posición cambie entre documentos — robusto a
desvíos de layout, más que un bbox fijo.

Degrada con gracia: si el PDF no tiene texto (escaneado) o no se encuentran las anclas,
devuelve None y el llamador cae al bbox estático de la zona. (Para escaneados se podría
sumar OCR tesseract; hoy no es necesario para PDFs con texto.)
"""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Optional


def _render_pil(page, dpi: int | None = None):
    """Renderiza la página a PIL (para OCR del texto que está solo en la imagen)."""
    from PIL import Image

    d = dpi or int(os.getenv("OCR_DPI", "220"))
    pix = page.get_pixmap(dpi=d)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def _lineas_norm(page) -> list[dict[str, Any]]:
    """Líneas {texto, y0, y1} con y NORMALIZADA (0–1). Usa la capa de texto del PDF; si no hay
    (escaneo / rasterizado), cae a OCR sobre el render. [] si no hay ninguna ni OCR."""
    h = float(page.rect.height) or 1.0
    ls = _lineas(page)
    if ls:
        return [{"texto": L["texto"], "y0": L["y0"] / h, "y1": L["y1"] / h} for L in ls]
    try:
        from tools import ocr

        if ocr.disponible():
            return ocr.ocr_lineas(_render_pil(page))
    except Exception:
        pass
    return []


def _lineas(page) -> list[dict[str, float]]:
    """Reconstruye líneas (texto + bbox en puntos) desde las palabras de la capa de texto."""
    palabras = page.get_text("words")  # (x0,y0,x1,y1, palabra, bloque, linea, n)
    lineas: dict[tuple, dict[str, Any]] = {}
    for x0, y0, x1, y1, w, b, ln, _n in palabras:
        key = (b, ln)
        L = lineas.get(key)
        if L is None:
            lineas[key] = {"t": [w], "x0": x0, "y0": y0, "x1": x1, "y1": y1}
        else:
            L["t"].append(w)
            L["x0"] = min(L["x0"], x0); L["y0"] = min(L["y0"], y0)
            L["x1"] = max(L["x1"], x1); L["y1"] = max(L["y1"], y1)
    out = []
    for key in sorted(lineas):
        L = lineas[key]
        out.append({"texto": " ".join(L["t"]), "y0": L["y0"], "y1": L["y1"]})
    return out


def _compilar(patron: str) -> re.Pattern:
    try:
        return re.compile(patron, re.IGNORECASE)
    except re.error:
        return re.compile(re.escape(patron), re.IGNORECASE)


def localizar_bbox(pdf_path: str, page_idx: int = 0,
                   ancla_inicio: str | None = None, ancla_fin: str | None = None) -> Optional[dict]:
    """bbox relativo (0–1, banda de ancho completo) entre la línea que matchea `ancla_inicio` y
    la que matchea `ancla_fin` (regex). Si solo hay inicio, banda de alto por defecto. None si
    no hay anclas, el PDF no tiene texto, o no se encuentran."""
    if not ancla_inicio and not ancla_fin:
        return None
    p = Path(pdf_path)
    if p.suffix.lower() != ".pdf" or not p.exists():
        return None
    try:
        import fitz

        with fitz.open(str(p)) as doc:
            if page_idx >= doc.page_count:
                return None
            lineas = _lineas_norm(doc[page_idx])  # y normalizada 0–1 (capa de texto u OCR)
            if not lineas:
                return None

            def buscar(patron: str | None, desde: int = 0) -> Optional[int]:
                if not patron:
                    return None
                rx = _compilar(patron)
                for i in range(desde, len(lineas)):
                    if rx.search(lineas[i]["texto"]):
                        return i
                return None

            i0 = buscar(ancla_inicio) if ancla_inicio else 0
            if i0 is None:
                return None
            i1 = buscar(ancla_fin, i0) if ancla_fin else None
            y0 = lineas[i0]["y0"]
            y1 = lineas[i1]["y1"] if i1 is not None else min(1.0, y0 + 0.18)
            yb0 = max(0.0, y0 - 0.01)
            yb1 = min(1.0, y1 + 0.01)
            if yb1 - yb0 < 0.02:
                yb1 = min(1.0, yb0 + 0.02)
            return {"x": 0.0, "y": round(yb0, 4), "w": 1.0, "h": round(yb1 - yb0, 4)}
    except Exception:
        return None


def _valor_tras_ancla(lineas: list[str], ancla: str) -> Optional[str]:
    """Valor que sigue al ancla (regex) en la misma línea; si no hay nada después, la línea
    siguiente no vacía. Pure (testeable sin PDF)."""
    rx = _compilar(ancla)
    for i, t in enumerate(lineas):
        m = rx.search(t)
        if m:
            resto = t[m.end():].strip(" :.–—\-\t|=")
            if resto:
                return resto
            for j in range(i + 1, min(i + 3, len(lineas))):
                if lineas[j].strip():
                    return lineas[j].strip()
            return None
    return None


def _refinar(texto: str | None, patron: str | None) -> Optional[str]:
    """Si hay patrón, devuelve el primer match dentro del texto (el token preciso); si no, el
    texto limpio. None si no hay nada / no matchea."""
    t = (texto or "").strip()
    if not t:
        return None
    if patron:
        m = _compilar(patron).search(t)
        return m.group(0) if m else None
    return t


def _extraer_valor(lineas: list[str], ancla_inicio: str | None, ancla_fin: str | None,
                   patron: str | None) -> Optional[str]:
    """Valor de texto acotado por anclas, refinado por patrón:
    - inicio + fin → el texto ENTRE ambas marcas (puede abarcar varias líneas), refinado por patrón;
    - solo inicio + patrón → el ancla UBICA la línea y el patrón extrae el token de esa línea (el
      token puede incluir al ancla, p. ej. ancla "ECA-BRD" + patrón "ECA-BRD-[0-9]+");
    - solo inicio sin patrón → el valor que sigue al ancla (misma línea o la siguiente: caso etiqueta).
    """
    if ancla_inicio and ancla_fin:
        texto = "\n".join(lineas)
        ri = _compilar(ancla_inicio).search(texto)
        if not ri:
            return None
        rf = _compilar(ancla_fin).search(texto, ri.end())
        span = texto[ri.end(): rf.start()] if rf else texto[ri.end():]
        return _refinar(span.strip(" :.\n\t|=–—-"), patron)

    if ancla_inicio and patron:
        rx_a, rx_p = _compilar(ancla_inicio), _compilar(patron)
        for i, t in enumerate(lineas):
            if rx_a.search(t):
                for cand in (t, lineas[i + 1] if i + 1 < len(lineas) else ""):
                    m = rx_p.search(cand)
                    if m:
                        return m.group(0)
                return None
        return None

    if ancla_inicio:
        return _valor_tras_ancla(lineas, ancla_inicio)
    return _refinar("\n".join(lineas), patron)


def _texto_en_bbox(page, bbox: dict) -> str:
    """Texto cuyas palabras caen dentro del bbox relativo (0–1) de la página."""
    w, h = float(page.rect.width), float(page.rect.height)
    rx0, ry0 = bbox.get("x", 0) * w, bbox.get("y", 0) * h
    rx1 = (bbox.get("x", 0) + bbox.get("w", 0)) * w
    ry1 = (bbox.get("y", 0) + bbox.get("h", 0)) * h
    out = []
    for x0, y0, x1, y1, palabra, *_ in page.get_text("words"):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
            out.append(palabra)
    return " ".join(out).strip()


def extraer_campos_zonas(pdf_path: str | None, zonas: list[dict]) -> dict[str, str]:
    """Extrae DETERMINÍSTICAMENTE el valor de cada zona con `campo` (mejora 'b'):
    - con `ancla_inicio`: el valor que sigue al ancla (posición VARIABLE, sigue al texto);
    - si no, con su `bbox`: el texto dentro del recuadro (posición FIJA).
    Devuelve {campo: valor}. Vacío si el PDF no tiene texto o no se encuentra (cae al LLM)."""
    out: dict[str, str] = {}
    if not pdf_path:
        return out
    p = Path(pdf_path)
    if p.suffix.lower() != ".pdf" or not p.exists():
        return out
    try:
        import fitz

        with fitz.open(str(p)) as doc:
            cache: dict[int, list[str]] = {}
            for z in zonas or []:
                campo = z.get("campo")
                if not campo or z.get("comparar") == "visual":  # las visuales no extraen texto
                    continue
                pg = max(0, int(z.get("pagina", 1) or 1) - 1)
                if pg >= doc.page_count:
                    continue
                page = doc[pg]
                patron = z.get("patron")
                val: Optional[str] = None
                if z.get("ancla_inicio") or z.get("ancla_fin"):
                    if pg not in cache:
                        cache[pg] = [ln["texto"] for ln in _lineas_norm(page)]  # capa de texto u OCR
                    val = _extraer_valor(cache[pg], z.get("ancla_inicio"), z.get("ancla_fin"), patron)
                else:
                    bb = z.get("bbox") or {}
                    if float(bb.get("w", 0)) > 0 and float(bb.get("h", 0)) > 0:
                        txt = _texto_en_bbox(page, bb) or _ocr_bbox(page, bb)  # capa de texto, si no OCR
                        val = _refinar(txt, patron)
                if val:
                    out[campo] = val
    except Exception:
        pass
    return out


def _ocr_bbox(page, bb: dict) -> str:
    """OCR del recorte (bbox relativo) cuando el texto está solo en la imagen. '' si no hay OCR."""
    try:
        from tools import ocr

        if not ocr.disponible():
            return ""
        pil = _render_pil(page)
        w, h = pil.size
        crop = pil.crop((int(bb.get("x", 0) * w), int(bb.get("y", 0) * h),
                         int((bb.get("x", 0) + bb.get("w", 0)) * w),
                         int((bb.get("y", 0) + bb.get("h", 0)) * h)))
        return ocr.ocr_texto(crop, psm=6)
    except Exception:
        return ""


def _y_de_ancla(pdf_path: str, page_idx: int, ancla: str) -> Optional[float]:
    """`y` relativa (0–1) de la línea que matchea el ancla (capa de texto u OCR). Para el recuadro anclado."""
    p = Path(pdf_path)
    if p.suffix.lower() != ".pdf" or not p.exists():
        return None
    try:
        import fitz

        with fitz.open(str(p)) as doc:
            if page_idx >= doc.page_count:
                return None
            rx = _compilar(ancla)
            for ln in _lineas_norm(doc[page_idx]):
                if rx.search(ln["texto"]):
                    return ln["y0"]
    except Exception:
        pass
    return None


def bbox_efectivo(zona: dict, pdf_path: str | None) -> Optional[dict]:
    """bbox a usar para una zona (visual) en ESTE documento:
    - ancla + recuadro (w,h) → 'recuadro anclado': conserva el tamaño/x del recuadro y lo sigue
      VERTICALMENTE hasta donde aparece el ancla (posición variable, región precisa);
    - solo ancla → banda de ancho completo entre inicio/fin (localizar_bbox);
    - sin ancla → el recuadro estático dibujado a mano."""
    pagina = max(0, int(zona.get("pagina", 1) or 1) - 1)
    ancla = zona.get("ancla_inicio")
    bb = zona.get("bbox") or {}
    tiene_box = float(bb.get("w", 0)) > 0 and float(bb.get("h", 0)) > 0

    if pdf_path and ancla and tiene_box:
        y = _y_de_ancla(pdf_path, pagina, ancla)
        if y is not None:
            return {"x": bb["x"], "y": max(0.0, min(1.0, y)),
                    "w": bb["w"], "h": min(bb["h"], 1.0 - max(0.0, min(1.0, y)))}
        return bb  # ancla no encontrada → recuadro estático
    if pdf_path and (zona.get("ancla_inicio") or zona.get("ancla_fin")):
        dyn = localizar_bbox(pdf_path, pagina, zona.get("ancla_inicio"), zona.get("ancla_fin"))
        if dyn:
            return dyn
    return zona.get("bbox")
