# Guía de la UI — Cotejar

> Recorrido de las pantallas y conceptos de la interfaz. Espejo de la **Ayuda en la app** (botón
> **? Ayuda** arriba a la derecha, componente `frontend/src/components/Help.tsx`). Para el detalle del flujo
> de revisión de contenido ver [REVISION_UI.md](REVISION_UI.md); para la arquitectura, [ARCHITECTURE.md](ARCHITECTURE.md).

La app tiene **sidebar** (Validar · Templates · Observatorio · Historial), **header** (título + subtítulo +
botón **Ayuda**) y el contenido de cada pantalla. Tema claro, acento petróleo (`#0e7c86`).

## Sistema de diseño (compartido)
Las pantallas de administración (Templates, Observatorio, Historial) comparten lenguaje visual y código:
`frontend/src/design/facets.tsx` centraliza **colores/etiquetas por eje** (`FACET_AXIS`), la **barra de
progreso** (`Bar`), los **chips de faceta etiquetados** (`FacetChips`) y la **tarjeta de métrica** (`Stat`).
Los hover/animaciones viven en `frontend/src/screens/Templates.css`.

**Ejes (facetas) y su color:** Tipo (teal) · Empresa (índigo) · Disciplina (slate) · Jurisdicción (ámbar) ·
Proyecto (violeta).

**Madurez (calibración por ejemplos):** `Solo reglas` (0–1) → `Calibrando` (2–4) → `Calibrado` (≥5, decisivo).

## Validar documento
Subís un PDF y elegís un **template**. Corre el **gate de admisión** (rápido) y, si admite, la **revisión de
contenido** (todo el documento) con hallazgos ubicados por hoja; observación visual (IA) a pedido. Detalle
completo en [REVISION_UI.md](REVISION_UI.md).

## Templates de referencia
Catálogo de **familias** de documento (cada una = un template con su tipo, reglas/normas y ejemplos de
calibración). No es un árbol fijo: las familias se ubican por **facetas**.

- **Pivot (tabla dinámica):** la barra **"Pivot — agrupar en orden"** define el **orden de los ejes**; la
  lista se agrupa **anidada** y **colapsable**. Reordená un eje con **‹ ›**, sumá con **+ Eje**, quitá con
  **✕**; **colapsar/expandir todo**.
- **Filtros:** por faceta (eje + valor), búsqueda por nombre/id.
- **Facetas por familia:** chips etiquetados (`Empresa: Camuzzi`, `Proyecto: CAREM25`…). Clic en un chip
  filtra por ese valor.
- **Madurez:** chip de estado + barra de progreso + sub-texto ("3/5 · faltan 2 para decidir"). Una familia
  nueva puede **heredar** ejemplos de su familia genérica (`↳ hereda …`) hasta tener propios.
- **3 vistas** (selector arriba): **A** tabla · **B** pivot + panel de detalle · **C** tarjetas.
- El detalle de una familia (lápiz / "Editar reglas y ejemplos" / "Ver reglas" / "Calibrar") abre el editor
  de reglas, ejemplos y zonas.

`GET /api/tipos` expone las facetas y `hereda_de`; `GET /api/facetas` el registro de etiquetas por eje.

## Observatorio de reglas
Planilla de **todas las reglas** con su **estadística de cumplimiento** + el **feedback humano**, facetada.

- **Resumen:** reglas en vista · cumplimiento promedio · con juicio «regla mal».
- **Pivot** por **Norma · Severidad · Disciplina** (misma mecánica que Templates).
- **% de cumplimiento** = `ok / (ok + fallo)` (sobre lo verificable), barra verde/ámbar/rojo.
- **Feedback:** 👍 de acuerdo · 🚫 no aplica · ⚠ regla mal. El indicador **↗ norma** marca juicios con
  **alcance** norma/global (se reusan en todas las familias que usan la regla).
- **Expandir una regla** → desglose **por familia** (facetas etiquetadas + % + feedback).

`GET /api/reglas/estadisticas` agrega por regla (global y por familia) + feedback.

## Historial y auditoría
Todas las validaciones registradas.

- **Resumen:** validados · % de aprobación · pendientes · promovidos a referencia.
- **Filtros:** búsqueda (documento/template) + chips de **veredicto** con conteo en vivo.
- **Tabla:** documento (badge `↑ ref` si fue promovido) · template · veredicto · score · fecha.
- **Detalle** (clic en una fila): análisis completo + panel de **decisión**: un revisor sénior puede
  **sobrescribir** la decisión y **promover** el documento a referencia (mejora el template) o marcarlo como
  **contra-ejemplo**.

## Ayuda y tooltips
- **Botón "? Ayuda"** (header): abre el modal con esta guía resumida (`Help.tsx`).
- **Tooltips** (`title`) en los controles: selector de vistas, etiqueta del pivot, controles de eje (‹ › ✕),
  tarjetas de resumen, % de cumplimiento, severidad, chips de faceta y de feedback, badge de herencia, etc.
