"""Similitud por embeddings de imagen (Cotejar §3.1).

Proveedor configurable (`EMBED_PROVIDER`, default "local" = CLIP vía open-clip-torch).
Embebe imágenes (páginas renderizadas y/o recorte del cajetín) y calcula el score como
coseno del candidato contra el set de referencias del template (top-k mean), en [0,100].

Degrada con gracia: si el modelo/deps no están disponibles, `embed_*` devuelve None y el
flujo sigue por reglas (score None / no concluyente). Nunca rompe el cotejo.

El SCORE jamás se le pide al LLM (regla del spec). El LLM solo se usa para localizar el
cajetín (bounding box), que es localización, no un número de similitud.
"""

from __future__ import annotations

import base64
import io
import os
from functools import lru_cache
from typing import Any, Optional

from ai_agents.provider import build_agent
from ai_agents.util import build_input, extract_json, run_agent


def _provider() -> str:
    return (os.getenv("EMBED_PROVIDER") or "local").strip().lower()


def _model_name() -> str:
    return os.getenv("EMBED_MODEL") or "ViT-B-32"


def _pretrained() -> str:
    return os.getenv("EMBED_PRETRAINED") or "laion2b_s34b_b79k"


def _topk() -> int:
    return int(os.getenv("SIM_TOPK", "3"))


@lru_cache(maxsize=1)
def _clip():
    """Carga perezosa del modelo CLIP local. Devuelve None si no se puede (degrade).

    Por defecto carga en modo OFFLINE (HF_HUB_OFFLINE): el modelo ya está en la cache local,
    así evitamos un ping a HuggingFace Hub que, con red lenta/caída, COLGABA la primera carga
    tras cada reinicio del worker. Para la descarga inicial en una máquina nueva, exportá
    EMBED_ALLOW_DOWNLOAD=1 una vez."""
    if _provider() != "local":
        return None
    try:
        if os.getenv("EMBED_ALLOW_DOWNLOAD", "").lower() not in ("1", "true", "yes"):
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

        import open_clip
        import torch

        model, _, preprocess = open_clip.create_model_and_transforms(
            _model_name(), pretrained=_pretrained()
        )
        model.eval()
        return (model, preprocess, torch)
    except Exception:
        return None


def disponible() -> bool:
    """¿Hay backend de embeddings operativo?"""
    return _clip() is not None


def _to_pil(img: Any):
    from PIL import Image

    if isinstance(img, str) and img.startswith("data:"):
        raw = base64.b64decode(img.split(",", 1)[1])
        return Image.open(io.BytesIO(raw)).convert("RGB")
    if isinstance(img, (bytes, bytearray)):
        return Image.open(io.BytesIO(img)).convert("RGB")
    return Image.open(img).convert("RGB")


def embed_image(img: Any) -> Optional[list[float]]:
    c = _clip()
    if not c:
        return None
    model, preprocess, torch = c
    try:
        pil = _to_pil(img)
        with torch.no_grad():
            tensor = preprocess(pil).unsqueeze(0)
            vec = model.encode_image(tensor)
            vec = vec / vec.norm(dim=-1, keepdim=True)
        return vec[0].tolist()
    except Exception:
        return None


def embed_images(imgs: list[Any]) -> list[list[float]]:
    out: list[list[float]] = []
    for im in imgs or []:
        e = embed_image(im)
        if e:
            out.append(e)
    return out


def _cos(a: list[float], b: list[float]) -> float:
    import numpy as np

    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    den = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(np.dot(va, vb) / den) if den else 0.0


def _topk_mean(cands: list[list[float]], refs: list[list[float]]) -> Optional[float]:
    """Media de los top-k cosenos entre dos conjuntos de vectores (coseno crudo [-1,1])."""
    if not cands or not refs:
        return None
    sims = sorted((_cos(c, r) for c in cands for r in refs), reverse=True)
    if not sims:
        return None
    top = sims[: min(_topk(), len(sims))]
    return sum(top) / len(top)


def score(cand_vectors: list[list[float]], ref_vectors: list[list[float]]) -> Optional[float]:
    """0–100 = media de los top-k cosenos candidato×referencias. None si falta data."""
    m = _topk_mean(cand_vectors, ref_vectors)
    return round(max(0.0, min(1.0, m)) * 100, 1) if m is not None else None


def _pesos() -> tuple[float, float]:
    """Pesos (cajetín, página) normalizados para el score ponderado."""
    wc = float(os.getenv("SIM_WEIGHT_CAJETIN", "0.7"))
    wp = float(os.getenv("SIM_WEIGHT_PAGINA", "0.3"))
    s = wc + wp
    return (wc / s, wp / s) if s else (0.5, 0.5)


def score_grupos(cand: dict, ref_groups: list[dict]) -> Optional[float]:
    """Score 0–100 ponderando cajetín vs página (§3.1).

    `cand`/`ref` = {"paginas": [vec...], "cajetin": [vec...]}. Combina:
      score = w_cajetin · sim(cajetín) + w_pagina · sim(página).
    Si falta el cajetín en algún lado, cae con gracia al score de página sola
    (y viceversa). None si no hay datos comparables.
    """
    cand_pag = cand.get("paginas") or []
    cand_caj = cand.get("cajetin") or []
    ref_pag = [v for g in ref_groups for v in (g.get("paginas") or [])]
    ref_caj = [v for g in ref_groups for v in (g.get("cajetin") or [])]

    sim_pag = _topk_mean(cand_pag, ref_pag)
    sim_caj = _topk_mean(cand_caj, ref_caj)

    if sim_pag is None and sim_caj is None:
        return None
    if sim_caj is None:
        val = sim_pag
    elif sim_pag is None:
        val = sim_caj
    else:
        wc, wp = _pesos()
        val = wc * sim_caj + wp * sim_pag
    return round(max(0.0, min(1.0, val)) * 100, 1)


def _pct(sim: Optional[float]) -> Optional[float]:
    return round(max(0.0, min(1.0, sim)) * 100, 1) if sim is not None else None


def detalle_score(cand: dict, ref_groups: list[dict]) -> dict:
    """Desglose observable del score: componentes (cajetín/página) y la referencia más
    parecida. Para que el humano vea QUÉ se comparó, no solo el número final."""
    cand_pag = cand.get("paginas") or []
    cand_caj = cand.get("cajetin") or []
    ref_pag = [v for g in ref_groups for v in (g.get("paginas") or [])]
    ref_caj = [v for g in ref_groups for v in (g.get("cajetin") or [])]

    top_idx, top_score = None, None
    for i, g in enumerate(ref_groups):
        s = score_grupos(cand, [g])
        if s is not None and (top_score is None or s > top_score):
            top_idx, top_score = i, s

    return {
        "score": score_grupos(cand, ref_groups),
        "cajetin": _pct(_topk_mean(cand_caj, ref_caj)),
        "pagina": _pct(_topk_mean(cand_pag, ref_pag)),
        "top_index": top_idx,
        "top_score": top_score,
    }


def umbrales_calibrados(ref_groups: list[dict]) -> Optional[tuple[float, float]]:
    """(aprobación, revisión) estimados de la distribución intra-referencias (leave-one-out).

    Cada referencia se puntúa contra las demás con la MISMA métrica que el candidato;
    eso da el rango de score esperado para un documento genuino del tipo. Umbrales:
      aprobación ≈ media − 1σ   ·   revisión ≈ media − 2.5σ (con piso y separación mínima).
    None si hay menos de 3 referencias con datos (cae a los umbrales globales del entorno).
    """
    groups = [g for g in ref_groups if (g.get("paginas") or g.get("cajetin"))]
    if len(groups) < 3:
        return None
    intra: list[float] = []
    for i, g in enumerate(groups):
        s = score_grupos(g, groups[:i] + groups[i + 1:])
        if s is not None:
            intra.append(s)
    if len(intra) < 3:
        return None
    import numpy as np

    arr = np.asarray(intra, dtype=float)
    mean, std = float(arr.mean()), float(arr.std())
    approval = max(60.0, min(99.0, mean - std))
    revision = max(40.0, min(mean - 2.5 * std, approval - 3.0))
    return (round(approval, 1), round(revision, 1))


def _zone_pad() -> float:
    """Margen (fracción de página) que se agrega alrededor de la zona al recortar para el
    score. Absorbe pequeños desvíos de posición del cajetín/encabezado entre documentos
    (env SIM_ZONE_PAD, def. 0.05). Mismo margen en candidato y referencias -> comparable."""
    return float(os.getenv("SIM_ZONE_PAD", "0.05"))


def recortar_bbox(img_data_url: str, bbox: dict, pad: float = 0.0) -> Optional[str]:
    """Recorta una región (bbox relativo 0–1) de una imagen data-url → nueva data-url PNG.
    `pad` expande la región en cada lado (fracción de página) para tolerar desvíos de posición."""
    if not bbox:
        return None
    try:
        pil = _to_pil(img_data_url)
        w, h = pil.size
        x0 = (bbox.get("x", 0) - pad)
        y0 = (bbox.get("y", 0) - pad)
        x1 = (bbox.get("x", 0) + bbox.get("w", 0) + pad)
        y1 = (bbox.get("y", 0) + bbox.get("h", 0) + pad)
        px0, py0 = int(max(0.0, x0) * w), int(max(0.0, y0) * h)
        px1, py1 = int(min(1.0, x1) * w), int(min(1.0, y1) * h)
        if px1 - px0 <= 0 or py1 - py0 <= 0:
            return None
        crop = pil.crop((px0, py0, px1, py1))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


_ZONA_PROMPT = (
    "Localizá el BLOQUE QUE IDENTIFICA al documento en la primera página: la región con el "
    "TIPO de documento, código, título, proyecto, revisión, empresa/logo. Según el tipo puede "
    "estar en el ENCABEZADO (p. ej. hojas de datos, memorias, especificaciones) o en el RÓTULO/"
    "CAJETÍN al pie o lateral (p. ej. planos). Elegí la región más distintiva de la identidad, "
    "NO los pies de página genéricos. Respondé SOLO un JSON con su bounding box en fracciones "
    '0–1 de la página: {"x":<izq>,"y":<arriba>,"w":<ancho>,"h":<alto>}. Si no hay, devolvé {}.'
)


def detectar_zona_identidad(imagenes: list[str]) -> Optional[dict]:
    """LLM de visión: localiza el bloque que identifica el documento (encabezado o rótulo),
    sin asumir que está al pie. Solo localización (para proponer la zona del template)."""
    if not imagenes:
        return None
    try:
        agent = build_agent("zona-identidad", instructions=_ZONA_PROMPT)
        out = run_agent(agent, build_input("Ubicá el bloque de identidad.", imagenes[:1]))
        bbox = extract_json(out, {})
        if all(k in bbox for k in ("x", "y", "w", "h")):
            z = {k: float(bbox[k]) for k in ("x", "y", "w", "h")}
            if z["w"] > 0 and z["h"] > 0:
                return {k: min(1.0, max(0.0, v)) for k, v in z.items()}
    except Exception:
        pass
    return None


# Alias retrocompatible (el cotejo plegado y el fallback de display lo usan).
detectar_cajetin_bbox = detectar_zona_identidad
