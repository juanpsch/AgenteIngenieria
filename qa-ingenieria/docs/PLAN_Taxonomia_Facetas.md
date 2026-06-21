# Plan de implementación — Taxonomía facetada (reuso de reglas/ejemplos/aprendizaje)

> Plan accionable derivado de [DISENO_Taxonomia_Familias.md](DISENO_Taxonomia_Familias.md). 2026-06-21.
> Principio rector: **modelo facetado + composición**; el árbol es una vista. **No-breaking**: las familias
> planas siguen funcionando sin tocarlas.

> **Estado: FASE 1 implementada (2026-06-21).** `knowledge/facetas.yaml` + `tools/facetas.py` + resolvedor v2.
> Ajuste vs este plan: las coordenadas van en **`revision.facetas`** (no top-level) → cero cambios en los
> callers de `resolver_requisitos`. Las 8 familias migradas resuelven las MISMAS normas que antes (verificado).
> Decisiones configurables en `facetas.yaml` (`ejes.*.precedencia`, `politica.conflicto_severidad`).

## 0. Decisiones fijadas (defaults; confirmables)
- **Ejes** (con precedencia, 1 = más específico gana): `proyecto(1) > organizacion(2) > tipo(3) > disciplina(4) > jurisdiccion(5) > global(6)`.
- **Resolución de reglas**: unión de todas las facetas − exclusiones; ante mismo `id`, **gana la faceta más específica** (override completo de la regla, incl. severidad). Empate de precedencia → desempate por orden de eje + **log ruidoso** (nunca silencioso).
- **Jerarquía intra-eje**: un valor puede tener `padre` (p.ej. `pid` ⊂ `diagrama`); el ancestro aporta reglas, el hijo pisa.
- **Ejemplos/aprendizaje**: una familia con < `CALIBRADO_MIN` ejemplos propios **hereda** los del padre (la familia genérica de su `tipo`); al superar el umbral, usa los propios. (LCPN + prototipo heredado; shrinkage ponderado = fase posterior.)
- **Compatibilidad**: una familia sin `facetas` se comporta EXACTLY como hoy (`revision.normas/requisitos`).

## 1. Modelo de datos

### 1.1 Registro de facetas — `knowledge/facetas.yaml` (nuevo, único)
```yaml
ejes:                       # precedencia: menor número = más específico
  proyecto:     { precedencia: 1 }
  organizacion: { precedencia: 2 }
  tipo:         { precedencia: 3 }
  disciplina:   { precedencia: 4 }
  jurisdiccion: { precedencia: 5 }

valores:                    # por eje: valor -> {nombre, padre?, normas?, requisitos?, excluir?}
  tipo:
    diagrama:   { nombre: "Diagramas" }
    pid:        { nombre: "P&ID", padre: diagrama, normas: [iram-instrumentacion, iram-dibujo] }
    memoria:    { nombre: "Memoria de cálculo" }
    hoja_datos: { nombre: "Hoja de datos de recipiente", normas: [asme-viii-1] }
    plano:      { nombre: "Plano (dibujo técnico)", normas: [iram-dibujo] }
  organizacion:
    camuzzi:    { nombre: "Camuzzi", normas: [camuzzi] }
    epa_bc:     { nombre: "EPA / Brown & Caldwell", normas: [epa-wwtp] }
  disciplina:
    instrumentacion: { nombre: "Instrumentación" }
    electrica:       { nombre: "Eléctrica" }
    estructural:     { nombre: "Estructural", normas: [cirsoc-201] }
  jurisdiccion:
    AR: { nombre: "Argentina" }
    US: { nombre: "EE.UU." }
```
- Reglas viven en `normas/` (sin cambios); las facetas solo las **referencian**. Un valor de faceta es un
  "mini-perfil" de un solo eje.

### 1.2 Familia con coordenadas — `knowledge/tipos/<id>.yaml`
```yaml
tipo_doc: pid_camuzzi
nombre: "P&ID Camuzzi (gas)"
facetas: { tipo: pid, organizacion: camuzzi, disciplina: instrumentacion, jurisdiccion: AR }
revision:
  requisitos: []     # extras/override propios (lo más específico) — opcional
  excluir: []        # opcional
  legibilidad: { blur_var_min: 80, ocr_conf_min: 0.6 }
  # revision.normas ya NO hace falta (salen de las facetas). Si se deja, se respeta como override del template.
```
Familia plana (legacy): sin `facetas`, con `revision.normas` → idéntico a hoy.

## 2. Algoritmo de resolución (extiende `tools/normas.resolver_requisitos`)
Entrada: el `tipo` (con `facetas` + `revision`). Salida: lista de requisitos a evaluar (igual que hoy).
```
contribs = []                                  # (precedencia, fuente, bundle)
for (eje, valor) in tipo.facetas:
    for v in cadena(eje, valor):               # [ancestros..., valor]  (vía 'padre')
        b = facetas.valores[eje][v]
        prof = profundidad de v en su eje       # ancestro = menos específico
        contribs.append( (ejes[eje].precedencia*10 + prof, eje, b) )
contribs.append( (0, "template", tipo.revision) )   # lo propio: lo más específico

out = {}                                        # id_local -> regla
excl = set()
for (_, fuente, b) in sort(contribs, key=precedencia, DESC):   # menos → más específico
    for r in expand(b.normas) ∪ b.requisitos ∪ b.reglas:
        out[r.id_local] = anotar(r, fuente)     # más específico PISA; guarda 'origen' p/ explicabilidad
    excl |= set(b.excluir)
return [r for (id,r) in out if id not in excl]
```
- **Determinista** (orden total por precedencia). Empate exacto → orden de eje + `log.warning`.
- `perfiles`: **consolidados en facetas y RETIRADOS (2026-06-21)** — eran el mecanismo pre-taxonomía para
  "proyecto/jurisdicción → normas"; el bundle del único perfil (aea+cirsoc) ya lo dan las facetas
  `disciplina: electrica/estructural`. Se eliminó `tools/perfiles`, el endpoint y la UI.
- Cada requisito resuelto lleva `origen` (qué faceta lo trajo) → para mostrar en la UI ("regla de: org=Camuzzi").

## 3. Reuso de ejemplos/aprendizaje (Fase 3)
- **Mapa faceta→familia genérica**: el valor `tipo: pid` apunta a la familia genérica `pid_instrumentacion`
  (campo `familia_generica` en el valor de faceta, o convención `pid_<eje>`). 
- **`referencias_resueltas(tipo)`** (nueva, en `tools/refs`):
  - `propias = vectores_por_referencia(tipo)`.
  - si `len(propias) >= CALIBRADO_MIN`: usar **solo propias** (peso 1).
  - si no: usar **propias (peso 1) + heredadas de la familia genérica del `tipo` (peso λ)**; λ decae con `len(propias)` (p.ej. `λ = 1 / (1 + len(propias))`). Marcar las heredadas como tales.
- El gate (`graph/nodes._check_similitud`) usa `referencias_resueltas` en vez de `vectores_por_referencia`.
- **Negativos**: igual — `negativos_resueltos` hereda del padre con la misma regla.
- **Aplicabilidad** (`api/aprendizaje`): el corpus y el feedback se consultan por faceta; lo aprendido en el
  `tipo` genérico se hereda; el override específico pisa. (Misma fórmula de pooling.)
- **Explicabilidad**: el desglose del score muestra cuántos ejemplos son propios vs heredados.

## 4. Fases (cada una: implementar + tests + docs + commit; no-breaking)

### Fase 1 — Facetas para REGLAS  ⭐ (arrancar acá)
- **Nuevo**: `knowledge/facetas.yaml`; `tools/facetas.py` (`cargar_facetas`, `cadena(eje,valor)`, `reglas_de_faceta`).
- **Cambia**: `tools/normas.resolver_requisitos` → suma las contribs de facetas con precedencia + `origen`.
- **Datos**: agregar `facetas: {...}` a las familias existentes (pid_camuzzi, pid_efluentes, memoria_electrica…). Mantienen su `revision` como override.
- **Tests**: una familia con `facetas` resuelve la unión correcta; precedencia (org pisa tipo); excluir; familia plana intacta; empate → log.
- **Aceptación**: `pid_camuzzi` con solo `facetas` resuelve `iram-instrumentacion + iram-dibujo + camuzzi` sin listar normas; quitar `organizacion: camuzzi` saca las reglas Camuzzi.
- **Tamaño**: chico-medio. No toca el grafo ni el front (salvo opcional: mostrar `origen` en la grilla).

### Fase 2 — Herencia de familias + UI de origen
- Familia puede declararse vía facetas; resolver ya lo soporta. UI: la grilla muestra `origen` de cada regla (qué faceta). Editor de familia = selección de facetas (no lista cruda de normas).
- **Aceptación**: en la revisión se ve "esta regla viene de: org=Camuzzi / tipo=P&ID".

### Fase 3 — Ejemplos heredados (shrinkage) ⭐
- `tools/refs.referencias_resueltas` / `negativos_resueltos`; mapa faceta→familia genérica; `nodes._check_similitud` los usa; desglose muestra propios vs heredados.
- **Aceptación**: `pid_camuzzi` (0 ejemplos propios) **calibra usando los de `pid_instrumentacion`**; al promover P&IDs Camuzzi reales, los propios toman peso. (Cierra el dolor de hoy.)

### Fase 4 — Aprendizaje por faceta (con ALCANCE + override por familia)
> **Estado: override de SEVERIDAD por faceta/familia HECHO (2026-06-21).** `severidad: {id: nivel}` en una
> faceta o en `revision`; resuelto por precedencia (`severidad_overrides`), aplicado a requisitos y a
> `norma_declarada`. Demo real: "declarar la norma" = mayor en memoria, menor en plano (vía faceta `tipo`),
> overridable por familia. Aplicabilidad "no aplica acá" ya estaba (`excluir` por familia). **Pendiente:** que
> el JUICIO (de_acuerdo/no_aplica/regla_mal) que alimenta al aprendedor se guarde y resuelva con alcance.
**Refinamiento (2026-06-21):** una regla puede importar en una familia y en otra NO ("declarar la norma" es
*mayor* en una memoria pero *menor/irrelevante* en un plano). Por eso el juicio NO se globaliza a la norma sin
más: vive en un **alcance** y se resuelve con la **misma precedencia que las reglas** (lo más específico gana).
- **Alcance** (elegible por el humano / inferido por evidencia): `familia > organización > tipo > disciplina > norma/global`.
- "regla mal" / "no aplica" / severidad / agregados del corpus se guardan **con su scope**; al evaluar una
  familia se toma el **más específico aplicable** (la familia siempre puede **override**). Así "isa_tags está
  roto" (scope norma) se reusa, pero "acá no aplica" (scope familia) queda local.
- **Severidad de checks transversales** (ej. "declara la norma"): poder atarla a la faceta correcta
  (tipo=memoria→mayor; tipo=plano→menor) u overridearla por familia, no solo per-norma (hoy `deteccion.severidad`).
- UI: al juzgar, elegir el alcance ("solo esta familia" por defecto / "esta norma" / "esta faceta").

### Fase 5 — Navegación facetada (UI)  ← (idea del usuario, 2026-06-21)
- En **Templates**, ver los tipos de doc **pivoteados por la faceta que uno elija** (entrar por empresa, por
  disciplina, por tipo…) — un selector de "agrupar por" + drill-down, manejable desde la UI.
- **Filtros por metadata**: filtrar el set por valores de faceta (org=Camuzzi ∧ disciplina=instrumentación) y
  por otra metadata del doc, con conteos en vivo + breadcrumbs.
- **Barato ahora**: tras la Fase 1, cada familia ya lleva `revision.facetas` → la UI solo agrupa/filtra por esos
  valores. Backend: exponer `facetas` en `GET /api/tipos` (hoy devuelve nombre/disciplinas/refs/maturity).
- Nada de árbol fijo en el dato: el árbol es la vista (pivot), como concluyó el análisis.
- **HECHO (rework 2026-06-21)**: tabla dinámica MULTINIVEL — se elige el ORDEN de los ejes (chips reordenables
  ◀ ▶, agregar/quitar) y agrupa anidado en ese orden; nodos COLAPSABLES (colapsar/expandir todo) + filtro por
  faceta. (Antes era un solo nivel y "siempre lideraba el tipo".)

## 5. Riesgos y mitigaciones (operativas)
- **Conflicto de facetas** → precedencia documentada + log ruidoso ante empate (no resolver en silencio).
- **Dilución de ejemplos** → λ decreciente + alerta si la media del subgrupo se aleja del padre.
- **Facetas no ortogonales** → revisar que cada eje sea mutuamente excluyente al definir `facetas.yaml`.
- **Explicabilidad** → `origen` por regla + propios/heredados en el score (requisito de aceptación, no opcional).
- **Migración** → familias planas no se tocan; las nuevas usan facetas; se migran de a una.

## 6. Decisiones a confirmar antes de codear
1. **Ejes y precedencia**: ¿el orden `proyecto>org>tipo>disciplina>jurisdicción` es el que querés? (define quién pisa a quién).
2. **`CALIBRADO_MIN`** para heredar ejemplos (default 5; ya es el umbral de "calibrado").
3. **Override de severidad**: ¿"lo más específico gana" siempre, o "lo más restrictivo gana" para bloqueantes? (default: más específico).
4. **Empezar por Fase 1 + Fase 3** (reglas por faceta + ejemplos heredados) — son las que sacan dolor hoy.

## 7. Orden recomendado
**Fase 1** (reglas por faceta, no-breaking) → **Fase 3** (ejemplos heredados, cierra Camuzzi) → Fase 2 (UI origen) → Fase 4 (aprendizaje por faceta) → Fase 5 (navegación). Cada una es un incremento verificado y commiteado.
