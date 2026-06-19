"""Nodos del grafo (T0.12, T0.15).

Cada nodo es `state -> updates` (dict parcial que LangGraph mergea). Los nodos
**solo** llaman a tools/ y a los agentes — nunca instancian SDKs ni hacen IO
inline (regla sandbox-able).

Fase 0 cubre el frente: parser -> validación -> triage -> (faltan datos /
incompleta / no admisible / lista para revisión).
"""

from __future__ import annotations

from typing import Any

from ai_agents.parser import parse_trigger
from ai_agents.triage import run_cotejar, run_triage
from graph.state import CasoState, Status, clasificar_score, umbrales_score
from tools import docs, refs
from tools.email import enviar_dueno, enviar_emisor
from tools.layout import bbox_efectivo, extraer_campos_zonas
from tools.reglas import chequear_campos, chequear_reglas
from tools.sheets import leer_catalogo
from tools.tipos import cargar_tipos, reglas_de, zonas_visuales_de


def armar_checks(checks_llm: list, checks_extra: list) -> list[dict[str, Any]]:
    """Mergea checks del LLM (Identidad + Completitud cualitativa) con los extra
    (regex de cajetín, similitud). Dedup por (dimensión, label)."""
    out: list[dict[str, Any]] = []
    seen: set = set()
    for c in [*(checks_llm or []), *(checks_extra or [])]:
        if not isinstance(c, dict):
            continue
        label = (c.get("label") or "").strip()
        key = (c.get("dimension"), label.lower())
        if not label or key in seen:
            continue
        seen.add(key)
        nuevo = {
            "dimension": c.get("dimension", "completitud"),
            "label": label,
            "state": c.get("state", "info"),
            "detail": c.get("detail", ""),
            "requerido": bool(c.get("requerido")),
        }
        for k in ("campo", "patron", "valor", "regla_tipo"):  # metadata de regla (feedback)
            if c.get(k) is not None:
                nuevo[k] = c[k]
        out.append(nuevo)
    return out


def _add_accion(state: CasoState, linea: str) -> list[str]:
    return list(state.get("acciones", [])) + [linea]


def _panel_cards(documentos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tarjetas para el panel de Archivos del sandbox (ui.files_field).
    Muestra TODOS los documentos acumulados del caso, no solo el último subido.
    """
    cards: list[dict[str, Any]] = []
    for d in documentos:
        datos = [{"clave": "tipo", "valor": d.get("tipo_doc") or "(sin clasificar)"}]
        if d.get("relevante") is not None:
            datos.append({"clave": "relevante", "valor": "si" if d.get("relevante") else "no"})
        if d.get("formato_ok") is not None:
            datos.append({"clave": "formato", "valor": "ok" if d.get("formato_ok") else "revisar"})
        motivo = d.get("motivo") or ""
        faltan = d.get("faltan") or []
        if faltan:
            motivo = (motivo + " · " if motivo else "") + "falta: " + ", ".join(faltan)
        cards.append({
            "titulo": d.get("filename"),
            "datos": datos,
            "calidad": "leida" if d.get("legible", True) else "snippet",
            "fuera_de_criterio": d.get("relevante") is False or d.get("formato_ok") is False,
            "motivo": motivo,
            "razonamiento": d.get("razonamiento", ""),
        })
    return cards


def _nombres_recibidos(state: CasoState) -> str:
    nombres = [d.get("filename") for d in state.get("documentos", []) if d.get("filename")]
    return ", ".join(nombres) if nombres else "(ninguno)"


def faltan_minimos(state: CasoState) -> list[str]:
    faltan: list[str] = []
    if not state.get("documentos"):
        faltan.append("documento adjunto")
    if state.get("tipo_objetivo"):
        # Modo Cotejar (single-doc): el template elegido ya viene; alcanza con el adjunto.
        return faltan
    if not state.get("tipo_entrega"):
        faltan.append("tipo de entrega")
    if not state.get("disciplina"):
        faltan.append("disciplina")
    return faltan


def parser_node(state: CasoState) -> dict[str, Any]:
    """Acumula los archivos entrantes del turno en el caso, los lee (docs.py) y
    extrae/completa los datos de la entrega (parser). Permite la ida y vuelta:
    cada turno suma documentos al mismo caso y se vuelve a evaluar.
    """
    # Documentos ya acumulados, indexados por filename (el reenvío reemplaza).
    acumulados: dict[str, dict[str, Any]] = {
        d.get("filename"): dict(d) for d in state.get("documentos", [])
    }
    for nf in state.get("nuevos_archivos", []):
        path = nf.get("path", "")
        leido = docs.read_document(path) if path else {}
        imagenes = list(leido.get("imagenes", []))
        if path.lower().endswith(".pdf"):
            # Visión para el chequeo: el cajetín/diagrama NO es texto. Renderizamos varias
            # páginas (zonas multipágina) aunque el PDF tenga texto (simetría con la captura).
            imagenes = docs.render_pdf_images(path, max_pages=refs._MAX_PAGES) or imagenes
        acumulados[nf.get("filename")] = {
            **nf,
            "contenido": leido.get("contenido", ""),
            "imagenes": imagenes,
            "legible": leido.get("legible", True),
            "motivo": leido.get("motivo", ""),
        }
    documentos = list(acumulados.values())

    # En modo Cotejar (single-doc) el tipo ya viene elegido: no inferimos entrega
    # (evita un llamado LLM innecesario del parser).
    if state.get("tipo_objetivo"):
        meta = {}
    else:
        filenames = [d.get("filename", "") for d in documentos]
        meta = parse_trigger(state.get("trigger_text", "") or "", filenames)

    updates: dict[str, Any] = {
        "documentos": documentos,
        "nuevos_archivos": [],
        "documentos_panel": _panel_cards(documentos),
    }
    # No pisar lo ya conocido del caso; completar lo que falte con lo inferido.
    for k in ("tipo_entrega", "disciplina", "proyecto", "revision"):
        updates[k] = state.get(k) or meta.get(k)
    return updates


def validacion_node(state: CasoState) -> dict[str, Any]:
    """Marca qué datos mínimos faltan (el router decide a dónde va)."""
    return {"faltan_minimos": faltan_minimos(state)}


def pedir_datos_node(state: CasoState) -> dict[str, Any]:
    faltan = state.get("faltan_minimos") or faltan_minimos(state)
    cuerpo = (
        "Para poder revisar tu entrega necesitamos estos datos mínimos:\n- "
        + "\n- ".join(faltan)
        + "\n\nReenviá la entrega indicando esos datos. Gracias."
    )
    accion = enviar_emisor(state.get("emisor"), "Faltan datos para revisar la entrega", cuerpo)
    return {"status": Status.FALTAN_DATOS.value, "respuesta": cuerpo, "acciones": _add_accion(state, accion)}


_SIM_CHECK = {
    "dimension": "identidad", "label": "Similitud visual con el template",
    "state": "info", "detail": "No calibrado — el score se calcula en una fase posterior",
    "requerido": False,
}


def _resultado_cotejo(state: CasoState, doc: dict, checks: list, resumen: str, razon: str = "",
                      score: float | None = None, no_concluyente: bool = True,
                      cajetin_bbox: dict | None = None, score_veredicto: str | None = None,
                      score_detalle: dict | None = None, campos: dict | None = None,
                      zonas_resultado: list | None = None) -> dict[str, Any]:
    docs_ = state.get("documentos", [])
    doc2 = {**doc, "tipo_doc": state.get("tipo_objetivo"), "checks": checks,
            "razonamiento": razon, "legible": doc.get("legible", True)}
    # El documento cotejado es el ÚLTIMO subido (importa en la ida-y-vuelta, donde
    # se acumulan reenvíos): se reemplaza in situ conservando los previos.
    documentos = [*docs_[:-1], doc2] if docs_ else [doc2]
    return {
        "status": Status.EN_TRIAGE.value,
        "documentos": documentos,
        "documentos_panel": _panel_cards(documentos),
        "checks": checks,
        "score": score,
        "no_concluyente": no_concluyente,
        "score_veredicto": score_veredicto,
        "score_detalle": score_detalle,
        "campos": campos or {},
        "zonas_resultado": zonas_resultado or [],
        "cajetin_bbox": cajetin_bbox,
        "resumen": resumen,
    }


def _evaluar_similitud(tipo: str, doc: dict, bbox: dict | None = None, zonas: list[dict] | None = None) -> dict[str, Any]:
    """Score ponderado (zonas de identidad / página) + bbox + gating por madurez (§3.1).

    `zonas` = zonas de identidad del template (pueden estar en distintas páginas y/o ancladas a
    texto). Cada una se recorta con PADDING (tolera desvíos) en su página; las ancladas se ubican
    por texto en ESTE documento (siguen al contenido). El veredicto del score se decide UNA vez
    acá (umbrales auto del template) y el router lo lee.
    """
    from ai_agents import similarity

    imgs = doc.get("imagenes") or []
    pdf_path = doc.get("path")
    zonas = zonas or []
    pad = similarity._zone_pad()

    # Display: bbox de la 1ª zona de identidad ubicada en página 1 (el preview muestra pág. 1).
    display_bbox = None
    for z in zonas:
        if int(z.get("pagina", 1)) == 1:
            display_bbox = bbox_efectivo(z, pdf_path)
            break
    if display_bbox is None:
        display_bbox = bbox
    if display_bbox is None and imgs:
        display_bbox = similarity.detectar_cajetin_bbox(imgs)
    label = "Similitud visual con el template"
    mat = refs.maturity(tipo)

    def _res(check: dict, score: float | None, no_concl: bool,
             ver: str | None = None, detalle: dict | None = None) -> dict[str, Any]:
        return {"check": check, "score": score, "no_concluyente": no_concl,
                "bbox": display_bbox, "veredicto": ver, "detalle": detalle}

    if not similarity.disponible():
        det = "Backend de embeddings no disponible — el cotejo siguió por reglas."
        return _res({"dimension": "identidad", "label": label, "state": "info", "detail": det, "requerido": False}, None, True)
    if mat == "solo_reglas":
        return _res(dict(_SIM_CHECK), None, True)

    ref_groups = refs.vectores_por_referencia(tipo)
    cand_caj: list = []
    for z in zonas:
        pg = max(0, int(z.get("pagina", 1)) - 1)
        if pg >= len(imgs):
            continue
        zbbox = bbox_efectivo(z, pdf_path)  # anclas (sigue al texto) o bbox estático
        crop = similarity.recortar_bbox(imgs[pg], zbbox, pad) if zbbox else None
        cv = similarity.embed_image(crop) if crop else None
        if cv:
            cand_caj.append(cv)
    cand: dict[str, list] = {"paginas": similarity.embed_images(imgs), "cajetin": cand_caj}

    d = similarity.detalle_score(cand, ref_groups)
    s = d["score"]
    if s is None:
        return _res(dict(_SIM_CHECK), None, True)

    auto_um = similarity.umbrales_calibrados(ref_groups)
    appr, rev = auto_um if auto_um else umbrales_score()
    wc, wp = similarity._pesos()
    top = None
    if d["top_index"] is not None:
        g = ref_groups[d["top_index"]]
        top = {"filename": g.get("filename"), "score": d["top_score"]}
    detalle = {
        "score": s, "cajetin": d["cajetin"], "pagina": d["pagina"],
        "peso_cajetin": round(wc, 2), "peso_pagina": round(wp, 2),
        "umbral_aprobacion": appr, "umbral_revision": rev, "umbrales_auto": auto_um is not None,
        "n_referencias": len(ref_groups), "ref_top": top, "decisivo": mat == "calibrado",
    }

    if mat == "calibrado":
        v = clasificar_score(s, (appr, rev))
        st = {"valido": "pass", "revision_manual": "warn", "invalido": "fail"}[v]
        det = {"valido": f"{s}% · sobre umbral ({appr:.0f})",
               "revision_manual": f"{s}% · zona de revisión ({rev:.0f}–{appr:.0f})",
               "invalido": f"{s}% · bajo umbral ({rev:.0f})"}[v]
        return _res({"dimension": "identidad", "label": label, "state": st, "detail": det, "requerido": False},
                    s, False, v, detalle)
    # calibrando -> check blando, score informativo (no concluyente)
    return _res({"dimension": "identidad", "label": label, "state": "info",
                 "detail": f"{s}% · calibrando ({len(ref_groups)} ej., no concluyente)", "requerido": False},
                s, True, None, detalle)


def _estado_visual(score: float | None, mat: str, appr: float, rev: float) -> str:
    """Estado de una zona visual a partir de su score (0–100)."""
    if score is None:
        return "info"
    if mat == "calibrado":
        return {"valido": "pass", "revision_manual": "warn", "invalido": "fail"}[clasificar_score(score, (appr, rev))]
    # calibrando/solo_reglas: informativo, pero si está claramente bajo lo marcamos para que SE VEA.
    return "warn" if score < rev else "info"


def _zonas_resultado(tipo: str, tpl: dict, doc: dict, checks_det: list) -> list[dict[str, Any]]:
    """Resultado POR ZONA (observabilidad): una entrada por zona del template con su estado
    (pass/fail/warn/info), el bbox EFECTIVO en ESTE documento (para dibujarlo encima de la página)
    y, si es visual, su score propio comparado contra esa misma zona de las referencias.

    Esto evalúa cada zona visual por separado (no diluida en el score global): un logo tapado da
    bajo parecido en SU zona aunque el resto de la página coincida.
    """
    from ai_agents import similarity

    out: list[dict[str, Any]] = []
    chk_por_campo = {c.get("campo"): c for c in (checks_det or []) if c.get("campo")}
    path = doc.get("path")
    imgs = doc.get("imagenes") or []

    visuales = zonas_visuales_de(tpl)
    idx_visual = {id(z): j for j, z in enumerate(visuales)}  # alineado a refs["zonas"][j]
    backend = similarity.disponible()
    ref_groups = refs.vectores_por_referencia(tipo) if backend else []
    mat = refs.maturity(tipo)
    auto = similarity.umbrales_calibrados(ref_groups) if ref_groups else None
    appr, rev = auto if auto else umbrales_score()
    pad = similarity._zone_pad()

    for z in (tpl.get("zonas") or []):
        bbox = bbox_efectivo(z, path)
        pagina = int(z.get("pagina", 1) or 1)
        es_visual = bool(z.get("identidad") or z.get("comparar") == "visual")
        entry: dict[str, Any] = {
            "nombre": z.get("nombre") or z.get("campo") or "Zona",
            "pagina": pagina,
            "bbox": bbox,
            "clase": "identidad" if z.get("identidad") else ("visual" if z.get("comparar") == "visual" else "regla"),
            "requerido": bool(z.get("requerido")),
        }
        if es_visual:
            score = None
            j = idx_visual.get(id(z))
            if backend and j is not None and imgs:
                pg = max(0, pagina - 1)
                cand = (similarity.embed_image(similarity.recortar_bbox(imgs[pg], bbox, pad))
                        if pg < len(imgs) and bbox else None)
                ref_embs = [e for g in ref_groups
                            for e in ((g.get("zonas") or [])[j] if j < len(g.get("zonas") or []) else [])]
                if cand and ref_embs:
                    score = similarity.score([cand], ref_embs)
            entry["estado"] = _estado_visual(score, mat, appr, rev)
            entry["score"] = score
            entry["detalle"] = (f"{score:.0f}% de parecido vs. referencias" if score is not None
                                else ("sin backend de imagen" if not backend
                                      else ("template no calibrado" if mat != "calibrado"
                                            else "sin referencias de esta zona")))
        else:
            c = chk_por_campo.get(z.get("campo"))
            entry["estado"] = (c or {}).get("state", "info")
            entry["detalle"] = (c or {}).get("detail", "") or (f"campo «{z.get('campo')}»" if z.get("campo") else "")
            entry["campo"] = z.get("campo")
            entry["valor"] = (c or {}).get("valor")
        out.append(entry)
    return out


def _cotejar_single(state: CasoState) -> dict[str, Any]:
    """Modo Cotejar: valida UN documento contra el TEMPLATE del tipo elegido.
    Ensambla checks de Identidad (LLM + `es_el_tipo` forzado) + Completitud (LLM + regex) + Similitud."""
    docs_ = state.get("documentos", [])
    doc = docs_[-1] if docs_ else {}   # el último adjunto (el recién subido en la ida-y-vuelta)
    tipo = state.get("tipo_objetivo")
    tpl = cargar_tipos().get(tipo)

    # Guard: el template elegido no existe -> rechazo claro, sin gastar LLM.
    if not tpl:
        check = {"dimension": "identidad", "label": f"Es el tipo: {tipo}", "state": "fail",
                 "detail": f"el template '{tipo}' no existe", "requerido": True}
        return _resultado_cotejo(state, doc, armar_checks([check], [_SIM_CHECK]),
                                 f"El tipo de documento '{tipo}' no existe.")

    res = run_cotejar(doc, tipo)

    # FIX QA (mayor): el check clave de Identidad sale del `es_el_tipo` AUTORITATIVO
    # (requerido), no de que el LLM lo marque bien. Va primero -> gana en el dedup.
    es_tipo = bool(res.get("es_el_tipo"))
    check_tipo = {
        "dimension": "identidad",
        "label": f"Es el tipo: {tpl.get('nombre', tipo)}",
        "state": "pass" if es_tipo else "fail",
        "detail": "El documento corresponde al tipo elegido." if es_tipo
                  else "El documento NO corresponde al tipo elegido.",
        "requerido": True,
    }
    # Campos: el LLM los extrae de TODO el doc; las zonas con `campo` + ancla/bbox los extraen
    # DETERMINÍSTICAMENTE acotados a su región (mejora 'b') y pisan al LLM (más confiable y scoped).
    campos = dict(res.get("campos") or {})
    det = extraer_campos_zonas(doc.get("path"), tpl.get("zonas") or [])
    campos.update({k: v for k, v in det.items() if v})

    # Reglas DETERMINISTAS (extract-then-check): regex / match-con-filename / presencia. Van ANTES
    # que los checks cualitativos del LLM para ganar en el dedup (la regla determinista manda).
    reglas = reglas_de(tpl)
    checks_det = chequear_campos(campos, doc.get("filename", ""), reglas)
    if not reglas:  # sin reglas definidas, caemos al chequeo por texto (legacy)
        checks_det = chequear_reglas(doc.get("contenido", ""), (tpl.get("cajetin") or {}).get("reglas") or [])

    sim = _evaluar_similitud(tipo, doc, res.get("cajetin_bbox"), zonas_visuales_de(tpl))

    # Resultado POR ZONA (observabilidad + arreglo del logo tapado): cada zona visual se evalúa
    # contra ESA zona de las referencias, sin diluirse en el score global. Una zona visual marcada
    # `requerido` que falla/queda en revisión emite un check decisivo (el humano la hace bloqueante).
    zonas_res = _zonas_resultado(tipo, tpl, doc, checks_det)
    checks_zonas = [
        {"dimension": "identidad", "label": f"Zona «{zr['nombre']}» (visual)",
         "state": zr["estado"], "detail": zr["detalle"], "requerido": True}
        for zr in zonas_res
        if zr["clase"] in ("identidad", "visual") and zr.get("requerido") and zr["estado"] in ("fail", "warn")
    ]

    checks = armar_checks([check_tipo, *checks_det, *res.get("checks", [])], [sim["check"], *checks_zonas])
    return _resultado_cotejo(state, doc, checks, res.get("resumen", ""), res.get("razonamiento", ""),
                             score=sim["score"], no_concluyente=sim["no_concluyente"],
                             cajetin_bbox=sim["bbox"], score_veredicto=sim["veredicto"],
                             score_detalle=sim["detalle"], campos=campos, zonas_resultado=zonas_res)


def extractor_node(state: CasoState) -> dict[str, Any]:
    """Revisión Fase 1 — extrae contenido estructurado del doc admitido para los tiers.
    En esta rebanada (Tier 1) es liviano: texto/render ya vienen del parser; deja un extracto
    observable (nº de páginas, tamaño de texto) y, best-effort, las tablas para tiers futuros."""
    docs_ = state.get("documentos", [])
    doc = docs_[-1] if docs_ else {}
    extracto: dict[str, Any] = {
        "n_paginas": len(doc.get("imagenes") or []),
        "texto_chars": len(doc.get("contenido") or ""),
    }
    return {"revision_extracto": extracto}


def revisor_node(state: CasoState) -> dict[str, Any]:
    """Revisión Fase 1 — corre los tiers (Tier 1 hoy) y agrega la severidad en un veredicto.
    La admisión NO se toca: `status` queda EN_REVISION; el veredicto de revisión es aparte
    (`verdicto_revision`), para no pisar el chip de admisión en la UI."""
    from ai_agents.revisor import revisar
    from graph.revision import agregar_revision

    tipo = state.get("tipo_objetivo")
    tpl = cargar_tipos().get(tipo) or {}
    cfg = tpl.get("revision")
    docs_ = state.get("documentos", [])
    doc = docs_[-1] if docs_ else {}
    if not cfg or not doc:
        return {"hallazgos": [], "verdicto_revision": None, "severidad_max": None}

    hallazgos = revisar(doc, cfg)
    agg = agregar_revision(hallazgos)
    doc2 = {**doc, "hallazgos": hallazgos, "verdicto_revision": agg["verdicto"],
            "severidad_max": agg["severidad_max"]}
    documentos = [*docs_[:-1], doc2]
    return {
        "documentos": documentos,
        "documentos_panel": _panel_cards(documentos),
        "hallazgos": hallazgos,
        "verdicto_revision": agg["verdicto"],
        "severidad_max": agg["severidad_max"],
        "revision_confiabilidad": agg["confiabilidad"],
    }


def triage_node(state: CasoState) -> dict[str, Any]:
    """Cotejo single-doc (si hay tipo_objetivo) o triage de entrega multi-doc."""
    if state.get("tipo_objetivo"):
        return _cotejar_single(state)

    requeridos = leer_catalogo(state.get("proyecto"), state.get("tipo_entrega"))
    resultado = run_triage(
        tipo_entrega=state.get("tipo_entrega"),
        disciplina=state.get("disciplina"),
        proyecto=state.get("proyecto"),
        documentos=state.get("documentos", []),
        requeridos=requeridos,
    )

    # Volcar la evaluación por documento sobre el estado
    eval_por_archivo = {d.get("filename"): d for d in resultado.get("documentos", [])}
    documentos = []
    for d in state.get("documentos", []):
        ev = eval_por_archivo.get(d.get("filename"), {})
        documentos.append({
            **d,
            "tipo_doc": ev.get("tipo_doc", d.get("tipo_doc")),
            "relevante": ev.get("relevante"),
            "formato_ok": ev.get("formato_ok"),
            "faltan": ev.get("faltan", []),
            "motivo": ev.get("motivo", d.get("motivo", "")),
            "razonamiento": ev.get("razonamiento", ""),
        })

    admisibilidad = {
        "es_admisible": bool(resultado.get("es_admisible")),
        "completa": bool(resultado.get("completa")),
        "faltantes": resultado.get("faltantes", []),
        "irrelevantes": resultado.get("irrelevantes", []),
        "motivo": resultado.get("motivo", ""),
    }
    return {
        "status": Status.EN_TRIAGE.value,
        "documentos": documentos,
        "documentos_panel": _panel_cards(documentos),
        "admisibilidad": admisibilidad,
        "entrega_completa": admisibilidad["completa"],
    }


def reclamar_faltantes_node(state: CasoState) -> dict[str, Any]:
    adm = state.get("admisibilidad", {})
    faltantes = adm.get("faltantes", [])
    cuerpo = (
        f"Recibimos: {_nombres_recibidos(state)}.\n"
        "La entrega está incompleta. Faltan estos documentos requeridos:\n- "
        + "\n- ".join(faltantes)
        + "\n\nEnviá los faltantes (respondé a este mismo hilo) para completar la entrega."
    )
    accion = enviar_emisor(state.get("emisor"), "Entrega incompleta - faltan documentos", cuerpo)
    return {"status": Status.INCOMPLETA.value, "respuesta": cuerpo, "acciones": _add_accion(state, accion)}


def _fails(state: CasoState) -> list[str]:
    return [f"{c.get('label')}: {c.get('detail')}" for c in state.get("checks", []) if c.get("state") == "fail"]


def requiere_decision_node(state: CasoState) -> dict[str, Any]:
    """Cotejar (ámbar): admisión ambigua -> decide un humano."""
    resumen = state.get("resumen") or "Admisión ambigua: requiere decisión humana."
    fails = _fails(state)
    detalle = ("\n- " + "\n- ".join(fails)) if fails else ""
    cuerpo = f"REVISIÓN MANUAL — {resumen}{detalle}"
    return {"status": Status.REQUIERE_DECISION.value, "respuesta": cuerpo, "acciones": _add_accion(state, cuerpo)}


def devolver_no_admisible_node(state: CasoState) -> dict[str, Any]:
    """Devuelve al emisor con el detalle (qué está mal / falta / sobra).
    Al 3er rebote del caso, avisa al dueño (T0.15)."""
    if state.get("tipo_objetivo"):  # Cotejar single-doc
        fails = _fails(state)
        cuerpo = "INVÁLIDO — " + (state.get("resumen") or "el documento no corresponde al tipo elegido")
        if fails:
            cuerpo += "\n- " + "\n- ".join(fails)
        return {"status": Status.NO_ADMISIBLE.value, "respuesta": cuerpo, "acciones": _add_accion(state, cuerpo)}

    rebotes = int(state.get("rebotes_admisibilidad", 0)) + 1
    adm = state.get("admisibilidad", {})

    lineas = ["Revisamos tu entrega y no la podemos admitir. Detalle:", ""]

    # Qué está mal / sobra — problema por documento recibido
    for d in state.get("documentos", []):
        problemas: list[str] = []
        if d.get("relevante") is False:
            problemas.append("no corresponde a esta entrega (fuera de alcance)")
        if d.get("formato_ok") is False:
            faltan = d.get("faltan") or []
            problemas.append(
                "formato incorrecto — falta: " + ", ".join(faltan) if faltan else "formato incorrecto"
            )
        if problemas:
            extra = f" — {d.get('motivo')}" if d.get("motivo") else ""
            lineas.append(f"• {d.get('filename')}: {'; '.join(problemas)}{extra}")

    # Qué falta — tipos de documento requeridos no cubiertos
    faltantes = adm.get("faltantes") or []
    if faltantes:
        lineas.append(f"• Faltan documentos requeridos: {', '.join(faltantes)}")

    if not any(line.startswith("•") for line in lineas):
        # Fallback si el triage no detalló por documento
        lineas.append(f"• {adm.get('motivo') or 'la entrega no cumple los requisitos esperados'}")

    lineas += ["", "Corregí lo indicado y reenviá la entrega."]
    cuerpo = "\n".join(lineas)

    acciones = list(state.get("acciones", []))
    acciones.append(enviar_emisor(state.get("emisor"), "Entrega no admisible", cuerpo))

    if rebotes >= 3:  # 2 rebotes silenciosos; el 3º escala al dueño
        aviso = (
            f"La entrega del caso {state.get('thread_id')} (emisor {state.get('emisor')}) "
            f"fue rechazada por admisibilidad {rebotes} veces. Conviene una mirada humana."
        )
        acciones.append(enviar_dueno(None, "Aviso: entrega rebotada 3 veces", aviso))

    return {
        "status": Status.NO_ADMISIBLE.value,
        "rebotes_admisibilidad": rebotes,
        "respuesta": cuerpo,
        "acciones": acciones,
    }


def listo_para_revision_node(state: CasoState) -> dict[str, Any]:
    """Admisible. En Cotejar single-doc = VÁLIDO; en entrega = listo para revisión (Fase 1)."""
    if state.get("tipo_objetivo"):  # Cotejar single-doc
        cuerpo = "VÁLIDO — " + (state.get("resumen") or f"el documento es admisible como '{state.get('tipo_objetivo')}'")
        return {"status": Status.EN_REVISION.value, "respuesta": cuerpo, "acciones": _add_accion(state, cuerpo)}

    cuerpo = (
        f"Documentos recibidos: {_nombres_recibidos(state)}.\n"
        f"Entrega admisible y completa (proyecto={state.get('proyecto')}, "
        f"tipo={state.get('tipo_entrega')}, disciplina={state.get('disciplina')}). "
        "Lista para revisión de contenido (Fase 1)."
    )
    print(f"[OK] {cuerpo}")
    return {"status": Status.EN_REVISION.value, "respuesta": cuerpo, "acciones": _add_accion(state, cuerpo)}
