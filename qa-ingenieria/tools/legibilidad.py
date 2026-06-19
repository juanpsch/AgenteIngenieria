"""Métricas determinísticas de legibilidad/presencia (Tier 1 de la revisión de contenido).

Sin LLM: se MIDE (nitidez, resolución, confianza de OCR) y se detecta PRESENCIA de secciones por
texto. Todo degrada con gracia: si algo no se puede medir, el caller lo marca `no_verificable`
(nunca `ok` inventado). Reusa `tools/ocr` (confianza) y `tools/layout` (búsqueda anclada por texto).
"""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path
from typing import Any, Optional


def _to_pil(img: Any):
    from PIL import Image

    if hasattr(img, "size") and hasattr(img, "mode"):
        return img
    if isinstance(img, str) and img.startswith("data:"):
        return Image.open(io.BytesIO(base64.b64decode(img.split(",", 1)[1])))
    if isinstance(img, (bytes, bytearray)):
        return Image.open(io.BytesIO(img))
    return Image.open(img)


def varianza_laplaciano(img: Any) -> Optional[float]:
    """Varianza del Laplaciano en escala de grises (proxy de nitidez): bajo = borroso.
    Implementado con numpy (sin OpenCV). None si no se puede leer la imagen."""
    try:
        import numpy as np

        g = np.asarray(_to_pil(img).convert("L"), dtype=np.float64)
        if g.ndim != 2 or min(g.shape) < 3:
            return None
        # Laplaciano 4-vecinos: -4·centro + arriba + abajo + izq + der
        lap = (-4.0 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
        return round(float(lap.var()), 1)
    except Exception:
        return None


def confianza_ocr(img: Any) -> Optional[float]:
    """Confianza media del OCR (0–1). None si no hay OCR disponible."""
    try:
        from tools import ocr

        return ocr.confianza(img)
    except Exception:
        return None


def dpi_efectivo(pdf_path: str | None, page_idx: int = 0) -> Optional[float]:
    """DPI real del escaneo: resolución de la mayor imagen embebida vs el tamaño de la página.
    None si la página es vectorial (sin raster: calidad inherentemente alta → no aplica) o no se puede."""
    if not pdf_path:
        return None
    p = Path(pdf_path)
    if p.suffix.lower() != ".pdf" or not p.exists():
        return None
    try:
        import fitz

        with fitz.open(str(p)) as doc:
            if page_idx >= doc.page_count:
                return None
            page = doc[page_idx]
            alto_in = (float(page.rect.height) / 72.0) or 1.0
            px_alto = 0
            for img in page.get_images(full=True):
                xref = img[0]
                info = doc.extract_image(xref)
                px_alto = max(px_alto, int(info.get("height", 0)))
            return round(px_alto / alto_in, 0) if px_alto else None
    except Exception:
        return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9áéíóúñ ]+", " ", (s or "").lower())


def contiene_seccion(texto: str, frase: str) -> bool:
    """¿El texto del documento menciona la sección? Match por tokens significativos (≥3 letras):
    todos presentes (tolerante a orden/relleno). P. ej. 'cuadro de cargas' → 'cuadro' y 'cargas'."""
    if not frase:
        return False
    base = _norm(texto)
    toks = [t for t in _norm(frase).split() if len(t) >= 3]
    if not toks:
        return frase.lower() in (texto or "").lower()
    return all(t in base for t in toks)


def ubicacion_seccion(pdf_path: str | None, frase: str, page_idx: int = 0) -> Optional[dict]:
    """{pagina, bbox} de la sección si se la puede anclar por texto (para 'ver en plano'). None si no."""
    try:
        from tools.layout import localizar_bbox

        bbox = localizar_bbox(pdf_path, page_idx, frase) if pdf_path else None
        return {"pagina": page_idx + 1, "bbox": bbox} if bbox else None
    except Exception:
        return None
