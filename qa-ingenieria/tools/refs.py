"""Documentos de referencia por tipo + madurez (Cotejar §3.2).

Sidecar en knowledge/refs/<tipo_doc>/: index.json + archivos de referencia.
Los EMBEDDINGS se agregan en Fase C (acá solo gestión de archivos + madurez).
No toca knowledge/tipos/<id>.yaml (las reglas) — son fuentes separadas.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

_REFS_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "refs"


def _safe(tipo_doc: str) -> str:
    """Slug seguro del id (sin path traversal)."""
    return re.sub(r"[^a-z0-9_]+", "_", (tipo_doc or "").strip().lower()).strip("_")


def _calibrating_min() -> int:
    return int(os.getenv("CALIBRATING_MIN", "2"))


def _calibrated_min() -> int:
    return int(os.getenv("CALIBRATED_MIN", "5"))


def _dir(tipo_doc: str) -> Path:
    return _REFS_DIR / _safe(tipo_doc)


def _index_path(tipo_doc: str) -> Path:
    return _dir(tipo_doc) / "index.json"


def listar_referencias(tipo_doc: str) -> list[dict[str, Any]]:
    p = _index_path(tipo_doc)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def refs_count(tipo_doc: str) -> int:
    return len(listar_referencias(tipo_doc))


def maturity(tipo_doc: str) -> str:
    n = refs_count(tipo_doc)
    if n >= _calibrated_min():
        return "calibrado"
    if n >= _calibrating_min():
        return "calibrando"
    return "solo_reglas"


def _guardar_index(tipo_doc: str, refs: list[dict[str, Any]]) -> None:
    d = _dir(tipo_doc)
    d.mkdir(parents=True, exist_ok=True)
    _index_path(tipo_doc).write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding="utf-8")


_IMG_EXT = ("png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff")
_MAX_PAGES = int(os.getenv("SIM_MAX_PAGES", "6"))  # páginas a renderizar (zonas multipágina)


def _embeber_referencia(tipo_doc: str, ref_id: str, dest: Path) -> str | None:
    """Renderiza el doc de referencia y persiste sus embeddings en <ref_id>.npz
    (arrays `paginas` y `cajetin`). Degrada con gracia: None si no hay backend de
    embeddings o no hay imágenes. El cajetín se localiza con visión (best-effort)."""
    try:
        import numpy as np

        from ai_agents import similarity
        from tools import docs

        if not similarity.disponible():
            return None
        ext = dest.suffix.lower().lstrip(".")
        if ext == "pdf":
            imgs = docs.render_pdf_images(str(dest), max_pages=_MAX_PAGES)
        elif ext in _IMG_EXT:
            imgs = [str(dest)]
        else:
            return None  # tipos sin imagen (xlsx/dxf) -> sin embedding visual

        pag = similarity.embed_images(imgs)
        caj: list[list[float]] = []
        zona_embs: list[list[list[float]]] = []  # alineado a zonas_visuales_de (para eval POR zona)
        if imgs:
            from tools.layout import bbox_efectivo
            from tools.tipos import cargar_tipos, zonas_visuales_de

            pad = similarity._zone_pad()
            for z in zonas_visuales_de(cargar_tipos().get(tipo_doc) or {}):
                pg = max(0, int(z.get("pagina", 1)) - 1)
                cv = None
                if pg < len(imgs):
                    bbox = bbox_efectivo(z, str(dest))  # anclas o bbox estático
                    crop = similarity.recortar_bbox(imgs[pg], bbox, pad) if bbox else None
                    cv = similarity.embed_image(crop) if crop else None
                zona_embs.append([cv] if cv else [])
                if cv:
                    caj.append(cv)
        if not pag and not caj:
            return None
        dim = len(pag[0]) if pag else len(caj[0])
        arrays = {
            "paginas": np.asarray(pag, dtype=float) if pag else np.zeros((0, dim)),
            "cajetin": np.asarray(caj, dtype=float) if caj else np.zeros((0, dim)),
        }
        for i, ze in enumerate(zona_embs):  # crops por zona, para el informe/eval por zona
            arrays[f"z{i}"] = np.asarray(ze, dtype=float) if ze else np.zeros((0, dim))
        p = _dir(tipo_doc) / f"{ref_id}.npz"
        np.savez(str(p), **arrays)
        return str(p)
    except Exception:
        return None


def vectores_por_referencia(tipo_doc: str) -> list[dict[str, list]]:
    """Embeddings agrupados por referencia: [{"paginas", "cajetin", "zonas": [[...zona0...], ...]}].
    `zonas` está alineado a `zonas_visuales_de(template)` (para evaluar/comparar POR zona).
    Lee el formato nuevo (.npz) y el legacy (.npy = solo páginas)."""
    try:
        import numpy as np
    except Exception:
        return []
    out: list[dict[str, list]] = []
    for r in listar_referencias(tipo_doc):
        ep = r.get("embed_path")
        if not ep or not Path(ep).exists():
            continue
        meta = {"filename": r.get("filename"), "ref_id": r.get("ref_id"), "origin": r.get("origin")}
        try:
            if ep.endswith(".npz"):
                z = np.load(ep)
                zonas = []
                i = 0
                while f"z{i}" in z.files:  # crops por zona, en orden
                    zonas.append(z[f"z{i}"].tolist())
                    i += 1
                out.append({**meta, "paginas": z["paginas"].tolist(),
                            "cajetin": z["cajetin"].tolist(), "zonas": zonas})
            else:  # legacy .npy: solo páginas
                out.append({**meta, "paginas": np.load(ep).tolist(), "cajetin": [], "zonas": []})
        except Exception:
            continue
    return out


def vectores_referencia(tipo_doc: str) -> list[list[float]]:
    """Embeddings de página de todas las referencias (aplanado). Compat."""
    return [v for g in vectores_por_referencia(tipo_doc) for v in g.get("paginas", [])]


def reembeber_todas(tipo_doc: str) -> int:
    """Re-embebe todas las referencias del tipo (tras cambiar la zona de identidad: el recorte
    del cajetín cambia). Devuelve cuántas se re-embebieron."""
    idx = listar_referencias(tipo_doc)
    n = 0
    for r in idx:
        dest = Path(r.get("path") or "")
        if dest.exists():
            r["embed_path"] = _embeber_referencia(tipo_doc, r["ref_id"], dest)
            n += 1
    _guardar_index(tipo_doc, idx)
    return n


def agregar_referencia(tipo_doc: str, filename: str, data: bytes, origin: str = "inicial") -> dict[str, Any]:
    """Guarda un documento de referencia, computa su embedding y lo agrega al index."""
    d = _dir(tipo_doc)
    d.mkdir(parents=True, exist_ok=True)
    ref_id = uuid.uuid4().hex[:8]
    dest = d / f"{ref_id}{Path(filename).suffix.lower()}"
    dest.write_bytes(data)
    embed_path = _embeber_referencia(tipo_doc, ref_id, dest)
    from tools import docs as _docs

    refs = listar_referencias(tipo_doc)
    entry = {"ref_id": ref_id, "filename": filename, "origin": origin,
             "path": str(dest), "embed_path": embed_path, "paginas": _docs.contar_paginas(str(dest))}
    refs.append(entry)
    _guardar_index(tipo_doc, refs)
    return {"refs_count": len(refs), "maturity": maturity(tipo_doc), "ref": entry}


def agregar_referencia_desde_path(tipo_doc: str, src_path: str, filename: str | None = None,
                                  origin: str = "promovido") -> dict[str, Any]:
    p = Path(src_path)
    return agregar_referencia(tipo_doc, filename or p.name, p.read_bytes(), origin=origin)


def eliminar_referencia(tipo_doc: str, ref_id: str) -> dict[str, Any]:
    refs = listar_referencias(tipo_doc)
    for r in refs:
        if r.get("ref_id") == ref_id and r.get("path"):
            try:
                Path(r["path"]).unlink()
            except Exception:
                pass
    keep = [r for r in refs if r.get("ref_id") != ref_id]
    _guardar_index(tipo_doc, keep)
    return {"refs_count": len(keep), "maturity": maturity(tipo_doc)}
