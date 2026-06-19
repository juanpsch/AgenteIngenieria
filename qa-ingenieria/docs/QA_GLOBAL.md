# QA global — Cotejar / QA-Ingeniería

Resumen del estado de calidad tras Fase C (embeddings) + Fase D (frontend), la review global
E2E y la pasada de modularidad/prolijidad. Fecha: 2026-06-17.

## 1. Qué se verificó end-to-end

| Verificación | Resultado |
|--------------|-----------|
| Backend importa/compila completo (graph, ai_agents, tools, api) | ✅ |
| CLIP local: carga, embeddings (dim 512), coseno self=100 | ✅ |
| Cotejo **calibrado**: score 100 → veredicto `valido`, check "Similitud · sobre umbral" | ✅ |
| Gating por madurez: `calibrando` → score informativo (no concluyente); `solo_reglas` → reglas | ✅ |
| Degradación con gracia: sin backend de embeddings, score=None, sigue por reglas | ✅ |
| Router score (`clasificar_score`): 99→válido, 90→revisión, 50→inválido | ✅ |
| Frontend: `tsc --noEmit` limpio + `vite build` (≈170 KB) | ✅ |
| Dev server sirve (200) y el **proxy `/api`** llega al backend | ✅ |
| **E2E completo** vía proxy: `POST /api/validar` PANDA → `valido`, score, bbox bottom-right, checks | ✅ |
| **Sin regresión** del modo entrega multi-doc (clasifica, rutea, "manda" mail) | ✅ |
| Preview real: la API expone `imagen` (1ª pág) y el front la muestra con el bbox del cajetín | ✅ |

## 2. Hallazgos de la auditoría y su resolución

Dos auditorías independientes (backend Python y frontend React). Triage:

### Backend — corregidos
- **Ida-y-vuelta validaba el documento viejo** (`_cotejar_single` tomaba `docs_[0]`): ahora coteja
  el **último** adjunto y lo reemplaza in situ.
- **Umbralado del score duplicado** (nodo + router leían env por separado → posible divergencia):
  extraído a `graph.state.clasificar_score()` como **fuente única**; nodo y router lo reusan.
- **Métrica de aprobación** mezclaba "aprobado por humano" con "válido automático": ahora una
  decisión humana (`approved`/`rejected`) **prevalece** sobre el veredicto automático (`_admitido`).
- **Código muerto**: `nodes.dimension_pasa` (duplicado de `edges._dim_pasa`) eliminado; `import os`
  sin uso removido.
- **UX del check de similitud**: distingue "backend de embeddings no disponible" de "template sin calibrar".

### Frontend — corregidos
- **Clicks muertos ante error**: `decidir()`/`confirmarPromo()` ahora con try/catch y error visible
  (importa porque `promover` devuelve **409** si el caso no fue aprobado).
- **Botón "Descargar reporte"** sin handler ni endpoint: removido.
- **Reset incompleto** en "Validar otro documento": ahora limpia `res/decision/promoted/err/tipoDoc`.
- **Keys de React por índice** → estables (`label` en checks, `thread_id` en historial).
- **Tipos**: `documento_panel` deja de ser `any` (interfaz mínima).
- **Accesibilidad**: navegación y filas operables por teclado (`role/tabIndex/onKeyDown`), badges con
  `aria-label`, "Deshacer" como `<button>`.
- **Duplicación**: helpers únicos `maturityLabel()` / `errMsg()` y componente `VeredictoChip`
  compartido (Historial dejó de reimplementar su propio chip).

## 3. Limitaciones conocidas (deuda registrada, no bloqueante)

- **Catálogo de entrega — divergencia de forma** (`tools/sheets.py`): el lookup por proyecto espera
  `entregas.<tipo>.documentos_requeridos` (dict anidado) mientras la escritura programática usa lista
  plana. Solo afecta el modo *entrega multi-doc* (no el cotejo web). Unificar la forma.
- **Cache de `cargar_tipos` + escrituras concurrentes** (`tools/tipos.py`): `lru_cache` global con
  `cache_clear()` disperso. Riesgo bajo en uso local single-user; revisar si se va multi-usuario.
- **Preview = 1ª página**: se muestra/recorta solo la primera página (donde suele estar el cajetín).
  Multipágina queda fuera del preview.
- **"Processing" cosmético**: los pasos animados avanzan por timer; la llamada a la API es síncrona,
  no reflejan progreso real del backend.
- **Layout de resultado**: se implementó una vista (split preview + dimensiones). El handoff proponía
  3 variantes (A/B/C); los datos son los mismos.
- **Sin autenticación**: usuario fijo en el sidebar (fuera de alcance, como en el prototipo).

## 4. Cómo re-correr la verificación

```bash
# Tests del core (sin LLM ni red)
uv run pytest                       # 43 tests

# Backend
uv run python scripts/run_cotejar.py knowledge/tipos/filesTipos/PANDA_CARRIER.pdf --tipo-doc esquematico_electronico
uv run python scripts/run_local.py sandbox/test_fixtures/plano_P102.pdf sandbox/test_fixtures/memoria_calculo_P102.pdf --tipo-entrega fabricacion

# Frontend (en frontend/)
npm run typecheck && npm run build

# E2E (API en :8000 y dev server en :5173)
curl -s -F "file=@knowledge/tipos/filesTipos/PANDA_CARRIER.pdf" -F "tipo_doc=esquematico_electronico" http://localhost:5173/api/validar
```

## 5. Iteración de mejoras (2026-06-18)

Sobre el MVP, a partir del análisis global:

- **Bug "no puedo subir referencias"**: el backend funcionaba (200); el front no tenía feedback ni
  manejo de error en `addRef` y el embeber tarda. Ahora dropzone + estado "Subiendo y calibrando…" + error visible.
- **Robustez**: `run_agent` con timeout (`LLM_TIMEOUT`) y reintentos con backoff (`LLM_RETRIES`);
  validación de upload (413/415/400) en `/validar`, `capturar` y referencias; `try/except` → **502**
  estructurado en vez de 500 crudo. Lifespan en vez de `on_event` (deprecado).
- **Bbox en 1 sola llamada LLM**: la localización del cajetín se plegó en el prompt de cotejo
  (la imagen ya viajaba al LLM) → ~50% menos costo/latencia por validación.
- **Score auto-calibrado + ponderado**: cajetín (banda inferior **determinista**) vs página con pesos
  (0.7/0.3) y umbrales **auto-estimados** por template (intra-refs). El nodo decide `score_veredicto`
  una vez; el router lo lee. **Hallazgo**: el bbox por LLM jitterea entre corridas y, pesado al 0.7,
  daba **falsos negativos** (mismo doc → inválido); el recorte determinista de la banda lo resolvió
  (PANDA idéntico → 100/válido; presupuesto → 36/inválido).
- **UI**: componente `Dropzone` reutilizable con **drag&drop** real (de-duplica 3 inputs).
- **Tests**: suite pytest (43) del core determinista (`uv run pytest`).

Pendiente de §3 que sigue abierto: catálogo de entrega, cache de tipos, preview multipágina,
"processing" cosmético, auth.

## 6. Iteración: observabilidad, zonas y reglas deterministas

- **Observabilidad** (UI): panel de explicabilidad del score (escala con bandas/umbrales,
  componentes zona/página, referencia más parecida), modal de preview con overlay, galería de
  referencias con miniaturas, explicación de cómo se compara. Endpoint de preview de refs +
  `score_detalle` en `/validar`.
- **Variantes A/B/C** del desglose (Dividida / Tarjetas / Compacta) — resuelto.
- **Zonas gráficas por template**: se definen **visualmente** (drag + presets + "sugerir" por visión)
  las regiones donde mirar. La zona `identidad` alimenta el score (resuelve el caso de la **hoja de
  datos**: la identidad está en el encabezado, no en el pie). Cambiar la zona re-embebe las referencias.
- **Reglas deterministas (extract-then-check)**: el LLM solo *extrae* los campos; `chequear_campos`
  valida sin LLM — `regex` / `filename` (código ↔ nombre de archivo) / `presencia`. Verificado E2E:
  «PANDA_CARRIER» del documento coincidió con el filename; las regex del template también.
- **Bug encontrado y corregido por E2E**: el re-embed leía el campo legacy `zona_identidad` en vez de
  la lista `zonas` → el componente de identidad daba None; corregido (usa `zona_identidad_de`).
- Tests del core: **55** (`uv run pytest`), suman `chequear_campos` y los helpers de zonas.

Mejora futura: detección de zona por *layout* más fina y zonas multipágina.
