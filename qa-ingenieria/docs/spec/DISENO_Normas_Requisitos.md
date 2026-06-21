# Diseño — Normas, requisitos chequeables y aplicabilidad aprendida

> Estado: **diseño acordado, sin implementar**. Captura el esquema decidido para evolucionar el vínculo
> documento ↔ norma de la revisión de contenido (Fase 1). Complementa
> [SPEC_Cotejar_Fase1_Revision.md](SPEC_Cotejar_Fase1_Revision.md) y [../REVISION_UI.md](../REVISION_UI.md).

## 1. El problema

- Una **familia** (template/`tipo_doc`) define qué ES un documento y los requisitos de **pertenencia**
  (identidad + completitud, Fase 0).
- Las **normas/códigos de diseño** que un documento debe cumplir son **transversales a las familias** y
  dependen de varios factores (disciplina, jurisdicción, proyecto/cliente, subtipo), no solo de la familia.

→ El error a evitar: que la familia "posea" las normas. Es un **muchos-a-muchos**.

## 2. Los tres conceptos (no mezclarlos)

| Concepto | Qué es | Rol |
|---|---|---|
| **Familia** (template) | identidad + completitud | qué tipo de doc es |
| **Norma** (catálogo) | id + detección (anclas) + **agrupa requisitos** | procedencia + atajo |
| **Requisito** (elemento chequeable) | regla atómica (`presencia`/`patron`/`norma_lookup`/`tabla`) + `norma_ref` + tags (disciplina, severidad) | **la unidad que se asigna** |

La unidad que se asigna a una familia **no es la norma sino el requisito**. Un documento cumple un
**conjunto de requisitos** que puede mezclar varias normas.

## 3. Dónde viven (decisión)

Los requisitos viven **dentro de cada norma** (`reglas` en `knowledge/normas/<id>.yaml` — ya existen),
direccionables por id global **`<norma>:<id>`** (ej. `aea-90364:aea_caida_tension`). El **catálogo** es la
**vista plana** de todos los requisitos de todas las normas, con sus tags (disciplina, severidad, norma_ref).

## 4. Asignación a la familia (resolvedor)

El template declara un set componible:
```yaml
revision:
  normas: [iso-128]                       # atajo: TODOS los requisitos de esa norma (transversal)
  requisitos:                             # selección granular (de cualquier norma)
    - aea-90364:aea_caida_tension
    - cirsoc-201:cirsoc_recubrimiento     # un doc puede mezclar normas
  excluir: [aea-90364:aea_cuadro_cargas]
```
`resolver_requisitos(template)` = `expand(normas) ∪ requisitos − excluir`. La revisión corre ese set; cada
hallazgo cita su `norma_ref`. (Hoy ya funciona el atajo `normas:[...]`; falta el id global + `requisitos`/`excluir`.)

## 5. Aplicabilidad APRENDIDA (no estática) — decisión

El sistema **aprende qué requisitos exige cada familia** del corpus de casos, y **propone** (nunca
auto-aplica; mismo loop que las variantes de regex: propone → evidencia → humano confirma → se guarda al template).

**Señal principal (decidida): que los APROBADOS lo CUMPLAN.** Un requisito que pasa consistentemente en los
documentos aprobados de la familia se **confirma** como requisito real (n/N; madurez tras N aprobados — como
la auto-calibración del score). Señales secundarias:
- **Falla pero se aprueba igual** → sugerir **quitar/ajustar** (probablemente no aplica).
- **Edición humana** del template → refuerza el prior.
- **Lo que declaran los aprobados** (anclas) → candidato a agregar.

**Arranque en frío (decidido): prior por disciplina.** Una familia nueva hereda los requisitos de los
templates ya curados/aprobados de su **misma disciplina** (ej. nueva familia eléctrica → requisitos típicos
eléctricos), hasta tener casos propios.

### Matriz de confusión por requisito (resultado × decisión)

La señal no es "pasa en aprobados" a secas, sino el cruce **resultado del requisito × decisión humana**.
Pensamos cada requisito como un **clasificador de "este doc tiene un problema"** y lo medimos contra la
decisión:

| | Aprobado | Desaprobado |
|---|---|---|
| **Cumple (ok)** | **A** ✅ aplicable y satisfecho → confirma (madurez ↑). *Si cumple SIEMPRE (aprob.+rechaz.) → no discrimina* | **D** ➖ neutro para ese requisito (el rechazo fue por otra causa) |
| **No cumple (fallo)** | **B** ⚠️ conflicto → revisar (no auto-quitar) | **C** ✅✅ discrimina bien → la evidencia MÁS fuerte |

- **A — cumple+aprobado:** requisito real y satisfecho → confirma. Pero si además cumple en los rechazados
  (nunca falla) es **no discriminativo** → mantener como **informativo**, no bloqueante.
- **B — falla+aprobado (conflicto):** tres hipótesis que el humano desambigua (nunca se auto-quita):
  (1) **regla mal escrita** (falso negativo, p. ej. `mm²`) → dispara el **loop de variante** (proponer un
  patrón que cubra los aprobados); (2) **no aplica** → sugerir quitar/bajar severidad; (3) **aprobación
  laxa** → no se toca la regla, es señal de *calidad*.
- **C — falla+desaprobado:** el requisito **coincide con el rechazo** → válido **y** útil → confirmar y
  candidato a **bloqueante**. Es la evidencia más fuerte (más que A).
- **D — cumple+desaprobado:** neutro para ese requisito. **Señal agregada:** si un doc rechazado cumple
  **TODOS** los requisitos → **hueco de cobertura** → falta un requisito que capture ese motivo → sugerir
  agregar uno nuevo.

**Resumen operativo (precisión/recall por requisito):** mucho **C** y poco **B** → preciso y útil
(*promover*, hasta bloqueante); mucho **B** → ruidoso (*revisar/relajar/loop de variante*); solo **A** sin
ningún **C** → aún sin probar como discriminador (*informativo*).

### Guarda contra el sesgo
Si se **aprueba flojo** (docs que no cumplen), el sistema podría aprender a **quitar** requisitos válidos.
Mitigación: nada auto-aplica; se muestra la **evidencia n/N**; el humano **distingue** "no aplica" (falla
pero el doc es correcto) de "se aprobó pese a fallar" (calidad laxa). Todo reversible y auditable.

## 6. Corpus extendido (lo que hay que registrar)

Hoy el historial guarda `campos + decisión`. Para el aprendizaje se suma por validación:
```json
{ "familia": "...", "normas_declaradas": ["aea-90364"],
  "requisitos_evaluados": [{ "id": "aea-90364:aea_caida_tension", "estado": "ok" }],
  "decision": "approved" }
```
El "aprendedor" agrega por familia (cumplimiento en aprobados) y por disciplina (prior).

## 6b. UI: grilla jerárquica de requisitos + feedback por regla

La observabilidad y el aprendizaje fino se materializan en una **grilla-árbol plegable**, jerarquía de
**dos niveles: Norma → Dimensión → requisito**, con roll-up por nodo. Cada fila muestra el resultado
automático y un **juicio humano OPCIONAL por regla** (default `—`): es lo que mueve el feedback de "solo
global" (aprobar/rechazar el doc) a **por regla**.

```
Revisión de contenido — requisitos                      [▾ plegable por nodo]
▾ AEA 90364                                       4/5 ✓ · 1 a revisar
   ▾ Norma (cumplimiento)
      ✓  Caída de tensión ≤ 5%        mayor    mi juicio: [ — ]
      ✕  Cuadro de cargas (columnas)  menor    mi juicio: [ no aplica ]
   ▾ Legibilidad
      ?  Puesta a tierra (no verif.)  mayor    mi juicio: [ — ]
▸ ISO 128 — dibujo técnico                        3/3 ✓
```

**`mi juicio` — 3 acciones** (mapean directo a la matriz §5):
- **de acuerdo** → confirma la regla en esta familia (refuerza A / C; sube su madurez/confianza).
- **no aplica** → la regla no corresponde a esta familia → sugiere quitarla (`revision.excluir`) — cubre la
  hipótesis (2) de la celda B.
- **regla mal** → el check está errado (falso positivo si falló / falso negativo si pasó) → dispara el
  **loop de variante** (proponer un patrón corregido y verificarlo contra el corpus) — hipótesis (1) de B.

Estas etiquetas POR REGLA son **más fuertes** que inferir de la decisión global, y entran directo a la
matriz y a `sugerir_requisitos(familia)`. Nada se auto-aplica: el juicio queda registrado y el sistema
**propone**; el humano confirma los cambios al template.

**Backend:** `POST /casos/{id}/requisito-feedback { requisito_id, juicio, nota? }` (extiende el corpus §6
con la etiqueta por regla). La grilla se arma del `revision.hallazgos` (que ya trae `check_id`, `dimension`,
`severidad`, `norma_ref`, `estado`) agrupado por `norma_ref` → `dimension`.

## 7. Plan incremental (sin romper lo actual)

1. **Paso 1 — Resolvedor (backend) ✅ hecho:** id global `<norma>:<id>` + `revision.requisitos`/`excluir` +
   `resolver_requisitos(template)` en `revisor._tier2_reglas` (`tools/normas.py`).
2. **Paso 2 — Catálogo ✅ hecho:** `catalogo_requisitos()` + `GET /api/normas/catalogo`.
3. **Paso 3 — UI grilla + feedback por regla (§6b) ✅ hecho:** `GrillaRequisitos` (árbol Norma→Dimensión→
   requisito, plegable) con `mi juicio` (3 acciones) + `POST /casos/{id}/requisito-feedback` (persistido en
   `api/historial` tabla `requisito_feedback`; `req_id` viaja en cada hallazgo).
4. **Paso 4 — UI de asignación ✅ hecho:** `RequisitosEditor` en el detalle del template (catálogo por
   norma, checkboxes, "sugeridos por disciplina" vía `aplica_a`) + `PUT /api/tipos/{id}/requisitos`
   (`tools/tipos.set_revision_requisitos`, lista explícita = fuente de verdad).
5. **Paso 5 — Aprendedor ✅ hecho:** `api/aprendizaje.sugerir_requisitos(familia)` (matriz §5: agregar si
   los aprobados lo cumplen, quitar si falla en aprobados / feedback `no_aplica`, prior por disciplina) +
   `GET /api/tipos/{id}/requisitos/sugerencias` + panel "Sugerencias del aprendizaje" en `RequisitosEditor`.
   El corpus se extendió: `validaciones.requisitos` ({req_id: estado}) + tabla `requisito_feedback`.
6. **Paso 6 — perfiles (proyecto/jurisdicción):** ~~`knowledge/perfiles/`, `tools/perfiles`, `GET /api/perfiles`,
   selector en `RequisitosEditor`~~ **RETIRADO (2026-06-21): consolidado en la taxonomía facetada.** El bundle
   "proyecto/jurisdicción → normas" ahora lo dan los ejes de faceta (`proyecto`, `jurisdiccion`, `disciplina`);
   ver `docs/PLAN_Taxonomia_Facetas.md`.

## 8. En una frase
**La norma define el requisito; el corpus de aprobados aprende cuáles exige cada familia (señal: que los
aprobados los cumplan; arranque: prior por disciplina); el humano confirma.** El catálogo es la biblioteca;
el aprendizaje arma la receta de cada familia.
