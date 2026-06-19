# Handoff: Cotejar — Sistema de carga y validación de documentos técnicos

## Overview
**Cotejar** es un "gate de admisión" documental: valida si un documento entregado (planos, memorias de cálculo, documentos legales) es válido contra un *template de referencia* previamente cargado. La UI está en español, orientada a un usuario administrativo que valida decenas de documentos por día y necesita leer el veredicto de un vistazo.

Tres ideas centrales que el diseño debe preservar:
1. **El veredicto no es binario.** Hay tres estados: `VÁLIDO` (verde), `INVÁLIDO` (rojo), `REVISIÓN MANUAL` (ámbar). El caso ámbar requiere decisión humana explícita.
2. **Dos dimensiones independientes** se evalúan y se muestran por separado: **Identidad/pertenencia** (¿es el tipo X de la empresa ABC?) y **Completitud/conformidad** (¿están todos los campos obligatorios?).
3. **Madurez del template + loop de aprendizaje.** Un template madura con la cantidad de ejemplos de referencia (`Solo reglas` → `Calibrando` → `Calibrado`). Cuando un documento se aprueba, puede **promoverse a documento de referencia**, lo que mejora la precisión futura. La similitud visual es un *check duro* solo si el template está calibrado; en `Solo reglas` se muestra como **informativa/no concluyente**.

## About the Design Files
El archivo de este bundle (`Cotejar.dc.html`) es una **referencia de diseño creada en HTML** — un prototipo interactivo que muestra el look y el comportamiento buscados, **no código de producción para copiar tal cual**. La tarea es **recrear este diseño en el entorno del codebase destino** (React, Vue, etc.) usando sus patrones y librerías establecidos. Si todavía no hay entorno, elegí el framework más apropiado (recomendado: React + TypeScript) e implementá ahí.

> Nota técnica sobre el formato: el prototipo está escrito como un "Design Component" — un único archivo con un template HTML (markup con holes `{{ }}`) y una clase de lógica `Component extends DCLogic` con `state`, handlers y un `renderVals()` que expone los valores al template. Es esencialmente un componente tipo React. Toda la lógica de estado descrita abajo está en ese bloque `<script data-dc-script>`. Podés abrir el archivo en un navegador para interactuar con él.

## Fidelity
**Alta fidelidad (hifi).** Colores, tipografía, espaciados e interacciones son finales. Recreá la UI de forma fiel usando las librerías/sistema de diseño del codebase. Los valores exactos están en *Design Tokens*.

---

## Screens / Views

La app tiene un **layout de shell fijo**: sidebar de 236px a la izquierda + panel principal scrolleable a la derecha (`display:flex; height:100vh`). El sidebar es persistente; el panel principal cambia según la sección activa. Tamaño base de fuente: 13px, line-height 1.45.

### Sidebar (persistente)
- **Ancho**: 236px, `flex:none`. Fondo `#0A363C` (petróleo profundo), texto `#CFE0E1`, borde derecho `#06292e`.
- **Marca** (arriba): cuadro 34×34 `border-radius:8px` fondo `#0E6E78` con ícono check; título "Cotejar" (16px/700, `#fff`) y subtítulo "GATE DE ADMISIÓN" (10.5px, `#6FA2A7`, letter-spacing .3px). Separador inferior `1px rgba(255,255,255,.07)`.
- **Nav** (2 grupos con encabezados 10px/600 `#5C8C91`):
  - Grupo "FLUJO": **Validar documento** (ícono escudo+check).
  - Grupo "ADMINISTRACIÓN": **Templates de referencia** (ícono capas), **Historial y auditoría** (ícono reloj).
  - Item activo: fondo `#0E6E78`, texto `#fff`, peso 600. Inactivo: fondo transparente, texto `#AFCBCD`, peso 500. Padding `9px 11px`, `border-radius:9px`, gap 11px con el ícono (17px).
- **Pie**: tarjeta "PENDIENTES DE REVISIÓN" (fondo `rgba(255,255,255,.05)`, radius 9px) con número `23` (IBM Plex Mono, 20px/600, `#F0C674`). Debajo, avatar circular 30px "MR" + "M. Rossi" / "Mesa de admisión".

### Header de sección (sticky)
Cada sección tiene un header sticky: fondo `rgba(234,238,238,.9)` + `backdrop-filter:blur(8px)`, borde inferior `#D7DEDF`, padding `18px 32px`. Título `h1` 20px/700 letter-spacing -.4px; subtítulo 12.5px `#5C6B71`.

El contenedor de contenido bajo el header: `max-width:1180px; margin:0 auto; padding:24–28px 32px 60px`.

---

### 1. Validar documento (pantalla de inicio)
Flujo de 3 etapas controlado por `state.stage`: `'upload'` → `'processing'` → `'result'`.

#### 1a. Etapa Upload (`stage === 'upload'`)
Grid de 2 columnas `1.4fr 1fr`, gap 22px, `align-items:start`.

- **Columna izquierda — tarjeta blanca** (`#fff`, borde `#DDE3E4`, radius 14px, padding 26px):
  - Eyebrow "PASO 1 · DOCUMENTO A VALIDAR" (11px/600, `#0E6E78`, letter-spacing .6px).
  - **Dropzone**: `<label>` con `<input type="file">` oculto. Borde `1.5px dashed`; estado vacío `#BFCBCC` sobre `#FAFCFC`, estado con archivo `#0E6E78` sobre `#F2FAFA`. Radius 12px, padding 34px, centrado. Ícono upload 40px. Texto principal 14px/600 (nombre del archivo o "Seleccioná un archivo para validar"); subtexto 12px `#7C8A8F` ("Arrastrá un PDF o imagen, o hacé clic para buscar · máx. 50 MB").
  - Eyebrow "PASO 2 · TEMPLATE DE REFERENCIA".
  - **Select** custom (appearance:none) fondo `#F7F9F9`, borde `#CBD4D5`, radius 9px, padding `12px 38px 12px 13px`, con chevron SVG absoluto a la derecha. Opciones muestran el tipo + madurez (ej. "Plano estructural tipo X — ABC · Calibrado").
  - Texto de ayuda 11.5px `#8A989E`.
  - **Botón "Validar documento"** (ancho completo, padding 13px, radius 10px, 14px/600, ícono escudo+check). Habilitado: fondo `#0E6E78`, texto `#fff`, cursor pointer. Deshabilitado (sin archivo o sin template): fondo `#C4D2D3`, `cursor:not-allowed`.
- **Columna derecha — aside "CÓMO FUNCIONA EL GATE"** (tarjeta blanca): 3 pasos numerados (cuadros 26px radius 7px fondo `#E6F0F1` texto `#0E6E78`/700) — Identidad, Completitud, Veredicto en 3 estados. Pie con 3 métricas (IBM Plex Mono 17px): umbral aprob. (verde `#1F8A5B`), umbral revisión (ámbar `#C2860E`), prom. análisis ~6s.

#### 1b. Etapa Processing (`stage === 'processing'`)
Tarjeta centrada `max-width:640px`, padding 34px. Spinner 30px (borde `#D7E4E5`, top `#0E6E78`, `animation:ct-spin .8s linear infinite`). Título "Validando documento…" + subtexto con nombre de archivo y template. Barra indeterminada 6px (gradiente teal con `animation:ct-bar 1.1s`). Lista de **5 pasos** que se completan secuencialmente (`state.procStep` 0→5, avanza con `setTimeout` a 400/950/1500/2050ms, y a 2550ms pasa a `result`):
1. Extrayendo texto (OCR)
2. Detectando rótulo / cajetín
3. Cotejando identidad (empresa · tipo)
4. Verificando campos obligatorios
5. Calculando score de similitud

Cada paso: dot 22px. Estado `done` = fondo `#1F8A5B` con ✓ blanco; `active` = borde 2px `#0E6E78`, `animation:ct-pulse 1s`; `pending` = borde `#DDE3E4`, texto `#C4CDCE`.

#### 1c. Etapa Result (`stage === 'result'`) — LA PANTALLA MÁS IMPORTANTE

**Banner de veredicto** (flex, justify-between, padding `22px 24px`, radius 14px). Colores según veredicto:
- `REVISIÓN MANUAL` (ámbar, default del demo): fondo `#FBF1DC`, texto `#855A06`, borde `#EBDDB6`, ícono cuadro `#C2860E` con glifo "!".
- `APROBADO` (tras aprobación manual): fondo `#E6F4EC`, texto `#145C3C`, borde `#C9E6D6`, ícono `#1F8A5B` con "✓".
- `RECHAZADO`: fondo `#FBEAE9`, texto `#8E2B27`, borde `#EBC9C6`, ícono `#C0413B` con "✕".
- Izquierda: cuadro de ícono 52px radius 13px + eyebrow "VEREDICTO" + label 24px/700 + resumen 12.5px (máx 560px).
- Derecha: nombre de archivo + template (IBM Plex Mono) + badge de madurez; separado por borde, el **score** grande (IBM Plex Mono 30px/600) con caption "SIMILITUD" o "NO CALIBRADO".

**Selector de vista del desglose** (segmented control): 3 opciones — `Dividida` (A), `Tarjetas` (B), `Compacta` (C). Controla `state.layout`. Pestaña activa: fondo `#0E6E78`, texto `#fff`. Contenedor blanco, borde `#CBD4D5`, radius 8px, padding 3px.

Las 3 variantes muestran **los mismos datos** (las dos dimensiones con sus checks), distinta disposición:

- **Vista A "Dividida"** — grid `1fr 1.25fr`. Izquierda (sticky): tarjeta de **previsualización del documento** (ver más abajo) + 2 cajas resumen (Identidad / Completitud) + toolbar Previsualizar/Descargar. Derecha: dos `<section>` apiladas, una por dimensión, cada una con header (ícono + título + nota) y filas de check.
- **Vista B "Tarjetas"** — grid `1fr 1fr`. Dos tarjetas, una por dimensión, con borde izquierdo de acento de 3px (verde si la dimensión pasa, ámbar si no), un pill de estado arriba a la derecha, y las filas de check.
- **Vista C "Compacta"** — una sola tarjeta densa. Header con miniatura clicable + nombre + dos pills (Identidad / Completitud). Luego dos grupos ("IDENTIDAD", "COMPLETITUD") con filas compactas: badge pequeño 18px + texto + detalle alineado a la derecha.

**Fila de check** (componente reusable): badge circular 22px (en C: 18px) + texto 12.5px/500 + detalle 11.5px. Estados:
- `pass`: ✓, color `#1F8A5B`, fondo badge `#E6F4EC`. Detalle en `#7C8A8F`.
- `fail`: ✕, color `#C0413B`, fondo `#FBEAE9`.
- `warn`: !, color `#C2860E`, fondo `#FBF1DC`.
- `info`: i, color `#5C6B71`, fondo `#EEF1F2`. (Se usa para "Similitud visual" cuando el template es `Solo reglas`.)

Ejemplos de filas (Identidad): "Rótulo detectado en posición esperada" ✓, "Código de empresa coincide (ABC)" ✓, "Código de tipo coincide (X)" ✓, "Logo / sello de la empresa presente" ✓, "Similitud visual con el template" (warn `87% · sobre umbral de revisión…` **o** info `Informativa — el template tiene 1 ejemplo…` si Solo reglas).
Ejemplos (Completitud): "Campo 'Número de plano' presente" ✓, "Escala" ✓, "Fecha" ✓, **"Campo 'Revisión' presente" ✕ — Falta el campo**, "Campo 'Firma' presente" ! (baja confianza), "Formato de código de empresa válido" ✓.

**Previsualización del documento** (en vista A): caja 100%×300px, fondo `#F4F7F7`, borde `#E2E8E8`, radius 10px, `overflow:hidden`, clicable (`cursor:zoom-in` → abre el modal de preview). Contenido placeholder de plano técnico: grilla de fondo (gradientes 26px), marco interior, dibujo SVG tenue, y un **recuadro resaltando el cajetín/rótulo** (borde 2px `#0E6E78`, fondo `rgba(14,110,120,.07)`, `box-shadow:0 0 0 4px rgba(14,110,120,.1)`) con etiqueta "Cajetín detectado · 87% match" y texto mono adentro.

**Footer de acciones / loop de promoción** (tarjeta blanca debajo del desglose):
- Estado pendiente (`state.decision === null`): nota ámbar "Este caso está en ámbar: la decisión final es humana…" + 3 botones a la derecha: **Descargar reporte** (neutro), **Rechazar** (outline rojo `#C0413B`/borde `#E3B7B4`), **Aprobar manualmente** (sólido verde `#1F8A5B`).
- Rechazado (`decision === 'rejected'`): barra `#FBEAE9` con ✕, "Documento rechazado", botón "Deshacer".
- Aprobado (`decision === 'approved'`): barra verde `#E6F4EC` con ✓ "Aprobado manualmente" + auditoría, y a continuación el **panel de promoción**:
  - Título "Promover a documento de referencia" + texto explicativo ("Se agregará «archivo» a los N ejemplos… cada aprobación humana entrena el template").
  - **Toggle** "Usar este documento para mejorar el template" (`state.promote`, default `true`). Switch: track 38×22 radius 12 (`#0E6E78` on / `#CBD4D5` off), knob 18px blanco que se desliza.
  - Botón **"Confirmar y promover"** (o "Confirmar sin promover" si el toggle está off; sólido `#0E6E78` / `#5C6B71`).
  - Tras confirmar (`state.promoted = true`): banner de éxito verde "Agregado como referencia · el template ahora tiene N+1 ejemplos" + nueva madurez, con botón "Ver template →".

---

### 2. Templates de referencia
`state.tplDetail === null` muestra la **lista**; con un id muestra el **detalle**. Botón "Nuevo template" (sólido teal) abre un **modal lateral**.

#### 2a. Lista
Tabla en tarjeta blanca. Header de columnas (grid `2.2fr .9fr 1fr .85fr 1.2fr .9fr 108px`, fondo `#FAFCFC`, labels 10.5px/600 `#7C8A8F`): TIPO DE DOCUMENTO · EMPRESA · DISCIPLINA · REFERENCIAS · MADUREZ · ACTUALIZADO · ACCIONES.
- Cada fila clicable (hover `#F7FAFA`) abre el detalle. Ícono de documento 30px en cuadro `#E6F0F1`. REFERENCIAS en IBM Plex Mono ("7 docs").
- **Badge de MADUREZ**: `Calibrado` = fondo `#E6F4EC`/texto `#145C3C`; `Calibrando` = `#FBF1DC`/`#855A06`; `Solo reglas` = `#EEF1F2`/`#5C6B71`. 10.5px/600, padding `3px 9px`, radius 6px.
- **Acciones** (3 botones 28px radius 7px, borde `#E2E8E8`): Editar (lápiz, `#5C6B71` — abre detalle en modo edición), Descargar (`#5C6B71`), Borrar (papelera `#C0413B` — elimina el template del estado). Los handlers llaman `e.stopPropagation()` para no disparar el click de fila.
- Nota al pie explicando la progresión de madurez.

Datos seed (4 templates): Plano estructural tipo X / ABC / Estructuras / 7 / Calibrado; Plano arquitectónico tipo A / Delta Ing. / Arquitectura / 9 / Calibrado; Memoria de cálculo MC-02 / ABC / Estructuras / 3 / Calibrando; Plano de instalación eléctrica / Delta Ing. / Eléctrica / 1 / Solo reglas.

#### 2b. Detalle del template
Header con botón "volver" (flecha) + título = tipo del template. Tres secciones apiladas (gap 18px):

1. **Calibración** (tarjeta): ícono + nombre + badge de madurez (o, en modo edición `state.editingTpl`, tres inputs editables tipo/empresa/disciplina). A la derecha, contador de referencias (IBM Plex Mono 22px `#0E6E78`) + "/ 5 ejemplos sugeridos" + barra de progreso 7px (color según madurez). Fila de acciones: **Editar datos** (toggle; "Listo" cuando edita, pasa a sólido teal), **Descargar template**, **Borrar template** (outline rojo, alineado a la derecha). Mensaje contextual coloreado según madurez ("Solo validás campos obligatorios…" / "Buen comienzo…" / "Umbral de similitud calibrado…").
2. **Documentos de referencia** (galería): grid `repeat(auto-fill, minmax(150px,1fr))`. Cada tile: miniatura 96px clicable (`cursor:zoom-in`, abre preview) con recuadro de cajetín teal; nombre en mono; fila con **tag** + 3 botones 24px (Previsualizar=ojo, Descargar, Borrar). El tag distingue origen: **"Promovido"** (fondo `#E6F0F1`/texto `#0E6E78`) vs **"Inicial"** (`#EEF1F2`/`#7C8A8F`). Tile final punteado "Agregar ejemplos" (`+`).
3. **Reglas de validación · campos del rótulo** (tarjeta): botón "Agregar campo". Header de columnas (grid `1.3fr 1.6fr auto auto`): CAMPO · PATRÓN ESPERADO (regex/formato) · REQUERIDO · (borrar). Cada fila editable: input nombre + input patrón (mono) + toggle "requerido" + botón borrar. Filas seed: Número de plano (`^PL-[0-9]{3,5}$`), Revisión (`^REV-[0-9]+$`), Escala (`^1:[0-9]+$`), Fecha (`DD/MM/AAAA`), Firma (sin patrón), Código de empresa (`^[A-Z]{3}$`), todas requeridas. Add/remove/toggle modifican `state.rules`.

#### 2c. Modal "Nuevo template" (`state.showNew`)
Panel lateral derecho 560px, slide-in, fondo overlay `rgba(16,36,42,.45)`. Header sticky con título y botón cerrar. Cuerpo: campos Tipo (full width) / Empresa / Disciplina; dropzone "Arrastrá PDF o imágenes…" con nota **"Podés empezar con uno solo e ir sumando ejemplos después para calibrar la similitud"**; sección de campos obligatorios (mismas filas editables que el detalle). Footer sticky: "Cancelar" + "Crear template".

---

### 3. Historial y auditoría
- **Strip de métricas**: 4 tarjetas (grid 4 col): Validados (mes) `1.284`; % de aprobación `78%` (verde); Pendientes revisión `23` (ámbar); Promovidos a referencia `61` (teal). Números en IBM Plex Mono 26px/600.
- **Tabla** (grid `1.6fr 2fr 1.3fr 0.8fr 1fr 1.1fr`): DOCUMENTO · TEMPLATE · VEREDICTO · SCORE · OPERADOR · FECHA. El documento muestra ícono + nombre (mono) y, si fue promovido, un tag "↑ ref" teal. VEREDICTO es un chip con los mismos colores de estado (pass/warn/fail). 6 filas seed cubriendo los tres veredictos.

---

### Modal de previsualización (reusable, `state.preview`)
Overlay `rgba(16,36,42,.55)`, panel centrado 780px (max 94vw / 90vh). Header: ícono doc + **input de nombre editable** (renombra; si es el documento subido actualiza `state.fileName`) + tag de origen + cerrar. Cuerpo scrolleable fondo `#EAEEEE`: hoja `aspect-ratio:1.414/1` (A-series) con el plano placeholder y el cajetín resaltado en grande. Footer: miniaturas de páginas (la activa con borde teal) + botones "Descargar" y "Cerrar". Se abre desde: miniatura/botón del documento subido (kind `'upload'`, nombre editable) y desde cada tile de la galería de referencias (kind `'ref'`).

---

## Interactions & Behavior
- **Navegación**: clic en items del sidebar cambia `state.section` (`validar` | `templates` | `historial`) y resetea detalle/modales.
- **Validación**: el botón se habilita solo con archivo + template seleccionados. Al validar, animación de processing (~2.55s con pasos secuenciales) y luego resultado.
- **Veredicto del demo**: siempre `REVISIÓN MANUAL` porque falta un campo obligatorio (Revisión); identidad confirmada; similitud en zona de revisión (o "no concluyente" si el template es `Solo reglas`). El texto del resumen y el caption del score se adaptan a la madurez del template elegido.
- **Decisión humana**: Aprobar/Rechazar/Deshacer cambian `state.decision`. Aprobar revela el panel de promoción.
- **Promoción**: toggle + confirmar → estado de éxito que comunica que el template "aprende" (sube ejemplos y madurez).
- **Gestión de documentos**: editar (inline en detalle de template), descargar (placeholder, no-op), borrar (quita del estado), previsualizar (modal). Aplica a templates, documentos de referencia y al documento subido.
- **Animaciones/keyframes**: `ct-fade` (entrada, **solo translateY — sin opacity**, .3s; importante: el contenido nunca debe depender de opacity:0 inicial), `ct-spin` (.8s linear, spinner), `ct-bar` (1.1s, barra indeterminada), `ct-pulse` (1s, paso activo). Transiciones de toggles/switches .15s.
- **Hover**: filas de tabla `#F7FAFA`; tiles de galería aclaran; miniaturas de preview `cursor:zoom-in`.

## State Management
Estado principal (en la clase `Component`):
- `section`: `'validar' | 'templates' | 'historial'`.
- `stage`: `'upload' | 'processing' | 'result'`; `procStep` (0–5); `fileName`; `selectedTemplate` (string).
- `layout`: `'A' | 'B' | 'C'` (vista del desglose; default vía prop `defaultLayout`).
- `decision`: `null | 'approved' | 'rejected'`; `promote` (bool); `promoted` (bool).
- `templates`: array `{id, tipo, empresa, disc, maturity, refs, score, date}` (mutable: editar/borrar).
- `tplDetail`: id o null; `editingTpl` (bool); `refDocs`: array `{id, name, tag, promoted}`; `rules`: array `{id, name, pattern, required}`; `showNew` (bool).
- `preview`: `null | {name, tag, promoted?, kind}`.

Transiciones clave: ver *Interactions*. Data fetching real (no presente en el prototipo): cargar/crear/editar/borrar templates, subir documento, ejecutar validación (devuelve veredicto + checks + score + bounding box del cajetín), aprobar/rechazar, promover a referencia.

## Design Tokens
**Colores**
- Fondo app: `#EAEEEE`. Superficie: `#FFFFFF`. Bordes: `#DDE3E4` / `#E2E8E8` / líneas suaves `#EDF1F1` `#F1F4F4`.
- Tinta: `#16242A` (texto principal), `#3A474C` (secundario), `#5C6B71` (mutado), `#7C8A8F` / `#8A989E` (terciario / faint).
- Marca/acento teal: `#0E6E78` (primario), `#0A363C` (sidebar profundo), `#E6F0F1` (teal 50), `#F2FAFA` (teal lavado).
- Verde (válido/aprobado): `#1F8A5B`, texto `#145C3C`, fondo `#E6F4EC`.
- Rojo (inválido/rechazado): `#C0413B`, texto `#8E2B27`, fondo `#FBEAE9`, borde `#E3B7B4`.
- Ámbar (revisión): `#C2860E`, texto `#855A06`, fondo `#FBF1DC`, borde `#EBDDB6`.
- Neutro/info & "Solo reglas": `#5C6B71` sobre `#EEF1F2`.

**Tipografía**
- Sans: **IBM Plex Sans** (400/500/600/700) — UI general. Base 13px, line-height 1.45.
- Mono: **IBM Plex Mono** (400/500/600) — códigos, scores, nombres de archivo, contadores, patrones.
- Escala observada: h1 20px/700 (-.4px); títulos de sección 14–16px/700; cuerpo 12.5–13px; labels/eyebrows 10.5–11px/600 (letter-spacing .5–.8px); detalles 11.5px; score grande 30px; métricas 26px.

**Espaciado / radios / sombras**
- Radios: botones/inputs 8–10px; tarjetas 13–14px; badges/chips/pills 5–6px; ícono-cuadros 7–10px; circulares 50%.
- Padding tarjetas: 16–26px. Gaps de grid: 12–22px. Contenedor: max-width 1180px, padding lateral 32px.
- Sombras: tarjetas casi planas; sombras solo en overlays/modales (`0 24px 60px rgba(0,0,0,.32)`, panel lateral `-8px 0 30px rgba(0,0,0,.18)`) y resalte del cajetín (`0 0 0 4px rgba(14,110,120,.1)`).

**Props/tweaks expuestos** (configurables): `defaultLayout` (A/B/C), `approvalThreshold` (default 96), `revisionThreshold` (default 85).

## Assets
- **Sin imágenes externas.** Todos los íconos son SVG inline (escudo+check, capas, reloj, documento, upload, download, papelera, lápiz, ojo, +, ✓/✕/!, chevron). Recreá con la librería de íconos del codebase (ej. lucide/heroicons) — los equivalentes: shield-check, layers, clock, file-text, upload, download, trash, pencil/edit, eye, plus, check, x, alert-triangle, chevron-down.
- La previsualización de planos es un **placeholder dibujado con CSS/SVG** (grilla + marco + dibujo tenue + recuadro de cajetín). En producción se reemplaza por el render real del documento con el bounding box del rótulo devuelto por el backend.
- Fuentes vía Google Fonts (IBM Plex Sans / IBM Plex Mono). Usá el equivalente del codebase si ya hay un sistema tipográfico.

## Files
- `Cotejar.dc.html` — prototipo completo (shell + las 3 secciones + modales + toda la lógica de estado). Abrilo en un navegador para interactuar. La clase de lógica (`Component extends DCLogic`) contiene `state`, los handlers y `renderVals()` con todos los estilos computados y datos seed referenciados arriba.
