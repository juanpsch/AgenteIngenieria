# Handoff — Backend QA-Ingeniería (Fase 0)

Documento para **integrar este backend con un frontend** diseñado aparte y armar la app completa.
Describe qué hace, su modelo de datos, sus funciones públicas y el **contrato de API** que el frontend debe consumir.

> Estado: **Fase 0 completa y validada** — *admisión de documentos* (clasificar tipo, validar formato/cajetín, completitud de la entrega) con explicabilidad. La *revisión de contenido* (hallazgos técnicos), HITL y la infra real (email/Neon/Vercel) son fases siguientes (§9).

---

## 1. Qué hace (en una línea)
Recibe una **entrega** (uno o varios documentos de ingeniería), **clasifica cada documento** contra templates por tipo, valida **formato/cajetín** y **completitud** contra lo que la entrega requiere, y emite un **dictamen** (admisible / incompleta / no admisible / faltan datos) **con el razonamiento** de cada decisión.

## 2. Stack
- **Python 3.12**, gestionado con **uv** (venv + lockfile).
- **LangGraph** (StateGraph + checkpointer) — orquestación del flujo.
- Checkpointer **SQLite local** (`DB_MODE=local`); en producción migra a Postgres/Neon (`DB_MODE=neon`, pendiente).
- **OpenAI Agents SDK** como runner; **proveedor LLM configurable** (`LLM_PROVIDER=openai|claude` vía LiteLLM).
- Lectura de documentos: **PyMuPDF** (texto + render de páginas) · **pdfplumber** (tablas) · **openpyxl/python-docx** (Office) · **ezdxf/ODA** (CAD) · visión sobre páginas renderizadas.
- UI actual de prueba: **Streamlit** (`sandbox/ui_intake.py`) — se reemplaza/o convive con el frontend nuevo.

## 3. Mapa de módulos
| Archivo | Responsabilidad | Funciones públicas clave |
|---|---|---|
| `graph/state.py` | Estado del caso + enum `Status` | `CasoState`, `Status`, `initial_state()` |
| `graph/nodes.py` | Nodos del flujo (puros `state→updates`) | `parser_node`, `validacion_node`, `triage_node`, `pedir_datos_node`, `reclamar_faltantes_node`, `devolver_no_admisible_node`, `listo_para_revision_node` |
| `graph/edges.py` | Routers condicionales | `route_entry`, `route_validation`, `route_triage` |
| `graph/graph.py` | Ensamblado + checkpointer | `build_graph(checkpointer)`, `get_compiled_graph()` |
| `ai_agents/provider.py` | Proveedor LLM configurable | `build_agent()`, `build_model()` |
| `ai_agents/parser.py` | Extrae datos de la entrega del trigger | `parse_trigger(texto, filenames)` |
| `ai_agents/triage.py` | Admisibilidad + completitud (núcleo) | `run_triage(tipo_entrega, disciplina, proyecto, documentos, requeridos)` |
| `ai_agents/tipo_extractor.py` | Capturar template desde un ejemplo | `proponer_template(filename, contenido, imagenes, tid_hint, nom_hint)` |
| `ai_agents/util.py` | Runner + parseo JSON robusto + visión | `run_agent`, `extract_json`, `build_input`, `load_prompt` |
| `tools/docs.py` | Lectura híbrida de documentos | `read_document(path)`, `render_pdf_images(path, max_pages, dpi)` |
| `tools/email.py` | Armado del estado inicial (+ envíos fake) | `build_trigger_state(files, meta)`, `enviar_emisor/senior/dueno` |
| `tools/sheets.py` | Catálogo de entregas (fixture local) | `leer_catalogo`, `tipos_entrega`, `entregas_detalle`, `guardar_tipo_entrega`, `eliminar_tipo_entrega` |
| `tools/tipos.py` | Tipos de documento (templates) | `cargar_tipos`, `template_de`, `render_template`, `to_yaml`, `guardar_template`, `eliminar_tipo`, `slug` |
| `tools/disciplinas.py` | Catálogo de disciplinas | `cargar_disciplinas`, `guardar_disciplinas`, `agregar_disciplina`, `eliminar_disciplina` |
| `tools/db.py` | Checkpointer (SQLite local / Neon) | `get_checkpointer()` |
| `prompts/*.txt` | Instrucciones de los agentes | parser, triage, tipo_extractor |
| `knowledge/` | **Fuente de verdad de configuración** (ver §5) | — |

## 4. Modelo de datos

### 4.1 Estado del caso (`CasoState`)
```
thread_id, trigger_text, tipo_entrega, disciplina, proyecto, revision, emisor, norma_ref,
documentos: [Documento], nuevos_archivos: [Documento], entrega_completa: bool,
admisibilidad: {es_admisible, completa, faltantes[], irrelevantes[], motivo},
faltan_minimos[], rebotes_admisibilidad, ronda, status,
ref_thread_id, respuesta, documentos_panel: [card], acciones[]
```
`Documento` = `{tipo_doc, filename, path, presente, legible, contenido, imagenes[], formato_ok, relevante, faltan[], motivo, razonamiento}`

`Status`: `RECIBIDO · FALTAN_DATOS · EN_TRIAGE · INCOMPLETA · NO_ADMISIBLE · EN_REVISION` (+ placeholders Fase 1+: `ESPERANDO_APROBACION_SENIOR, OBSERVADO, APROBADO, APROBADO_CON_NOTAS, RECHAZADO`).

### 4.2 Template de tipo de documento (`knowledge/tipos/<id>.yaml`)
```yaml
tipo_doc: <id == nombre de archivo>
nombre: <legible>
disciplinas: [..]
formatos_archivo: [pdf, xlsx, dwg, ...]
cajetin: { requerido: bool, campos_requeridos: [..], logo_empresa: bool }
secciones_requeridas: [..]
columnas_requeridas: [..]
caracteristicas: [..]            # reglas concretas verificables
nomenclatura: <patrón orientativo>
bloqueante: [..]                 # condiciones que tiran a NO_ADMISIBLE
senales_reconocimiento: <prosa>  # cómo clasificarlo
criterios_aceptacion: <prosa>
no_corresponde: <prosa>
```
> Invariante: el **id del tipo = nombre del archivo** (`cargar_tipos` lo normaliza). Ver/editar/borrar usan ese id.

### 4.3 Catálogo de entregas (`knowledge/catalogo.json`)
```json
{
  "proyectos": { "P-102": { "nombre": "...", "entregas": { "<tipo_entrega>": { "documentos_requeridos": ["<tipo_doc>"], "estado": "pendiente" } } } },
  "_default_por_tipo_entrega": { "<tipo_entrega>": ["<tipo_doc>", ...] }
}
```
Una **entrega** = un `tipo_entrega` que **requiere** una lista de `tipo_doc`. `leer_catalogo(proyecto, tipo_entrega)` resuelve los requeridos (proyecto primero, luego default).

### 4.4 Disciplinas (`knowledge/disciplinas.json`)
Lista de strings editable.

## 5. Configuración (fuente de verdad = archivos)
- `knowledge/tipos/*.yaml` — tipos de documento.
- `knowledge/catalogo.json` — entregas (qué tipos requiere cada una) por proyecto + defaults.
- `knowledge/disciplinas.json` — disciplinas.
- `.env` — `LLM_PROVIDER`, `LLM_MODEL`, `LLM_MODEL_FAST`, `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, `DB_MODE`, `LOCAL_DB_PATH`, `ODA_CONVERTER_PATH`.

## 6. Flujo del agente
```
trigger (archivos + meta) → build_trigger_state → grafo:
  parser (lee docs + clasifica metadata)
   → validación de datos mínimos (adjunto + tipo_entrega + disciplina)
        faltan → FALTAN_DATOS (pide al emisor)
   → triage (clasifica cada doc contra su template; valida formato/cajetín/completitud)
        irrelevante / formato malo → NO_ADMISIBLE (devuelve con detalle)
        faltan requeridos          → INCOMPLETA (reclama; acumula reenvíos)
        completa + admisible       → EN_REVISION (listo para Fase 1)
```
El triage emite, por documento: `tipo_doc, relevante, formato_ok, faltan[], motivo, razonamiento` (explicabilidad).

## 7. Contrato de integración (lo que el frontend consume)

### 7.1 Hoy (in-process, Python)
- Procesar: `state = build_trigger_state(files, meta)` → `graph = get_compiled_graph()` → `graph.invoke(state, {"configurable": {"thread_id": state["thread_id"]}})` → devuelve `CasoState` (con `status`, `admisibilidad`, `documentos_panel`, `respuesta`).
- Config (CRUD) vía las funciones de `tools/tipos.py`, `tools/sheets.py`, `tools/disciplinas.py`, y captura con `ai_agents/tipo_extractor.proponer_template`.

### 7.2 API HTTP propuesta (a implementar al unir con el frontend)
Capa fina **FastAPI** que envuelve las funciones de arriba. Contrato sugerido:

**Procesar entrega**
- `POST /api/entregas/procesar` (multipart): `files[]`, `proyecto`, `tipo_entrega`, `disciplina`, `texto`
  → `{ status, tipo_entrega, disciplina, proyecto, admisibilidad{es_admisible, completa, faltantes[], irrelevantes[], motivo}, respuesta, documentos:[{filename, tipo_doc, relevante, formato_ok, faltan[], motivo, razonamiento}] }`

**Tipos de documento**
- `GET /api/tipos` → `[{tipo_doc, nombre, ...template}]`
- `GET /api/tipos/{id}` → template
- `POST /api/tipos/capturar` (multipart `file`, `tipo_doc?`, `nombre?`) → template propuesto (para revisar/editar)
- `PUT /api/tipos/{id}` (body: YAML o JSON del template) → guarda
- `DELETE /api/tipos/{id}`

**Tipos de entrega**
- `GET /api/entregas-tipo` → `{ "<tipo_entrega>": ["<tipo_doc>"] }`
- `PUT /api/entregas-tipo/{id}` (body: `documentos_requeridos[]`) → crea/edita
- `DELETE /api/entregas-tipo/{id}`

**Disciplinas**
- `GET /api/disciplinas` · `POST /api/disciplinas` (`{nombre}`) · `DELETE /api/disciplinas/{nombre}`

**Proyectos (lectura)**
- `GET /api/proyectos` → del catálogo.

> Notas de contrato: el `documentos_panel` que hoy arma el backend ya viene "listo para tarjetas" (`{titulo, datos:[{clave,valor}], calidad, fuera_de_criterio, motivo, razonamiento}`) — el frontend puede usar ese shape o el crudo `documentos[]`. Procesar es **stateless por request** (cada request crea su `thread_id`); para el ciclo ida-y-vuelta multi-turno se reutiliza el `thread_id` (ver §8).

## 8. Notas para el frontend
- **Multi-documento / ida y vuelta:** una entrega puede completarse en varios envíos. El backend **acumula** documentos por `thread_id`. Para soportarlo, el frontend debe poder mandar un `thread_id` existente (a exponer en el endpoint de procesar) o tratar cada envío como caso nuevo (Fase 0 simple).
- **Explicabilidad:** mostrar `razonamiento` por documento (por qué se clasificó/aceptó/rechazó) y `admisibilidad.motivo` global.
- **Estados → UI:** `EN_REVISION`=verde, `INCOMPLETA`=amarillo (mostrar `faltantes`), `NO_ADMISIBLE`=rojo (mostrar detalle por doc), `FALTAN_DATOS`=info.
- **Gestión (config):** el frontend de administración (tipos/entregas/disciplinas) mapea 1:1 a los endpoints de §7.2.

## 9. Qué falta (roadmap)
- **Fase 1:** revisión de contenido (extractor + revisor → hallazgos con severidad).
- **Fase 2:** HITL (aprobación senior) + informe (Doc/PDF) + write-back a Sheet.
- **Fase 3:** respuestas/ciclo de corrección (clasificador).
- **Fase 4:** infra real (Resend/Svix inbound, Neon, Drive/Sheets, Vercel, cron) — hoy fakeada.
- **Capa API HTTP (§7.2):** no existe aún; es el primer paso para unir con el frontend.

## 10. Cómo correr (hoy)
- Setup: `uv sync` (Python 3.12). Key en `.env`.
- UI de prueba: `uv run streamlit run sandbox/ui_intake.py`.
- Smoke CLI: `uv run python scripts/run_local.py <archivos> --tipo-entrega <id> --proyecto P-102 --disciplina <d>`.

## 11. Decisiones de diseño (para no romperlas)
- **Config en archivos** (`knowledge/`), no en código: tipos, entregas, disciplinas editables.
- **Tipos de primera clase + captura desde ejemplo** (con visión).
- **Chequeo texto + visión** simétrico entre captura y validación.
- **Cajetín tolerante:** válido si presente e identifica el doc; campos secundarios = observación, no bloquean (verificación campo-por-campo estricta con LLM es frágil).
- **Proveedor LLM configurable** y **IO en `tools/`** (sandbox-able / testeable).
- **Explicabilidad**: cada veredicto trae `razonamiento`.
