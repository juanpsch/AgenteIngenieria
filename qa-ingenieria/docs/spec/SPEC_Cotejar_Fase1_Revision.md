# Especificación — Fase 1: Revisión de contenido (complemento del spec base)

> **Para Claude Code.** Este documento **complementa** `SPEC_Cotejar_QA-Ingenieria.md` (el gate de admisión, Fase 0). No reemplaza nada de ahí: agrega la capa de **revisión de contenido** que corre **después** de que un documento fue admitido. Vocabulario, stack, convenciones de archivos y patrones (config en `knowledge/`, proveedores pluggables, explicabilidad, IO en `tools/`) son los del spec base — respetarlos.

## Estado de implementación (rebanada Tier 1 — punta a punta)

> **IMPLEMENTADO** (verificado: `uv run pytest` 95 ✓, frontend build ✓, E2E del grafo ✓):
> - **Andamiaje completo**: schema `Hallazgo` + agregación de severidad→veredicto (`graph/revision.py`),
>   nodos `extractor`/`revisor` (`graph/nodes.py`), router de entrada `route_post_admision` con **toggle
>   de interrupt** (`revisar_auto`), cableado del grafo (`listo_para_revision → extractor → revisor`),
>   estados/`veredicto_ui` (`graph/state.py`).
> - **Tier 1 (determinístico)**: `tools/legibilidad.py` (nitidez=varianza Laplaciano con numpy, DPI
>   efectivo, confianza de OCR vía `tools/ocr.confianza`, presencia de secciones por texto/OCR) orquestado
>   en `ai_agents/revisor.py`. Lo no medible → `no_verificable` (nunca un `ok` inventado).
> - **Modalidad**: continua-auto (gate `valido` → revisión en el mismo invoke) **con toggle de interrupt**
>   (si está off, queda `EN_REVISION` y se revisa a pedido); aprobar la admisión de un caso ámbar dispara
>   la revisión. El `status` de admisión NO se pisa: el veredicto de revisión vive en `verdicto_revision`.
> - **Contrato HTTP**: bloque `revision` en `/api/validar` y `/api/casos/{id}`; `POST /api/casos/{id}/revisar`
>   y `POST /api/casos/{id}/revision/decision`.
> - **UI**: sección **Revisión de contenido** (banner + hallazgos por dimensión + "ver en plano" sobre el
>   visor multipágina) + toggle "Revisar contenido al admitir" en Validar.
> - **Piloto**: bloque `revision:` en `knowledge/tipos/esquematico_electronico.yaml`.
>
> **PENDIENTE** (se enchufan en `ai_agents/revisor.py` sin tocar el grafo): **Tier 2** (reglas sobre
> OCR + tablas pdfplumber, §3.2/§4), **Tier 3** (observación VLM, §3.3), compliance símbolo-por-símbolo
> (§11), informe Doc/PDF + write-back, aprobación senior real (solo el *hook* `pendiente_senior`).

## 0. Relación con el gate (no confundir las dos preguntas)
- **Gate (Fase 0, ya especificado):** *identidad + completitud*. "¿Es un plano tipo X de ABC y trae los campos/secciones requeridos?" → veredicto `VÁLIDO` / `REVISIÓN MANUAL` / `INVÁLIDO`.
- **Revisión (Fase 1, este doc):** *calidad + cumplimiento*. "Ya que entró, ¿el contenido es bueno?" → veredicto `APROBADO` / `APROBADO_CON_NOTAS` / `OBSERVADO` / `RECHAZADO`.

Solo entran a revisión los documentos **admitidos** (gate `VÁLIDO`, o `REVISIÓN MANUAL` aprobado por humano → status backend `EN_REVISION`). Un plano puede pasar el gate impecable y tener contenido deficiente: son ejes distintos.

## 1. Alcance Fase 1
**Dentro:**
- Motor de revisión **estratificado por tiers** (§3).
- Extensión del template para declarar el **checklist de revisión** por tipo/disciplina (§4).
- Nodos `extractor` + `revisor` en el grafo, schema de **hallazgos**, estados nuevos y verdicto de revisión (§5–§6).
- Endpoints y sección de UI para mostrar hallazgos y resolver el verdicto (§8–§9).
- Caso piloto: checklist concreto de **plano eléctrico** (§10).

**Sigue fuera (Fase 2+ del roadmap base):** aprobación senior real / HITL completo (acá solo se deja el *hook* `ESPERANDO_APROBACION_SENIOR`), informe Doc/PDF + write-back, ciclo de corrección automatizado, infra real. Compliance **símbolo-por-símbolo** contra biblioteca normativa: queda como tier posterior (§11), no se implementa ahora.

## 2. Decisiones de diseño (no romperlas)
1. **Estratificar por cuán checkeable es cada cosa.** No resolver la revisión con una sola pasada LLM "revisá el plano": da hallazgos vagos y no reproducibles. Lo mecánico se **mide**, lo semántico se **chequea con reglas**, y solo lo difuso va al **VLM** (§3).
2. **El LLM/VLM nunca es autoridad única de un `fallo` bloqueante.** Emite **observaciones con severidad y razonamiento** para que decida un humano. Lo bloqueante sale de reglas determinísticas, no de un juicio del modelo.
3. **Lo no verificable se marca como tal** (`no_verificable`), nunca se inventa un `ok`. Si la extracción de una tabla falla o el OCR no es confiable, el check se degrada con gracia.
4. **El estándar vive en el template**, no en el código. Cada `tipo_doc` declara su checklist de revisión (§4). Revisar un plano eléctrico difiere de uno estructural porque su template lo declara distinto.
5. **Explicabilidad:** cada hallazgo trae `razonamiento`, `evidencia` y, cuando se puede, `ubicacion` (página + bbox) para saltar al lugar en la previsualización.

## 3. Motor de revisión por tiers
Tres capas, de barato a caro. Todas alimentan el mismo array de `hallazgos`.

### 3.1 Tier 1 — Determinístico (sin LLM)
Métricas y presencia. Módulo `tools/legibilidad.py` + detección de secciones.
- **Legibilidad:**
  - Nitidez: varianza del Laplaciano sobre el render (OpenCV `cv2.Laplacian(img, CV2.CV_64F).var()`); por debajo de un umbral → borroso.
  - DPI/resolución efectiva del render o del escaneo.
  - **Confianza media del OCR** sobre la hoja; muchos tokens de baja confianza → ilegible.
  - Alto de texto mínimo vs escala (texto demasiado chico).
- **Presencia de contenido:** ¿están las secciones que el template marca obligatorias (unifilar, cuadro de cargas, simbología, puesta a tierra, escala, norte)? Misma mecánica que el cajetín en el gate: detección de región / búsqueda anclada por texto / locate con VLM. Reusar lo que ya exista del gate.

### 3.2 Tier 2 — Reglas sobre OCR (lógica determinística)
Módulo `tools/reglas_revision.py`. Opera sobre el texto y las tablas extraídas por el `extractor`.
- **Patrón:** un campo matchea un regex (IDs de circuito, nº de plano, formato de revisión).
- **Presencia con unidad:** secciones de conductor con unidad, tensiones declaradas, protecciones etiquetadas.
- **Tabla:** extraer el cuadro de cargas (pdfplumber) y chequear consistencia (columnas requeridas presentes; cada circuito del cuadro aparece etiquetado en el dibujo; sumatorias plausibles).
- **Simbología vs leyenda (parcial):** todo símbolo *referenciado en texto* figura en la tabla de referencias. La detección visual símbolo-por-símbolo queda para §11.

### 3.3 Tier 3 — Juicio VLM (cualitativo, como observación)
Módulo `ai_agents/revisor.py` + `prompts/revisor.txt`. Visión sobre las páginas renderizadas + el texto extraído, con `revision.norma_ref`, `criterios_aceptacion` y `revision.observacion_vlm.instrucciones` del template en el prompt. Devuelve observaciones tipo "la escala declarada no condice con las cotas", "anotaciones incompletas, parece borrador", "la leyenda referencia un símbolo que no aparece". **Cada observación trae severidad sugerida + razonamiento**; nunca produce un bloqueante por sí sola.

## 4. Extensión del template (`knowledge/tipos/<id>.yaml`)
Agregar un bloque `revision:` (todo lo demás del YAML queda igual). Ejemplo (plano eléctrico; los valores normativos son **declarativos del template**, no hardcodeados):

```yaml
revision:
  norma_ref: "AEA 90364 / IRAM (lo que aplique al tipo)"
  legibilidad:
    dpi_min: 200
    blur_var_min: 120          # varianza Laplaciano
    ocr_conf_min: 0.70
    alto_texto_min_mm: 1.8
  contenido_requerido:         # Tier 1 (presencia)
    - { id: unifilar,      detectar: "diagrama unifilar",      severidad_si_falta: mayor }
    - { id: cuadro_cargas, detectar: "cuadro de cargas",       severidad_si_falta: mayor }
    - { id: simbologia,    detectar: "tabla de simbología",    severidad_si_falta: menor }
    - { id: puesta_tierra, detectar: "puesta a tierra",        severidad_si_falta: mayor }
    - { id: escala,        detectar: "escala",                 severidad_si_falta: menor }
  reglas:                      # Tier 2
    - { id: circuito_id,        tipo: patron,          campo: "id de circuito", patron: "^C\\d{2}$", severidad: menor }
    - { id: seccion_conductor,  tipo: presencia_unidad, campo: "sección",        unidad: "mm2",       severidad: mayor }
    - { id: proteccion_label,   tipo: presencia,        campo: "protección",                          severidad: mayor }
    - { id: cuadro_consistente, tipo: tabla,            tabla: cuadro_cargas, columnas: [circuito, carga, proteccion], severidad: mayor }
  observacion_vlm:             # Tier 3
    instrucciones: >
      Revisá como un ingeniero junior: coherencia escala/cotas, anotaciones completas,
      símbolos referenciados que aparezcan en la leyenda, aspecto general de borrador vs final.
```

Catálogo de severidades: `bloqueante` · `mayor` · `menor` · `observacion`.

## 5. Modelo de datos

### 5.1 Hallazgo
```ts
type Dimension = "legibilidad" | "norma" | "contenido" | "consistencia";
type Severidad = "bloqueante" | "mayor" | "menor" | "observacion";
type EstadoCheck = "ok" | "advertencia" | "fallo" | "no_verificable";
type Fuente = "deterministico" | "reglas" | "vlm";

interface Hallazgo {
  check_id: string;
  dimension: Dimension;
  severidad: Severidad;
  estado: EstadoCheck;
  ubicacion?: { pagina: number; bbox?: { x: number; y: number; w: number; h: number } };
  evidencia?: string;        // qué se encontró / no se encontró
  razonamiento: string;      // por qué
  sugerencia?: string;       // cómo corregir
  fuente: Fuente;
}
```

### 5.2 Extensión de `CasoState` / `Documento`
Agregar a cada `Documento`: `hallazgos: Hallazgo[]`, `verdicto_revision`, `severidad_max`. A `CasoState`: `revision_resuelta: bool`, `revisor_notas`.

### 5.3 Estados nuevos (enum `Status`) y verdicto de revisión
Usar los placeholders ya reservados en el spec base: `ESPERANDO_APROBACION_SENIOR`, `OBSERVADO`, `APROBADO`, `APROBADO_CON_NOTAS`, `RECHAZADO`.

Agregación de severidad → verdicto (regla determinística):

| Condición sobre hallazgos | Status | Verdicto UI | Color |
|---|---|---|---|
| Algún `fallo` con severidad `bloqueante` | `RECHAZADO` | Rechazado | rojo |
| Algún `fallo` `mayor` (sin bloqueante) | `OBSERVADO` | Observado (corregir) | ámbar |
| Solo `menor` / `observacion` | `APROBADO_CON_NOTAS` | Aprobado con notas | verde claro |
| Sin hallazgos accionables | `APROBADO` | Aprobado | verde |
| Requiere firma senior (hook Fase 2) | `ESPERANDO_APROBACION_SENIOR` | Pendiente senior | info |

> `no_verificable` no cuenta como `fallo` pero se muestra y baja la confianza global del dictamen.

## 6. Flujo del agente (extendido)
Dos nodos nuevos tras `EN_REVISION`:
```
… gate … → EN_REVISION (admitido)
  → extractor_node     (texto completo + tablas[pdfplumber] + secciones detectadas + render por página)
  → revisor_node       (corre Tier 1 + Tier 2 + Tier 3 → ensambla hallazgos[])
  → route_revision (por severidad agregada):
       bloqueante      → RECHAZADO
       mayor           → OBSERVADO
       menor/observ.   → APROBADO_CON_NOTAS
       limpio          → APROBADO
       (hook senior)   → ESPERANDO_APROBACION_SENIOR
```
Nodos puros `state→updates`, como el resto del grafo. Router `route_revision` en `graph/edges.py`.

## 7. Mapa de módulos nuevos
| Archivo | Responsabilidad |
|---|---|
| `ai_agents/extractor.py` | Extrae contenido estructurado de un doc admitido (texto, tablas, secciones, imágenes) |
| `ai_agents/revisor.py` | Orquesta los tres tiers y ensambla `hallazgos[]` |
| `tools/legibilidad.py` | Métricas Tier 1 (blur/Laplaciano, DPI, OCR conf, alto de texto) |
| `tools/reglas_revision.py` | Motor de reglas Tier 2 (patrón, presencia, unidad, tabla) |
| `prompts/revisor.txt` | Instrucciones del agente VLM (Tier 3) |
| `graph/nodes.py` (extender) | `extractor_node`, `revisor_node` |
| `graph/edges.py` (extender) | `route_revision` |

Reusar lo existente: `tools/docs.py` (`read_document`, `render_pdf_images`), `ai_agents/provider.py` (modelo/visión), detección de regiones del gate.

## 8. Contrato HTTP (extender la capa FastAPI del spec base)
La revisión corre en el **mismo grafo** que la admisión (un solo `invoke`). Por defecto, si el doc queda admitido, el grafo continúa a revisión y la respuesta de `POST /api/validar` (definida en el spec base §7.1) gana un bloque `revision`:

```json
{
  "...": "campos de admisión del spec base",
  "revision": {
    "verdicto": "observado",                 // aprobado | aprobado_con_notas | observado | rechazado | pendiente_senior
    "severidad_max": "mayor",
    "hallazgos": [
      {
        "check_id": "seccion_conductor",
        "dimension": "norma", "severidad": "mayor", "estado": "fallo",
        "ubicacion": { "pagina": 1, "bbox": { "x":0.31,"y":0.55,"w":0.18,"h":0.06 } },
        "evidencia": "Circuito C03 sin sección especificada",
        "razonamiento": "La regla exige sección con unidad mm2 por circuito.",
        "sugerencia": "Indicar sección del conductor de C03.",
        "fuente": "reglas"
      }
    ]
  }
}
```

Endpoints nuevos:
- `GET /api/casos/{thread_id}` → caso completo (admisión + `revision.hallazgos`), para recargar la vista.
- `POST /api/casos/{thread_id}/revision/decision` body `{"decision":"aprobado"|"observado"|"rechazado"|"escalar_senior","notas?":"..."}` → fija el verdicto final humano sobre la revisión y, si corresponde, dispara el hook senior.

> Si preferís separar etapas en la UI (mostrar primero admisión y revisar a pedido), exponer `POST /api/casos/{thread_id}/revisar` que corre solo los nodos `extractor`+`revisor` sobre un caso ya `EN_REVISION`. Implementar **una** de las dos modalidades; default: continua automático.

## 9. Frontend (extender el resultado de validación)
Cuando hay `revision`, agregar una sección **"Revisión de contenido"** debajo del veredicto de admisión:
- **Banner de verdicto de revisión** con sus 4 estados (Aprobado / Con notas / Observado / Rechazado) + el hook "Pendiente senior".
- **Hallazgos agrupados por dimensión** (`legibilidad` / `norma` / `contenido` / `consistencia`). Cada fila: chip de severidad (colores: bloqueante rojo, mayor ámbar, menor gris, observación azul), `estado` con ícono (`fallo`/`advertencia`/`no_verificable`/`ok`), `razonamiento`, `sugerencia`, y si trae `ubicacion.bbox` un botón "ver en plano" que salta al recuadro en la **previsualización** (reusar el preview con bbox del gate).
- **Acciones:** Enviar a corrección (`observado`) · Aprobar · Aprobar con notas · Escalar a senior. Mapear a `POST …/revision/decision`.
- Distinguir visualmente `no_verificable` (no es un fallo; es "no se pudo chequear").

Estética y tokens: los del spec base (handoff de UI Cotejar). Mismos patrones de fila de check que el gate, ahora con la dimensión severidad.

## 10. Caso piloto — checklist de plano eléctrico
Implementar primero este template de revisión y validarlo end-to-end antes de generalizar a otras disciplinas.

| check_id | Tier | Dimensión | Qué chequea | Severidad |
|---|---|---|---|---|
| `nitidez` | 1 | legibilidad | varianza Laplaciano ≥ umbral | mayor |
| `ocr_confianza` | 1 | legibilidad | confianza media OCR ≥ 0.70 | mayor |
| `escala_presente` | 1 | contenido | hay escala declarada | menor |
| `unifilar_presente` | 1 | contenido | hay diagrama unifilar | mayor |
| `cuadro_cargas_presente` | 1 | contenido | hay cuadro de cargas | mayor |
| `simbologia_presente` | 1 | contenido | hay tabla de simbología | menor |
| `puesta_tierra_presente` | 1 | contenido | hay puesta a tierra | mayor |
| `circuito_id_formato` | 2 | norma | IDs de circuito matchean patrón | menor |
| `seccion_conductor` | 2 | norma | secciones con unidad mm² | mayor |
| `proteccion_label` | 2 | norma | protecciones etiquetadas | mayor |
| `cuadro_consistencia` | 2 | consistencia | columnas del cuadro + circuitos del cuadro aparecen en el dibujo | mayor |
| `simbolo_en_leyenda` | 2 | consistencia | símbolos referenciados en texto figuran en la leyenda | menor |
| `obs_general` | 3 | (varias) | observaciones VLM (borrador/coherencia/escala) | observacion |

## 11. Límites conocidos y guardas
- **Compliance símbolo-por-símbolo contra norma** (detección visual de cada símbolo y verificación contra la biblioteca normativa) es genuinamente difícil: requiere un detector entrenado en esa biblioteca o un VLM que conozca los símbolos. **No** implementar en Fase 1; dejar como tier posterior. Para nivel JR alcanza con legibilidad + presencia + nomenclatura + observación VLM.
- **Extracción de tablas puede fallar** (planos con tablas dibujadas, no tabuladas): si pdfplumber no recupera la tabla, marcar los checks de tabla como `no_verificable`, no como `ok` ni `fallo`.
- **VLM nunca decide un bloqueante solo** (decisión de diseño §2.2). Su severidad sugerida es para ordenar la cola humana.
- **Lo no verificable se reporta**; baja la confianza del dictamen y empuja a decisión humana antes que a un falso aprobado.

## 12. Criterios de aceptación (Definition of Done)
1. Un doc admitido continúa a revisión y la respuesta incluye `revision.hallazgos` con dimensión, severidad, estado, razonamiento.
2. Tier 1 produce métricas reales (blur/Laplaciano, DPI, OCR conf) y presencia de secciones; un escaneo borroso da hallazgo de legibilidad.
3. Tier 2 corre las reglas del template (patrón/unidad/tabla) y un cuadro de cargas inconsistente genera hallazgo `mayor`.
4. Tier 3 agrega observaciones VLM con severidad sugerida, sin producir bloqueantes por sí solo.
5. La severidad agregada deriva el verdicto (`APROBADO`/`APROBADO_CON_NOTAS`/`OBSERVADO`/`RECHAZADO`) según §5.3.
6. La UI muestra hallazgos agrupados por dimensión, con salto a bbox en la previsualización, y resuelve el verdicto vía `…/revision/decision`.
7. Checks no verificables se muestran como `no_verificable`, nunca como `ok`.
8. El template de plano eléctrico (§10) corre end-to-end como piloto.
