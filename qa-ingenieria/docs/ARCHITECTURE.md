# Arquitectura — Cotejar / QA-Ingeniería

Documento técnico. Para puesta en marcha y modo de uso ver el [README](../README.md).

## 1. Visión general

```
                 Frontend React (Vite :5173)
                        │  fetch /api/*  (proxy)
                        ▼
                 FastAPI (uvicorn :8000)        api/main.py
                        │  build_trigger_state()
                        ▼
                 LangGraph  (StateGraph)        graph/graph.py
                        │  checkpointer SQLite (por thread_id)
        ┌───────────────┼───────────────────────────────┐
        ▼               ▼                                 ▼
  ai_agents/*     tools/* (IO+dominio)              api/historial.py (auditoría)
  (LLM, sin       docs, tipos, refs, reglas,        SQLite local
   estado)        layout, sheets, disciplinas, email
```

Principio rector: **los nodos del grafo son funciones `state -> state` casi puras; todo el IO
vive en `tools/` y todo lo que llama al LLM vive en `ai_agents/`.** El LLM razona identidad,
**extrae** los valores de los campos y ubica zonas; pero la **validación de reglas es determinista**
(`tools/reglas`) y el **score lo calculan embeddings** (`ai_agents/similarity`) — nunca el LLM.

## 2. El grafo (graph/)

- **`state.py`** — `CasoState` (TypedDict del estado persistente), enum `Status`, y helpers de
  presentación/decisión que son **fuente única**:
  - `veredicto_ui(status)` → `valido | revision_manual | invalido | faltan_datos` (mapea `Status`).
  - `umbrales_score()` / `clasificar_score(score, umbrales?)` → umbralado del score. El nodo decide
    el veredicto **una vez** (con los umbrales del template) y lo guarda en `score_veredicto`; el
    router solo lo lee. Una sola definición evita divergencias.
- **`nodes.py`** — nodos: `parser` → `validacion` → `triage` → terminales. En modo cotejo,
  `_cotejar_single` arma los checks de **Identidad** (LLM `es_el_tipo` autoritativo + similitud +
  match código↔filename) y **Completitud** (reglas deterministas sobre los `campos` extraídos +
  checks cualitativos del LLM), calcula el score por zonas (`_evaluar_similitud`) y arma el
  **resultado POR zona** (`_zonas_resultado`): cada zona del template evaluada por separado en ESTE
  doc (las visuales contra ESA zona de las referencias, sin diluirse en el score global → un logo
  tapado da bajo parecido en su zona) con `{estado, bbox efectivo, score}`. Para el informe y los
  overlays. Una zona visual `requerido` que falla emite un check decisivo.
- **`edges.py`** — routers condicionales. `route_post_triage` unifica ambos modos:
  - *Cotejo*: identidad falla → `invalido`; score concluyente fuera de umbral → `invalido`/`revision_manual`;
    completitud requerida falla → `revision_manual`; todo pasa → `valido`.
  - *Entrega*: irrelevante/formato → `invalido`; faltan docs → `incompleta`; ok → `valido`.
  - `route_post_admision`: tras admitir (EN_REVISION), ¿continúa a la **revisión de contenido**? Sí si
    el toggle `revisar_auto` está on, es cotejo single-doc y el template declara bloque `revision:`.
- **`graph.py`** — arma el `StateGraph`, conecta nodos/edges y compila con el checkpointer.

### Revisión de contenido (Fase 1) — el segundo nodo

Tras la **admisión** (gate Fase 0 → `EN_REVISION`), un cotejo single-doc puede continuar a la
**revisión de calidad/cumplimiento** en el mismo invoke (toggle `revisar_auto`; si está off, queda
`EN_REVISION` y se dispara a mano). Flujo: `listo_para_revision → extractor → revisor → END`.

- **`extractor_node`** — extrae contenido para los tiers (texto/render ya vienen del parser; deja un
  `revision_extracto` observable; tablas/pdfplumber para tiers futuros).
- **`revisor_node`** — corre los tiers (**Tier 1 + Tier 2**) vía `ai_agents/revisor.revisar` y agrega la
  severidad en un veredicto con `graph/revision.agregar_revision`. **La admisión NO se toca**: `status`
  queda `EN_REVISION`; el veredicto de revisión va aparte en `verdicto_revision` (no pisa el chip de
  admisión). Motor por tiers (spec `docs/spec/SPEC_Cotejar_Fase1_Revision.md`): lo mecánico se **mide**
  (Tier 1, determinista), lo semántico con **reglas/normas** (Tier 2, determinista), lo difuso al **VLM**
  (Tier 3, pendiente; nunca decide un bloqueante solo).

#### Vínculo documento ↔ norma (Tier 2)

Las normas/códigos viven en un **catálogo reutilizable** (`knowledge/normas/<id>.yaml`) que los templates
**referencian** (`revision.normas: [aea-90364, ...]`). El vínculo tiene dos direcciones:
- **Detección** (doc → norma): `tools/normas.detectar_normas` busca las `anclas` de cada norma en el
  texto (¿el doc la declara? ¿qué versión?). Declarar la norma esperada es en sí un hallazgo.
- **Aplicación** (norma → checks): `reglas_de_normas` trae sus reglas Tier 2; se **mergean** con las del
  template (el template gana por `id`). Cada hallazgo lleva `norma_ref` (cita la norma incumplida).
Una norma declara: `deteccion.anclas`, `reglas` (Tier 2), `lookups` (tablas de la norma como dato) y
`vlm` (`norma_ref` + criterios para Tier 3). El `extractor_node` suma `tablas` (pdfplumber) para las
reglas `tabla`. Lo no medible (tabla dibujada, valor no extraíble) → `no_verificable`, nunca un `ok`.

**Cobertura y UX (dos pasos).** El gate usa `SIM_MAX_PAGES` (≈6, identidad en portada). La **revisión**
cubre **todo el documento** (`REVISION_MAX_PAGES`, 0=todas): el texto ya cubre todas las páginas, las
**tablas** se extraen de todas, y la **legibilidad** se muestrea en varias páginas (`REVISION_LEG_SAMPLES`)
reportando la peor. Como la revisión es más cara, corre como **2º paso con progreso**: la UI valida el
gate (rápido), lo muestra, y luego llama `POST /casos/{id}/revisar` (mientras el usuario lee la admisión).
Flujo de pantalla detallado: [REVISION_UI.md](REVISION_UI.md).
- **Hallazgo** (`graph/revision.Hallazgo`): `{check_id, dimension, severidad, estado, ubicacion?, evidencia, razonamiento, sugerencia?, fuente}`.
  Agregación determinista → `aprobado | aprobado_con_notas | observado | rechazado | pendiente_senior`;
  `no_verificable` no cuenta como fallo pero baja la confianza (nunca se inventa un `ok`).

### Estados (Status) y veredicto UI

| Status backend | Veredicto UI | Color |
|----------------|--------------|-------|
| `EN_TRIAGE`, `EN_REVISION`, `APROBADO`, `APROBADO_CON_NOTAS` | `valido` | 🟢 |
| `REQUIERE_DECISION`, `OBSERVADO`, `ESPERANDO_APROBACION_SENIOR` | `revision_manual` | 🟡 |
| `NO_ADMISIBLE`, `RECHAZADO` | `invalido` | 🔴 |
| `FALTAN_DATOS`, `INCOMPLETA` | `faltan_datos` | ⚪ |

> El **veredicto de revisión** (Fase 1) NO usa el campo `status` (que refleja la admisión): vive en
> `verdicto_revision` y se muestra en su propia sección/banner. Así el chip de admisión no se pisa.

### Checks y dimensiones

Cada check: `{dimension: "identidad"|"completitud", label, state: pass|fail|warn|info, detail, requerido}`.
Una **dimensión pasa** si no tiene checks `requerido` en `fail` (`edges._dim_pasa`). `armar_checks`
mergea y deduplica por `(dimension, label)` — el check autoritativo va primero y gana en el dedup.

## 3. Agentes LLM (ai_agents/)

- **`provider.py`** — `build_agent()` / `build_model()` con proveedor configurable (OpenAI directo
  o LiteLLM para Claude/otros).
- **`parser.py`** — extrae datos del trigger (proyecto, tipo, disciplina…). Se saltea en modo cotejo.
- **`triage.py`** — `run_triage` (entrega multi-doc) y `run_cotejar(doc, tipo)` (single-doc: devuelve
  `es_el_tipo`, `checks[]`, **`campos`** (valores EXTRAÍDOS para las reglas), `cajetin_bbox`,
  `razonamiento`, `resumen`). El LLM solo *encuentra* los datos; la validación es determinista.
- **`tipo_extractor.py`** — `proponer_template(...)` captura características de un modelo (modo
  `ejemplo`) o de un documento normativo (modo `especificacion`); además **propone la zona de
  identidad por visión** (encabezado o rótulo según el tipo).
- **`similarity.py`** — embeddings CLIP locales (carga perezosa **offline** desde la cache para no
  pingear HuggingFace Hub —evita cuelgues—, `EMBED_ALLOW_DOWNLOAD=1` para la descarga inicial; la API
  lo **precalienta** en un hilo al arrancar). Degrada con gracia. `disponible()`, `embed_image(s)`,
  `score_grupos`/`detalle_score`/`umbrales_calibrados`, `recortar_bbox(img, zona, pad)`,
  `region`-helpers y `detectar_zona_identidad()` (visión LLM, solo localización).
- **`revisor.py`** — orquestador de la **revisión de contenido** (Fase 1): `revisar(doc, cfg)` corre
  los tiers (hoy Tier 1 determinístico vía `tools/legibilidad`) y devuelve `hallazgos[]`. Los Tier 2
  (reglas/tablas) y Tier 3 (VLM) se enchufan acá sin tocar el grafo.
- **`util.py`** — `run_agent` (sync, vía `asyncio.run`; política de event loop Selector en Windows),
  `build_input` (multimodal), `extract_json`, `load_prompt`.

## 4. Tools (tools/)

| Módulo | Rol |
|--------|-----|
| `docs.py` | Lectura híbrida de documentos + `render_pdf_images()` (para visión y embeddings). |
| `tipos.py` | Templates YAML en `knowledge/tipos/` (invariante **id == nombre de archivo**). CRUD + render + **`zonas`** (`guardar_zonas`, `zona_identidad_de`, `reglas_de`). |
| `refs.py` | Ejemplos de referencia por tipo (`knowledge/refs/<id>/`): alta/baja, `maturity()`, **embeddings persistidos** (`.npz`: páginas + zona) + `vectores_por_referencia()` + `reembeber_todas()` (al cambiar la zona). |
| `reglas.py` | `chequear_campos(campos, filename, reglas)` — validación DETERMINISTA de valores ya extraídos: `regex` / `filename` (código ↔ nombre de archivo) / `presencia`. `chequear_reglas(texto, reglas)` = legacy por texto. |
| `layout.py` | Zonas por texto (cajas de palabras PyMuPDF): `localizar_bbox`/`bbox_efectivo` (recorte que sigue al ancla) + `extraer_campos_zonas` (valor de cada zona-regla: dentro del recuadro, entre anclas o junto al ancla; refinado por patrón). Cae a OCR si no hay capa de texto. |
| `ocr.py` | OCR opcional (`OCR_PROVIDER=tesseract`, local). Fuente de texto de respaldo cuando el dato vive solo en la imagen (escaneo) + `confianza()` (Tier 1 de revisión). Degrada con gracia. |
| `legibilidad.py` | Métricas Tier 1 de la revisión de contenido: `varianza_laplaciano` (nitidez, numpy/sin cv2), `dpi_efectivo` (resolución del escaneo; None si es vectorial), `confianza_ocr`, `contiene_seccion`/`ubicacion_seccion` (presencia de secciones por texto). |
| `normas.py` | Catálogo de normas/códigos REUTILIZABLE (`knowledge/normas/<id>.yaml`). `cargar_normas`, `detectar_normas`/`auto_detectar` (vínculo doc↔norma por anclas de texto), `reglas_de_normas` (reglas Tier 2 de la norma, anotadas con `norma_ref`). |
| `reglas_revision.py` | Motor de reglas **Tier 2** (determinista, sobre texto/tablas): `presencia`, `presencia_unidad`, `patron`, `norma_lookup` (extrae valores y verifica max/min, p. ej. caída ≤5%), `tabla` (columnas requeridas; `no_verificable` si no se extrajo). |
| `sheets.py`, `disciplinas.py` | Catálogos editables (tipos de entrega, disciplinas). |
| `email.py` | `build_trigger_state(...)` (armador de estado) + emisores fake (sandbox). |

## 5. Zonas, similitud y reglas deterministas

**Zonas (gráficas, por template).** Un template define `zonas`: regiones nombradas
(`{nombre, pagina, bbox, identidad?, campo?, patron?, tipo?, requerido?, ancla_inicio?, ancla_fin?}`),
definibles **visualmente** (dibujar/mover/redimensionar, multipágina) en la UI. Una zona `identidad`
(pueden ser varias, en distintas páginas) se usa para el **score visual** (encabezado en una HD,
rótulo al pie en un plano — no asumimos el pie). La captura **propone** la zona por visión.

**Robustez a desvíos.** (1) El recorte se hace con un **margen/padding** (`SIM_ZONE_PAD`) idéntico en
candidato y referencias, así un corrimiento chico sigue cayendo en la ventana. (2) Una zona puede
**anclarse a texto** (`ancla_inicio`/`ancla_fin`, regex): `tools/layout.py` ubica esas palabras con
las cajas de PyMuPDF y deriva el bbox **por documento**, de modo que la zona *sigue al contenido*
aunque se mueva (robusto a layout variable; degrada al bbox estático si no hay texto/anclas).

**Score (similitud).**
1. Al **agregar una referencia** se renderizan sus páginas y se embeben con CLIP; además se recorta la
   **zona de identidad del template** (recorte determinista por bbox — comparable, sin jitter de LLM) y
   se embebe. Ambos grupos van a `<ref_id>.npz` (`paginas`, `cajetin`). Cambiar la zona **re-embebe**.
2. Al **cotejar**, el candidato recorta la **misma** zona. El **score** es ponderado:
   `w_cajetin · sim(zona) + w_pagina · sim(página)` (def. 0.7/0.3). Sin zona → solo página.
3. **Umbrales**: con template `calibrado` se **auto-estiman** de la distribución intra-referencias
   (leave-one-out): aprobación ≈ media−1σ, revisión ≈ media−2.5σ; si no alcanza, globales. El
   **veredicto del score lo decide el nodo una vez** (`score_veredicto`) y el router lo lee.
4. **Madurez**: `solo_reglas` → no concluyente; `calibrando` → informativo; `calibrado` → decide.
5. **Degradación con gracia**: sin backend de embeddings → `score=None` y se decide por reglas + LLM.

**Reglas deterministas (extract-then-check).** Las reglas del template (derivadas de las zonas con
`campo` + `cajetin.reglas`) son casi todas deterministas. Las zonas con `campo` **extraen su valor
acotado** (recuadro = posición fija, ancla = sigue al texto; `layout.extraer_campos_zonas`) y pisan
lo del LLM, que solo cubre los campos sin zona (`campos` en `run_cotejar`).
`reglas.chequear_campos(campos, filename, reglas)` decide pass/fail **sin LLM**: `regex` (patrón), `filename` (el código del doc debe coincidir con el nombre de archivo —
señal de identidad), `presencia`. Los checks deterministas van **antes** que los cualitativos del LLM
(ganan en el dedup). El overlay visual del preview resalta la zona de identidad usada.

## 5.b Loop de aprendizaje (human-in-the-loop)

El **template es el "modelo"; los documentos con OK/NO humano son las etiquetas.** Tres piezas:
- **Captura multi-doc** (`proponer_template_multi`): induce reglas consolidadas desde N ejemplos +
  `cobertura_reglas` (cuántos cumplen cada patrón). Mejor que un solo ejemplo (generaliza).
- **Corpus** (`api/historial`): cada validación guarda los `campos` extraídos; `corpus(tipo)` los
  devuelve etiquetados por la decisión humana (positivos/negativos).
- **Feedback en el rechazo**: ante una regla fallida, `sugerir-variante` pide al LLM una regex que
  cubra el valor + los positivos del corpus y `reglas.verificar_variante` la **valida** (matchea todos
  los válidos, ninguno de los rechazados) antes de ofrecerla; el humano la aplica (`set_patron_regla`).
Nada se auto-aplica: el motor **verifica**, el humano **decide**. El score ya tiene su propio loop
automático (la calibración de umbrales).

## 6. Contrato de la API (§7)

Base `/api`. Endpoints (ver `api/main.py`):

| Método | Ruta | Qué hace |
|--------|------|----------|
| `POST` | `/api/validar` | Multipart (file + tipo_doc + `revisar`=toggle…) → corre el grafo → veredicto + checks + score + zonas + imágenes + bloque `revision`. |
| `GET` | `/api/tipos` | Lista de tipos con `refs_count` y `maturity`. |
| `GET` | `/api/tipos/{id}` | Template completo + `yaml` + referencias. |
| `POST` | `/api/tipos/capturar` | Propone un template desde **un** ejemplo/especificación. |
| `POST` | `/api/tipos/capturar-multi` | Propone un template **consolidado** desde **varios** ejemplos + `cobertura` (n/N por regla). |
| `PUT` / `DELETE` | `/api/tipos/{id}` | Guardar (desde YAML) / borrar. |
| `POST` / `DELETE` | `/api/tipos/{id}/referencias[/{ref_id}]` | Agregar (computa embeddings) / borrar referencia. |
| `GET` | `/api/tipos/{id}/referencias/{ref_id}/preview?page=N` | PNG de la página N de una referencia (galería/preview/editor multipágina). |
| `PUT` | `/api/tipos/{id}/zonas` | Guarda las zonas gráficas del template y **re-embebe** las referencias. |
| `GET` | `/api/tipos/{id}/zona-sugerida` | Propone (visión) el bbox del bloque de identidad usando la 1ª referencia. |
| `POST` | `/api/tipos/{id}/reglas/sugerir-variante` | Propone una regex (LLM) que cubra un valor que el humano dice válido, **verificada** contra el corpus. |
| `POST` | `/api/tipos/{id}/reglas/aplicar` | Aplica una variante de patrón a la regla de un campo (visto bueno humano). |
| `GET` | `/api/casos/{thread_id}` | Detalle de un análisis pasado (reconstruido del checkpointer). |
| `POST` | `/api/casos/{thread_id}/decision` | Decisión humana de admisión (`approved`/`rejected`). Al aprobar un caso `EN_REVISION` dispara la revisión de contenido. |
| `POST` | `/api/casos/{thread_id}/revisar` | Dispara la **revisión de contenido** a pedido (cuando el toggle interrumpió). **409** si el caso no está `EN_REVISION`. |
| `GET` | `/api/casos/{thread_id}/pagina/{page}` | Render PNG de la página N del documento del caso, **on-demand** (la previsualización no viaja en el payload; el visor pide cada hoja). |
| `POST` | `/api/casos/{thread_id}/requisito-feedback` | Juicio humano POR REGLA (`de_acuerdo`/`no_aplica`/`regla_mal`) — retroalimenta a la regla, no solo al doc. |
| `GET` | `/api/normas/catalogo` | Catálogo plano de **requisitos chequeables** (biblioteca asignable a las familias). |
| `PUT` | `/api/tipos/{id}/requisitos` | Asigna el set de requisitos de revisión a la familia (`revision.requisitos`). |
| `GET` | `/api/tipos/{id}/requisitos/sugerencias` | Sugerencias del **aprendedor** (agregar/quitar/prior) desde el corpus etiquetado. |
| `POST` | `/api/casos/{thread_id}/revision/decision` | Veredicto humano de la revisión (`aprobado`/`aprobado_con_notas`/`observado`/`rechazado`/`escalar_senior` + `notas`). |
| `POST` | `/api/tipos/{id}/referencias/promover` | Promueve el doc del caso a referencia (gate humano; **409** si el caso no fue aprobado). |
| `GET`/`PUT`/`DELETE` | `/api/entregas-tipo[/{id}]` | Catálogo de tipos de entrega. |
| `GET`/`POST`/`DELETE` | `/api/disciplinas[/{nombre}]` | Catálogo de disciplinas. |
| `GET` | `/api/proyectos` | Catálogo de proyectos. |
| `GET` | `/api/historial` | Validaciones + métricas. |

Respuesta de `/api/validar` (`_map_validacion`): `{thread_id, status, veredicto, tipo_doc, score,
no_concluyente, score_detalle, maturity, cajetin_bbox, resumen, checks[], campos, zonas_resultado[],
documento_panel, imagen, imagenes[], n_paginas}`. `imagenes` = páginas pre-renderizadas del gate
(fallback); `n_paginas` = total real → el visor pide cada hoja al endpoint `/casos/{id}/pagina/{n}`
(preview on-demand, no infla el payload). `zonas_resultado` = resultado por zona `[{nombre, pagina, bbox, clase
(identidad|visual|regla), estado, detalle, score?, requerido?, campo?, valor?}]` (informe + overlays).
Los `checks` de reglas llevan metadata (`campo, patron, valor, regla_tipo`) para el feedback.
`score_detalle` (observabilidad) = `{score, cajetin, pagina, peso_cajetin, peso_pagina,
umbral_aprobacion, umbral_revision, umbrales_auto, n_referencias, ref_top:{filename,score}, decisivo}`.
`revision` (Fase 1; `None` si no corrió) = `{verdicto, severidad_max, confiabilidad, resuelta, notas,
hallazgos[]}` con cada `hallazgo` = `{check_id, dimension, severidad, estado, ubicacion?, evidencia,
razonamiento, sugerencia?, fuente, norma_ref?}` (`norma_ref` = norma que origina el chequeo).

**Seguridad**: nombres de archivo y de tipo se sanitizan (anti path-traversal) en `_safe_name()`
(uploads) y `refs._safe()` (slug). CORS abierto (uso local).

## 7. Persistencia

- **Estado de casos**: checkpointer SQLite de LangGraph (`local_state/…sqlite`), keyed por `thread_id`.
- **Auditoría**: `api/historial.py` — tabla `validaciones` (validación + decisión + promoción) y `metricas()`.
- **Conocimiento**: `knowledge/` — templates YAML (con `zonas` y `revision`), **normas** (`knowledge/normas/<id>.yaml`:
  detección + reglas + lookups + vlm), referencias (archivos + `.npz` de embeddings: páginas + zonas),
  catálogos JSON. Las referencias, los PDFs de cliente y `.env` están gitignored. Fixtures de prueba
  (públicos) se bajan con `scripts/descargar_fixtures.py` (gitignored, reproducibles vía `tests/fixtures/manifest.yaml`).

## 8. Frontend (frontend/)

React 18 + TS + Vite. `src/api/client.ts` es el cliente tipado del contrato §7. 3 pantallas en
`screens/` (Validar, Templates, Historial); tokens en `design/tokens.ts` (teal, IBM Plex). Componentes:

- `components/ui.tsx` — `CheckRow`, `VerdictBanner`, `VeredictoChip`, `MaturityBadge`, `CajetinPreview`,
  `Dropzone` (drag&drop).
- `ScoreBreakdown` — explicabilidad del score: escala con bandas/umbrales, componentes zona/página,
  referencia más parecida.
- `Desglose` — checks por dimensión en 3 vistas (Dividida / Tarjetas / Compacta).
- `PaginasViewer` — visor **multipágina** del documento validado con las zonas dibujadas encima,
  coloreadas por estado (cumple/no cumple/a revisar/informativo) + índice de páginas con zonas + zoom.
  Pide cada hoja **on-demand** al endpoint del caso (`threadId`+`nPaginas`) — cubre TODO el doc sin payload;
  cae a `imagenes` pre-renderizadas si no hay `threadId`.
- `InformeZonas` — informe prolijo POR zona (cada regla/zona con estado, página y % de parecido si es visual).
- `RevisionSection` — sección **Revisión de contenido** (Fase 1): banner del veredicto de revisión +
  hallazgos por dimensión + overlay "ver en plano" (reusa `PaginasViewer`) + acciones para resolverla.
- `PreviewModal` — preview ampliado del documento/referencia con overlay de la zona.
- `ZonaEditor` — editor visual de zonas: dibujar/mover/redimensionar (multipágina), marcar identidad,
  campo+regla, anclas a texto, sugerir por visión y guardar (re-embebe).
- `Activity` — indicador de avance colapsable (qué está haciendo + historial de pasos); `ActivityProvider`
  envuelve la app y las operaciones lentas usan `useActivity().run(label, fn, pasos)`.

**Observabilidad** (clave para la confianza y la promoción): el resultado muestra *qué se tuvo en
cuenta* — el desglose del score (componentes y umbrales), la referencia más parecida, los checks por
dimensión con el valor encontrado, la zona resaltada, y una explicación de cómo se compara — para que
el humano decida y promueva con evidencia.

## 9. Tests

Suite pytest en `tests/` (`uv run pytest` — **113 tests**), enfocada en el núcleo **determinista**
(sin LLM ni red):
- `test_state` — umbralado del score (global y por-template) + mapeo de veredicto.
- `test_nodes` — dedup de checks (autoritativo primero, case-insensitive).
- `test_edges` — routers en ambos modos (cotejo single-doc + entrega multi-doc).
- `test_similarity` — coseno, top-k, score ponderado (zona/página) y umbrales auto-calibrados.
- `test_reglas` — motor determinista: regex / filename (código↔archivo) / presencia.
- `test_tipos` — normalización de zonas, zona de identidad y reglas derivadas.
- `test_layout` — zonas ancladas a texto (rutas sin/with anclas, fallback a bbox estático).
- `test_triage` — normalización del bbox.
- `test_historial` — la decisión humana manda sobre el veredicto automático.
- `test_api` — saneo de nombres, validación de upload (413/415/400) y mapeo de la respuesta.
- `test_ocr` — degradación con gracia del OCR (no rompe si tesseract no está; provider `none`).
- `test_zonas_resultado` — estado visual por zona (calibrado/calibrando) + lectura per-zona de refs.
- `test_revision` — Fase 1: agregación severidad→veredicto, router de entrada (toggle), Tier 1 y nodos.
- `test_reglas_revision` — motor Tier 2: cada tipo de regla con casos VÁLIDO e INVÁLIDO (y dónde falla).
- `test_normas` — catálogo de normas: detección del vínculo, merge template↔norma, integración válido/inválido.
