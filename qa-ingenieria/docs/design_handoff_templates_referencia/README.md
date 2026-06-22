# Handoff: Cotejar — Pantalla "Templates de referencia"

## Overview
Rediseño de la pantalla **Templates de referencia** de *Cotejar*, una app web interna de escritorio (en español) para una oficina de ingeniería que controla la admisión y revisión de documentos técnicos (P&IDs, planos, memorias, hojas de datos, esquemáticos).

La pantalla es el **catálogo de "familias" (templates)** de documento. Cada familia define qué tipo de documento es, qué reglas/normas se le exigen y con qué ejemplos se calibró su reconocimiento. El concepto central es una **taxonomía facetada** (no un árbol fijo): el usuario arma una tabla dinámica eligiendo el ORDEN de los ejes y agrupando anidado por ellos (como un pivot de Excel).

El prototipo entrega **3 direcciones de layout** conmutables desde un selector en el header. El developer puede implementar una, dos o las tres según se decida.

## About the Design Files
El archivo de este bundle (`Templates de referencia.dc.html`) es una **referencia de diseño creada en HTML** — un prototipo que muestra el aspecto y comportamiento buscados, **no código de producción para copiar tal cual**. Internamente usa un micro-runtime propietario (`support.js`, no incluido ni relevante): **no lo reproduzcas**. La tarea es **recrear estos diseños en el entorno existente del codebase destino** (el brief pide **React + TypeScript + CSS plano, sin librería de componentes pesada, íconos estilo Lucide**), siguiendo sus patrones establecidos. Si no hay entorno aún, React + TS + CSS Modules / vanilla CSS es la elección recomendada por el brief.

Para ver el prototipo en vivo: abrir `Templates de referencia.dc.html` en un navegador.

## Fidelity
**Alta fidelidad (hifi).** Colores, tipografía, espaciados, estados e interacciones son finales. Recrear pixel-perfect con las librerías/patrones del codebase. La tipografía es la **font stack del sistema** (no requiere fuente custom).

---

## Modelo de datos

### Familia (template)
```ts
type Maturity = 'solo_reglas' | 'calibrando' | 'calibrado';

interface Family {
  id: string;              // id técnico, p.ej. "pid_camuzzi" (se muestra en monospace)
  name: string;            // nombre legible
  // Coordenadas en ejes ortogonales (facetas). null = "sin valor" en ese eje.
  tipo: string | null;       // P&ID | Plano | Memoria | Hoja de datos | Esquemático | Diagrama
  empresa: string | null;    // Camuzzi | EPA / Brown & Caldwell | …
  disc: string[];            // disciplina(s) — MÚLTIPLE; [] = sin valor
  juris: string | null;      // AR | US
  proyecto: string | null;   // AABBCC | PANDA
  disciplinas: string[];     // tags de disciplina completos para mostrar (distinto de la faceta `disc`)
  examples: number;          // nº de ejemplos / "referencias (N docs)" con que se calibró
  inheritsFrom?: string;     // id de otra familia de la que hereda ejemplos
  maturity: Maturity;        // estado de calibración (ver abajo)
}
```

**Ejes / facetas** (orden canónico) con su color de acento:
| key | label | color |
|---|---|---|
| `tipo` | Tipo | `#0e7c86` (teal) |
| `empresa` | Empresa | `#4f46e5` (indigo) |
| `disc` | Disciplina | `#475569` (slate) |
| `juris` | Jurisdicción | `#b45309` (ámbar) |
| `proyecto` | Proyecto | `#9333ea` (violeta) |

> Nota importante: la faceta `disc` (coordenada de pivot, puede ser múltiple) es **distinta** de `disciplinas` (lista completa de tags que se muestra en la fila/tarjeta). Ej: *Plano genérico* tiene `disc: []` (sin valor en el eje) pero `disciplinas: ['civil','mecánica','eléctrica']`.

### Madurez (calibración)
Umbral configurable `T` (default **5**). Define color, label y mensaje:

| maturity | label | rango ejemplos | fg | bg | border | dot | sub-texto |
|---|---|---|---|---|---|---|---|
| `solo_reglas` | Solo reglas | 0–1 | `#5b6b78` | `#eef1f4` | `#dce3e8` | `#94a3b8` | si hereda → `sin ejemplos · hereda de <id>`; si no → `<ex>/T · sumá <max(2-ex,1)> para calibrar` |
| `calibrando` | Calibrando | 2–4 | `#946312` | `#fdf4e3` | `#f0ddb6` | `#e0a32e` | `<ex>/T · faltan <T-ex> para decidir` |
| `calibrado` | Calibrado | ≥5 (≥T) | `#0d6b53` | `#e4f4ee` | `#c3e7da` | `#12a87f` | `<ex> ejemplos · decisivo` |

Barra de progreso: `pct = min(100, round(ex / T * 100))`, color = `dot` del estado. En el panel de detalle se dibuja además una **marca de umbral "calibrando"** en `min(100, round(2/T*100))%`.

### Datos de ejemplo (11 familias reales — usar tal cual)
| id | name | tipo | empresa | disc | juris | proyecto | disciplinas | examples | inheritsFrom | maturity |
|---|---|---|---|---|---|---|---|---|---|---|
| pid_instrumentacion | P&ID / Diagrama de instrumentación | P&ID | — | [instrumentación] | — | — | instrumentación, procesos | 9 | — | calibrado |
| pid_camuzzi | P&ID Camuzzi (gas) | P&ID | Camuzzi | [instrumentación] | AR | — | instrumentación, procesos, gas | 0 | pid_instrumentacion | solo_reglas |
| pid_efluentes | P&ID Planta de efluentes | P&ID | EPA / Brown & Caldwell | [instrumentación] | — | — | instrumentación, procesos | 11 | — | calibrado |
| memoria_electrica | Memoria de cálculo eléctrica | Memoria | — | [eléctrica] | — | — | eléctrica | 0 | — | solo_reglas |
| memoria_estructural | Memoria de cálculo estructural | Memoria | — | [estructural] | — | — | estructural | 0 | — | solo_reglas |
| plano_generico | Plano genérico (dibujo técnico) | Plano | — | [] | — | — | civil, mecánica, eléctrica | 0 | — | solo_reglas |
| plano_electrico_unifilar | Plano eléctrico / unifilar | Plano | — | [eléctrica] | — | — | eléctrica | 0 | — | solo_reglas |
| hoja_datos_recipiente | Hoja de datos de recipiente a presión (ASME VIII-1) | Hoja de datos | — | [mecánica] | — | — | mecánica, procesos | 0 | — | solo_reglas |
| hd_2 | Hojas de Datos · Proyecto AABBCC | Hoja de datos | — | [mecánica] | — | AABBCC | mecánica | 4 | — | calibrando |
| esquematico_electronico | Esquemático electrónico | Esquemático | — | [electrónica] | — | — | eléctrica, electrónica | 3 | — | calibrando |
| pandacarrierelectrico | Panda Carrier Eléctrico | Plano | — | [eléctrica] | — | PANDA | eléctrica | 0 | — | solo_reglas |

---

## App shell (común a todas las vistas)

Layout raíz: `display:flex; height:100vh; overflow:hidden`. **Sidebar fijo (248px)** + **columna main (flex:1)**.

### Sidebar (`width:248px`, `background:#0c2030`, texto `#cdd9e2`)
- **Brand**: cuadro 34×34 `border-radius:9px` con gradiente `linear-gradient(150deg,#13a3a3,#0a6a78)` e ícono Lucide `shield-check` blanco. Título "Cotejar" (`#fff`, 16px, 700) + subtítulo "GATE DE ADMISIÓN" (10px, 700, `letter-spacing:1.5px`, `#5e7a8c`).
- **Grupos de nav** con label (10px, 700, `letter-spacing:1.5px`, `#566f80`):
  - FLUJO → "Validar documento" (ícono shield-check)
  - ADMINISTRACIÓN → **"Templates de referencia" (ACTIVO)**, "Observatorio de reglas" (bar-chart), "Historial y auditoría" (clock)
  - Item activo: `background:#0e7c86; color:#fff; font-weight:600; border-radius:8px; box-shadow:0 2px 10px rgba(14,124,134,.4)`. Inactivos: `color:#aebeca`, hover `background:#13293a`.
  - Padding item: `9px 11px`, gap ícono-label `11px`, ícono 17px stroke 1.9.
- **Footer** (`margin-top:auto`): card "PENDIENTES DE REVISIÓN" (`background:#102536; border:1px solid #1d3548; border-radius:10px`) con número grande `2` (24px, 700, `#e0a32e`) + "documentos en cola"; debajo avatar circular 30px "MR" (`background:#2a4b5e; color:#cfe3ee`) + "M. Rossi" / "Revisor sénior".

### Header (`background:#fff; border-bottom:1px solid #e2e8ec; padding:18px 28px`)
- Título `h1` "Templates de referencia" (20px, 700, `letter-spacing:-.2px`, `#13252f`) + subtítulo (13px, `#6b7d89`): "Definí tipos de documento, sus reglas y los ejemplos con los que calibra el reconocimiento."
- A la derecha: **selector de vista** (segmented control) + botón primario.
  - Segmented: contenedor `background:#eef1f3; border-radius:9px; padding:3px`. Cada tab: `padding:7px 12px; border-radius:7px; font:12px/600`. Activo: `background:#fff; color:#0e7c86; box-shadow:0 1px 3px rgba(20,40,55,.12)`. Inactivo: `color:#6b7d89; background:transparent`. Cada tab lleva una etiqueta-letra (A/B/C) `10px/800 opacity:.6` antes del label: "Tabla pivot", "Pivot + panel", "Tarjetas".
  - Botón **"+ Nuevo template"**: `background:#0e7c86; color:#fff; 13px/600; padding:9px 15px; border-radius:9px; box-shadow:0 2px 8px rgba(14,124,134,.3)`, ícono Lucide `plus`. Hover `#0b6b74`.

### Toolbar (`background:#fff; border-bottom:1px solid #e7edf0; padding:14px 28px`) — común a A, B y C
Dos filas, gap 11px:

**Fila 1 — Pivot:**
- Label: ícono Lucide `list-filter`/`align` teal + "Pivot — agrupar en orden" (12.5px/700, `#34495a`).
- **Chips de eje** (uno por eje en `order`, reordenables): `border:1.5px solid <axisColor>; border-radius:8px; padding:3px 3px 3px 9px`. Contiene: dot 7px del color del eje, número de orden (9.5px/800 `#9aa7b0`), label del eje (12.5px/700 `#2b3a45`), y 3 botones: **‹** (mover antes), **›** (mover después), **✕** (quitar). Botones ‹ › : `background:#f0f3f5; 20×22; border-radius:5px`. ✕: transparente, hover `background:#fdeceb; color:#d0473e`.
- **Botones "+ <Eje>"** para los ejes no usados: `border:1.5px dashed #c7d2da; border-radius:8px; padding:5px 11px; 12.5px/600; color:#5d7180`. Hover `border-color:#0e7c86; color:#0e7c86; background:#f2fafa`.
- A la derecha: "colapsar todo" / "expandir todo" (links 12px/600 `#5d7180`, hover bg `#eef1f3`).
- **Orden por defecto: `['tipo','disc']`.**

**Fila 2 — Filtros (feedback en vivo):**
- **Buscar**: input con ícono lupa, `border:1px solid #dce3e8; border-radius:8px; padding:7px 10px 7px 30px; width:220px; background:#fafbfc`. Placeholder "Buscar familia o id…". Filtra por `name` o `id` (case-insensitive).
- Label "MADUREZ" (11.5px/600 `#9aa7b0`) + **3 chips toggle** (Solo reglas / Calibrando / Calibrado): pill `border-radius:20px; border:1.5px solid <border>; background:<bg>` con dot + label (12px/600) + **conteo en vivo** (badge `background:rgba(255,255,255,.65); border-radius:9px`). Chips no seleccionados cuando hay selección activa → `opacity:.4`. El conteo se calcula sobre el set filtrado por búsqueda+faceta (NO por madurez), para que togglear madurez no ponga los demás en cero.
- **Chip de faceta activa** (cuando se clickea una faceta en una fila/tarjeta): `background:#eef7f8; border:1px solid #bfe0e4; border-radius:20px`, texto `"<Eje>: <valor>"` (`#0b6b74`) + ✕ para limpiar.
- A la derecha: contador "**N** de 11 familias".

### Content area
`flex:1; overflow:auto; padding:20px 28px 40px`. Estado vacío (sin resultados): centrado, "Sin resultados" + "Ninguna familia coincide con los filtros activos." + botón "Limpiar filtros".

---

## Vistas / Direcciones

### A — Tabla pivot mejorada (evolución del diseño actual)
Card blanco (`border:1px solid #e4eaee; border-radius:12px; box-shadow:0 1px 3px rgba(20,40,55,.05)`). Tabla con **grid de 6 columnas**: `2.3fr 1.5fr 1.2fr 74px 1.15fr 58px`.
- **Header de columnas** (`background:#f7f9fa; border-bottom:1px solid #e7edf0; 10.5px/700; letter-spacing:.6px; color:#90a0aa`): TIPO DE DOCUMENTO · FACETAS · DISCIPLINAS · REF. (centrado) · MADUREZ · (acciones).
- **Filas de grupo** (anidadas, una por nivel del pivot): full-width, `padding:9px 18px` + `padding-left` por profundidad (`18 + depth*20` px). Contienen: caret chevron (rota `rotate(-90deg)` colapsado → `0deg` abierto, `transition:transform .18s`), label del eje en mayúsculas (10px/800 color del eje), valor del grupo (13.5px/700; si "sin valor" → itálica `#aab4bb`), y badge de conteo (`background:#eef2f4; border-radius:10px`). Fondo nivel 0 `#f4f7f8`, niveles internos `#fafbfc`. Click togglea colapso. Hover `#eef4f5`.
- **Filas hoja (familia)** en el grid de 6 columnas, `padding:12px 18px; border-bottom:1px solid #eef2f4`; primera celda con `padding-left = 4 + order.length*20`. Animación de entrada `czfade .2s`. Hover `background:#fafcfc`.
  1. **Documento**: nombre (13.5px/600 `#1c2c36`) + fila con id en monospace (11px `#8597a2`) y, si hereda, badge "↳ hereda <id>" (10.5px `#a07a2e; background:#fdf6e7; border:1px solid #f0e2bf`).
  2. **Facetas**: chips clicables de `tipo/empresa/juris/proyecto` con valor (solo los no nulos): `background:#f6f8f9; border:1px solid #e6ecef; border-radius:6px`, dot cuadrado 6px del color del eje + valor (11.5px `#3f5260`). Click → setea filtro por esa faceta. Hover `border-color:<axisColor>`.
  3. **Disciplinas**: tags `background:#eef2f4; border-radius:5px; 11px; color:#52646f`.
  4. **Ref.**: número (14px/700; `#2b3a45` si >0, `#b6c0c7` si 0) + "docs" (9.5px `#a3b0b8`).
  5. **Madurez**: chip de estado (dot + label, ver tabla) + barra de progreso (alto 5px, `background:#edf1f3`, fill color del estado) + sub-texto (10px `#94a3ab`).
  6. **Acciones**: botón editar (Lucide `pencil`/`edit-3`) y borrar (Lucide `trash`), 28×28 `border-radius:7px; background:#f0f3f5`. Editar hover teal; borrar hover rojo `#d0473e`.

### B — Pivot compacto + panel de detalle
Grid de 2 columnas: `minmax(380px,1fr) 1.15fr`, gap 18px, `align-items:start`.
- **Izquierda**: mismo árbol pivot pero **compacto** — filas de grupo iguales (más chicas) y filas hoja como botones seleccionables: dot 9px del estado + nombre (13px/600, truncado) + id monospace (10.5px) + "<N> ref". La hoja seleccionada: `background:#eef7f8; border-left:3px solid #0e7c86`. Hover `#f3f9f9`.
- **Derecha — panel de detalle** (sticky top, `border-radius:12px`, animación `czpanel .22s`):
  - **Header**: gradiente `linear-gradient(180deg,#f8fafb,#fff)`. Nombre `h2` (17px/700 `#13252f`) + id monospace (12px `#7e8f9a`) + chip de madurez. Si hereda: nota "↳ Hereda ejemplos de **<id>** mientras no tenga propios." (`#a07a2e; background:#fdf6e7`).
  - **CALIBRACIÓN**: número grande (30px/700) + "ejemplos · objetivo T". Barra de progreso alto 9px con la **marca de umbral** (línea 2px `#c2cdd4` en `2/T%`). Leyenda: sub-texto del estado + "calibrando ≥2 · decisivo ≥T".
  - **COORDENADAS (FACETAS)**: lista de los **5 ejes** (incluye los "sin valor"). Cada fila: dot cuadrado del color del eje (gris `#cfd6db` si sin valor) + label del eje (11.5px/600, ancho fijo 92px) + valor (13px; "sin valor" en itálica `#aab4bb`; fila con `background:#fbfcfc`). Contenedor `border:1px solid #eef2f4; border-radius:9px`.
  - **DISCIPLINAS**: tags como en A (12px, `padding:3px 10px`).
  - **Acciones**: botón primario teal "Editar reglas y ejemplos" (Lucide `edit-3`) + botón secundario "Duplicar" (`border:1px solid #e1e8ec`).

### C — Tarjetas agrupadas por faceta
Secciones (`display:flex; flex-direction:column; gap:22px`) **agrupadas por el PRIMER eje del pivot**.
- **Banda de sección**: dot cuadrado 9px del color del eje + label del eje en mayúsculas (10px/800) + valor (15px/700; "sin valor" en itálica) + badge de conteo + línea divisoria flex `height:1px; background:#e1e8ec`.
- **Grid de tarjetas**: `repeat(auto-fill, minmax(310px,1fr))`, gap 14px.
- **Tarjeta** (`background:#fff; border:1px solid #e4eaee; border-radius:12px; padding:15px 16px; box-shadow:0 1px 3px rgba(20,40,55,.05)`; hover `border-color:#cfdbe1; box-shadow:0 4px 14px rgba(20,40,55,.09)`; animación `czfade .2s`), columna gap 11px:
  1. Header: nombre (14px/700) + id monospace; chip de madurez a la derecha.
  2. Barra de progreso (alto 6px) + sub-texto.
  3. Chips de facetas (`tipo/empresa/juris/proyecto`) + tags de disciplinas, mezclados en una fila wrap.
  4. Footer (`border-top:1px solid #eef2f4; padding-top:11px`): "**N** referencias" a la izquierda; a la derecha, si necesita calibración (`examples < T` y no calibrado) → botón punteado **"+ Calibrar"** (teal, invita a sumar ejemplos); si calibrado → botón "Ver reglas".

---

## Interacciones & comportamiento

| Acción | Comportamiento |
|---|---|
| Reordenar eje (‹ ›) | Swap del eje con su vecino en `order`; **resetea el colapso**. |
| Quitar eje (✕) | Remueve del `order`; resetea colapso. |
| Agregar eje (+ Eje) | Append al `order`; resetea colapso. |
| Click fila de grupo | Togglea colapso de ese grupo (por `gKey` = path acumulado `…>eje:valor`). |
| colapsar/expandir todo | Setea `collapsed` = todas las `gKey` del árbol actual / vacío. |
| Click chip de faceta (en fila/tarjeta) | Setea `facet = {axisKey, value}` (no aplica a "sin valor"). |
| Toggle chip de madurez | Agrega/quita del set `maturity`. Set vacío = todos. |
| Buscar | Filtra por `name`/`id` (substring, lowercase). |
| Cambiar vista (A/B/C) | Cambia `view`. |
| Click hoja (vista B) | Setea `selected = id`. |
| Limpiar filtros | `search=''`, `facet=null`, `maturity=∅`. |

**Animaciones / keyframes:**
- `czfade`: `opacity 0→1, translateY(4px)→0`, ~.2s — filas hoja y tarjetas.
- `czpanel`: `opacity 0→1, translateX(10px)→0`, ~.22s — panel de detalle (B).
- Caret de grupo: `transition:transform .18s`.
- Barras de progreso: `transition:width .3s`.
- Foco visible: `outline:2px solid #0e7c86; outline-offset:1px` en inputs y botones.

**Construcción del pivot (algoritmo a replicar):**
1. Filtrar familias por búsqueda + faceta + madurez.
2. Aplanar recursivamente a una lista de filas (`group` | `leaf`) según `order`:
   - En cada nivel, agrupar por `valuesFor(family, axisKey)` → para `disc` es el array (multi: una familia puede caer en varios grupos); para el resto, `[value || '—']`. `'—'` se ordena **al final** ("sin valor").
   - Por cada grupo se emite una fila `group` (con `gKey` acumulado); si no está colapsado, se recursiona; al llegar al fondo (`depth === order.length`) se emiten las filas `leaf`.
   - Profundidad → indentación (`padding-left`).
3. Conteos de madurez en vivo se calculan sobre el set filtrado por búsqueda+faceta (sin aplicar el filtro de madurez).

## State management
```ts
interface ScreenState {
  view: 'A' | 'B' | 'C';        // default 'A'
  order: string[];              // ejes activos del pivot, default ['tipo','disc']
  collapsed: Set<string>;       // gKeys colapsadas
  maturity: Set<Maturity>;      // filtro de madurez (vacío = todos)
  search: string;
  facet: { axisKey: string; value: string } | null;
  selected: string | null;      // id de familia (vista B), default 'pid_efluentes'
}
```
Parámetros configurables (en el prototipo expuestos como "tweaks"): `defaultView` (A/B/C), `calibratedThreshold` (T, default 5, rango 3–10), `showInheritance` (boolean — muestra/oculta las notas "hereda de"). Todo el estado es local en cliente; no hay fetching en el mock (datos embebidos). En producción, las familias vendrían de la API.

## Design tokens
**Colores**
- Sidebar: `#0c2030` (bg), `#102536` (card), `#1d3548` (border), `#cdd9e2` / `#aebeca` (texto), `#566f80` / `#5e7a8c` (labels/muted), `#2a4b5e` (avatar).
- Acento teal/petróleo: `#0e7c86` (primario), `#0b6b74` (hover), `#0b6b74` (texto sobre tint), `#13a3a3`/`#0a6a78` (gradiente brand).
- Fondo app: `#eef1f3`. Superficies: `#fff`. Bordes: `#e4eaee` / `#e7edf0` / `#eef2f4`. Headers de tabla: `#f7f9fa`.
- Texto: `#13252f` (títulos), `#1c2c36` (fuerte), `#2b3a45` / `#3f5260` (cuerpo), `#6b7d89` / `#7e8f9a` / `#90a0aa` (secundario), `#aab4bb` (sin valor).
- Ejes: tipo `#0e7c86`, empresa `#4f46e5`, disc `#475569`, juris `#b45309`, proyecto `#9333ea`.
- Madurez: ver tabla de Madurez (fg/bg/border/dot por estado).
- Alertas: ámbar `#e0a32e`; herencia `#a07a2e`/`#fdf6e7`/`#f0e2bf`; borrar/rojo `#d0473e`/`#fdeceb`.

**Tipografía**: font stack del sistema (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`). IDs técnicos en monospace (`ui-monospace, SFMono-Regular, Menlo, monospace`). Escala usada: 9.5–11px (labels/meta), 11.5–13.5px (cuerpo/celdas), 14–17px (nombres/títulos de card), 20px (título de pantalla), 24–30px (números grandes). Pesos 500/600/700/800.

**Radios**: 5–6px (chips/tags/botones-icon), 7–9px (botones/pills/inputs), 10–12px (cards), 20px (pills de filtro), 50% (avatar/dots).

**Sombras**: card `0 1px 3px rgba(20,40,55,.05)`; card hover `0 4px 14px rgba(20,40,55,.09)`; botón primario `0 2px 8px rgba(14,124,134,.3)`; nav activo `0 2px 10px rgba(14,124,134,.4)`; tab activo `0 1px 3px rgba(20,40,55,.12)`.

**Espaciado**: paddings de sección 14–28px; gaps 4–18px; indentación de pivot 20px por nivel.

## Assets
- **Íconos**: estilo **Lucide** (usar `lucide-react` o equivalente). Usados: `shield-check`, `layers`, `bar-chart`, `clock`, `plus`, `align-left`/`list-filter`, `chevron-down`, `pencil`/`edit-3`, `trash`, `search`, `x`. En el prototipo son SVG inline con stroke `currentColor`, width ~13–17px, stroke 1.9–2.2.
- **Sin imágenes ni fuentes custom.** Avatar "MR" es texto sobre círculo.

## Files
- `Templates de referencia.dc.html` — prototipo hifi con las 3 direcciones (referencia visual y de comportamiento). Toda la lógica de pivot/filtros/datos está dentro (datos mock embebidos, ver la sección de datos arriba).

> El `<script src="support.js">` y la sintaxis `<x-dc>`/`<sc-for>`/`{{ }}` del archivo son del runtime de prototipado — **ignorarlos**. Reimplementar con React + TS + CSS plano según este README.
