# Plan de implementación — Agente QA-Ingeniería

Construcción **por fases, sandbox-first y local-first**. La idea: validar **el agente** (que razone bien sobre documentos reales) en un sandbox 100% local, antes de cablear nada de la arquitectura real (email, webhook, Neon, Vercel). El cableado de infra real es la **última** fase, no la primera.

> Convención sandbox-able (clave para que esto funcione): todo IO (email, drive, db, sheets) vive en callables module-level en `tools/`, con implementación **real y fake** intercambiable por toggle; los nodos nunca llaman SDKs inline. Un único `build_trigger_state` arma el estado inicial — desde un email (infra real) **o desde archivos subidos** (sandbox). El sandbox espeja esa misma función.

---

## Stack (Fase 0–3, local)

| Capa | Elección | Notas |
|---|---|---|
| Entorno / deps | **uv** | instala y fija el Python, venv, lockfile (`uv python install 3.12`, `uv venv`, `uv add`) |
| Python | **3.12** | estable, mejor soporte de libs CAD/PDF |
| Orquestación + estado | **LangGraph** (StateGraph + checkpointer) | patrón del template |
| Checkpointer local | **SQLite** (`langgraph-checkpoint-sqlite`) | toggle `DB_MODE=local\|neon`; mismo patrón que Neon en prod |
| Runner de agentes | **OpenAI Agents SDK** (Agent + Runner) | del template |
| Proveedor LLM | **configurable** (`ai_agents/provider.py`) | OpenAI directo o Claude/otros vía LiteLLM, por env var; arranca con uno |
| Lectura PDF | **PyMuPDF** (texto + render de páginas) + **pdfplumber** (tablas) | self-contained en Windows |
| Visión | modelo multimodal del proveedor sobre páginas renderizadas | híbrido: texto donde se puede, visión para planos/imágenes |
| Office | **openpyxl** (xlsx) + **python-docx** (docx) | lista de materiales como planilla |
| CAD | **ezdxf** (DXF nativo) + **ezdxf.addons.odafc** + **ODA File Converter** (binario externo) para DWG | DWG→DXF automático |
| Sandbox | **agent-sandbox** + extensión de upload | chat local con subida de archivos |
| Email / Drive / Sheets | **fakes en memoria** en `tools/` | infra real diferida a Fase 4 |

**Prerrequisito de sistema (Fase 0):** instalar **ODA File Converter** (descarga gratuita de Open Design Alliance) para leer DWG; `ezdxf.addons.odafc` lo invoca. Si no está instalado, el agente degrada con gracia (loguea que no puede leer el DWG y lo trata como faltante/no legible).

---

## Fase 0 — Sandbox local (validar el agente)  ← **empezamos acá**
Objetivo: probar el razonamiento del agente (parser + validación + triage) sobre **archivos reales que subís**, sin mails, sin Neon, sin Vercel. Todo local. OpenAI real; email/Drive/Sheets fakeados.

- [ ] **Datos** — `graph/state.py`: estado del caso (`tipo_entrega`, `disciplina`, `proyecto`, `revision`, `emisor`, `documentos[]`, `entrega_completa`, `admisibilidad`, `rebotes_admisibilidad`, `status`). Status hasta `EN_TRIAGE / INCOMPLETA / NO_ADMISIBLE`.
- [ ] **DB local** — checkpointer apuntando a **SQLite/Postgres local** (no Neon); los casos persisten entre reinicios del sandbox.
- [ ] **Knowledge** — `knowledge/entrega_<tipo>.md`: por tipo de entrega, qué documentos requiere + formato esperado (semilla: ej. "fabricación" = Plano + Lista de materiales).
- [ ] **Tools (fake)** — `tools/email.py`, `tools/sheets.py`, `tools/drive.py` con implementación **fake en memoria** (el catálogo de entregas sale de un fixture local; los envíos se loguean en el chat, no se mandan).
- [ ] **Entrada local** — `build_trigger_state` que arma el estado desde **archivos subidos** (nombre + bytes + metadata del chat), no desde un email.
- [ ] **Agentes** — `ai_agents/parser.py` + `prompts/parser.txt`: extrae `tipo_entrega`, `disciplina`, `proyecto`, `revision`, lista documentos. JSON con regex + fallback.
- [ ] **Agentes** — `ai_agents/triage.py` + `prompts/triage.txt`: resuelve el conjunto requerido y evalúa completitud + tipo/relevancia + formato sobre los archivos subidos. Salida `{es_admisible, completa, faltantes[], irrelevantes[], documentos[], motivo}`.
- [ ] **Grafo** — `graph/nodes.py`: `parser`, `validacion_datos_minimos`, `triage`, `pedir_datos`, `reclamar_faltantes`, `devolver_no_admisible`. `graph/edges.py`: routers de validación y de triage.
- [ ] **Grafo** — `graph/graph.py`: ensamblado + checkpointer local + entrada condicional.
- [ ] **Borde** — contador `rebotes_admisibilidad`: 2 rebotes silenciosos, al 3º "notifica al dueño" (en el sandbox = log).
- [ ] **Sandbox UI** — chat local con **subida de archivos** + toggles real/fake por dependencia/nodo; manifest que espeja `build_trigger_state`. Levantar y conversar.
- [ ] **Validar** — correr a mano los escenarios sobre archivos reales: entrega completa, entrega incompleta (Plano sin Lista), archivo irrelevante, sin tipo de entrega. Ajustar prompts hasta que el triage dictamine bien.

**Resultado Fase 0:** subís archivos en un chat local y el agente responde "completa y admisible / faltan estos documentos / esto no corresponde", con su DB local. Validado el agente, no la arquitectura.

## Fase 1 — Revisión de contenido (extractor + revisor) — aún en el sandbox
- [ ] `ai_agents/extractor.py` + prompt: lee cada documento, extrae secciones/datos con `confidence` por ítem.
- [ ] `knowledge/checklist_<disciplina>.md`: checklists por disciplina.
- [ ] `ai_agents/revisor.py` + prompt: checklist + hallazgos libres → Markdown; severidad Bloqueante/No bloqueante.
- [ ] Nodos `extractor`, `revisor`; router por severidad. Estado `EN_REVISION`.
- [ ] Baja confianza marcada para resaltar al senior. Validar en el sandbox sobre archivos reales.

## Fase 2 — HITL senior + documento (aún sandbox, envíos fake)
- [ ] Aprobación previa siempre: nodo que "envía" al senior (fake = log/chat) con `[REF:thread_id]`, bloqueantes/baja confianza resaltados; espera OK/edición. Estado `ESPERANDO_APROBACION_SENIOR`.
- [ ] `tools/drive.py`: informe Markdown → Doc/PDF (en sandbox, generación local del documento; formato/logo en try/except).
- [ ] `tools/sheets.py` (fake): write-back de hallazgos al "Sheet" en memoria.
- [ ] Estados `OBSERVADO / APROBADO_CON_NOTAS / APROBADO / RECHAZADO`.

## Fase 3 — Respuestas + ciclo de corrección (sandbox)
- [ ] `ai_agents/clasificador.py` + prompt: `correccion_reenviada`, `pregunta`, `no_acuerda`, `aprobacion_senior`, `rechazo_senior`, `desconoce_corta`.
- [ ] Entrada condicional por `[REF:thread_id]` → clasificador.
- [ ] Ciclo: corrección reenviada → re-triage (ronda+1) → re-revisión.
- [ ] Borde: "no acuerda" (observación o triage) → escala senior; "desconoce/corta" → avisa dueño y detiene.

## Fase 4 — Cablear arquitectura real  ← **"eso lo hacemos dps"**
Recién acá se reemplazan los fakes por la infra real, un toggle por vez.

- [ ] `tools/email.py` real — Resend send + verificación Svix sobre body crudo + From con nombre/Reply-To + descarga inbound `GET /emails/receiving/{id}`.
- [ ] `tools/db.py` real — pool Neon persistente (singleton, `prepare_threshold=None`, autocommit). Migrar el checkpointer de local a Neon.
- [ ] `tools/sheets.py` / `tools/drive.py` real — Google Sheets (read catálogo + write-back) y Drive/Docs reales.
- [ ] `server/main.py` — webhook (ack 200 + background), filtro por `to`, `/assets/logo.png`.
- [ ] `vercel.json` — `builds` + `routes` con `api/index.py`; `.gitignore` con secretos.
- [ ] `/cron/*` con `CRON_SECRET`: umbrales por etapa (aprobación senior en horas; corrección del emisor en días).
- [ ] Config por tenant: identidad/logo/remitente/dominio inbound, senior aprobador, umbrales, `DRIVE_ROOT`, `SHEET_MAESTRO_ID`.

## Fase 5 — Deploy + smoke
- [ ] Deploy Vercel; inbound en Resend (subdominio + filtro `to`).
- [ ] Smoke end-to-end por camino (completa, incompleta, no admisible, bloqueante+ciclo).
- [ ] Limpieza de datos de prueba antes de producción.

---

## Detalle de tareas — Fase 0 y Fase 1

Tareas granulares, en orden de dependencia. Cada una con archivo(s) y **criterio de aceptación** (cómo sé que está hecha). `[dep: …]` indica de qué tarea depende.

### Fase 0 — Sandbox local

**Setup**
- **T0.0 — Entorno con uv.** `uv python install 3.12`, `uv venv`, `pyproject.toml` con deps base (langgraph, langgraph-checkpoint-sqlite, openai-agents, litellm, pymupdf, pdfplumber, openpyxl, python-docx, ezdxf, python-dotenv) y lockfile. `.env.example` con las claves (LLM provider/keys, `DB_MODE`). Documentar el prerrequisito de **ODA File Converter** para DWG.
  - *Aceptación:* `uv run python -c "import langgraph, fitz, ezdxf"` corre sin error; lockfile commiteado.
- **T0.0b — Proveedor LLM configurable.** `ai_agents/provider.py`: arma el modelo del Agents SDK desde env (`LLM_PROVIDER=openai|claude`, modelo, key). OpenAI directo o vía LiteLLM para Claude/otros. Helper único que usan todos los agentes.
  - *Aceptación:* cambiando `LLM_PROVIDER` por env, los agentes corren contra OpenAI o Claude sin tocar su código.

**Datos / estado**
- **T0.1 — Estado del caso.** `graph/state.py`: TypedDict con `tipo_entrega, disciplina, proyecto, revision, emisor, documentos[], entrega_completa, admisibilidad, rebotes_admisibilidad, ronda, status`. `documentos[]` = `{tipo_doc, filename, presente, formato_ok, relevante, motivo}`.
  - *Aceptación:* importa sin error; un estado de ejemplo se serializa.
- **T0.2 — Enum Status.** En `state.py`: `RECIBIDO, FALTAN_DATOS, EN_TRIAGE, INCOMPLETA, NO_ADMISIBLE` (+ placeholders `EN_REVISION` para Fase 1). [dep: T0.1]
  - *Aceptación:* enum cerrado, sin estados sueltos en el código.

**DB local**
- **T0.3 — Checkpointer local.** `tools/db.py`: factory del checkpointer apuntando a **SQLite local** (archivo en el repo, gitignored) con la misma interfaz que tendrá Neon. Toggle `DB_MODE=local|neon`.
  - *Aceptación:* se crea un thread, se corta el proceso, se reabre y el caso retoma su `status`.

**Knowledge / fixtures**
- **T0.4 — Plantillas de entrega.** `knowledge/entrega_fabricacion.md` (= Plano + Lista de materiales + formato esperado) y al menos un 2º tipo (ej. `entrega_calculo.md`) para probar relevancia/irrelevancia.
  - *Aceptación:* cada plantilla lista documentos requeridos y reglas de formato legibles por el triage.
- **T0.5 — Catálogo por proyecto (fixture).** `knowledge/catalogo.json`: proyecto → entregas esperadas (qué documentos por entrega, estado). Lo que en infra real saldrá del Sheet maestro. [dep: T0.4]
  - *Aceptación:* el fake de sheets lo lee y devuelve los requeridos de un `(proyecto, tipo_entrega)`.

**Tools (fake / local)**
- **T0.6 — email fake.** `tools/email.py`: `enviar_emisor/enviar_senior/enviar_dueno` que **loguean** (no mandan) + `build_trigger_state(files, meta)`. Toggle real/fake.
  - *Aceptación:* llamar a enviar deja el "email" visible en el log/chat del sandbox.
- **T0.7 — sheets fake.** `tools/sheets.py`: `leer_catalogo(proyecto, tipo_entrega)` desde el fixture; `write_back(...)` no-op/log. [dep: T0.5]
  - *Aceptación:* `leer_catalogo` devuelve los requeridos esperados.
- **T0.8 — Lectura de documentos (híbrido, multi-formato).** `tools/docs.py`: dado un archivo subido, devuelve una representación legible (texto/markdown + páginas renderizadas si hace falta) que el parser/triage/extractor puedan usar. Router por extensión:
  - **PDF** → PyMuPDF (texto + render de páginas); pdfplumber para tablas. Si la página no tiene texto → render a imagen para visión.
  - **Office** → openpyxl (xlsx) / python-docx (docx) a texto/markdown.
  - **CAD** → ezdxf para DXF (capas, textos, entidades); **DWG** vía `ezdxf.addons.odafc` (ODA Converter) → DXF.
  - **Imágenes** → pasan directo a visión.
  - Cada lector aislado en try/except: si uno falla, devuelve metadato (nombre/tipo) y marca el documento como "no legible" sin romper el flujo. [dep: T0.0]
  - *Aceptación:* un PDF de texto, un xlsx, un DXF y un DWG de prueba devuelven contenido legible; un archivo corrupto no tumba el proceso.
- **T0.9 — drive fake (stub).** `tools/drive.py`: stub presente (no se usa en F0) para no romper imports. 
  - *Aceptación:* importable.

**Agentes**
- **T0.10 — Parser.** `ai_agents/parser.py` + `prompts/parser.txt`: del trigger (texto del chat + nombres de archivos) extrae `tipo_entrega, disciplina, proyecto, revision` y lista documentos. JSON con **regex + fallback**. [dep: T0.0b, T0.1, T0.8]
  - *Aceptación:* sobre 3 triggers de prueba, extrae los campos o cae al default sin crashear.
- **T0.11 — Triage.** `ai_agents/triage.py` + `prompts/triage.txt`: resuelve requeridos (T0.7) y evalúa **completitud + tipo/relevancia + formato** sobre el texto de los archivos (T0.8). Salida `{es_admisible, completa, faltantes[], irrelevantes[], documentos[], motivo}`, regex + fallback. [dep: T0.7, T0.8, T0.10]
  - *Aceptación:* clasifica bien los 4 escenarios (completa / falta lista / archivo irrelevante / sin tipo).

**Grafo**
- **T0.12 — Nodos.** `graph/nodes.py`: `parser`, `validacion_datos_minimos`, `triage`, `pedir_datos`, `reclamar_faltantes`, `devolver_no_admisible`. Los nodos solo llaman a `tools/` y agentes (nunca IO inline). [dep: T0.10, T0.11]
  - *Aceptación:* cada nodo es una función pura de `state -> state`.
- **T0.13 — Routers.** `graph/edges.py`: router de validación (faltan datos mínimos → `pedir_datos`/FALTAN_DATOS) y router de triage (completa → fin de fase / faltan docs → INCOMPLETA / irrelevante|formato → NO_ADMISIBLE). [dep: T0.12]
  - *Aceptación:* cada salida del triage rutea al nodo correcto.
- **T0.14 — Ensamblado.** `graph/graph.py`: arma el grafo + checkpointer local (T0.3) + entrada condicional (trigger nuevo vs respuesta con `[REF:thread_id]`). [dep: T0.12, T0.13, T0.3]
  - *Aceptación:* `ainvoke` corre el frente entero y persiste el estado.
- **T0.15 — Borde rebotes.** Contador `rebotes_admisibilidad`: incrementa en cada NO_ADMISIBLE; al 3º del mismo caso, `enviar_dueno` (log). [dep: T0.14]
  - *Aceptación:* 2 rebotes silenciosos, el 3º deja aviso al dueño en el log.

**Sandbox**
- **T0.16 — Manifest.** Manifest del sandbox que declara nodos, tools con toggle real/fake, y espeja `build_trigger_state`. [dep: T0.14]
  - *Aceptación:* el sandbox levanta y reconoce el grafo y sus dependencias.
- **T0.17 — Subida de archivos.** Afordancia de upload en el harness: pasa `(filename, bytes)` a `build_trigger_state`. (Posible extensión fina del agent-sandbox.) [dep: T0.16]
  - *Aceptación:* subo 1+ archivos en el chat y aparecen como documentos del caso.
- **T0.18 — Validación del agente.** Levantar el sandbox, correr los 4 escenarios sobre archivos reales, **ajustar prompts** de parser/triage hasta dictaminar bien. [dep: T0.17]
  - *Aceptación:* los 4 escenarios dan el dictamen correcto de forma estable.

### Fase 1 — Revisión de contenido (en el sandbox)

- **T1.1 — Extractor.** `ai_agents/extractor.py` + `prompts/extractor.txt`: lee cada documento y extrae secciones/datos **con `confidence` por ítem**. [dep: Fase 0]
  - *Aceptación:* sobre un documento real, devuelve secciones con confidence; lo dudoso queda marcado.
- **T1.2 — Checklists.** `knowledge/checklist_<disciplina>.md` (estructural + al menos otra).
  - *Aceptación:* el revisor los lee y los aplica ítem por ítem.
- **T1.3 — Revisor.** `ai_agents/revisor.py` + `prompts/revisor.txt`: checklist + hallazgos libres → **Markdown**; cada hallazgo con severidad **Bloqueante / No bloqueante**. El código no deja que el LLM orqueste tools. [dep: T1.1, T1.2]
  - *Aceptación:* produce lista de hallazgos con severidad y un dictamen propuesto.
- **T1.4 — Estado.** Ampliar `state.py`: `hallazgos[] = {item, seccion, severidad, descripcion, norma, confidence}`, `dictamen`, status `EN_REVISION`. [dep: T1.3]
  - *Aceptación:* el estado guarda los hallazgos y el dictamen.
- **T1.5 — Nodos.** `graph/nodes.py` += `extractor`, `revisor`. [dep: T1.3, T1.4]
  - *Aceptación:* tras triage "completa", corre extractor → revisor.
- **T1.6 — Router por severidad.** `graph/edges.py`: ≥1 bloqueante → OBSERVADO/RECHAZADO; solo no bloqueantes → APROBADO_CON_NOTAS; sin hallazgos → APROBADO. [dep: T1.5]
  - *Aceptación:* el dictamen depende correctamente de la severidad.
- **T1.7 — Resaltar baja confianza.** Marcar en el estado los ítems de baja confianza del extractor para destacarlos (al senior en Fase 2). [dep: T1.1]
  - *Aceptación:* los ítems de baja confianza quedan flagueados.
- **T1.8 — Validar en sandbox.** Correr una entrega completa con y sin hallazgo bloqueante; ajustar prompts. [dep: T1.6]
  - *Aceptación:* dictamen y severidades correctos en ambos casos.

---

## Checklist de producción (al llegar a Fase 4–5)
- [ ] Carpeta `ai_agents/` (no `agents/`).
- [ ] Firma Svix sobre body crudo · filtro por `to` activo.
- [ ] Pool de Postgres persistente · entrada condicional.
- [ ] Parseo LLM robusto (regex + fallback) · generación → Markdown, el código formatea.
- [ ] Formato/logo/adjuntos en try/except · secretos en `.gitignore` · `CRON_SECRET`.
- [ ] Datos de prueba limpiados.
