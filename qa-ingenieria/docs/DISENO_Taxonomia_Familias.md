# Análisis de diseño — Taxonomía de familias: facetas, jerarquía y reuso (2026-06-20)

> Análisis **sin código**. Objetivo: cómo agrupar/jerarquizar las familias de documentos para **reutilizar
> reglas, ejemplos y aprendizaje**. Autor: Claude (Opus 4.8). Disparado por: "P&IDs → P&IDs de Camuzzi /
> Empresa A → HDs Empresa A… quizás algo cruzado".

## 1. El problema
Hoy las **familias** (`knowledge/tipos/<id>.yaml`) son **planas**: `pid_camuzzi`, `memoria_electrica`,
`pid_efluentes`… Cada una es una isla. Queremos:
- **Jerarquizar** ("P&IDs" → "P&IDs de Camuzzi").
- **Agrupar por cliente/empresa** ("Empresa A" → sus HDs, sus memorias).
- Y, sobre todo, **reutilizar** entre grupos: reglas, ejemplos (CLIP) y aprendizaje (aplicabilidad + negativos).

El usuario ya intuyó lo correcto: **"quizás algo cruzado"**. Un documento es a la vez *un P&ID* **y** *de
Camuzzi* **y** *de instrumentación* **y** *jurisdicción AR*. Eso **no es un árbol** — es una matriz.

## 2. Diagnóstico: Cotejar YA es medio facetado (pero solo para reglas)
Mapeando lo que existe:

| Pieza actual | Qué es en términos de taxonomía |
|---|---|
| `knowledge/normas/<id>.yaml` | **Bundle de reglas reutilizable** (se comparte entre familias). Ya es composición. |
| `norma.aplica_a {disciplinas, jurisdiccion}` | **Tags de faceta** de una norma (a qué eje pertenece). |
| `knowledge/perfiles/<id>.yaml` | **Bundle cross-cutting** (normas+requisitos por proyecto/jurisdicción). Ya es multi-eje, embrionario. |
| `tipo.revision.normas / requisitos / excluir` | Resolución por **composición** (`expand(normas) ∪ requisitos − excluir`). |
| `tipo` (familia) | **Familia plana** = hoy mezcla identidad + selección de reglas, sin padre. |
| `knowledge/refs/<tipo>/` (pos/neg) | **Ejemplos + aprendizaje del gate, atados a la familia plana** (NO se comparten). |

**Conclusión:** ya reutilizamos **reglas** (vía normas/perfiles/composición). Lo que **falta**:
1. Hacer las **facetas explícitas y multi-eje** (no solo disciplina/jurisdicción de las normas).
2. **Jerarquía dentro de un eje** + **resolución por precedencia** ("lo más específico gana").
3. Extender el reuso a **ejemplos** y **aprendizaje** (hoy viven pegados a la familia plana → Camuzzi quedó sin calibrar porque no tiene P&IDs propios, aunque "P&IDs" en general sí).

## 3. Tesis: modelo FACETADO + composición, NO un árbol
El prior art es unánime — ningún sistema serio de ingeniería usa árbol único:
- **ISO/IEC 81346** clasifica el MISMO objeto por aspectos **ortogonales** en paralelo (`=`función `-`producto `+`ubicación). Explícitamente *no* es un árbol.
- **ISO 19650 / BS 1192**: el código de documento es la **concatenación de ~7 facetas independientes** (proyecto–originador–volumen–nivel–tipo–disciplina–nº); la clasificación va como **metadata separada**.
- **CFIHOS / Hexagon SDx**: incluso cuando fusionan disciplina+tipo, los EDMS maduros lo **des-fusionan** en ejes independientes para poder buscar cruzado.
- **Ranganathan / faceted classification**: para contenido grande, heterogéneo e interdisciplinario → facetas, no enumeración.

**Insight central:** el árbol "P&IDs → P&IDs de Camuzzi" que dibujaste es una **VISTA navegable**, no el modelo
de datos. Si faceteás los datos, la UI puede ofrecer **muchos árboles pivotables** sobre lo mismo
(por-tipo-luego-empresa, o por-empresa-luego-tipo) sin duplicar nada. Eso es "lo cruzado".

## 4. Los ejes (facetas) de Cotejar
Propuestos, **ortogonales** (regla de oro: cada eje mutuamente excluyente; mezclar dos características en un
eje es el error clásico):

| Eje | Ejemplos | Jerárquico internamente? |
|---|---|---|
| **Tipo de documento** | P&ID, memoria, hoja de datos, plano, unifilar, esquemático | Sí (P&ID ⊂ diagramas; P&ID de proceso / de lazo) |
| **Disciplina** | instrumentación, eléctrica, mecánica, civil, estructural, procesos | Sí (poco) |
| **Organización / cliente** | Camuzzi, Empresa A, EPA/Brown&Caldwell | Sí (corporativo → unidad) |
| **Norma / código** | iram-dibujo, iram-instrumentacion, aea-90364, asme-viii-1, camuzzi | (ya existe como capa) |
| **Jurisdicción** | AR, US | Sí (país → provincia) |
| **Proyecto** | Salliqueló, Pahala WWTP | el más específico |

Una **familia** = una **selección de valores de faceta** (un punto/región del lattice).
"P&IDs de Camuzzi" = `tipo=P&ID ∩ org=Camuzzi (∩ disciplina=instrumentación ∩ jurisdicción=AR)`.

## 5. Reuso de REGLAS — composición + precedencia
- **Cada valor de faceta lleva reglas** (sus `normas`/`requisitos`). Hoy: el tipo lleva normas. Mañana:
  también el cliente ("estándar de dibujo de Empresa A" = una norma atada a `org=EmpresaA`), la
  jurisdicción, etc. Es **generalizar los perfiles a todos los ejes**.
- **La familia resuelve = UNIÓN de las reglas de todas sus facetas − exclusiones**, dedup por id.
  (Hoy el resolvedor ya hace `expand ∪ requisitos − excluir`; se extiende a "expand de todas las facetas".)
- **Precedencia "lo más específico gana"** cuando dos facetas chocan en la misma regla (p.ej. una severidad).
  Modelo recomendado por el prior art: **especificidad tipo CSS** (comparar columnas de más a menos
  específico, NO sumar) con orden de ejes: `proyecto > organización > tipo de documento > disciplina >
  jurisdicción > global`. Desempate final estable (último declarado).
- **Operadores de merge explícitos** (estilo AWS tag-policies), no implícitos: `asignar` (reemplaza),
  `agregar` (extiende lista), `quitar` (excluye). Un padre puede **bloquear** un valor para que el hijo no lo pise.
- **Para reglas de cumplimiento, "lo más restrictivo gana"** (no "lo más específico"): si una faceta dice
  bloqueante y otra menor, prevalece bloqueante. Y **fallar ruidoso ante orden ambiguo** (como el `MRO
  conflict` de Python), no resolver en silencio.

**Ejemplo — "P&ID de Camuzzi" resuelve:** `iram-dibujo` (transversal) ∪ `iram-instrumentacion` (tipo=P&ID) ∪
`camuzzi` (org) − exclusiones; si `camuzzi` redefine la severidad de un símbolo, **gana camuzzi** (org es más
específico que tipo).

## 6. Reuso de EJEMPLOS — herencia con peso decreciente (lo nuevo y difícil)
Hoy los ejemplos CLIP viven por familia plana → **un subgrupo nuevo arranca sin nada** (el dolor real:
`pid_camuzzi` sin P&IDs propios no calibra, aunque "P&IDs" en general sí tiene). La solución del prior art es
**una sola regla** (partial pooling / James-Stein / prototipos / kNN ponderado):

> `estimación = w·(ejemplos propios) + (1−w)·(ejemplos heredados del padre)`, con **w que crece con el nº de
> ejemplos propios**.

Concretamente, sin re-entrenar CLIP (sigue congelado):
- Los ejemplos se **etiquetan por faceta** (no por familia). El set de referencia de una familia = sus
  ejemplos propios **+** los heredados de sus facetas/padres, **con peso decreciente** (los propios pesan más).
- **Cold-start (lo que pediste):** un subgrupo nuevo usa los ejemplos del **padre** (p.ej. "P&IDs" genérico)
  hasta acumular N propios; a partir de N, su centroide propio domina. (Patrón *Local Classifier per Parent
  Node* + prototipo heredado; el préstamo se diluye solo.)
- **Implementación más simple y explicable:** prototipo/centroide por faceta, o **kNN con peso de ejemplo
  heredado** (`weights=callable` que decae). Cero re-entrenamiento, se ve "qué vecinos votaron".
- Esto **resuelve Camuzzi de una**: `pid_camuzzi` heredaría los P&IDs de `pid_instrumentacion` como prior, y
  los iría reemplazando con P&IDs Camuzzi reales cuando aparezcan.

## 7. Reuso de APRENDIZAJE — misma regla de shrinkage
- **Aplicabilidad de reglas** (qué requisitos aplican): la señal "los aprobados lo cumplen" se computa al
  **nivel de faceta más informativo**. Lo aprendido en "P&IDs" aplica a *todos* los P&ID (herencia); un
  override de "Camuzzi" pisa. Agregación = pooling con peso por volumen de evidencia.
- **Negativos del gate** (contra-ejemplos): hoy por familia. Mañana **por faceta** → un negativo de "P&IDs"
  penaliza a todas las sub-familias; uno de Camuzzi solo a Camuzzi. Misma precedencia.
- El **juicio por regla** (de_acuerdo/no_aplica/regla_mal) se atribuye a la faceta donde es válido (a la norma,
  no a la familia puntual) → se reutiliza en todas las familias que usan esa norma.

## 8. Lo "cruzado" = la UI son árboles pivotables sobre datos facetados
No bakear una jerarquía. Con datos facetados, la navegación es **drill-down + pivot** con conteos en vivo:
elegís el orden de los ejes (por-tipo, por-empresa, por-disciplina) y el mismo documento se alcanza por
cualquier ruta. Breadcrumbs. (Patrón de faceted navigation estándar.) El "árbol" es una preferencia de vista.

## 9. Mapeo a Cotejar — evolución, NO reescritura
Lo bueno: el modelo facetado es **un superconjunto** de lo que ya hay. Las familias planas siguen siendo
válidas (= "una selección de facetas con nombre"). Evolución:

| Concepto facetado | Artefacto hoy | Evolución propuesta |
|---|---|---|
| Eje + valores | `aplica_a` (parcial) | Registro de **facetas** (ejes + valores, con jerarquía intra-eje) |
| Reglas por faceta | `normas` (atadas a disciplina) | normas/requisitos atables a **cualquier** valor de faceta |
| Bundle multi-eje | `perfiles` | Generalizar: perfil = selección de facetas reusable |
| Familia | `tipos/<id>` | Familia = **selección de facetas** + criterios de identidad; opcional `padre`/herencia |
| Ejemplos/aprendizaje | `refs/<tipo>` (por familia) | Ejemplos **etiquetados por faceta** + resolución con shrinkage |
| Navegación | lista plana de tipos | Árbol **pivotable** por eje |

## 10. Riesgos a vigilar
- **Conflictos entre facetas** → una regla de precedencia **documentada** + **fallo ruidoso** ante ambigüedad
  (nunca resolución silenciosa: es el modo de falla raíz de la herencia múltiple).
- **Dilución de ejemplos** al heredar sin ponderar → shrinkage decreciente; alertar cuando la media de un
  subgrupo se aleja de la del padre (señal de que ya merece independizarse).
- **Facetas no ortogonales** (mezclar dos características en un eje) → auditar exclusividad mutua.
- **Polijerarquía descontrolada** (un valor con muchos padres) → máximo ~2 padres, regla "all-some", lo
  débil va como "relacionado", no como jerarquía.
- **Explicabilidad** (Cotejar la valora): con unión de reglas + shrinkage, el usuario DEBE ver *por qué* se
  aplicó cada regla (qué faceta la trajo, qué ganó) y *de dónde* salió cada ejemplo. Prototipos + precedencia
  tipo CSS son explicables por diseño; preferirlos sobre transfer/Bayes opaco en el núcleo auditable.

## 11. Plan por fases (incremental, no-breaking)
1. **Facetas explícitas (solo reglas).** Registro de ejes/valores; permitir atar normas a `org`/`jurisdicción`
   (no solo disciplina); resolvedor = unión de facetas con precedencia. Las familias planas siguen andando.
   *Desbloquea: "estándar de Empresa A" reutilizado por todas sus familias.*
2. **Herencia de familias (padre).** Una familia puede declarar `padre`; hereda reglas + identidad. Resolución
   por precedencia. *Desbloquea: "P&IDs de Camuzzi" hereda de "P&IDs".*
3. **Ejemplos heredados (shrinkage).** Ejemplos etiquetados por faceta; score con prototipo/kNN ponderado que
   hereda del padre y se diluye. *Desbloquea: calibrar subgrupos nuevos con los ejemplos del padre (Camuzzi).*
4. **Aprendizaje por faceta.** Negativos + aplicabilidad + juicio por regla atribuidos a la faceta correcta.
5. **UI facetada.** Árbol pivotable + breadcrumbs + conteos.

## 12. Recomendación
Adoptar el **modelo facetado** como esqueleto (no un árbol), con **composición + precedencia "lo más
específico gana"** para reglas y **shrinkage (prototipo/kNN ponderado, peso del padre → 0)** para ejemplos y
aprendizaje. Es la unión de lo que ya hace Cotejar (normas/perfiles/aplica_a) con lo que falta (multi-eje,
herencia, reuso de ejemplos/aprendizaje), y se puede hacer **por fases sin romper** las familias planas. El
árbol jerárquico que se quiere ver es una **vista**, no el dato. Empezar por la **Fase 1** (facetas para
reglas) y la **Fase 3** (ejemplos heredados) — son las que más dolor sacan hoy (estándares por cliente +
calibrar subgrupos nuevos).
