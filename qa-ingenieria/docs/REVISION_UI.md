# Revisión de contenido — guía del flujo en la UI

> Cómo se ve y se usa la **revisión de contenido (Fase 1)** en la pantalla de Validar. Es el "segundo
> gate": una vez que un documento fue **admitido** (Fase 0), la revisión mira si el **contenido** es
> bueno y cumple la norma. Pensada para que un revisor entienda qué está viendo y decida con evidencia.

## Las dos preguntas (no confundirlas)

| Gate (Fase 0) | Revisión (Fase 1) |
|---|---|
| **¿Es lo que dice ser?** identidad + completitud | **¿El contenido es bueno y cumple?** calidad + norma |
| Veredicto: 🟢 válido · 🟡 revisión manual · 🔴 inválido | Veredicto: **aprobado · con notas · observado · rechazado** |
| Mira la **portada/cajetín** (rápido) | Mira **todo el documento** (más lento) |

Solo los documentos **admitidos** entran a revisión.

## El flujo en pantalla (dos pasos)

```mermaid
flowchart LR
  U["Subís PDF + elegís template"] --> G["PASO 1 · Gate (admisión)<br/>rápido — se muestra enseguida"]
  G -->|admitido 🟢| R["PASO 2 · Revisión de contenido<br/>corre con barra de progreso (todo el doc)"]
  G -->|inválido 🔴| FIN1["Queda en el gate (no se revisa)"]
  R --> V["Sección 'Revisión de contenido'<br/>veredicto + hallazgos + ver en plano"]
```

1. **Paso 1 — Gate.** Apenas subís el documento, corre la admisión (rápida, mira la portada) y **se
   muestra el veredicto de admisión**. Ya podés leerlo.
2. **Paso 2 — Revisión.** Si el documento fue **admitido**, automáticamente arranca la revisión de
   contenido **cubriendo todo el documento**, con una **barra de progreso** ("Revisando el contenido…").
   No bloquea: seguís leyendo el gate mientras corre. Al terminar aparece la sección de revisión.

> **Toggle.** El checkbox *"Revisar contenido al admitir"* controla el paso 2. Si lo **destildás**, el
> documento queda admitido y la revisión no corre; aparece un botón **"Revisar contenido ahora"** para
> dispararla cuando quieras. (Para casos en *revisión manual* ámbar, la revisión arranca cuando un humano
> **aprueba** la admisión.)

## La sección "Revisión de contenido"

Aparece debajo del veredicto de admisión, con tres partes:

**1. Banner del veredicto de revisión** — uno de:

| Veredicto | Significado |
|---|---|
| 🟢 **Aprobado** | sin hallazgos accionables |
| 🟢 **Aprobado con notas** | solo observaciones menores |
| 🟡 **Observado** | hay algo *mayor* que corregir |
| 🔴 **Rechazado** | hay un *bloqueante* |
| ⤴ **Pendiente senior** | escalado a revisión senior |

Si dice **"confiabilidad parcial"** es porque hubo checks **no verificables** (ver abajo): el dictamen
es incompleto y conviene una mirada humana.

**2. Hallazgos agrupados por dimensión** — *legibilidad · norma · contenido · consistencia*. Cada fila:

- **Ícono de estado**: ✓ cumple · ! a revisar · ✕ no cumple · **? no verificable**.
- **Severidad**: `bloqueante` (rojo) · `mayor` (ámbar) · `menor` (gris) · `observacion` (azul).
- **Chip de norma** (ej. `AEA 90364`): de qué norma/código sale el chequeo (trazabilidad).
- **Evidencia** + **razonamiento** + **sugerencia** de corrección.

**3. "Ver en plano"** — abajo, el documento **multipágina** con los hallazgos **dibujados encima** de la
hoja donde ocurren, coloreados por estado. Navegás **todas** las páginas (no solo 6): cada hoja se pide
al vuelo (no viaja en la respuesta). Es la misma observabilidad del gate, ahora sobre el contenido:
**se ve dónde cumple y dónde no.**

El visor además tiene un **buscador** que busca el texto en **todo el documento**: salta a la página y
**resalta** la coincidencia (la miniatura marca con un punto naranja las páginas con hits). Y un botón
**"abrir doc"** que abre el PDF original en una pestaña (visor nativo del navegador: Ctrl+F, zoom, scroll)
— útil para chequear rápido o para escaneos sin capa de texto donde la búsqueda interna no aplica.

## `no_verificable` — qué significa (importante)

El sistema **nunca inventa un "cumple"**. Si no puede medir algo, lo marca **no verificable**, por ejemplo:
- el **cuadro de cargas está dibujado** (no es una tabla real) → no se puede leer la columna;
- un **valor vive solo en la imagen** y no hay OCR;
- la hoja no se pudo renderizar;
- el documento es **casi puro dibujo** (P&ID/plano sin capa de texto): las reglas de texto que fallan por
  *ausencia* se degradan a `no_verificable` (no a `fallo`) → la confiabilidad queda **parcial** e invita a
  la observación visual, en vez de inflar el veredicto con falsos negativos. (umbral: `REVISION_MIN_CHARS_PAGINA`)

Un `no_verificable` **no cuenta como fallo**, pero **baja la confianza** y empuja a que un humano lo mire.

## Resolver la revisión

Abajo de los hallazgos podés fijar el veredicto humano (con notas opcionales):
**Aprobar · Aprobar con notas · Enviar a corrección (observado) · Rechazar · Escalar a senior.**
La decisión queda registrada; el veredicto automático es una ayuda, **decide la persona**.

## De dónde sale el chequeo de norma (el vínculo)

El template del tipo **referencia** las normas que le aplican (`revision.normas: [aea-90364]`). Al revisar:
1. **Detecta** si el documento **declara** esa norma (busca sus marcas en el texto). *Declarar la norma
   esperada es en sí un check.*
2. **Aplica** las reglas de la norma; cada hallazgo **cita la norma** (`norma_ref`).

Las normas viven en `knowledge/normas/<id>.yaml` (reutilizables entre templates). Para sumar una norma o
ajustar umbrales, se edita ese YAML; para asociarla a un tipo, se agrega a `revision.normas` del template.
Detalle técnico en [ARCHITECTURE.md](ARCHITECTURE.md) y el spec
[SPEC_Cotejar_Fase1_Revision.md](spec/SPEC_Cotejar_Fase1_Revision.md).

## Observación visual (IA) — a pedido

La revisión automática corre solo lo **determinista** (Tier 1 legibilidad + Tier 2 reglas/normas). La
**mirada del VLM** (Tier 3) es **a pedido**: en la sección *"Observación visual (IA)"* hay un botón
**"Pedir observación visual (IA)"**. Al apretarlo, un VLM mira el documento con los criterios de la norma
(símbolos, líneas, prolijidad, coherencia) y lista observaciones **no bloqueantes** (no cambian el veredicto
por sí solas; aparecen aparte de la grilla). Es deliberado porque es **caro/lento** — sobre todo útil en
**P&ID y planos** donde los datos viven en el dibujo y las reglas de texto no alcanzan.

## Probarlo

1. (una vez) Bajá documentos de ejemplo: `uv run python scripts/descargar_fixtures.py`.
2. En **Validar**, elegí el template **"Memoria de cálculo eléctrica"** y subí una memoria eléctrica.
3. Vas a ver el **gate** y, enseguida, la **revisión** con los checks de **AEA 90364** y dónde falla.

### Planos de prueba (norma IRAM dibujo técnico, espectro de cumplimiento)
`uv run python scripts/generar_planos_demo.py` crea 3 planos sintéticos en `tests/fixtures/docs/_sinteticos/`:
- **plano_cumple.pdf** → debería dar **aprobado** (rótulo, escala 1:50, cotas mm, proyección).
- **plano_parcial.pdf** → **aprobado con notas** (escala 1:30 no normalizada, cotas en cm, sin proyección).
- **plano_no_cumple.pdf** → **observado** (no declara IRAM, sin rótulo, sin escala, sin mm).
Validalos contra el template **"Plano genérico (dibujo técnico)"** (referencia `iram-dibujo`). *Nota:* el
gate (Fase 0) puede marcar el croquis como dudoso; si queda en revisión manual, aprobalo y la revisión corre.

### Planos REALES (deep research, `scripts/descargar_fixtures.py`)
En `tests/fixtures/manifest.yaml`, cada uno con su `caso` esperado.
- **Cumplen**: `plano_mec_cinta/eje`, `plano_arq_oasis`, `plano_mec_surcos`, `elec_unr_proyecto`,
  `instr_isa_ch7`, `instr_utn_frrq` → aprobado / con notas.
- **No cumplen** (para probar fallos): `pid_kimray` (tags dentro del gráfico → **observado**, es trabajo del
  VLM), `elec_ria_unifilar` (unifilar real que no cita AEA → **observado**), `plano_arq_oliva` (escala
  `1 EN 100` no normalizada → con notas).
