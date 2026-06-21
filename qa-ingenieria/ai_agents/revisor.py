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


_TIPOS_AUSENCIA = {"presencia", "presencia_unidad", "patron", "tabla"}  # fallan por AUSENCIA de texto


def _imagen_dominante(doc: dict) -> bool:
    """¿El documento es casi puro dibujo? (poca capa de texto por página). En ese caso un `fallo` de una
    regla de texto por AUSENCIA es en realidad 'no verificable por este medio' → hay que mirarlo con el VLM.
    Umbral configurable con REVISION_MIN_CHARS_PAGINA (default 600)."""
    imgs = doc.get("imagenes") or []
    if not imgs:                       # sin imágenes no hay "dibujo" que domine: es texto (o doc vacío)
        return False
    umbral = int(os.getenv("REVISION_MIN_CHARS_PAGINA", "600") or "600")
    return len(doc.get("contenido") or "") < umbral * len(imgs)


def _degradar_no_verificable(h: Hallazgo) -> Hallazgo:
    """Convierte un `fallo` por ausencia de texto en `no_verificable` (el dato puede estar en el dibujo)."""
    base = (h.get("evidencia") or "").rstrip(". ")
    return {**h, "estado": "no_verificable",
            "evidencia": (f"{base} — no verificable por texto (el documento casi no tiene capa de texto; "
                          "el dato suele estar en el dibujo)").lstrip(" —"),
            "sugerencia": "Pedí la observación visual (IA) para verificarlo sobre el dibujo."}


def _tier2_reglas(doc: dict, cfg: dict, extracto: dict) -> list[Hallazgo]:
    """Tier 2 (determinista): vínculo doc↔norma + reglas sobre texto/tablas.
    1) Detección: ¿el doc DECLARA las normas que el template espera? (declarar la norma es un check).
    2) Aplicación: reglas del template + reglas de las normas (merge; el template pisa por id).
    Si el doc es 'dominado por imagen', los fallos por AUSENCIA de texto se degradan a `no_verificable`
    (la confiabilidad baja a parcial e invita a la observación visual, en vez de inflar el veredicto)."""
    out: list[Hallazgo] = []
    texto = doc.get("contenido") or ""
    tablas = (extracto or {}).get("tablas") or []
    dominante = _imagen_dominante(doc)

    # Conjunto final de requisitos (atajo `normas` + granular `requisitos` + inline − `excluir`).
    reglas = normas.resolver_requisitos(cfg)

    # 1) Detección del vínculo: normas esperadas = las listadas + las que están detrás de los requisitos.
    esperadas = sorted({*(cfg.get("normas") or []), *(r.get("norma_id") for r in reglas if r.get("norma_id"))})
    for det in normas.detectar_normas(texto, esperadas):
        declarada = det.get("declarada")
        h = mk(f"norma_declarada:{det['id']}", "norma", det.get("severidad", "mayor"),
               "ok" if declarada else "fallo", fuente="reglas",
               evidencia=(f"el documento declara «{det['nombre']}»" if declarada
                          else f"no se declara la norma esperada «{det['nombre']}»"),
               razonamiento="El documento debe citar la norma/código de diseño aplicable.",
               sugerencia="" if declarada else f"Citar «{det['nombre']}» en la sección de normas o el cajetín.",
               norma_ref=det.get("norma_ref"))
        if dominante and not declarada:   # no se puede confirmar la cita por texto → no_verificable
            h = _degradar_no_verificable(h)
        out.append(h)

    # 2) Aplicación de los requisitos resueltos (cada hallazgo cita su norma_ref).
    for r in reglas:
        h = reglas_revision.evaluar_regla(r, texto, tablas)
        if dominante and h.get("estado") == "fallo" and r.get("tipo") in _TIPOS_AUSENCIA:
            h = _degradar_no_verificable(h)
        out.append(h)
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
        ubic = {"pagina": int(pag)} if isinstance(pag, (int, float)) and not isinstance(pag, bool) and pag >= 1 else None
        out.append(mk(f"vlm:{o.get('id') or i + 1}", dim, sev, "advertencia", fuente="vlm",
                      evidencia=desc[:300], razonamiento=(o.get("razonamiento") or "Observación del revisor (visión)."),
                      sugerencia=(o.get("sugerencia") or ""), ubicacion=ubic, norma_ref=o.get("norma_ref")))
    return out


def _cargar_referencia(ruta: str | None) -> str | None:
    """Carga la imagen de referencia de una norma (leyenda/estándar) como data-url, para dársela al VLM
    como ground-truth. Acepta imagen o PDF (rinde la página 1). Ruta relativa a la raíz del repo.
    None si no existe / no se puede (degrada con gracia)."""
    if not ruta:
        return None
    try:
        from pathlib import Path as _P
        p = _P(ruta)
        if not p.is_absolute():
            p = _P(__file__).resolve().parent.parent / ruta
        if not p.exists():
            return None
        if p.suffix.lower() == ".pdf":
            from tools import docs
            imgs = docs.render_pdf_images(str(p), max_pages=1)
            return imgs[0] if imgs else None
        import base64
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")
    except Exception:
        return None


def _vlm_payload(doc: dict, cfg: dict, candidatas: list[Hallazgo]) -> dict:
    """UNA llamada al VLM: verifica las reglas `candidatas` (las que el texto no pudo) + observaciones
    cualitativas. Devuelve {'reglas': {check_id: {veredicto, razon}}, 'observaciones': [hallazgos]} o {}.
    No mira `REVISION_VLM` (el gate vive en quien llama). Degrada con gracia (sin LLM/criterios → {})."""
    instrucciones = ((cfg.get("observacion_vlm") or {}).get("instrucciones") or "").strip()
    norma_ids = sorted({r.get("norma_id") for r in normas.resolver_requisitos(cfg) if r.get("norma_id")}
                       | set(cfg.get("normas") or []))
    criterios = normas.vlm_de_normas(norma_ids)
    if not candidatas and not criterios and not instrucciones:
        return {}
    try:
        from ai_agents.provider import build_agent
        from ai_agents.util import build_input, extract_json, load_prompt, run_agent

        partes: list[str] = []
        if candidatas:
            partes.append("## Verificá estas reglas mirando las IMÁGENES. Para cada una: "
                          "veredicto = ok | fallo | no_verificable, con una razón breve.")
            for h in candidatas:
                q = normas.requisito_por_id(h.get("req_id")) if h.get("req_id") else None
                desc = (q or {}).get("descripcion") or h.get("razonamiento") or h.get("check_id")
                ref = f" [{h.get('norma_ref')}]" if h.get("norma_ref") else ""
                partes.append(f'- id="{h.get("check_id")}": {desc}{ref}')
        if instrucciones:
            partes += ["", "## Instrucciones de observación (NO bloqueante)", instrucciones]
        ref_imgs: list = []
        for v in criterios:
            partes.append(f"### Criterios — {v['norma_ref']}\n{v['criterios']}")
            ri = v.get("referencia_imagen")
            for ruta in (ri if isinstance(ri, list) else [ri]):   # 1 o varias leyendas de referencia
                img = _cargar_referencia(ruta)
                if img:
                    ref_imgs.append(img)
        if ref_imgs:
            partes.insert(0, f"## NOTA: las primeras {len(ref_imgs)} imagen(es) son la LEYENDA/ESTÁNDAR de "
                             "referencia de la(s) norma(s); las que siguen son el DOCUMENTO a revisar. "
                             "Compará el documento CONTRA esa leyenda.")
        partes += ["", "## Texto del documento", (doc.get("contenido") or "")[:6000] or "(ver imágenes)"]
        agent = build_agent("revisor-qa", instructions=load_prompt("revisor"))
        out = run_agent(agent, build_input("\n".join(partes), ref_imgs + (doc.get("imagenes") or [])))
        data = extract_json(out, {})
        reglas = {r["id"]: r for r in (data.get("reglas") or []) if isinstance(r, dict) and r.get("id")}
        return {"reglas": reglas, "observaciones": _a_hallazgos_vlm(data.get("observaciones") or [])}
    except Exception:
        return {}


def _tier3_vlm(doc: dict, cfg: dict, forzar: bool = False) -> list[Hallazgo]:
    """Tier 3 (cualitativo): observaciones VLM no bloqueantes. [] si `REVISION_VLM` off (salvo `forzar`)
    o si no hay LLM/criterios."""
    if not forzar and (os.getenv("REVISION_VLM", "1") or "1").strip().lower() in ("0", "false", "no", "off"):
        return []
    return _vlm_payload(doc, cfg, []).get("observaciones") or []


def observar_vlm(doc: dict, cfg: dict) -> list[Hallazgo]:
    """Observación visual (Tier 3) A PEDIDO: corre el VLM ignorando el flag `REVISION_VLM`.
    Pensado para que el revisor pida la 'mirada del VLM' con un botón (caro → no corre solo)."""
    if not cfg:
        return []
    return _tier3_vlm(doc, cfg, forzar=True)


def _restaurar_texto(hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    """Quita observaciones VLM previas y restaura el estado por-texto de las reglas que el VLM cambió.
    Hace idempotente el re-pedido de la observación (siempre parte del resultado determinista)."""
    base: list[Hallazgo] = []
    for h in hallazgos or []:
        if h.get("fuente") == "vlm":
            continue
        prev = h.get("estado_previo")
        if prev is not None:
            h = {k: v for k, v in h.items() if k not in ("estado_previo", "nota_vlm")}
            h["estado"] = prev
        base.append(h)
    return base


def verificar_reglas_vlm(doc: dict, cfg: dict, hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    """A PEDIDO: el VLM (1) verifica visualmente las reglas que el texto no pudo (estado fallo /
    no_verificable) y (2) agrega observaciones cualitativas. Devuelve la lista de hallazgos ACTUALIZADA.
    Las reglas que el VLM cambia quedan marcadas con `estado_previo` + `nota_vlm` ('el VLM cambió esto');
    siguen siendo 'duras' (fuente reglas) → el veredicto se recalcula con el resultado del VLM."""
    base = _restaurar_texto(hallazgos)
    if not cfg:
        return base
    candidatas = [h for h in base if h.get("estado") in ("fallo", "no_verificable")]
    payload = _vlm_payload(doc, cfg, candidatas)
    if not payload:
        return base
    verdictos = payload.get("reglas") or {}
    out: list[Hallazgo] = []
    for h in base:
        v = verdictos.get(h.get("check_id"))
        ve = (v or {}).get("veredicto")
        if v and ve in ("ok", "fallo", "no_verificable") and ve != h.get("estado"):
            out.append({**h, "estado_previo": h.get("estado"), "estado": ve,
                        "nota_vlm": (v.get("razon") or "Verificado por observación visual.")[:300]})
        else:
            out.append(h)
    out += payload.get("observaciones") or []
    return out


def revisar(doc: dict, cfg: dict, extracto: dict | None = None) -> list[Hallazgo]:
    """Corre los tiers DETERMINISTAS sobre un documento admitido y devuelve los hallazgos.
    `cfg` = bloque `revision:` del template; `extracto` = lo que dejó el extractor (tablas, etc.).
    Tier 1 (legibilidad/presencia) + Tier 2 (reglas/normas). El Tier 3 (observación VLM) NO corre acá:
    es a pedido vía `observar_vlm` (es caro y cualitativo)."""
    if not cfg:
        return []
    hallazgos: list[Hallazgo] = []
    hallazgos += _tier1_legibilidad(doc, cfg)
    hallazgos += _tier1_presencia(doc, cfg)
    hallazgos += _tier2_reglas(doc, cfg, extracto or {})
    return hallazgos
