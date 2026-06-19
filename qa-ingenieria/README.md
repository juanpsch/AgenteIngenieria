# Cotejar — QA-Ingeniería

**Gate de admisión documental para ingeniería.** Cuando llega documentación (un plano, una
hoja de datos, una memoria de cálculo, un esquemático…), Cotejar responde tres preguntas antes
de que un humano pierda tiempo con ella:

1. **Identidad** — ¿el documento *es* el tipo que dice ser? (empresa, tipo, cajetín/rótulo)
2. **Completitud** — ¿están los campos y secciones obligatorios?
3. **Veredicto** — 🟢 válido · 🟡 revisión manual (decide un humano) · 🔴 inválido.

El gate **nunca aprueba solo**: produce evidencia (checks por dimensión + un score de similitud)
y la decisión final la firma una persona. Los documentos aprobados se pueden **promover** a
ejemplos de referencia, que calibran el tipo y mejoran el cotejo siguiente.

Un documento **admitido** continúa (opcional, con toggle) a la **revisión de contenido** (Fase 1): un
segundo nodo que mide calidad/cumplimiento por *tiers* (lo mecánico se mide, lo semántico con reglas, lo
difuso al VLM) y produce su propio veredicto — **aprobado / con notas / observado / rechazado** — con
hallazgos que citan la norma. Hoy: **Tier 1** (legibilidad + presencia) + **Tier 2** (reglas + **catálogo
de normas** reutilizable que los templates referencian: AEA 90364, CIRSOC 201; el vínculo doc↔norma se
detecta por anclas y cada hallazgo cita `norma_ref`). Ver [docs/spec/SPEC_Cotejar_Fase1_Revision.md](docs/spec/SPEC_Cotejar_Fase1_Revision.md).

---

## Dos modos

El mismo grafo atiende dos flujos según el estado del caso:

| Modo | Disparador | Qué hace |
|------|-----------|----------|
| **Cotejo (single-doc)** | `tipo_objetivo` seteado | Valida **1 documento** contra el **template** del tipo elegido. Es lo que usa la web. |
| **Entrega (multi-doc)** | sin `tipo_objetivo` | Clasifica y valida **un paquete** de documentos contra un *tipo de entrega* (Plano + Lista + Memoria…). Flujo original Fase 0. |

> Un cotejo single-doc es una entrega degenerada de un solo tipo de documento.

---

## Stack e infraestructura

- **Python 3.12** gestionado con **[uv](https://docs.astral.sh/uv/)** (no Anaconda).
- **LangGraph** — `StateGraph` con checkpointer SQLite local (estado de cada caso por `thread_id`).
- **OpenAI Agents SDK** con **proveedor LLM configurable** (`LLM_PROVIDER=openai|claude`, vía LiteLLM para no-OpenAI).
- **FastAPI** + **uvicorn** — API HTTP (contrato §7 del spec).
- **React 18 + TypeScript + Vite** — frontend web (3 pantallas).
- **CLIP local** (`open-clip-torch`) — embeddings de imagen para el score de similitud (Fase C).
  Carga **offline** desde la cache (sin pingear la red); degrada con gracia si no está.
- **PyMuPDF** — además de leer/renderizar, ubica texto por **cajas de palabras** (zonas ancladas a texto).
- **OCR opcional** (`tesseract` local, vía `pytesseract`) — recupera texto que vive solo en la imagen
  (escaneos/cajetines rasterizados) para extracción determinista y para la legibilidad de la revisión.
  Degrada con gracia si no está instalado. Ver `OCR_*` en `.env.example`.
- **Streamlit** — sandbox de "mesa de entrada" para probar el agente sin web ni mails.
- Lectura de documentos: PyMuPDF / pdfplumber / openpyxl / python-docx / ezdxf (+ visión LLM).

Todo corre **local**. Sin mails reales, sin nube, sin secretos en el repo (`.env` está gitignored).

---

## Estructura del proyecto

```
qa-ingenieria/
├── ai_agents/         # Agentes LLM (sin estado): parser, triage/cotejo, extractor de templates,
│   │                  # similarity (embeddings CLIP), provider (LLM configurable), util
├── graph/             # El grafo: state (CasoState + Status + helpers), nodes, edges (routers), graph
├── tools/             # IO y dominio: docs (lectura), tipos (templates YAML + zonas), refs (ejemplos+embeddings),
│   │                  # reglas (validación determinista), layout (zonas por texto), sheets/disciplinas, email
│   │                  # (fakes)
├── api/               # FastAPI: main (endpoints §7), historial (SQLite de auditoría), schemas (Pydantic)
├── frontend/          # React + Vite (Validar / Templates / Historial)
├── sandbox/           # Streamlit + fakes para probar el flujo localmente
├── knowledge/         # Datos: tipos/*.yaml (templates), refs/<tipo>/ (ejemplos+embeddings), disciplinas.json
├── scripts/           # Runners de smoke (run_local, run_cotejar, probe_api…)
├── docs/              # spec, plan, handoff, ARCHITECTURE.md, QA_GLOBAL.md
└── local_state/       # SQLite (checkpointer + historial). Gitignored.
```

Ver **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** para el detalle de arquitectura y el contrato de la API,
y **[docs/REVISION_UI.md](docs/REVISION_UI.md)** para la guía del flujo de revisión de contenido en la pantalla.

---

## Puesta en marcha

### 1. Backend (Python + uv)

```bash
cd qa-ingenieria
uv sync                      # crea el venv e instala deps (incluye torch/open-clip para embeddings)
cp .env.example .env         # completá OPENAI_API_KEY o ANTHROPIC_API_KEY según LLM_PROVIDER
```

> **Modelo de embeddings:** la primera vez hay que descargar los pesos del CLIP (~600 MB) — corré
> una vez con `EMBED_ALLOW_DOWNLOAD=1` (o simplemente validá/agregá una referencia con conexión).
> Después carga **offline** desde la cache (sin pingear la red, así no se cuelga) y la API lo
> **precalienta** al arrancar. Si el modelo no está, el cotejo sigue por reglas (score "no concluyente").

### 2. API

```bash
uv run uvicorn api.main:app --reload --port 8000
# Swagger: http://127.0.0.1:8000/docs   (la raíz / redirige ahí)
```

### 3. Frontend web

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173  (proxya /api -> http://127.0.0.1:8000)
```

Para apuntar a otra API: `VITE_API_BASE=http://host:puerto npm run dev`.

### 4. Sandbox Streamlit (opcional, sin web)

```bash
uv run streamlit run sandbox/ui_intake.py
```

---

## Modo de uso (web)

1. **Validar documento** — subí un PDF/imagen, elegí el template y dale *Validar*. El resultado es
   **observable** (para confiar y decidir): el **veredicto**, el **desglose del score** (escala con
   bandas y umbrales, componentes zona/página, y la **referencia más parecida**), los **checks por
   dimensión** con el valor encontrado en cada regla, el **preview** del documento (clic = ampliar,
   con la zona de identidad resaltada), una explicación de *cómo se compara*, y 3 vistas del desglose
   (**Dividida / Tarjetas / Compacta**). La decisión (Aprobar / Rechazar) la tomás vos; al aprobar
   podés **promover** el documento a referencia para calibrar el tipo.

2. **Templates de referencia** — definí tipos de documento, sus zonas y reglas. Podés:
   - **Crear** un template *desde uno o **varios** ejemplos* (o una especificación): el capturador
     propone características, la zona de identidad y reglas. Con **varios ejemplos** las reglas se
     **consolidan** (generalizan) y se muestra la **cobertura** de cada regla (cuántos ejemplos
     cumple cada patrón) — las que no cumplen todos conviene revisarlas.
   - **Editor visual de zonas** — dibujá/mové/redimensioná regiones sobre una referencia
     (multipágina), marcá la de **identidad**, atá un **campo + regla**, o anclalas a **texto**.
   - **Galería de referencias** con miniaturas y preview; **agregar/quitar** ejemplos (calibración).
     La **madurez** (solo_reglas → calibrando → calibrado) sube con la cantidad de ejemplos.
   - **Editar el YAML** del template (avanzado).

3. **Historial y auditoría** — métricas (validados, % de admisión, pendientes, promovidos) y la
   lista de validaciones con su veredicto y score.

> Un **indicador de actividad** colapsable (abajo-derecha) muestra qué está haciendo el sistema en
> las operaciones que tardan (calcular embeddings, re-calibrar, capturar) y un historial de pasos.

---

## Calibración y score (cómo madura un template)

| Madurez | Referencias | Score de similitud |
|---------|-------------|--------------------|
| `solo_reglas` | `< CALIBRATING_MIN` (def. 2) | No se calcula (no concluyente). Cotejo por reglas + LLM. |
| `calibrando` | `[2, 5)` | **Informativo** (se muestra, no decide). |
| `calibrado` | `>= CALIBRATED_MIN` (def. 5) | **Decide** el veredicto del score. |

**El score** pondera la **zona de identidad** del template (encabezado o rótulo, según el tipo) y la
**página** completa (`SIM_WEIGHT_CAJETIN`/`SIM_WEIGHT_PAGINA`, def. 0.7/0.3). Cuando el template está
**calibrado**, los **umbrales se auto-estiman** de la distribución de scores de sus propios ejemplos
(media−1σ para aprobar, media−2.5σ para revisar); `APPROVAL_THRESHOLD`/`REVISION_THRESHOLD` son el fallback.

### Zonas y reglas deterministas

Cada template define **zonas** gráficas (`zonas` en el YAML), dibujables **visualmente** (mover/
redimensionar, **multipágina**) en *Templates → editor de zonas*. Una zona marcada **identidad**
alimenta el score visual (no se asume el pie: en una hoja de datos suele ser el **encabezado**).
A una zona se le ata un **campo** con una **regla determinista**:

- `regex` — el valor extraído debe cumplir un patrón.
- `filename` — el **código** del documento debe coincidir con el nombre de archivo (señal de identidad).
- `presencia` — el campo debe estar.

El **LLM solo extrae** los valores; la validación es **determinista** (sin LLM): predecible y auditable.
El **capturador** propone la zona de identidad (por visión) y reglas/anclas; el humano las ajusta.

**Robustez a desvíos de posición entre documentos** (dos mecanismos complementarios):

- **Padding** (`SIM_ZONE_PAD`, def. 0.05): el recorte agrega un margen idéntico en candidato y
  referencias, así un corrimiento chico sigue cayendo en la ventana.
- **Anclas a texto** (`ancla_inicio` / `ancla_fin`, regex): la zona se ubica por las **palabras** del
  documento (cajas de PyMuPDF) y **sigue al contenido** aunque cambie de lugar; cae al recuadro fijo
  si el PDF no tiene texto o no se encuentran las anclas.

---

## QA y verificación

Estado de QA, lo que se probó end-to-end y las limitaciones conocidas: **[docs/QA_GLOBAL.md](docs/QA_GLOBAL.md)**.

- Tests: `uv run pytest` (suite del core: scoring, dedup de checks, routers, similarity, API).
- Backend: `uv run python scripts/run_cotejar.py <archivo> --tipo-doc <tipo>` (cotejo single-doc).
- Backend: `uv run python scripts/run_local.py <doc1> <doc2> --tipo-entrega <t> …` (entrega multi-doc).
- Frontend: `npm run typecheck` y `npm run build` (en `frontend/`).
