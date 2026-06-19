# Plan de implementación — Cotejar (gate de admisión documental, full-stack)

Plan por fases para construir lo que pide `docs/spec/SPEC_Cotejar_QA-Ingenieria.md` sobre el backend existente.
Orden pensado para **desbloquear el frontend rápido** y dejar las dependencias pesadas aisladas.

## Decisiones tomadas (de la entrevista)
- **Embeddings: modelo LOCAL** (SigLIP/CLIP vía transformers/open-clip) — offline, sin key, reproducible. `EMBED_PROVIDER=local`.
- **UI handoff/tokens:** **disponible** en `docs/spec/design_handoff_cotejar/` (`README.md` con design tokens + `Cotejar.dc.html` prototipo). Fase D recrea fiel (ya no está bloqueada).
- **Cajetín bbox:** arrancamos con **LLM de visión** (localización aproximada; no viola "no pedir el score al LLM"); se puede endurecer con CV (OpenCV) después.
- **OCR:** PyMuPDF (texto de PDF vectorial) + visión; degradar con gracia si no hay texto. Tesseract queda como mejora si aparecen escaneados.

## Repo / layout (propuesto)
Mantener el backend en `qa-ingenieria/` y agregar:
```
qa-ingenieria/
  graph/  ai_agents/  tools/  prompts/  knowledge/      # existente (se extiende)
  ai_agents/similarity.py        # NUEVO (Fase C)
  knowledge/refs/<id>/...         # NUEVO (Fase C)
  api/                            # NUEVO (Fase B): main.py, routers/, schemas.py, deps.py
  frontend/                       # NUEVO (Fase D): React + TS + Vite
  scripts/  sandbox/              # el Streamlit/CLI siguen operativos (no romper)
```
> El smoke in-process (`scripts/run_local.py`) y la UI Streamlit deben seguir funcionando en todas las fases.

---

## Fase A — Backend core (sin dependencias nuevas)
Habilitar el modo **"validar 1 documento contra un template elegido"** con salida en **dos dimensiones (Identidad / Completitud) + `checks[]`**, el estado **`REQUIERE_DECISION`** y el **chequeo regex** de campos del cajetín. Todo con lo que ya tenemos; no suma libs. **No rompe** el modo entrega multi-doc ni Streamlit.

> **Aclaración clave de semántica.** En el modo Cotejar:
> - **Identidad** = "¿este documento ES el tipo elegido (empresa/tipo/cajetín/logo/señales/score)?" — clasificación **contra un tipo fijado**, no abierta.
> - **Completitud/conformidad** = "¿el documento tiene todos los **campos/secciones obligatorios** según el template?" — conformidad **interna del documento**. (≠ `INCOMPLETA`, que es "faltan **documentos** de la entrega" multi-doc, fuera de pantalla.)

- [ ] **A0 — Contratos.** Fijar el tipo `Check`, la **tabla de veredicto** (A6) y el **mapeo 1-doc** (entrega degenerada: `requeridos=[tipo_doc_elegido]`, un solo documento). Para que A1–A6 no diverjan.
- [ ] **A1 — Enum + veredicto.** `graph/state.py`: `Status.REQUIERE_DECISION`. Helper `veredicto_ui(status) -> "valido|revision_manual|invalido|faltan_datos"` (§4.3).
- [ ] **A2 — Estado.** `Check = {dimension:"identidad"|"completitud", label, state:"pass|fail|warn|info", detail}`. Agregar al estado: `checks: list[Check]`, `score`, `no_concluyente`, `cajetin_bbox`, `resumen`. (Single-doc: los `checks` del caso = los del documento elegido. `score/no_concluyente/cajetin_bbox` quedan en placeholder en Fase A; los llena C.)
- [ ] **A3 — Reglas regex del cajetín (Completitud determinística).** Schema de tipo: bloque `cajetin.reglas[] = {campo, patron, requerido}`. `tools/tipos.py`: cargar/serializar (+ extractor puede proponerlas). Helper `chequear_reglas(texto, reglas) -> [Check]` **determinístico** (regex sobre el texto extraído; degradar a `warn`/`info` si no hay texto, nunca inventar `pass`).
- [ ] **A4 — Triage contra el tipo elegido (Identidad + cualitativo).** `prompts/triage.txt` + `ai_agents/triage.py` en modo single-doc: emite **checks granulares** de **Identidad** ("¿es el tipo X?", rótulo presente/identifica, código de empresa/tipo, logo, señales) y de **Completitud cualitativa** (secciones/columnas requeridas presentes), cada uno con `state` + `detail`, más `razonamiento`. (El check "Similitud visual" queda `info`/`null` hasta Fase C.)
- [ ] **A5 — Ensamblar `checks[]`.** Helper que **mergea** los checks de A3 (regex, Completitud) + A4 (LLM, Identidad+secciones) en un único `checks[]` por dimensión, y calcula si cada dimensión **pasa** (sin `fail` en requeridos). Esto alimenta el router y el `documentos_panel`.
- [ ] **A6 — Router de veredicto (tabla, sin score aún).** `graph/edges.py` + `graph/nodes.py`:
  - Identidad falla duro (no es el tipo / `bloqueante` / formato no soportado) → **NO_ADMISIBLE** (rojo).
  - Identidad OK + algún check de Completitud **requerido** en `fail` (o baja confianza) → **REQUIERE_DECISION** (ámbar). Nodo nuevo `requiere_decision_node`.
  - Identidad OK + Completitud OK → **EN_REVISION** (verde).
  - Sin datos mínimos → **FALTAN_DATOS**.
- [ ] **A7 — Compat (no romper).** Mantener `relevante/formato_ok/faltan/motivo/razonamiento` + `documentos_panel` + el path multi-doc/`INCOMPLETA` (Streamlit + smoke). `checks[]` es aditivo; el router nuevo convive con `route_triage` (entrega) — Cotejar usa el modo single-doc.
  - *Aceptación:* validar 1 doc contra su template → `valido` con checks de ambas dimensiones; identidad OK + falta un campo requerido → `revision_manual` (ámbar) con el check en `fail`; doc de otro tipo / bloqueante → `invalido`. `run_local.py` y la UI Streamlit siguen verdes.

### Detalle de tareas — Fase A
Granular, en orden de dependencia. Cada tarea con archivo(s), qué hace y **criterio de aceptación**.

**A0 · Contratos (definiciones; habilitan el resto)**
- **A0.1 — Modo single-doc.** Decisión: el modo Cotejar se activa con un campo de estado `tipo_objetivo` (el template elegido). Presente → validar 1 doc contra ese tipo; ausente → modo entrega multi-doc actual (intacto). `build_trigger_state` lo toma de `meta["tipo_doc"]`.
  - *Aceptación:* documentado; `meta={"tipo_doc": "..."}` llega a `state["tipo_objetivo"]`.
- **A0.2 — Tabla de veredicto.** Fijar el mapeo dimensiones→status→veredicto_ui (rojo/ámbar/verde) que implementa A6.
  - *Aceptación:* tabla escrita y referenciada por A6.

**A1 · Status + veredicto**
- **A1.1 — `Status.REQUIERE_DECISION`** en `graph/state.py` (enum).
- **A1.2 — `veredicto_ui(status)`** → `"valido"|"revision_manual"|"invalido"|"faltan_datos"` (helper en `state.py`).
  - *Aceptación:* `veredicto_ui(Status.REQUIERE_DECISION)=="revision_manual"`, `EN_REVISION→valido`, `NO_ADMISIBLE→invalido`, `FALTAN_DATOS→faltan_datos`.

**A2 · Estado**
- **A2.1 — Tipo `Check`** (`TypedDict`) en `state.py`: `{dimension:"identidad"|"completitud", label:str, state:"pass|fail|warn|info", detail:str, requerido:bool}`.
- **A2.2 — Campos nuevos en `CasoState`:** `tipo_objetivo`, `checks: list[Check]`, `score: float|None`, `no_concluyente: bool`, `cajetin_bbox: dict|None`, `resumen: str`.
- **A2.3 — `initial_state`** con defaults (`checks=[]`, `score=None`, `no_concluyente=True`, `cajetin_bbox=None`, `tipo_objetivo=None`, `resumen=""`).
  - *Aceptación:* importa y serializa; defaults presentes.

**A3 · Reglas regex del cajetín (Completitud determinística)**
- **A3.1 — Schema de tipo:** soportar `cajetin.reglas[] = {campo, patron, requerido}` en `knowledge/tipos/*.yaml`. `tools/tipos.py`: incluir en `_ORDEN`, `render_template` y `to_yaml`.
  - *Aceptación:* un YAML con `cajetin.reglas` carga y re-serializa sin perderlas; aparecen en `render_template`.
- **A3.2 — `chequear_reglas(texto, reglas) -> list[Check]`** (nuevo módulo `tools/reglas.py` o en `tipos.py`): por cada regla, regex sobre el texto extraído del doc. Match→`pass`; requerido sin match→`fail` ("Falta el campo"/"Formato inválido"); opcional sin match→`warn`; sin texto extraíble→`warn`/`info` (nunca `pass` inventado).
  - *Aceptación:* sobre un texto de prueba, una regla `{campo:"Revisión", patron:"^REV-[0-9]+$", requerido:true}` da `pass` si hay "REV-3" y `fail` si no.

**A4 · Triage contra el tipo elegido (Identidad + cualitativo)**
- **A4.1 — Prompt single-doc.** `prompts/triage.txt`: cuando hay `tipo_objetivo`, instrucción = "validá si ESTE documento es el tipo **elegido** y si cumple su template". Emitir **checks granulares**: Identidad (`es_el_tipo`, rótulo presente/identifica, código empresa, código tipo, logo, señales) y Completitud cualitativa (secciones/columnas requeridas). Cada check con `state`+`detail`. Mantener `razonamiento`. El check "Similitud visual" sale `info`/sin número (lo llena C).
- **A4.2 — `triage.py` single-doc.** Si `tipo_objetivo`, render solo de ese template; salida JSON con `checks_llm[]` + (compat) `relevante/formato_ok/faltan/motivo/razonamiento`. Marcar claramente el check clave `es_el_tipo` (Identidad).
- **A4.3 — Parseo robusto** (regex+fallback) de `checks_llm[]`; default conservador si no parsea.
  - *Aceptación:* validando un doc real contra su tipo, devuelve checks de Identidad con `es_el_tipo=pass`; contra otro tipo, `es_el_tipo=fail`.

**A5 · Ensamblar `checks[]`**
- **A5.1 — `armar_checks(checks_llm, checks_regex) -> list[Check]`** (en `graph/nodes.py` o helper): mergea Identidad (LLM) + Completitud (regex `chequear_reglas` ∪ secciones/columnas del LLM). Dedup por `label`.
- **A5.2 — Pase por dimensión:** `dimension_pasa(checks, dim)` = sin `fail` en checks `requerido` de esa dimensión.
- **A5.3 — Volcar a estado y panel:** setear `state["checks"]`; mantener `documentos_panel` (agregar, si conviene, un resumen de checks).
  - *Aceptación:* `checks[]` final tiene ambas dimensiones; `dimension_pasa` refleja los `fail` requeridos.

**A6 · Router de veredicto**
- **A6.1 — `route_post_triage(state)`** en `graph/edges.py`: si `tipo_objetivo` (single-doc):
  - Identidad falla duro (`es_el_tipo=fail` / `bloqueante` / formato no soportado) → `"invalido"`.
  - Identidad pasa y Completitud tiene `fail` requerido (o baja confianza) → `"revision"`.
  - Ambas pasan → `"valido"`.
  - Sin `tipo_objetivo` → delega en el `route_triage` actual (modo entrega; intacto).
- **A6.2 — Nodo `requiere_decision_node`** (`graph/nodes.py`): setea `Status.REQUIERE_DECISION`, arma `resumen`/`respuesta` ("Identidad confirmada; falta el campo 'X'…").
- **A6.3 — Cableado del grafo** (`graph/graph.py`): tras `triage`, `add_conditional_edges` con `{valido: listo_para_revision, revision: requiere_decision, invalido: devolver_no_admisible, ...}` para single-doc; conservar las ramas del modo entrega.
  - *Aceptación:* los 3 caminos (valido/revision/invalido) terminan en el estado correcto con `resumen` poblado.

**A7 · Compat + verificación**
- **A7.1 — No romper entrega/Streamlit:** `documentos_panel`, `route_triage`, `INCOMPLETA` y los nodos existentes quedan operativos en modo entrega.
- **A7.2 — Smoke entrega:** `scripts/run_local.py` (modo entrega multi-doc) sigue verde.
- **A7.3 — Smoke single-doc:** nuevo `scripts/run_cotejar.py <archivo> --tipo-doc <id>` → imprime veredicto + checks por dimensión.
  - *Aceptación:* ambos smokes verdes; un doc correcto→`valido`, falta campo requerido→`revision_manual`, otro tipo→`invalido`.

## Fase B — Capa FastAPI (`api/`) + historial
Exponer el contrato §7 envolviendo funciones in-process. Sin lógica nueva de negocio (salvo historial).

- [ ] **B1 — App base.** `api/main.py` (FastAPI + CORS al dev server), `api/deps.py`, `api/schemas.py` (Pydantic de §7). `uv add fastapi uvicorn python-multipart`.
- [ ] **B2 — Validar.** `POST /api/validar` (multipart) → arma trigger (1 doc + meta), corre el grafo, mapea a la respuesta §7.1 (`status, veredicto, score, no_concluyente, maturity, cajetin_bbox, resumen, checks, documento_panel`). `thread_id` opcional (acumular).
- [ ] **B3 — Tipos (CRUD + captura).** `GET /api/tipos`, `GET /api/tipos/{id}`, `POST /api/tipos/capturar` (visión, ya existe), `PUT`, `DELETE`, `POST/DELETE /api/tipos/{id}/referencias` (Fase C completa refs; en B devuelve estructura base).
- [ ] **B4 — Catálogos.** `GET/PUT/DELETE /api/entregas-tipo`, `GET/POST/DELETE /api/disciplinas`, `GET /api/proyectos` (mapean a `tools/sheets.py` y `tools/disciplinas.py`).
- [ ] **B5 — Decisión humana.** `POST /api/casos/{thread_id}/decision` `{decision}` → setea estado del caso (persistir decisión).
- [ ] **B6 — Historial (SQLite).** Tabla `validaciones` (doc, template, veredicto, score, operador, fecha, promovido_a_ref). `GET /api/historial`. Registrar en cada `/api/validar`.
  - *Aceptación:* `uvicorn api.main:app` arriba; `POST /api/validar` con un PDF devuelve el JSON §7.1; CRUD de tipos/catálogos andando; cada validación queda en historial.

## Fase C — Similitud por embeddings + referencias + madurez + promoción
Las extensiones §3. Requiere el modelo local.

- [ ] **C1 — Proveedor de embeddings.** `ai_agents/similarity.py`: interfaz pluggable (`EMBED_PROVIDER`, `EMBED_MODEL`); impl local SigLIP/CLIP. `uv add` (open-clip-torch / transformers + torch). Embebe **imagen** (página y recorte de cajetín).
- [ ] **C2 — Bbox del cajetín.** Localización vía LLM de visión → `cajetin_bbox` (coords relativas). Recortar la región para embeber (mejor señal).
- [ ] **C3 — Sidecar de referencias.** `knowledge/refs/<id>/index.json` + ref files + embeddings persistidos. Helpers en `tools/refs.py` (no tocar `cargar_tipos`).
- [ ] **C4 — Score.** Coseno candidato vs refs → `top_k_mean` (k=`SIM_TOPK`), normalizado `[0,100]`; combinar cajetín 0.7 / página 0.3 (`SIM_WEIGHT_*`). Umbrales `APPROVAL_THRESHOLD=96`, `REVISION_THRESHOLD=85`.
- [ ] **C5 — Madurez.** Derivada de nº refs (`CALIBRATING_MIN=2`, `CALIBRATED_MIN=5`) → `solo_reglas|calibrando|calibrado`. Gating: solo_reglas→score `null`+`no_concluyente`; calibrando→blando; calibrado→duro. Exponer `refs_count, maturity, referencias[]` en `GET /api/tipos`.
- [ ] **C6 — Integrar al veredicto.** El score entra al router de Fase A (calibrado: `score<REVISION`→inválido, banda→decisión, `≥APPROVAL`→válido). El check de Identidad "Similitud visual" muestra número o `info` según madurez.
- [ ] **C7 — Promoción.** `POST /api/tipos/{id}/referencias/promover` (guarda dura: solo caso `approved`) → copia doc, embebe, agrega a `index.json` `origin="promovido"`, recalcula madurez. `GET /api/historial` marca `promovido_a_ref`.
  - *Aceptación:* template calibrado → score real + bbox; solo-reglas → info/no concluyente; promoción bloqueada sin aprobación; al promover sube la madurez.

## Fase D — Frontend React + TypeScript
3 pantallas del diseño *Cotejar*, cableadas a la API real. **Fuente de diseño:** `docs/spec/design_handoff_cotejar/README.md` (Design Tokens, screens, componentes, state) + `Cotejar.dc.html` (prototipo a recrear, no copiar).

- [ ] **D1 — Scaffold.** `frontend/` Vite + React + TS; `src/api/` (cliente tipado contra §7), `src/design/tokens.ts` (paleta/tipografía/radios del handoff), IBM Plex Sans/Mono (Google Fonts), `VITE_API_BASE`.
- [ ] **D2 — Shell.** Sidebar 236px `#0A363C` (marca Cotejar + nav FLUJO/ADMINISTRACIÓN + pie "Pendientes 23" + avatar) + main scrolleable; header sticky `blur(8px)`; `max-width:1180px`; íconos lucide (shield-check, layers, clock, file-text, upload, download, trash, pencil, eye, plus, check, x, alert-triangle, chevron-down); animación `ct-fade` solo `translateY` (nunca `opacity:0` inicial).
- [ ] **D3 — Validar documento.** Máquina `upload→processing→result`: dropzone + select de template (tipo·empresa·madurez), pasos de processing, banner de veredicto (3 estados), `checks` por dimensión, score grande (mono), preview con **recuadro del cajetín** (`cajetin_bbox`), acciones Descargar/Rechazar/Aprobar → panel de promoción.
- [ ] **D4 — Templates de referencia.** Tabla con badge de madurez ↔ detalle (calibración, galería de refs con tag Inicial/Promovido, reglas editables) + modal "Nuevo template" (captura→editar→guardar).
- [ ] **D5 — Historial y auditoría.** Strip de 4 métricas + tabla con chips de veredicto y tag `↑ ref`.
- [ ] **D6 — Cableado real.** Sin mocks; los 3 flujos contra la API. Estados vacíos guiados; responsivo.
  - *Aceptación:* los criterios §10.1 de la spec (validar calibrado/solo-reglas, ámbar→aprobar→promoción, CRUD completo, historial).

---

## Config nueva (.env)
`EMBED_PROVIDER`, `EMBED_MODEL`, `APPROVAL_THRESHOLD=96`, `REVISION_THRESHOLD=85`, `CALIBRATING_MIN=2`, `CALIBRATED_MIN=5`, `SIM_WEIGHT_CAJETIN=0.7`, `SIM_WEIGHT_PAGINA=0.3`, `SIM_TOPK=3`.

## Guardas (no romper)
- Score **siempre por embeddings**, nunca del LLM. Bbox por visión = localización (ok).
- Promoción **solo con aprobación humana**.
- Cajetín **tolerante**: reglas regex determinísticas; lo cualitativo va en `razonamiento`/confianza, no en `fail` falsos.
- IO en `tools/`, proveedores (`LLM_PROVIDER`, `EMBED_PROVIDER`) pluggables.
- `INCOMPLETA` multi-doc y vista de "entrega": fuera de alcance de UI (capacidad backend disponible).

## Dependencias entre fases
A → B (B usa los checks/veredicto de A). C extiende A (score en el router) y B (endpoints refs/promover). D depende de B (API); el handoff de UI **ya está disponible**. **Ruta crítica recomendada: A → B → C → D.**
