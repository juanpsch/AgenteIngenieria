"""API HTTP de Cotejar (FastAPI) — capa fina sobre las funciones in-process.

Contrato §7 del spec. Endpoints SÍNCRONOS a propósito: FastAPI los corre en un
threadpool, y el grafo/agentes usan `asyncio.run` internamente (que no puede correr
dentro de un loop activo). CORS abierto para el dev server del frontend.

Correr:  uv run uvicorn api.main:app --reload
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response

from ai_agents.tipo_extractor import proponer_template, proponer_template_multi
from api import historial
from api.schemas import (
    AplicarReglaIn, DecisionIn, DisciplinaIn, EntregaTipoIn, PromoverIn, RequisitoFeedbackIn,
    RequisitosIn, RevisionDecisionIn, SugerirVarianteIn, TemplateIn, ZonasIn,
)
from graph.graph import get_compiled_graph
from graph.nodes import extractor_node, revisor_node
from graph.state import Status, veredicto_ui
from tools import docs, normas, refs
from tools.disciplinas import agregar_disciplina, cargar_disciplinas, eliminar_disciplina
from tools.email import build_trigger_state
from tools.sheets import (
    eliminar_tipo_entrega, entregas_detalle, guardar_tipo_entrega, _catalogo,
)
from tools.tipos import (
    cargar_tipos, eliminar_tipo, guardar_template, guardar_zonas, set_patron_regla,
    set_revision_requisitos, to_yaml,
)

UP = Path("sandbox/uploads")

@asynccontextmanager
async def _lifespan(app: FastAPI):
    historial.init()
    # Precalienta el modelo de embeddings en background (carga ~5s de pesos desde disco),
    # así el primer "agregar referencia"/"validar" no espera la carga en frío.
    import threading

    from ai_agents import similarity

    threading.Thread(target=similarity.disponible, daemon=True).start()
    yield


app = FastAPI(title="Cotejar API", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False,
)


@app.get("/")
def _root():
    return RedirectResponse(url="/docs")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_name(name: str | None) -> str:
    """Nombre de archivo seguro (sin path traversal)."""
    return Path(name or "documento").name or "documento"


MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "25"))
ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
               ".xlsx", ".xls", ".docx", ".doc", ".dxf", ".dwg"}


def _leer_upload(file: UploadFile) -> tuple[str, bytes]:
    """Lee un archivo subido validando extensión y tamaño. Lanza HTTPException si no pasa."""
    safe = _safe_name(file.filename)
    ext = Path(safe).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"extensión no soportada: {ext or '(sin extensión)'}")
    data = file.file.read()
    if not data:
        raise HTTPException(400, "el archivo está vacío")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"el archivo supera el límite de {MAX_UPLOAD_MB:.0f} MB")
    return safe, data


def _state_de(thread_id: str) -> dict | None:
    """Lee el estado persistido de un caso por thread_id (checkpointer)."""
    try:
        snap = get_compiled_graph().get_state({"configurable": {"thread_id": thread_id}})
        return dict(snap.values) if snap and snap.values else None
    except Exception:
        return None


def _map_validacion(st: dict) -> dict:
    tipo = st.get("tipo_objetivo")
    panel = st.get("documentos_panel") or []
    docs_ = st.get("documentos") or []
    # El documento cotejado es el ÚLTIMO (la ida-y-vuelta lo reemplaza in situ).
    doc_ult = docs_[-1] if docs_ else {}
    imgs = doc_ult.get("imagenes") or []
    path = doc_ult.get("path")
    n_paginas = docs.paginas_utiles(path) if path else len(imgs)  # recorta hojas en blanco del final
    return {
        "thread_id": st.get("thread_id"),
        "status": st.get("status"),
        "veredicto": veredicto_ui(st.get("status", "")),
        "tipo_doc": tipo,
        "score": st.get("score"),
        "no_concluyente": st.get("no_concluyente", True),
        "score_detalle": st.get("score_detalle"),
        "maturity": refs.maturity(tipo) if tipo else None,
        "cajetin_bbox": st.get("cajetin_bbox"),
        "resumen": st.get("resumen") or st.get("respuesta"),
        "checks": st.get("checks", []),
        "campos": st.get("campos") or {},
        "zonas_resultado": st.get("zonas_resultado") or [],  # resultado por zona (informe + overlays)
        "revision": _map_revision(st),  # revisión de contenido (Fase 1); None si no corrió
        "requisito_feedback": historial.feedback_de(st.get("thread_id") or "") if st.get("thread_id") else {},
        "documento_panel": panel[0] if panel else None,
        "imagen": imgs[0] if imgs else None,  # data-url de la 1ª página (compat / fallback)
        "imagenes": imgs,  # páginas pre-renderizadas del gate (fallback del visor)
        "n_paginas": n_paginas,  # total real de páginas → el visor pide cada una on-demand al endpoint
    }


def _map_revision(st: dict) -> dict | None:
    """Bloque `revision` del contrato (Fase 1). None si la revisión aún no corrió."""
    verd = st.get("verdicto_revision")
    hall = st.get("hallazgos") or []
    if not verd and not hall:
        return None
    return {
        "verdicto": verd,
        "severidad_max": st.get("severidad_max"),
        "confiabilidad": st.get("revision_confiabilidad"),
        "resuelta": bool(st.get("revision_resuelta")),
        "notas": st.get("revisor_notas"),
        "hallazgos": hall,
    }


# ----------------------- Validación -----------------------
@app.post("/api/validar")
def validar(
    file: UploadFile = File(...),
    tipo_doc: str = Form(...),
    proyecto: str | None = Form(None),
    disciplina: str | None = Form(None),
    texto: str | None = Form(None),
    thread_id: str | None = Form(None),
    revisar: bool = Form(True),
):
    tid = thread_id or uuid.uuid4().hex[:12]
    updir = UP / tid
    updir.mkdir(parents=True, exist_ok=True)
    safe, data = _leer_upload(file)
    dest = updir / safe
    dest.write_bytes(data)

    meta = {"text": texto or "", "tipo_doc": tipo_doc, "proyecto": proyecto,
            "disciplina": disciplina, "emisor": "cotejar-api"}
    state = build_trigger_state([{"filename": safe, "path": str(dest)}], meta, thread_id=tid)
    state["revisar_auto"] = revisar  # toggle: continuar a revisión de contenido (o interrumpir en EN_REVISION)
    try:
        result = get_compiled_graph().invoke(state, {"configurable": {"thread_id": tid}})
    except Exception as exc:
        raise HTTPException(502, f"el agente falló procesando el documento: {exc}")

    resp = _map_validacion(result)
    historial.registrar_validacion(tid, file.filename, tipo_doc, result.get("status"),
                                   resp["veredicto"], resp.get("score"), "api", _now(),
                                   campos=resp.get("campos"))
    _registrar_requisitos(tid, result.get("hallazgos"))  # si la revisión corrió en el mismo invoke
    return resp


# ----------------------- Tipos de documento -----------------------
@app.get("/api/tipos")
def list_tipos():
    cargar_tipos.cache_clear()
    return [
        {"tipo_doc": tid, "nombre": t.get("nombre"), "empresa": t.get("empresa"),
         "disciplinas": t.get("disciplinas", []), "refs_count": refs.refs_count(tid),
         "maturity": refs.maturity(tid), "actualizado": None,
         "facetas": (t.get("revision") or {}).get("facetas") or {}}   # coordenadas (para pivot/filtros)
        for tid, t in cargar_tipos().items()
    ]


@app.get("/api/tipos/{tid}")
def get_tipo(tid: str):
    cargar_tipos.cache_clear()
    t = cargar_tipos().get(tid)
    if not t:
        raise HTTPException(404, "tipo no encontrado")
    resueltos = [r.get("req_id") for r in normas.resolver_requisitos(t.get("revision") or {}) if r.get("req_id")]
    return {**t, "yaml": to_yaml(t), "refs_count": refs.refs_count(tid), "maturity": refs.maturity(tid),
            "referencias": refs.listar_referencias(tid), "requisitos_resueltos": resueltos,
            "negativos": refs.listar_negativos(tid), "negativos_count": refs.negativos_count(tid)}


@app.post("/api/tipos/capturar")
def capturar(file: UploadFile = File(...), tipo_doc: str | None = Form(None),
             nombre: str | None = Form(None), modo: str = Form("ejemplo")):
    tmp = UP / ("cap_" + uuid.uuid4().hex[:8])
    tmp.mkdir(parents=True, exist_ok=True)
    safe, data = _leer_upload(file)
    p = tmp / safe
    p.write_bytes(data)
    leido = docs.read_document(str(p))
    imgs = list(leido.get("imagenes", [])) + docs.render_pdf_images(str(p), max_pages=refs._MAX_PAGES)
    propuesta = proponer_template(safe, leido.get("contenido", ""), imgs,
                                  tipo_doc or "", nombre or "", modo=modo)
    return {"template": propuesta, "yaml": to_yaml(propuesta)}


@app.post("/api/tipos/capturar-multi")
def capturar_multi(files: list[UploadFile] = File(...), tipo_doc: str | None = Form(None),
                   nombre: str | None = Form(None), modo: str = Form("ejemplo")):
    """Captura un template CONSOLIDADO desde VARIOS ejemplos del mismo tipo + cobertura de cada regla."""
    tmp = UP / ("capm_" + uuid.uuid4().hex[:8])
    tmp.mkdir(parents=True, exist_ok=True)
    documentos = []
    for f in files:
        safe, data = _leer_upload(f)
        p = tmp / safe
        p.write_bytes(data)
        leido = docs.read_document(str(p))
        imgs = list(leido.get("imagenes", [])) + docs.render_pdf_images(str(p), max_pages=refs._MAX_PAGES)
        documentos.append({"filename": safe, "contenido": leido.get("contenido", ""), "imagenes": imgs})
    if not documentos:
        raise HTTPException(400, "subí al menos un documento")
    res = proponer_template_multi(documentos, tipo_doc or "", nombre or "", modo=modo)
    return {"template": res["template"], "yaml": to_yaml(res["template"]), "cobertura": res["cobertura"]}


@app.put("/api/tipos/{tid}")
def put_tipo(tid: str, body: TemplateIn):
    try:
        guardar_template(tid, body.yaml)
    except Exception as exc:
        raise HTTPException(400, f"YAML inválido: {exc}")
    return {"ok": True, "tipo_doc": tid}


@app.delete("/api/tipos/{tid}")
def del_tipo(tid: str):
    return {"ok": eliminar_tipo(tid)}


@app.post("/api/tipos/{tid}/referencias")
def add_ref(tid: str, file: UploadFile = File(...)):
    safe, data = _leer_upload(file)
    return refs.agregar_referencia(tid, safe, data, origin="inicial")


@app.delete("/api/tipos/{tid}/referencias/{ref_id}")
def del_ref(tid: str, ref_id: str):
    return refs.eliminar_referencia(tid, ref_id)


@app.delete("/api/tipos/{tid}/negativos/{ref_id}")
def del_negativo(tid: str, ref_id: str):
    """Borra un contra-ejemplo del tipo (no toca CLIP; el score se recalcula solo en la próxima validación)."""
    return refs.eliminar_negativo(tid, ref_id)


@app.get("/api/tipos/{tid}/negativos/{ref_id}/preview")
def neg_preview(tid: str, ref_id: str, page: int = 1):
    """Render PNG de una página de un contra-ejemplo (galería del template)."""
    import base64

    ref = next((r for r in refs.listar_negativos(tid) if r.get("ref_id") == ref_id), None)
    if not ref:
        raise HTTPException(404, "contra-ejemplo no encontrado")
    p = ref.get("path")
    if not p or not Path(p).exists():
        raise HTTPException(404, "archivo del contra-ejemplo no encontrado")
    ext = Path(p).suffix.lower().lstrip(".")
    if ext in ("png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"):
        return Response(content=Path(p).read_bytes(), media_type=f"image/{ext}")
    durl = docs.render_pdf_page(p, page=max(1, page))
    if not durl:
        raise HTTPException(404, "página fuera de rango")
    return Response(content=base64.b64decode(durl.split(",", 1)[1]), media_type="image/png")


@app.put("/api/tipos/{tid}/zonas")
def put_zonas(tid: str, body: ZonasIn):
    """Guarda las zonas gráficas del template y re-embebe las referencias (su recorte cambia)."""
    t = guardar_zonas(tid, body.zonas)
    if not t:
        raise HTTPException(404, "tipo no encontrado")
    n = refs.reembeber_todas(tid)
    return {"ok": True, "zonas": t.get("zonas", []), "refs_reembebidas": n, "maturity": refs.maturity(tid)}


@app.put("/api/tipos/{tid}/requisitos")
def put_requisitos(tid: str, body: RequisitosIn):
    """Asigna el set de requisitos de revisión a una familia (`revision.requisitos`)."""
    t = set_revision_requisitos(tid, body.requisitos, normas=body.normas, excluir=body.excluir)
    if t is None:
        raise HTTPException(404, "tipo no encontrado")
    resueltos = [r.get("req_id") for r in normas.resolver_requisitos(t.get("revision") or {}) if r.get("req_id")]
    return {"ok": True, "requisitos_resueltos": resueltos}


@app.get("/api/tipos/{tid}/zona-sugerida")
def zona_sugerida(tid: str):
    """Propone (vía visión) el bbox del bloque de identidad usando la 1ª referencia del tipo."""
    from ai_agents import similarity

    ref = next((r for r in refs.listar_referencias(tid) if r.get("path") and Path(r["path"]).exists()), None)
    if not ref:
        raise HTTPException(404, "subí al menos una referencia para sugerir la zona")
    p = ref["path"]
    ext = Path(p).suffix.lower().lstrip(".")
    imgs = [p] if ext in ("png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff") else docs.render_pdf_images(p, max_pages=1)
    z = similarity.detectar_zona_identidad(imgs) if imgs else None
    if not z:
        raise HTTPException(422, "no se pudo sugerir una zona automáticamente")
    return {"zona": z}


@app.get("/api/tipos/{tid}/referencias/{ref_id}/preview")
def ref_preview(tid: str, ref_id: str, page: int = 1):
    """Render PNG de una página (1-indexada) de una referencia (galería/preview/editor de zonas)."""
    import base64

    ref = next((r for r in refs.listar_referencias(tid) if r.get("ref_id") == ref_id), None)
    if not ref:
        raise HTTPException(404, "referencia no encontrada")
    p = ref.get("path")
    if not p or not Path(p).exists():
        raise HTTPException(404, "archivo de referencia no encontrado")
    ext = Path(p).suffix.lower().lstrip(".")
    if ext in ("png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"):
        return Response(content=Path(p).read_bytes(), media_type=f"image/{ext}")
    durl = docs.render_pdf_page(p, page=max(1, page))
    if not durl:
        raise HTTPException(404, "página fuera de rango o tipo sin preview")
    return Response(content=base64.b64decode(durl.split(",", 1)[1]), media_type="image/png")


# ----------------------- Decisión + promoción -----------------------
@app.post("/api/tipos/{tid}/reglas/sugerir-variante")
def sugerir_variante(tid: str, body: SugerirVarianteIn):
    """Propone (y VERIFICA contra el corpus) una variante de regex que dejaría pasar `valor` sin
    romper los válidos ni aceptar los rechazados. El humano decide si la aplica."""
    from ai_agents.tipo_extractor import proponer_regex
    from tools.reglas import verificar_variante

    valor = (body.valor or "").strip()
    pos: list[str] = []
    neg: list[str] = []
    for r in historial.corpus(tid):
        v = (r.get("campos") or {}).get(body.campo)
        if not v:
            continue
        if r.get("decision") == "rejected":
            neg.append(v)
        elif r.get("decision") == "approved" or r.get("veredicto") == "valido":
            pos.append(v)
    deben = list(dict.fromkeys([*pos, valor]))  # dedup; incluye el valor que el humano dice que SÍ
    patron = proponer_regex(deben, neg)
    if not patron:
        raise HTTPException(422, "no se pudo proponer una variante")
    verif = verificar_variante(patron, deben, neg)
    return {"campo": body.campo, "patron": patron, "ejemplos_si": len(deben), "ejemplos_no": len(neg), **verif}


@app.post("/api/tipos/{tid}/reglas/aplicar")
def aplicar_regla(tid: str, body: AplicarReglaIn):
    """Aplica una variante de patrón a la regla de un campo (con visto bueno humano)."""
    if set_patron_regla(tid, body.campo, body.patron) is None:
        raise HTTPException(404, "tipo no encontrado")
    return {"ok": True, "campo": body.campo, "patron": body.patron}


@app.get("/api/casos/{thread_id}")
def get_caso(thread_id: str):
    """Detalle de un análisis pasado (reconstruido del checkpointer): mismo payload que /validar."""
    st = _state_de(thread_id)
    if not st:
        raise HTTPException(404, "no se encontró el estado del caso (pudo haberse purgado)")
    resp = _map_validacion(st)
    resp["decision"] = historial.decision_de(thread_id)
    return resp


@app.post("/api/casos/{thread_id}/negativo")
def caso_negativo(thread_id: str):
    """Guarda el caso como CONTRA-EJEMPLO del gate — acción DELIBERADA, simétrica a 'promover'. Solo para
    casos que el humano RECHAZÓ. Alimenta el embedding (similarity penaliza los parecidos a un rechazado)."""
    if historial.decision_de(thread_id) != "rejected":
        raise HTTPException(409, "solo se usa como contra-ejemplo un caso rechazado")
    st = _state_de(thread_id) or {}
    tipo = st.get("tipo_objetivo")
    docs_ = st.get("documentos") or []
    p = docs_[-1].get("path") if docs_ else None
    if not tipo or not p or not Path(p).exists():
        raise HTTPException(400, "no se encontró el documento del caso")
    from tools import refs

    r = refs.agregar_negativo(tipo, Path(p).name, Path(p).read_bytes(), origin="rechazo_humano")
    logging.getLogger("cotejar").info("negativo (manual) %s tipo=%s total=%s", thread_id, tipo, r.get("negativos_count"))
    return {"negativos_count": r.get("negativos_count")}


@app.post("/api/casos/{thread_id}/decision")
def decision(thread_id: str, body: DecisionIn):
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision debe ser 'approved' o 'rejected'")
    historial.registrar_decision(thread_id, body.decision)
    st = _state_de(thread_id) or {}
    status = st.get("status")
    cfg = {"configurable": {"thread_id": thread_id}}
    if body.decision == "approved":
        # Aprobar la admisión de un ámbar lo deja admitido (EN_REVISION) — spec §0.
        if status == Status.REQUIERE_DECISION.value:
            get_compiled_graph().update_state(cfg, {"status": Status.EN_REVISION.value})
            st = {**st, "status": Status.EN_REVISION.value}
            status = Status.EN_REVISION.value
        # Corre la revisión de contenido si el tipo la declara y aún no corrió (cubre ámbar + toggle off).
        if not st.get("hallazgos"):
            tpl = cargar_tipos().get(st.get("tipo_objetivo")) if st.get("tipo_objetivo") else None
            if tpl and tpl.get("revision"):
                try:
                    status = _correr_revision(thread_id, st).get("status", status)
                except Exception as exc:
                    logging.getLogger("cotejar").warning("revisión al aprobar falló (%s): %s", thread_id, exc)
    elif body.decision == "rejected" and status == Status.REQUIERE_DECISION.value:
        # Rechazar un ámbar lo deja NO admisible (refleja la decisión humana en el estado).
        # El contra-ejemplo (negativo) NO se toma solo: es una acción deliberada (endpoint /negativo).
        get_compiled_graph().update_state(cfg, {"status": Status.NO_ADMISIBLE.value})
        status = Status.NO_ADMISIBLE.value
    return {"status": status, "veredicto": veredicto_ui(status or ""), "decision": body.decision}


def _registrar_requisitos(thread_id: str, hallazgos: list | None) -> None:
    """Persiste {req_id: estado} de la revisión en el corpus (para el aprendedor)."""
    reqs = {h["req_id"]: h.get("estado") for h in (hallazgos or []) if h.get("req_id")}
    if reqs:
        historial.set_requisitos(thread_id, reqs)


def _correr_revision(thread_id: str, st: dict) -> dict:
    """Corre extractor+revisor sobre un caso ya admitido (EN_REVISION) y persiste el resultado."""
    upd1 = extractor_node(st)
    st1 = {**st, **upd1}
    upd2 = revisor_node(st1)
    cfg = {"configurable": {"thread_id": thread_id}}
    get_compiled_graph().update_state(cfg, {**upd1, **upd2})
    _registrar_requisitos(thread_id, upd2.get("hallazgos"))
    return {**st1, **upd2}


@app.post("/api/casos/{thread_id}/revisar")
def revisar_caso(thread_id: str):
    """Dispara la revisión de contenido a pedido (cuando el toggle interrumpió o tras aprobar admisión)."""
    st = _state_de(thread_id)
    if not st:
        raise HTTPException(404, "no se encontró el estado del caso")
    if st.get("status") != Status.EN_REVISION.value:
        raise HTTPException(409, "el caso no está admitido (EN_REVISION)")
    # No re-correr si un humano ya resolvió el veredicto de revisión (se perdería su decisión).
    merged = st if st.get("revision_resuelta") else _correr_revision(thread_id, st)
    resp = _map_validacion(merged)
    resp["decision"] = historial.decision_de(thread_id)
    return resp


@app.post("/api/casos/{thread_id}/revision/vlm")
def revision_vlm(thread_id: str):
    """Observación visual (VLM, Tier 3) A PEDIDO: el VLM verifica las reglas que el texto no pudo y agrega
    observaciones; se mergea en la revisión y se recalcula el veredicto."""
    from ai_agents.revisor import verificar_reglas_vlm
    from graph.revision import agregar_revision

    st = _state_de(thread_id)
    if not st:
        raise HTTPException(404, "no se encontró el estado del caso")
    docs_ = st.get("documentos") or []
    doc = docs_[-1] if docs_ else {}
    tpl = cargar_tipos().get(st.get("tipo_objetivo")) if st.get("tipo_objetivo") else None
    cfg = (tpl or {}).get("revision")
    if not doc or not cfg:
        raise HTTPException(409, "el caso no tiene revisión configurada")
    try:
        hall = verificar_reglas_vlm(doc, cfg, st.get("hallazgos") or [])
        agg = agregar_revision(hall)
        upd = {"hallazgos": hall, "verdicto_revision": agg["verdicto"],
               "severidad_max": agg["severidad_max"], "revision_confiabilidad": agg["confiabilidad"]}
        try:
            get_compiled_graph().update_state({"configurable": {"thread_id": thread_id}}, upd)
        except Exception as exc:  # si no se pudo persistir, devolvemos igual la observación calculada
            logging.getLogger("cotejar").warning("VLM: no se pudo persistir (%s): %s", thread_id, exc)
        return _map_revision({**st, **upd})
    except Exception as exc:
        logging.getLogger("cotejar").exception("observación visual falló (%s)", thread_id)
        raise HTTPException(500, f"observación visual falló: {exc}") from exc


@app.get("/api/casos/{thread_id}/pagina/{page}")
def caso_pagina(thread_id: str, page: int = 1):
    """Render PNG de la página N del documento del caso, on-demand desde el archivo guardado
    (la previsualización NO viaja en el payload: el visor pide cada hoja a este endpoint)."""
    import base64

    st = _state_de(thread_id)
    docs_ = (st or {}).get("documentos") or []
    p = docs_[-1].get("path") if docs_ else None
    if not p or not Path(p).exists():
        raise HTTPException(404, "documento del caso no encontrado")
    durl = docs.render_pdf_page(p, page=max(1, page))
    if not durl:
        raise HTTPException(404, "página fuera de rango o documento sin render")
    return Response(content=base64.b64decode(durl.split(",", 1)[1]), media_type="image/png")


@app.get("/api/casos/{thread_id}/informe")
def caso_informe(thread_id: str):
    """Informe de revisión en PDF (admisión + revisión + hallazgos + decisión humana)."""
    from datetime import date

    from tools.informe import generar_informe

    st = _state_de(thread_id)
    if not st:
        raise HTTPException(404, "no se encontró el caso")
    mapped = _map_validacion(st)
    rev = mapped.get("revision") or {}
    docs_ = st.get("documentos") or []
    ult = docs_[-1] if docs_ else {}
    fname = ult.get("filename") or (Path(ult["path"]).name if ult.get("path") else "documento")
    datos = {
        "fecha": date.today().isoformat(),
        "filename": fname, "tipo": mapped.get("tipo_doc"),
        "admision": mapped.get("veredicto"), "score": mapped.get("score"),
        "revision": rev, "hallazgos": rev.get("hallazgos"),
        "decision": historial.decision_de(thread_id), "notas": rev.get("notas"),
    }
    pdf = generar_informe(datos)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="informe_{thread_id}.pdf"'})


@app.get("/api/normas/catalogo")
def normas_catalogo():
    """Catálogo plano de requisitos chequeables (la biblioteca asignable a las familias)."""
    return normas.catalogo_requisitos()


@app.get("/api/reglas/estadisticas")
def reglas_estadisticas():
    """Observatorio de reglas: por cada regla, su estadística de cumplimiento (global y POR FAMILIA, con las
    facetas de cada familia) + el feedback humano agregado. Permite analizar qué reglas afectan a qué
    documentos/familias y revisar el juicio humano. Las familias traen sus facetas para poder facetar la vista."""
    cat = {q["req_id"]: q for q in normas.catalogo_requisitos()}
    tipos = cargar_tipos()
    fam_facetas = {tid: ((t.get("revision") or {}).get("facetas") or {}) for tid, t in tipos.items()}
    fam_nombre = {tid: (t.get("nombre") or tid) for tid, t in tipos.items()}

    def _z():
        return {"n": 0, "ok": 0, "fallo": 0, "no_verificable": 0, "advertencia": 0}

    glob: dict[str, dict] = {}          # req_id -> contadores
    porfam: dict[str, dict] = {}        # req_id -> {tipo_doc -> contadores}
    for row in historial.corpus_global():
        td = row.get("tipo_doc")
        for rid, est in (row.get("requisitos") or {}).items():
            g = glob.setdefault(rid, _z())
            f = porfam.setdefault(rid, {}).setdefault(td, _z())
            for c in (g, f):
                c["n"] += 1
                if est in c:
                    c[est] += 1

    fb_glob: dict[str, dict] = {}       # req_id -> {juicio: n}  (todos los alcances)
    fb_fam: dict[str, dict] = {}        # req_id -> {tipo_doc -> {juicio: n}}  (solo alcance familia)
    fb_amplio: dict[str, dict] = {}     # req_id -> {juicio: n}  (alcance norma/global: se reusa en todas)
    for r in historial.feedback_global():
        rid, td, j, n, al = r["req_id"], r["tipo_doc"], r["juicio"], int(r["n"]), r.get("alcance", "familia")
        gg = fb_glob.setdefault(rid, {}); gg[j] = gg.get(j, 0) + n
        if al in ("norma", "global"):
            aa = fb_amplio.setdefault(rid, {}); aa[j] = aa.get(j, 0) + n
        else:
            ff = fb_fam.setdefault(rid, {}).setdefault(td, {}); ff[j] = ff.get(j, 0) + n

    def _pct(c):
        base = c["ok"] + c["fallo"]      # % de cumplimiento sobre lo verificable (ok / (ok+fallo))
        return round(100 * c["ok"] / base, 1) if base else None

    out = []
    for rid in sorted(set(cat) | set(glob)):
        meta = cat.get(rid, {})
        g = glob.get(rid, _z())
        familias = [
            {"tipo_doc": td, "nombre": fam_nombre.get(td, td), "facetas": fam_facetas.get(td, {}),
             **c, "pct_cumple": _pct(c), "feedback": fb_fam.get(rid, {}).get(td, {})}
            for td, c in (porfam.get(rid) or {}).items()
        ]
        out.append({
            "req_id": rid, "id": meta.get("id"), "descripcion": meta.get("descripcion"),
            "norma_id": meta.get("norma_id"), "norma_ref": meta.get("norma_ref"),
            "severidad": meta.get("severidad"), "tipo": meta.get("tipo"),
            "disciplinas": meta.get("disciplinas") or [], "huerfana": rid not in cat,
            **g, "pct_cumple": _pct(g), "feedback": fb_glob.get(rid, {}),
            "feedback_amplio": fb_amplio.get(rid, {}),   # juicios a nivel norma/global (se reusan)
            "familias": sorted(familias, key=lambda x: -x["n"]),
        })
    return out


@app.get("/api/perfiles")
def list_perfiles():
    """Perfiles de cumplimiento (eje proyecto/cliente) con sus requisitos resueltos, para asignar en bloque."""
    from tools import perfiles

    return [{"id": pid, "nombre": p.get("nombre", pid), "proyecto": p.get("proyecto"),
             "jurisdiccion": p.get("jurisdiccion"), "requisitos": perfiles.requisitos_de_perfil(p)}
            for pid, p in perfiles.cargar_perfiles().items()]


@app.get("/api/tipos/{tid}/requisitos/sugerencias")
def requisitos_sugerencias(tid: str):
    """Sugerencias del aprendedor para la familia (agregar/quitar/prior), desde el corpus etiquetado."""
    from api import aprendizaje

    return aprendizaje.sugerir_requisitos(tid)


@app.post("/api/casos/{thread_id}/requisito-feedback")
def requisito_feedback(thread_id: str, body: RequisitoFeedbackIn):
    """Juicio humano POR REGLA (grilla): de_acuerdo / no_aplica / regla_mal, con ALCANCE
    (familia / norma / global). Alimenta el aprendizaje; norma/global se reusan en todas las familias."""
    if body.juicio not in ("de_acuerdo", "no_aplica", "regla_mal"):
        raise HTTPException(400, "juicio debe ser de_acuerdo | no_aplica | regla_mal")
    if body.alcance not in ("familia", "norma", "global"):
        raise HTTPException(400, "alcance debe ser familia | norma | global")
    st = _state_de(thread_id) or {}
    tipo = st.get("tipo_objetivo")
    estado = next((h.get("estado") for h in (st.get("hallazgos") or [])
                   if h.get("req_id") == body.requisito_id), None)
    historial.registrar_requisito_feedback(thread_id, body.requisito_id, body.juicio, _now(),
                                           tipo_doc=tipo, estado=estado, nota=body.notas, alcance=body.alcance)
    return {"ok": True, "requisito_id": body.requisito_id, "juicio": body.juicio, "alcance": body.alcance}


def _doc_path_caso(thread_id: str) -> str | None:
    docs_ = (_state_de(thread_id) or {}).get("documentos") or []
    return docs_[-1].get("path") if docs_ else None


@app.get("/api/casos/{thread_id}/buscar")
def caso_buscar(thread_id: str, q: str = ""):
    """Busca `q` en TODO el documento del caso → páginas + bboxes para resaltar en el previsualizador."""
    p = _doc_path_caso(thread_id)
    return docs.buscar_texto(p, q) if p else []


@app.get("/api/casos/{thread_id}/archivo")
def caso_archivo(thread_id: str):
    """Sirve el documento original del caso INLINE (abrirlo en pestaña/visor nativo: búsqueda, zoom)."""
    p = _doc_path_caso(thread_id)
    if not p or not Path(p).exists():
        raise HTTPException(404, "documento del caso no encontrado")
    ext = Path(p).suffix.lower().lstrip(".")
    media = "application/pdf" if ext == "pdf" else f"image/{ext}"
    return Response(content=Path(p).read_bytes(), media_type=media,
                    headers={"Content-Disposition": f'inline; filename="{Path(p).name}"'})


@app.post("/api/casos/{thread_id}/revision/decision")
def revision_decision(thread_id: str, body: RevisionDecisionIn):
    """Veredicto humano sobre la revisión de contenido (o escalar a senior)."""
    opciones = ("aprobado", "aprobado_con_notas", "observado", "rechazado", "escalar_senior")
    if body.decision not in opciones:
        raise HTTPException(400, f"decision debe ser uno de {opciones}")
    st = _state_de(thread_id)
    if not st:
        raise HTTPException(404, "no se encontró el estado del caso")
    verd = "pendiente_senior" if body.decision == "escalar_senior" else body.decision
    upd = {"verdicto_revision": verd, "revision_resuelta": body.decision != "escalar_senior",
           "revisor_notas": body.notas or None}
    get_compiled_graph().update_state({"configurable": {"thread_id": thread_id}}, upd)
    return {"verdicto": verd, "resuelta": upd["revision_resuelta"]}


@app.post("/api/tipos/{tid}/referencias/promover")
def promover(tid: str, body: PromoverIn):
    if historial.decision_de(body.thread_id) != "approved":
        raise HTTPException(409, "solo se puede promover un caso aprobado por un humano")
    if not body.promote:
        return {"refs_count": refs.refs_count(tid), "maturity": refs.maturity(tid), "promovido": False}
    st = _state_de(body.thread_id) or {}
    docs_ = st.get("documentos", [])
    # El doc cotejado es el ÚLTIMO (la ida-y-vuelta lo reemplaza); promover ese, no el primero.
    doc = docs_[-1] if docs_ else {}
    if not doc.get("path"):
        raise HTTPException(400, "no se encontró el documento del caso para promover")
    res = refs.agregar_referencia_desde_path(tid, doc["path"], doc.get("filename"), origin="promovido")
    historial.marcar_promovido(body.thread_id)
    return {"refs_count": res["refs_count"], "maturity": res["maturity"], "promovido": True}


# ----------------------- Catálogos -----------------------
@app.get("/api/entregas-tipo")
def get_entregas():
    return entregas_detalle()


@app.put("/api/entregas-tipo/{tid}")
def put_entrega(tid: str, body: EntregaTipoIn):
    return {"ok": True, "tipo_entrega": guardar_tipo_entrega(tid, body.documentos_requeridos)}


@app.delete("/api/entregas-tipo/{tid}")
def del_entrega(tid: str):
    return {"ok": eliminar_tipo_entrega(tid)}


@app.get("/api/disciplinas")
def get_disciplinas():
    return cargar_disciplinas()


@app.post("/api/disciplinas")
def add_disciplina(body: DisciplinaIn):
    return agregar_disciplina(body.nombre)


@app.delete("/api/disciplinas/{nombre}")
def del_disciplina(nombre: str):
    return eliminar_disciplina(nombre)


@app.get("/api/proyectos")
def get_proyectos():
    cat = _catalogo()
    return [{"id": pid, "nombre": p.get("nombre")} for pid, p in cat.get("proyectos", {}).items()]


# ----------------------- Historial -----------------------
@app.get("/api/historial")
def get_historial():
    return {"items": historial.listar(), "metricas": historial.metricas()}
