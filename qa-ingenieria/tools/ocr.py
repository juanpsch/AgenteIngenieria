"""OCR opcional para texto que vive solo en la imagen (escaneos, cajetines rasterizados).

Proveedor configurable (`OCR_PROVIDER`, default "tesseract" — local, en tu máquina/contenedor,
sin enviar datos a terceros). Degrada con gracia: si tesseract no está instalado, `disponible()`
devuelve False y todo cae al LLM (sin romper nada). Es una **fuente de texto de bajo nivel**: la
usan `tools/docs` (captura/cobertura) y `tools/layout` (validación por zonas).

Instalar (local, para probar):
  - Windows: instalá Tesseract (build de UB Mannheim) + idioma español, y `uv add pytesseract`.
  - Linux/Docker: `apt-get install -y tesseract-ocr tesseract-ocr-spa` + `pytesseract`.
"""

from __future__ import annotations

import base64
import io
import os
from functools import lru_cache
from typing import Any, Optional


def _provider() -> str:
    return (os.getenv("OCR_PROVIDER") or "tesseract").strip().lower()


def _lang() -> str:
    return os.getenv("OCR_LANG") or "spa+eng"


def _min_conf() -> float:
    try:
        return float(os.getenv("OCR_MIN_CONF", "40"))
    except ValueError:
        return 40.0


def _config(psm: int) -> str:
    """Config de tesseract: PSM + carpeta de idiomas opcional (OCR_TESSDATA_DIR)."""
    cfg = f"--psm {psm}"
    td = os.getenv("OCR_TESSDATA_DIR")
    if td:
        # pytesseract parte el config por espacios: NO usar comillas y evitar rutas con espacios.
        cfg = f"--tessdata-dir {td} " + cfg
    return cfg


@lru_cache(maxsize=1)
def _engine():
    """Devuelve el módulo pytesseract si está operativo (con binario), o None (degrade)."""
    if _provider() != "tesseract":
        return None
    try:
        import pytesseract

        cmd = os.getenv("TESSERACT_CMD")  # ruta al binario si no está en el PATH
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        pytesseract.get_tesseract_version()  # falla si el binario no está instalado
        return pytesseract
    except Exception:
        return None


def disponible() -> bool:
    return _engine() is not None


def _to_pil(img: Any):
    from PIL import Image

    if hasattr(img, "size") and hasattr(img, "mode"):  # ya es PIL
        return img.convert("RGB")
    if isinstance(img, str) and img.startswith("data:"):
        return Image.open(io.BytesIO(base64.b64decode(img.split(",", 1)[1]))).convert("RGB")
    if isinstance(img, (bytes, bytearray)):
        return Image.open(io.BytesIO(img)).convert("RGB")
    return Image.open(img).convert("RGB")


def ocr_texto(img: Any, psm: int = 6) -> str:
    """Imagen -> texto plano. psm 6=bloque, 7=una línea. '' si no hay OCR o falla."""
    eng = _engine()
    if not eng:
        return ""
    try:
        return eng.image_to_string(_to_pil(img), lang=_lang(), config=_config(psm)).strip()
    except Exception:
        return ""


def confianza(img: Any) -> Optional[float]:
    """Confianza media del OCR (0–1) sobre la imagen: proxy de legibilidad (Tier 1 de revisión).
    None si no hay OCR. Promedia la confianza de las palabras con conf >= 0 y ≥2 caracteres."""
    eng = _engine()
    if not eng:
        return None
    try:
        data = eng.image_to_data(_to_pil(img), lang=_lang(), config=_config(6), output_type=eng.Output.DICT)
        confs = []
        for k in range(len(data["text"])):
            txt = (data["text"][k] or "").strip()
            try:
                c = float(data["conf"][k])
            except (ValueError, TypeError):
                c = -1.0
            if len(txt) >= 2 and c >= 0:
                confs.append(c)
        return round(sum(confs) / len(confs) / 100.0, 3) if confs else None
    except Exception:
        return None


def ocr_lineas(img: Any) -> list[dict[str, Any]]:
    """Imagen -> líneas [{texto, y0, y1}] con y NORMALIZADA (0–1). Para anclas en escaneos.
    Filtra palabras con confianza < OCR_MIN_CONF. [] si no hay OCR o falla."""
    eng = _engine()
    if not eng:
        return []
    try:
        pil = _to_pil(img)
        h = float(pil.size[1]) or 1.0
        data = eng.image_to_data(pil, lang=_lang(), config=_config(6), output_type=eng.Output.DICT)
        lineas: dict[tuple, dict[str, Any]] = {}
        for k in range(len(data["text"])):
            txt = (data["text"][k] or "").strip()
            try:
                conf = float(data["conf"][k])
            except (ValueError, TypeError):
                conf = -1.0
            if not txt or conf < _min_conf():
                continue
            key = (data["block_num"][k], data["par_num"][k], data["line_num"][k])
            top = float(data["top"][k])
            bot = top + float(data["height"][k])
            L = lineas.get(key)
            if L is None:
                lineas[key] = {"t": [txt], "y0": top, "y1": bot}
            else:
                L["t"].append(txt)
                L["y0"] = min(L["y0"], top)
                L["y1"] = max(L["y1"], bot)
        return [{"texto": " ".join(lineas[k]["t"]), "y0": lineas[k]["y0"] / h, "y1": lineas[k]["y1"] / h}
                for k in sorted(lineas)]
    except Exception:
        return []
