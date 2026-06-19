"""Mesa de entrada (Streamlit) — gestión de documentos + dictamen de admisibilidad.

3 pestañas:
- 📥 Procesar entrega: subís documentos, elegís la entrega y procesás (corre el grafo).
- 🧩 Tipos de documento: crear (captura desde ejemplo), VER, EDITAR y borrar templates.
- 📦 Tipos de entrega: crear, EDITAR (qué documentos requiere) y borrar.

Reusa la lógica del agente sin duplicar: build_trigger_state + get_compiled_graph.
Correr:  uv run streamlit run sandbox/ui_intake.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from ai_agents.tipo_extractor import proponer_template  # noqa: E402
from graph.graph import get_compiled_graph  # noqa: E402
from tools import docs  # noqa: E402
from tools.disciplinas import (  # noqa: E402
    agregar_disciplina, cargar_disciplinas, eliminar_disciplina,
)
from tools.email import build_trigger_state  # noqa: E402
from tools.sheets import (  # noqa: E402
    eliminar_tipo_entrega, entregas_detalle, guardar_tipo_entrega, tipos_entrega,
)
from tools.tipos import (  # noqa: E402
    cargar_tipos, eliminar_tipo, guardar_template, to_yaml,
)

UP = Path("sandbox/uploads")
INFERIR = "(inferir del texto)"
TIPOS_ARCHIVO = ["pdf", "xlsx", "docx", "dxf", "dwg", "png", "jpg", "jpeg", "txt", "md", "csv"]

st.set_page_config(page_title="QA-Ingeniería · Lobox", page_icon="📥", layout="wide")


def _inject_brand() -> None:
    """Manual de marca Workforce AI by Lobox (Syne + Space Mono + Signal)."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Space+Mono:wght@400;700&display=swap');
        :root{ --signal:#2348FF; --signal-d:#1c39cc; --papel:#F4F2EE; --muted:#9c978d; --border:#3a3a3a; }
        html, body, .stApp, [class*="css"]{ font-family:'Syne',-apple-system,BlinkMacSystemFont,sans-serif; }
        h1,h2,h3,h4{ font-family:'Syne',sans-serif; font-weight:800; letter-spacing:-.01em; }
        code, pre, [data-testid="stMetricValue"], [data-testid="stMetricLabel"]{
            font-family:'Space Mono', ui-monospace, monospace; }
        [data-testid="stMetricLabel"]{ text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }
        .stButton>button{ background:var(--signal); color:#fff; border:none; font-weight:700;
            font-family:'Space Mono',monospace; letter-spacing:.02em; }
        .stButton>button:hover{ background:var(--signal-d); color:#fff; }
        .stDownloadButton>button{ background:transparent; color:var(--papel); border:1px solid var(--border);
            font-family:'Space Mono',monospace; }
        .lobox-mark{ font-family:'Syne',sans-serif; font-weight:800; letter-spacing:.02em; font-size:13px;
            color:var(--muted); display:inline-flex; align-items:center; gap:5px; text-transform:uppercase; }
        .lobox-mark .aibox{ background:var(--signal); color:#fff; font-weight:800; padding:1px 6px;
            border-radius:3px; letter-spacing:0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_brand()
st.markdown('<div class="lobox-mark">Workforce <span class="aibox">AI</span> by Lobox</div>', unsafe_allow_html=True)
st.title("QA-Ingeniería — Mesa de entrada")

# Reflejar ediciones a knowledge/tipos y catalogo.json en cada rerun
cargar_tipos.cache_clear()


# ===================== Sidebar: disciplinas (editable) =====================
with st.sidebar:
    st.header("🏷 Disciplinas")
    st.caption("Se ofrecen al clasificar la entrega. Fuente: `knowledge/disciplinas.json`")
    for _d in cargar_disciplinas():
        _dc1, _dc2 = st.columns([4, 1])
        _dc1.write(_d)
        if _dc2.button("🗑", key=f"del_disc_{_d}"):
            eliminar_disciplina(_d)
            st.rerun()
    _nueva_disc = st.text_input("Nueva disciplina", key="nueva_disc")
    if st.button("➕ Agregar disciplina", key="add_disc"):
        if _nueva_disc.strip():
            agregar_disciplina(_nueva_disc)
            st.rerun()
        else:
            st.warning("Escribí un nombre.")


# ===================== helpers =====================

def _preview(filename: str, data: bytes) -> None:
    ext = Path(filename).suffix.lower().lstrip(".")
    try:
        if ext in ("png", "jpg", "jpeg"):
            st.image(data, use_container_width=True)
        elif ext == "pdf":
            import fitz

            with fitz.open(stream=data, filetype="pdf") as d:
                total = d.page_count
                for pno in range(min(total, 20)):
                    pix = d[pno].get_pixmap(dpi=90)
                    st.image(pix.tobytes("png"), use_container_width=True, caption=f"Página {pno + 1} / {total}")
                if total > 20:
                    st.caption(f"… {total - 20} página(s) más no mostradas")
        elif ext == "xlsx":
            _preview_xlsx(data)
        elif ext in ("txt", "csv", "md"):
            st.text(data.decode("utf-8", "replace")[:1500])
        else:
            st.caption("Sin preview visual; se analiza el contenido al procesar.")
    except Exception as exc:
        st.caption(f"No se pudo generar preview ({exc}); se analiza igual al procesar.")


def _preview_xlsx(data: bytes, max_rows: int = 50) -> None:
    import io

    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for r in ws.iter_rows(values_only=True):
        rows.append(["" if c is None else c for c in r])
        if len(rows) >= max_rows:
            break
    titulo = ws.title
    wb.close()
    if not rows:
        st.caption("Planilla vacía.")
        return
    ncols = max(len(r) for r in rows)
    header, seen = [], {}
    for i in range(ncols):
        raw = str(rows[0][i]) if i < len(rows[0]) and rows[0][i] != "" else f"col{i + 1}"
        if raw in seen:
            seen[raw] += 1
            raw = f"{raw}_{seen[raw]}"
        else:
            seen[raw] = 0
        header.append(raw)
    registros = [{header[i]: (row[i] if i < len(row) else "") for i in range(ncols)} for row in rows[1:]]
    st.caption(f"Hoja: {titulo}")
    st.dataframe(registros, use_container_width=True, height=240)


def _procesar(files, meta) -> dict:
    run_dir = UP / uuid.uuid4().hex[:8]
    run_dir.mkdir(parents=True, exist_ok=True)
    entradas = []
    for f in files:
        dest = run_dir / f.name
        dest.write_bytes(f.getvalue())
        entradas.append({"filename": f.name, "path": str(dest)})
    state = build_trigger_state(entradas, meta)
    graph = get_compiled_graph()
    cfg = {"configurable": {"thread_id": state["thread_id"]}}
    return graph.invoke(state, cfg)


_BANNER = {
    "EN_REVISION": ("✅ Admisible y completa — lista para revisión", "success"),
    "INCOMPLETA": ("🟡 Incompleta — faltan documentos", "warning"),
    "NO_ADMISIBLE": ("⛔ No admisible", "error"),
    "FALTAN_DATOS": ("ℹ️ Faltan datos mínimos", "info"),
}

tab_proc, tab_doc, tab_ent = st.tabs(["📥 Procesar entrega", "🧩 Tipos de documento", "📦 Tipos de entrega"])


# ===================== TAB: Procesar entrega =====================
with tab_proc:
    col_docs, col_res = st.columns([1, 1], gap="large")
    with col_docs:
        st.subheader("Documentos de la entrega")
        files = st.file_uploader("Arrastrá o elegí archivos (varios)", accept_multiple_files=True,
                                 type=TIPOS_ARCHIVO, key="proc_files")
        st.markdown("**Datos de la entrega**")
        proyecto = st.text_input("Proyecto", value="P-102", key="proc_proy")
        tipo_label = st.selectbox("Tipo de entrega", [INFERIR, *tipos_entrega()], key="proc_tipo")
        tipo_val = None if tipo_label == INFERIR else tipo_label
        disc_label = st.selectbox("Disciplina", ["(inferir)", *cargar_disciplinas()], key="proc_disc")
        texto = st.text_area("Mensaje / contexto", value="Envío la entrega para revisar", key="proc_text")
        procesar = st.button("⚙️ Procesar entrega", type="primary", use_container_width=True)

        for i, f in enumerate(files or []):
            data = f.getvalue()
            with st.expander(f"📄 {f.name} · {len(data) // 1024 or 1} KB"):
                st.download_button("⬇️ Descargar", data, file_name=f.name, key=f"dl_{i}")
                _preview(f.name, data)

    if procesar:
        meta = {
            "text": texto, "proyecto": proyecto or None, "tipo_entrega": tipo_val,
            "disciplina": None if disc_label == "(inferir)" else disc_label,
            "emisor": "mesa-entrada@sandbox",
        }
        with st.spinner("Procesando entrega…"):
            st.session_state["resultado"] = _procesar(files or [], meta)

    with col_res:
        st.subheader("Resultado")
        res = st.session_state.get("resultado")
        if not res:
            st.info("Subí documentos, completá los datos y tocá **Procesar entrega**.")
        else:
            texto_banner, kind = _BANNER.get(res.get("status", ""), (res.get("status", "—"), "info"))
            getattr(st, kind)(texto_banner)
            st.markdown(f"**Entrega:** tipo `{res.get('tipo_entrega')}` · disciplina `{res.get('disciplina')}` · proyecto `{res.get('proyecto')}`")
            if res.get("respuesta"):
                st.markdown("**Respuesta del agente:**")
                st.write(res["respuesta"])
            adm = res.get("admisibilidad", {})
            if adm.get("faltantes"):
                st.warning("Faltan documentos requeridos: " + ", ".join(adm["faltantes"]))
            st.markdown("**Documentos evaluados**")
            cards = res.get("documentos_panel") or []
            if not cards:
                st.caption("Sin documentos evaluados.")
            for c in cards:
                datos = {d["clave"]: d["valor"] for d in c.get("datos", [])}
                borde = "🟥" if c.get("fuera_de_criterio") else "🟩"
                with st.container(border=True):
                    st.markdown(f"{borde} **{c.get('titulo')}**")
                    cols = st.columns(3)
                    cols[0].metric("Tipo", datos.get("tipo", "—"))
                    cols[1].metric("Relevante", datos.get("relevante", "—"))
                    cols[2].metric("Formato", datos.get("formato", "—"))
                    if c.get("motivo"):
                        st.caption(c["motivo"])
                    if c.get("razonamiento"):
                        with st.expander("¿Cómo decidió?"):
                            st.write(c["razonamiento"])
            with st.expander("Estado completo (debug)"):
                st.json({k: res.get(k) for k in (
                    "status", "tipo_entrega", "disciplina", "proyecto",
                    "entrega_completa", "admisibilidad", "rebotes_admisibilidad")})


# ===================== TAB: Tipos de documento =====================
with tab_doc:
    st.subheader("Tipos de documento")
    st.caption("Templates contra los que se chequea cada documento. Fuente: `knowledge/tipos/`")
    _tipos = cargar_tipos()

    st.markdown("##### Ver / editar un tipo existente")
    if _tipos:
        sel = st.selectbox("Tipo", list(_tipos.keys()), key="edit_sel")
        edit_key = f"edit_yaml_{sel}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = to_yaml(_tipos[sel])
        st.text_area("Template (YAML, editable)", key=edit_key, height=360)
        c1, c2 = st.columns([1, 1])
        if c1.button("💾 Guardar cambios", key=f"save_{sel}"):
            try:
                guardar_template(sel, st.session_state[edit_key])
                st.success(f"Guardado '{sel}'.")
            except Exception as exc:
                st.error(f"No se pudo guardar: {exc}")
        if c2.button("🗑 Eliminar tipo", key=f"del_{sel}"):
            eliminar_tipo(sel)
            st.session_state.pop(edit_key, None)
            st.rerun()
    else:
        st.caption("Todavía no hay tipos. Creá uno abajo (captura desde ejemplo).")

    st.divider()
    st.markdown("##### Crear un tipo nuevo (desde un ejemplo o una especificación)")
    cap_file = st.file_uploader("Documento fuente", type=TIPOS_ARCHIVO, key="cap_up")
    _modo_label = st.radio(
        "El documento que subo es:",
        ["Un ejemplo del tipo", "Una especificación / instructivo que define el tipo"],
        key="cap_modo", horizontal=True,
    )
    _modo = "especificacion" if _modo_label.startswith("Una espec") else "ejemplo"
    cc1, cc2 = st.columns(2)
    tid_hint = cc1.text_input("tipo_doc (id, opcional)", key="cap_tid_hint")
    nom_hint = cc2.text_input("Nombre (opcional)", key="cap_nom_hint")
    if st.button("🔎 Analizar", disabled=cap_file is None):
        with st.spinner("Analizando…"):
            _dir = UP / ("cap_" + uuid.uuid4().hex[:8])
            _dir.mkdir(parents=True, exist_ok=True)
            _p = _dir / cap_file.name
            _p.write_bytes(cap_file.getvalue())
            _leido = docs.read_document(str(_p))
            _imgs = list(_leido.get("imagenes", [])) + docs.render_pdf_images(str(_p), max_pages=4)
            _data = proponer_template(cap_file.name, _leido.get("contenido", ""), _imgs,
                                      tid_hint, nom_hint, modo=_modo)
        st.session_state["cap_area"] = to_yaml(_data)
        st.session_state["cap_save_tid"] = _data.get("tipo_doc", "")
    if st.session_state.get("cap_area"):
        st.text_area("Template propuesto (YAML, editable)", key="cap_area", height=320)
        st.text_input("Guardar como (id)", key="cap_save_tid")
        if st.button("💾 Guardar tipo nuevo"):
            try:
                _path = guardar_template(st.session_state.get("cap_save_tid", ""), st.session_state.get("cap_area", ""))
                st.success(f"Guardado en {_path}. Ya podés asociarlo a una entrega (pestaña 📦).")
            except Exception as exc:
                st.error(f"No se pudo guardar: {exc}")


# ===================== TAB: Tipos de entrega =====================
with tab_ent:
    st.subheader("Tipos de entrega")
    st.caption("Qué tipos de documento requiere cada entrega. Fuente: `knowledge/catalogo.json`")
    _ent = entregas_detalle()
    _doc_types = list(cargar_tipos().keys())

    st.markdown("##### Crear / editar")
    if not _doc_types:
        st.info("No hay tipos de documento. Creá uno en la pestaña 🧩 para poder requerirlo en una entrega.")
    _opciones = ["(nueva)"] + list(_ent.keys())
    _sel_e = st.selectbox("Entrega", _opciones, key="ent_sel")
    _editing = _sel_e != "(nueva)"
    _ent_id = st.text_input("tipo_entrega (id)", value=("" if not _editing else _sel_e), key=f"ent_id_{_sel_e}")
    _prefill = list(_ent.get(_sel_e, [])) if _editing else []
    # Opciones = tipos existentes + los que la entrega ya referencia (aunque falten),
    # para que el multiselect NUNCA crashee por "default no está en options".
    _opciones_docs = list(dict.fromkeys([*_doc_types, *_prefill]))
    _ent_reqs = st.multiselect("Documentos requeridos", _opciones_docs, default=_prefill, key=f"ent_reqs_{_sel_e}")
    _faltan_tipos = [d for d in _prefill if d not in _doc_types]
    if _faltan_tipos:
        st.warning("Esta entrega referencia tipos que ya no existen: " + ", ".join(_faltan_tipos) + " — quitalos del multiselect y guardá.")
    c1, c2 = st.columns([1, 1])
    if c1.button("💾 Guardar entrega", key="ent_save"):
        try:
            _tid = guardar_tipo_entrega(_ent_id, _ent_reqs)
            st.success(f"Entrega '{_tid}' guardada. Aparece en el dropdown de Procesar.")
        except Exception as exc:
            st.error(f"No se pudo guardar: {exc}")
    if _editing and c2.button("🗑 Eliminar entrega", key="ent_del"):
        eliminar_tipo_entrega(_sel_e)
        st.rerun()

    st.divider()
    st.markdown("##### Entregas definidas")
    if _ent:
        for _k, _reqs in _ent.items():
            st.markdown(f"- **{_k}** → {', '.join(_reqs) if _reqs else '(sin requeridos)'}")
    else:
        st.caption("No hay tipos de entrega definidos.")
