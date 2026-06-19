# Especificación de construcción — Cotejar (gate de admisión documental)

> **Para Claude Code.** Este documento combina dos handoffs (backend *QA‑Ingeniería Fase 0* + UI *Cotejar*) en una sola especificación full‑stack accionable. Construí lo que está acá; lo que está en §11 (roadmap) queda **fuera de alcance**.

## 0. Resumen ejecutivo
Construir una app web full‑stack que funciona como **gate de admisión documental**: el usuario sube un documento de ingeniería (plano, memoria de cálculo, documento legal), elige un **template de referencia** por tipo, y la app emite un **veredicto explicable** de si el documento es válido como ese tipo.

- **Backend:** extender el backend Python existente (LangGraph + agentes LLM) y exponerlo con una capa **FastAPI** nueva (hoy no existe).
- **Frontend:** **React + TypeScript** nuevo, recreando fielmente el diseño hi‑fi de *Cotejar* (tokens en el handoff de UI), cableado al backend real.
- **Tres extensiones** sobre Fase 0 (decididas, ver §3): (1) **score de similitud por embeddings**, (2) **madurez de template + múltiples docs de referencia**, (3) **loop de promoción a referencia**.

## 1. Alcance
**Dentro:**
- Capa HTTP FastAPI que envuelve las funciones in‑process del backend (contrato en §7).
- Extensiones de backend de §3.
- Frontend React+TS con las **3 pantallas** del diseño: *Validar documento*, *Templates de referencia*, *Historial y auditoría* + modales (nuevo template, previsualización).
- Cableado real frontend↔API (sin mocks en el entregable final).

**Fuera (no construir — roadmap del backend):** revisión de *contenido* / hallazgos técnicos (Fase 1), HITL de aprobación senior (Fase 2), ciclo de corrección (Fase 3), infra real email/Neon/Vercel/Drive (Fase 4). El checkpointer queda en **SQLite local** (`DB_MODE=local`).

## 2. Decisiones de diseño resueltas (NO reintroducir las incongruencias)
Estas decisiones resuelven choques entre los dos handoffs. Respetarlas:

1. **El score de similitud se calcula por EMBEDDINGS, nunca pidiéndoselo al LLM.** El LLM juzga identidad/conformidad cualitativamente y produce `razonamiento`; el número 0–100 sale del coseno entre el documento candidato y el set de referencias del template. Un score pedido al LLM sería precisión falsa y no reproducible.
2. **La similitud solo es un check duro si el template está `Calibrado`.** Con `Solo reglas` (≤1 referencia) se muestra como **informativa / no concluyente** (estado `info` en la UI). Con `Calibrando` es un check blando (no puede por sí solo tirar a rojo).
3. **Dos dimensiones independientes**: *Identidad/pertenencia* y *Completitud/conformidad*, evaluadas y mostradas por separado (§4.4).
4. **Estado ámbar de admisión nuevo y distinto de `EN_REVISION`.** `EN_REVISION` del backend = "admisión OK, encolar para revisión de contenido (Fase 1)" → en la UI es **VÁLIDO (verde)**. La UI **REVISIÓN MANUAL (ámbar)** es un estado nuevo = "admisión ambigua, decide un humano". Se introduce como status backend `REQUIERE_DECISION` (§4.3).
5. **Promoción a referencia: solo con aprobación humana, jamás automática.** Evita que el set de referencia derive reforzando aceptaciones borderline del propio modelo.
6. **Granularidad de la pantalla Validar = un documento contra un template.** Se mapea a una "entrega" degenerada de un solo `tipo_doc`. La capacidad multi‑documento (`entrega` con varios `tipo_doc` requeridos) y el estado `INCOMPLETA` (falta un *documento* requerido de la entrega) quedan disponibles en el backend pero **no tienen pantalla** en este build (coincide con el diseño, que no tiene vista de entrega).
7. **Cajetín tolerante** (decisión preexistente del backend, se mantiene): válido si está presente e identifica el doc; campos secundarios = observación (`warn`), no bloquean salvo que estén marcados `requerido` en las reglas del template.

## 3. Las 3 extensiones (detalle de implementación)

### 3.1 Score de similitud por embeddings
- Nuevo servicio `ai_agents/similarity.py` (o `tools/similarity.py`) con proveedor de embeddings **configurable** (espejo del patrón `LLM_PROVIDER`): `EMBED_PROVIDER`, `EMBED_MODEL`.
- **Qué se embebe:** la página renderizada del documento candidato **y** (preferido) el **recorte del cajetín** una vez detectado — el cajetín tiene más señal que la página entera (es el ancla de identidad). Calcular ambos y combinarlos (peso configurable; default cajetín 0.7 / página 0.3) o, si el cajetín no se detecta, caer a página completa.
- **Modelo sugerido (pluggable):** un embedding multimodal multilingüe (p. ej. `jina-embeddings-v4`, Apache‑2.0) o un SigLIP/CLIP para imágenes de página. Mantener la interfaz agnóstica al modelo.
- **Cálculo del score:** coseno del candidato contra cada referencia del template → `score = top_k_mean` (default k=3) o `max`, normalizado a `[0,100]`. Persistir embeddings de referencias (no recomputar en cada request).
- **Umbrales configurables** (props de la UI → env): `APPROVAL_THRESHOLD=96`, `REVISION_THRESHOLD=85`.
- **Gating por madurez** (ver 3.2): `Solo reglas` → no se computa score duro (se devuelve `null` + flag `no_concluyente`); `Calibrando` → score blando; `Calibrado` → score duro.
- **Salida:** además del número, devolver el **bounding box del cajetín** detectado (coordenadas relativas a la página) para que el frontend dibuje el recuadro de "Cajetín detectado · NN% match".

### 3.2 Madurez de template + docs de referencia
- **Storage (sidecar, mínimo impacto sobre la invariante `id = nombre de archivo`):** mantener `knowledge/tipos/<id>.yaml` (reglas) y agregar:
  ```
  knowledge/refs/<id>/
    index.json            # [{ref_id, filename, origin: "inicial"|"promovido", added_at, added_by, embed_path}]
    <ref_id>.<ext>        # documento de referencia
    <ref_id>.npy|json     # embedding persistido
  ```
  No tocar `cargar_tipos` (sigue leyendo `<id>.yaml`); las referencias se leen aparte.
- **Madurez derivada** del nº de referencias (umbrales configurables `CALIBRATING_MIN=2`, `CALIBRATED_MIN=5` — la UI dice "/ 5 ejemplos sugeridos"):
  - `Solo reglas`: refs < 2
  - `Calibrando`: 2 ≤ refs < 5
  - `Calibrado`: refs ≥ 5
- Exponer en `GET /api/tipos` y `GET /api/tipos/{id}`: `refs_count`, `maturity`, y la lista de referencias con su `origin`.
- **Opcional (dejar como TODO, no implementar ahora):** al sumar referencias, reusar `ai_agents/tipo_extractor.proponer_template` (visión) para *sugerir* refinamientos de reglas. No automatizar la escritura de reglas.

### 3.3 Loop de promoción a referencia
- Endpoint `POST /api/tipos/{id}/referencias/promover` (§7).
- **Guarda dura:** solo se permite si el caso fue **aprobado por un humano** (`decision="approved"`). Nunca en un VÁLIDO automático sin intervención.
- Efecto: copia el documento a `knowledge/refs/<id>/`, computa y persiste su embedding, agrega entry en `index.json` con `origin="promovido"`, recalcula madurez. Devuelve `{refs_count, maturity}` para que la UI muestre "el template ahora tiene N+1 ejemplos" + nueva madurez.

## 4. Modelo de datos

### 4.1 Lo que ya existe (preservar)
- `CasoState` y `Documento` (ver handoff backend §4.1). `Documento` ya trae `formato_ok, relevante, faltan[], motivo, razonamiento` y `documentos_panel` "listo para tarjetas".
- Template `knowledge/tipos/<id>.yaml`: `cajetin{requerido, campos_requeridos[], logo_empresa}`, `secciones_requeridas[]`, `columnas_requeridas[]`, `caracteristicas[]`, `nomenclatura`, `bloqueante[]`, `senales_reconocimiento`, `criterios_aceptacion`, `no_corresponde`. Invariante: `id == nombre de archivo`.
- `knowledge/catalogo.json` (entregas/proyectos), `knowledge/disciplinas.json`.

### 4.2 Campos nuevos
- Template (en respuesta API, derivados del sidecar §3.2): `refs_count: int`, `maturity: "solo_reglas"|"calibrando"|"calibrado"`, `referencias: [{ref_id, filename, origin, added_at}]`.
- Reglas de campos del rótulo editables desde la UI: lista `{name, pattern, required}` (la UI las edita; persistir mapeadas a `cajetin.campos_requeridos` + un nuevo bloque `cajetin.reglas[]` con `{campo, patron, requerido}` en el YAML).
- Resultado de validación de un documento: `score: float|null`, `no_concluyente: bool`, `cajetin_bbox: {x,y,w,h}|null`, `checks: Check[]` (§4.4).

### 4.3 Estados (enum `Status`) y mapeo a veredicto UI
Preexistentes: `RECIBIDO · FALTAN_DATOS · EN_TRIAGE · INCOMPLETA · NO_ADMISIBLE · EN_REVISION` (+ placeholders Fase 1+).
**Nuevo:** `REQUIERE_DECISION`.

Mapeo backend → veredicto UI (pantalla Validar, single‑doc):

| Status backend | Veredicto UI | Color | Cuándo |
|---|---|---|---|
| `EN_REVISION` | **VÁLIDO** | verde | Identidad confirmada **y** completitud OK (sin faltantes requeridos, sin `bloqueante`). En calibrado: `score ≥ APPROVAL`. |
| `REQUIERE_DECISION` | **REVISIÓN MANUAL** | ámbar | Ambiguo: `score` en banda `[REVISION, APPROVAL)`; **o** identidad OK pero falta un campo requerido / baja confianza; **o** `Solo reglas` con similitud no concluyente y alguna observación. |
| `NO_ADMISIBLE` | **INVÁLIDO** | rojo | Identidad falla: no es el tipo, condición `bloqueante`, formato no soportado, o (calibrado) `score < REVISION`. |
| `FALTAN_DATOS` | (info, pre‑veredicto) | info | Falta metadata mínima (adjunto / `tipo_entrega` / `disciplina`). |
| `INCOMPLETA` | — (sin pantalla) | — | Solo flujo multi‑doc (fuera de alcance UI). |

El **veredicto combina dos ejes** (§4.4); el status es la resultante. Regla: rojo si el eje Identidad falla duro; verde si ambos ejes pasan; ámbar en cualquier ambigüedad que requiera humano.

### 4.4 Las dos dimensiones y el array `checks`
Cada validación produce `checks: Check[]` agrupados por dimensión.

```ts
type CheckState = "pass" | "fail" | "warn" | "info";
interface Check {
  dimension: "identidad" | "completitud";
  label: string;        // "Código de empresa coincide (ABC)"
  state: CheckState;
  detail?: string;      // "Falta el campo" | "87% · sobre umbral de revisión"
}
```
- **Identidad** (de `relevante`, cajetín presente/identifica, logo, `senales_reconocimiento`, **score**): ej. "Rótulo detectado en posición esperada" `pass`; "Código de empresa coincide (ABC)" `pass`; "Logo/sello presente" `pass`; "Similitud visual con el template" → `warn` (`"87% · sobre umbral de revisión"`) **o** `info` (`"Informativa — el template tiene 1 ejemplo"`) si `Solo reglas`.
- **Completitud** (de reglas YAML: `campos_requeridos`, `cajetin.reglas`, `secciones_requeridas`, `columnas_requeridas`, `bloqueante`): ej. "Campo 'Número de plano' presente" `pass`; "Campo 'Revisión' presente" `fail` (`"Falta el campo"`); "Campo 'Firma' presente" `warn` (`"baja confianza"`); "Formato de código de empresa válido" (chequea patrón regex) `pass`.

## 5. Arquitectura / layout de repos
```
repo/
  backend/                 # Python existente (extendido)
    graph/  ai_agents/  tools/  prompts/  knowledge/
    ai_agents/similarity.py        # NUEVO (§3.1)
    knowledge/refs/<id>/...         # NUEVO (§3.2)
    api/                            # NUEVO — capa FastAPI (§7)
      main.py  routers/  schemas.py  deps.py
    pyproject.toml (uv)  .env
  frontend/                # NUEVO — React + TypeScript + Vite (§8)
    src/
      api/        # cliente HTTP tipado contra §7
      screens/    # Validar, Templates, Historial
      components/ # CheckRow, VerdictBanner, Dropzone, PreviewModal, MaturityBadge, ...
      design/     # tokens (§ Design Tokens del handoff UI)
```
Flujo: React → FastAPI (`api/`) → funciones in‑process (`build_trigger_state` → `get_compiled_graph().invoke(...)`, y CRUD de `tools/*`, `tipo_extractor`, `similarity`).

## 6. Flujo del agente (extendido)
```
trigger (1 archivo + meta: proyecto, tipo_entrega, disciplina, texto)
  → build_trigger_state
  → parser (lee doc + clasifica metadata)
  → validación de datos mínimos
       faltan → FALTAN_DATOS
  → triage del documento contra el template elegido:
       - clasifica/identifica (relevante, cajetín, logo, senales_reconocimiento)
       - valida reglas (campos/secciones/columnas/bloqueante) → faltan[], checks completitud
       - [NUEVO] similarity.score(candidato, refs[id]) según madurez → score, bbox, checks identidad
       - resuelve veredicto (§4.3):
            identidad falla duro / bloqueante / score<REVISION (calibrado) → NO_ADMISIBLE
            ambiguo (banda gris / falta campo requerido c/ identidad OK / no concluyente) → REQUIERE_DECISION
            todo OK (y score≥APPROVAL si calibrado) → EN_REVISION
  → emite dictamen con razonamiento por check y motivo global
```

## 7. Contrato HTTP (FastAPI — implementar)
Capa fina sobre las funciones existentes. JSON salvo cargas multipart. CORS habilitado para el dev server del frontend.

### 7.1 Validación
**`POST /api/validar`** (multipart): `file`, `tipo_doc` (id del template), `proyecto?`, `disciplina?`, `texto?`, `thread_id?`
→
```json
{
  "thread_id": "…",
  "status": "REQUIERE_DECISION",
  "veredicto": "revision_manual",            // valido | revision_manual | invalido | faltan_datos
  "tipo_doc": "plano_estructural_x",
  "score": 87.0,                              // null si no concluyente
  "no_concluyente": false,
  "maturity": "calibrado",
  "cajetin_bbox": {"x":0.62,"y":0.78,"w":0.34,"h":0.18},
  "resumen": "Identidad confirmada; falta el campo 'Revisión'.",
  "checks": [ {"dimension":"identidad","label":"…","state":"pass","detail":"…"} ],
  "documento_panel": { "titulo":"…","datos":[{"clave":"…","valor":"…"}],"calidad":"…","fuera_de_criterio":[],"motivo":"…","razonamiento":"…" }
}
```
> `thread_id` opcional para acumular en un mismo caso (multi‑envío); si se omite, cada request es un caso nuevo (Fase 0 simple).

### 7.2 Decisión humana y promoción
- **`POST /api/casos/{thread_id}/decision`** body `{"decision":"approved"|"rejected"}` → `{status, veredicto}`.
- **`POST /api/tipos/{id}/referencias/promover`** body `{"thread_id":"…","promote":true}` (requiere caso `approved`, §3.3) → `{refs_count, maturity}`.

### 7.3 Templates (tipos de documento)
- `GET /api/tipos` → `[{tipo_doc, nombre, empresa, disciplinas[], refs_count, maturity, actualizado}]`
- `GET /api/tipos/{id}` → template completo + `referencias[]` + `reglas[]`
- `POST /api/tipos/capturar` (multipart `file`, `tipo_doc?`, `nombre?`) → template **propuesto** (de `proponer_template`, con visión) para revisar/editar antes de guardar
- `PUT /api/tipos/{id}` (body YAML/JSON del template, incluye `reglas[]`) → guarda
- `DELETE /api/tipos/{id}`
- `POST /api/tipos/{id}/referencias` (multipart `file`) → agrega referencia `origin="inicial"` → `{refs_count, maturity}`
- `DELETE /api/tipos/{id}/referencias/{ref_id}`

### 7.4 Catálogos
- `GET /api/entregas-tipo` · `PUT /api/entregas-tipo/{id}` (`documentos_requeridos[]`) · `DELETE /api/entregas-tipo/{id}`
- `GET /api/disciplinas` · `POST /api/disciplinas` (`{nombre}`) · `DELETE /api/disciplinas/{nombre}`
- `GET /api/proyectos`

### 7.5 Historial
- `GET /api/historial` → `[{doc, template, veredicto, score, operador, fecha, promovido_a_ref:bool}]` (persistir cada validación en SQLite local; suficiente para el strip de métricas + tabla).

## 8. Frontend (React + TypeScript)
**Recrear** el diseño de *Cotejar* fielmente con la librería del codebase — **no** copiar el `.dc.html` tal cual (es prototipo). Tokens, tipografía, colores, espaciados y animaciones: tomar del handoff de UI (sección *Design Tokens*); son **finales (hi‑fi)**. Íconos: equivalentes lucide/heroicons (shield‑check, layers, clock, file‑text, upload, download, trash, pencil, eye, plus, check, x, alert‑triangle, chevron‑down). Fuentes: IBM Plex Sans / IBM Plex Mono.

**Shell:** sidebar fijo 236px (`#0A363C`) + panel principal scrolleable. Header de sección sticky. Contenedor `max-width:1180px`.

**Pantallas (las 3 del diseño):**
1. **Validar documento** — máquina de estados `stage: upload → processing → result`.
   - *Upload:* dropzone (file) + select de template (muestra `tipo — empresa · madurez`) + botón habilitado solo con archivo + template. Aside "Cómo funciona el gate" con los 3 umbrales (de los props/env).
   - *Processing:* 5 pasos secuenciales (OCR → cajetín → identidad → campos → score). En el build real, reflejar progreso del request (o mantener la animación si la API es síncrona).
   - *Result (la pantalla clave):* banner de veredicto (3 estados), selector de vista del desglose (A Dividida / B Tarjetas / C Compacta — mismos datos, distinta disposición), filas de check por dimensión (`pass/fail/warn/info`), score grande (mono) con caption "SIMILITUD" o "NO CALIBRADO", previsualización del documento con **recuadro del cajetín** (de `cajetin_bbox`). Footer de acciones: Descargar reporte / Rechazar / Aprobar. Tras aprobar → **panel de promoción** (toggle default ON + confirmar) → banner de éxito con nueva madurez.
2. **Templates de referencia** — lista (tabla con MADUREZ badge) ↔ detalle (calibración + galería de referencias con tag `Inicial`/`Promovido` + reglas de campos editables) + modal lateral "Nuevo template".
3. **Historial y auditoría** — strip de 4 métricas + tabla con chips de veredicto y tag `↑ ref` para promovidos.

**Modal de previsualización** reusable (documento subido con nombre editable / referencia), hoja A‑series con cajetín resaltado.

**Notas de comportamiento:** animación `ct-fade` **solo `translateY`, sin `opacity`** (el contenido nunca depende de `opacity:0` inicial). Estados vacíos guiados (sin templates → CTA a crear el primero). Responsivo.

### 8.1 Mapeo UI ↔ API
| Acción UI | Endpoint |
|---|---|
| Validar documento | `POST /api/validar` |
| Aprobar / Rechazar | `POST /api/casos/{thread_id}/decision` |
| Confirmar promoción | `POST /api/tipos/{id}/referencias/promover` |
| Lista / detalle de templates | `GET /api/tipos`, `GET /api/tipos/{id}` |
| Nuevo template (captura desde ejemplo) | `POST /api/tipos/capturar` → editar → `PUT /api/tipos/{id}` |
| Agregar / borrar referencia | `POST` / `DELETE /api/tipos/{id}/referencias[...]` |
| Editar reglas de campos | `PUT /api/tipos/{id}` (incluye `reglas[]`) |
| Borrar template | `DELETE /api/tipos/{id}` |
| Historial + métricas | `GET /api/historial` |
| Selects de disciplina / tipo de entrega / proyecto | `GET /api/disciplinas`, `/api/entregas-tipo`, `/api/proyectos` |

## 9. Configuración (.env — fuente de verdad en archivos)
Preexistentes: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_MODEL_FAST`, `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`, `DB_MODE=local`, `LOCAL_DB_PATH`, `ODA_CONVERTER_PATH`.
**Nuevos:** `EMBED_PROVIDER`, `EMBED_MODEL`, `APPROVAL_THRESHOLD=96`, `REVISION_THRESHOLD=85`, `CALIBRATING_MIN=2`, `CALIBRATED_MIN=5`, `SIM_WEIGHT_CAJETIN=0.7`, `SIM_WEIGHT_PAGINA=0.3`, `SIM_TOPK=3`.

## 10. Cómo correr (criterio de entrega)
- **Backend:** `uv sync` · `uv run uvicorn api.main:app --reload` (key en `.env`).
- **Frontend:** `pnpm i && pnpm dev` (Vite) apuntando a la URL del backend (`VITE_API_BASE`).
- **Smoke existente:** `uv run python scripts/run_local.py …` debe seguir funcionando (no romper el flujo in‑process).

### 10.1 Criterios de aceptación (Definition of Done)
1. Subir un documento + elegir template `Calibrado` → veredicto con **score real** (embeddings) + checks por dimensión + bbox del cajetín dibujado.
2. Mismo documento contra template `Solo reglas` → similitud aparece como **info/no concluyente**, no como número duro.
3. Caso ámbar (`REQUIERE_DECISION`) → Aprobar → aparece panel de promoción → Confirmar → madurez del template sube y la referencia aparece taggeada `Promovido`.
4. Promoción **bloqueada** si el caso no fue aprobado por humano.
5. CRUD completo de templates (incl. captura desde ejemplo con visión), referencias, reglas, disciplinas.
6. Historial registra cada validación con su veredicto/score; métricas del strip salen de ahí.
7. El backend in‑process (`scripts/run_local.py`) sigue operativo.

## 11. Fuera de alcance (no construir)
Revisión de contenido / hallazgos (Fase 1), HITL senior + informe Doc/PDF + write‑back (Fase 2), ciclo de corrección (Fase 3), infra real Resend/Svix/Neon/Drive/Vercel/cron (Fase 4). El `INCOMPLETA` multi‑doc y la vista de "entrega" no tienen pantalla en este build.

## 12. Guardas y riesgos (tener presente al implementar)
- **No derivar el score del LLM** (precisión falsa). Embeddings siempre.
- **Promoción solo humana** (evita drift del set de referencia).
- **OCR es dependencia dura** de la dimensión Completitud: degradar con gracia si la extracción falla (marcar checks como `warn`/no concluyente, no inventar `pass`).
- **No verificación campo‑por‑campo estricta vía LLM** para el cajetín tolerante: los patrones regex de reglas son determinísticos; lo cualitativo va con `razonamiento` + confianza, no con falsos `fail`.
- Mantener **IO en `tools/`** y proveedores (`LLM_PROVIDER`, `EMBED_PROVIDER`) pluggables/testeables.
