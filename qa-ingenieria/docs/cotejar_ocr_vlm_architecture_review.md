# Prompt para Claude VS Code: Revisión Arquitectura OCR/VLM en Cotejar

## CONTEXTO DEL PROYECTO

**Producto**: Cotejar - Sistema de admisión y validación de documentación técnica de ingeniería  
**Stack**: FastAPI + React + LangGraph + PostgreSQL  
**Objetivo**: Automatizar la conformidad y validación de planos de ingeniería (cajetín, contenido técnico, referencias)

---

## PROBLEMA A RESOLVER

Tenemos **dos candidatos tecnológicos** para extraer información de planos de ingeniería:

1. **OCR tradicional** (PaddleOCR, Tesseract, etc)
2. **Vision-Language Models** (Qwen2.5-VL, RolmOCR, DeepSeek-OCR, etc)

**Pregunta clave**: ¿Necesitamos ambos en la misma pipeline, o uno es suficiente?

---

## DATOS DE CONTEXTO

### Caso de uso de Cotejar
- **Input**: Archivo PDF o imagen de plano de ingeniería (escaneado o nativo)
- **Proceso esperado**:
  1. Detectar y extraer **cajetín (titleblock)**: metadata del plano (número, escala, revisión, autor, empresa, etc)
  2. Comparar cajetín contra documentos de referencia mediante **similitud vectorial (embeddings)**
  3. Validar **consistencias técnicas** (ej: escala coincide con dimensiones, referencias están actualizadas)
  4. Retornar: documento válido ✓ o rechazado con motivo ✗

### Características del documento
- Pueden ser: PDF nativos, escaneos de baja calidad, planos en color o B&W
- Layouts variados: CAD generado vs dibujado a mano
- Pueden incluir: tablas de revisiones, notas técnicas, referencias cruzadas, anotaciones manuscritas
- Normas técnicas aplicables: IRAM, DIN, ISO

### Requisitos de precisión
- Cajetín: **98%+ accuracy** (datos críticos para validación)
- Contenido técnico: **90%+ accuracy** (tolerancias, especificaciones)
- Falsos positivos: **inaceptables** (no queremos aprobar un documento inválido)

---

## HIPÓTESIS ACTUAL A VALIDAR

**¿Flujo óptimo?**

### Opción A: Solo VLM end-to-end
```
PDF → RolmOCR/Qwen2.5-VL → JSON {cajetín + contenido} → Embeddings → Validación LLM
```
✓ Una sola llamada, sin pipeline múltiple  
✗ ¿Suficientemente preciso para cajetín?  
✗ ¿Hallucina en documentos escaneados?

### Opción B: OCR + VLM híbrido
```
PDF → PaddleOCR-VL (layout) → RolmOCR (cajetín) + LLM (validación) → Embeddings
```
✓ Separación de concerns  
✓ Detecta estructura antes de extraer  
✗ Más llamadas = más latencia + costo  
✗ ¿Justifica el overhead?

### Opción C: OCR tradicional + VLM
```
PDF → Tesseract/PaddleOCR (texto puro) → Qwen2.5-VL (estructura + validación)
```
✗ OCR tradicional no maneja layouts complejos  
✓ Qwen puede contextualizar el texto roto

---

## PREGUNTAS ESPECÍFICAS PARA LA REVISIÓN

Por favor revisar y responder en el contexto de Cotejar:

1. **¿Es redundante usar OCR + VLM?**
   - Un VLM moderno (Qwen2.5-VL, RolmOCR) ya hace OCR end-to-end, ¿por qué agregar otra etapa de detección de layout?
   - ¿O hay casos de uso (escaneos degradados, layouts muy complejos) donde el pipeline híbrido suma valor?

2. **¿Cuál modelo elegir para cajetín?**
   - RolmOCR (7B, específico para OCR) vs Qwen2.5-VL (32B/72B, genérico pero muy preciso)?
   - ¿Qué trade-off latencia vs accuracy es aceptable?

3. **¿Dónde entra el LLM (Claude/OpenAI/DeepSeek)?**
   - ¿Solo en validación lógica post-extracción?
   - ¿O también en corrección de errores del OCR/VLM?
   - ¿Puede trabajar sobre el JSON extraído, o necesita ver la imagen original?

4. **Embeddings: ¿Cuándo y dónde?**
   - ¿El VLM genera los embeddings, o usamos un modelo separado (e.g., OpenAI embeddings)?
   - ¿Embeddings del cajetín completo, o campo-por-campo?
   - ¿Qué threshold de similitud es "válido"?

5. **Manejo de errores:**
   - Si OCR falla en cajetín: ¿reintentar con otro modelo o rechazar?
   - Si embedding match es bajo pero campos críticos coinciden: ¿override?

6. **Arquitectura de código:**
   - ¿Pasar una imagen al VLM completa o hacer pipeline: layout detection → crop cajetín → extracción?
   - ¿Cachear resultados de OCR/embeddings o recalcular cada vez?
   - ¿Qué patrones de error handling aplican?

---

## ENTREGABLES ESPERADOS

Por favor proporciona:

1. **Diagrama de arquitectura recomendado** (flujo simplificado, sin redundancias)

2. **Comparativa: Opción A vs B vs C** con matriz de:
   - Accuracy esperada (cajetín + contenido técnico)
   - Latencia (ms por documento)
   - Costo computacional (VRAM, GPU hours)
   - Complejidad de implementación
   - Manejo de casos edge (escaneos, anotaciones, layouts raros)

3. **Especificación de cada etapa:**
   - Modelo recomendado + parámetros
   - Input/output esperado
   - Validaciones intermedias
   - Manejo de fallos

4. **Integración con FastAPI + LangGraph:**
   - Cómo encadenar las etapas
   - Dónde paralelizar vs secuenciar
   - Manejo de state (qué persiste en BD, qué es ephemeral)

5. **Recomendaciones prácticas:**
   - ¿Fine-tuning del VLM para documentos técnicos vale la pena?
   - ¿Qué métricas monitorear en producción?
   - ¿Cómo manejar la retroalimentación de usuarios (correcciones manuales)?

---

## CONTEXTO ADICIONAL

- Estás en **Argentina**, enfocado en documentación técnica local (IRAM, estándares constructivos)
- El sistema debe ser **escalable** (múltiples documentos concurrentes)
- **Privacy**: Datos sensibles, preferencia por self-hosted cuando sea posible
- **Presupuesto**: Optimizar costo de inference (APIs externas son posibles pero no ideales)

---

## NOTAS IMPORTANTES

- No necesitamos decidir LLM aún (Claude/OpenAI/DeepSeek son intercambiables en validación)
- El foco es **OCR/VLM: ¿cuál y cómo?**
- Priorizá **accuracy en cajetín** sobre speed (es el dato crítico)
- Considerá que algunos documentos pueden ser **escaneos viejos de baja calidad**

---

## FIN DEL PROMPT

**Cómo usarlo:**
1. Abrí VS Code + Claude Remote Control (o chat directo)
2. Pegá este prompt + `@codebase` (si tenés Cotejar abierto)
3. Claude analizará tu estructura actual y responderá cada pregunta
4. Iterá basado en su feedback

---
---

# RESPUESTA — Revisión de arquitectura OCR / VLM / Embeddings (2026-06-20)

> Revisión hecha sobre el **código real** de Cotejar (no sobre el Cotejar hipotético del prompt de arriba).
> Autor: Claude (Opus 4.8) · Fecha: **2026-06-20**.

## TL;DR (decisión)
El prompt de arriba hace **las preguntas correctas pero asume la arquitectura equivocada** (el VLM como
motor que "lee todo y decide"). Para un gate donde *los falsos positivos son inaceptables*, esa es la
opción a evitar. **Cotejar ya tiene la respuesta madura y se ratifica como decisión de arquitectura:**

- **Lo DETERMINISTA decide** — reglas de texto (Tier 2, regex) sobre la capa de texto.
- **CLIP decide identidad** — similitud visual contra referencias (positivas **y** negativas), umbrales auto-calibrados.
- **El VLM solo asiste** — observa/juzga lo interpretativo (símbolos, leyendas, coherencia) **a pedido y sin bloquear**.
- **OCR (tesseract) es el *fallback* de capa de texto** — para que lo anterior funcione en escaneos.

NO migrar a "VLM end-to-end": perderíamos auditabilidad y ganaríamos alucinaciones justo donde no se pueden permitir.

## Correcciones al prompt (no refleja el sistema real)
- **Stack**: es **SQLite** (checkpointer de LangGraph), no PostgreSQL.
- **Embeddings**: son **CLIP visual local** ([similarity.py](similarity.py) / open-clip, offline), el VLM **no** los genera.
- **OCR vs VLM**: en el prompt compiten por el cajetín; en el sistema **hacen trabajos distintos** y son capas, no rivales.

## ¿OCR + VLM es redundante? — NO (hacen trabajos distintos)
| Capa | Rol | Dónde |
|------|-----|-------|
| **OCR (tesseract)** | Conseguir TEXTO cuando el PDF no lo trae (escaneo) → habilita reglas + búsqueda + confianza de legibilidad. No "lee" el cajetín semánticamente. | `tools/ocr.py`, `tools/docs.py` (fallback), `tools/legibilidad.py` |
| **CLIP (embeddings)** | ¿Es del mismo tipo que mis ejemplos? Identidad visual (cajetín ponderado + página), umbrales auto-calibrados, pos/neg. | `ai_agents/similarity.py`, `tools/refs.py` |
| **VLM** | Juzgar lo que el texto NO puede (¿hay leyenda real?, ¿símbolos coherentes?) — a pedido, no bloqueante. | `ai_agents/revisor.py` (Tier 3, `verificar_reglas_vlm`) |
| **LLM** | Identidad (`es_el_tipo`), localización del cajetín (bbox), observación interpretativa. **Nunca el score.** | `graph/nodes.py`, `ai_agents/similarity.py` (`detectar_zona_identidad`) |

## Veredicto sobre las 3 opciones del prompt
- **Opción A (solo VLM end-to-end): RECHAZADA.** No determinista, alucina, cara por documento, no auditable
  → incompatible con "cero falsos positivos" y "cajetín 98%".
- **Opción B/C (OCR + VLM): parcialmente correctas**, pero mal encuadradas: el OCR no es para "detectar layout"
  antes de extraer, sino para **rescatar texto** en escaneos. El layout/identidad lo resuelve CLIP + el bbox del LLM.
- **Arquitectura adoptada (la real):** determinista + CLIP deciden · VLM asiste a pedido · OCR rescata texto.

## Respuestas puntuales
1. **Cajetín 98%**: no pedirle a un VLM que lo lea libremente. Pipeline correcto (el que hay): **localizar zona**
   (bbox con visión) → **recortar** → **OCR del crop** si hace falta → **regex/reglas** validan los campos.
   Determinista sobre un recorte con buen texto ≫ VLM freeform.
2. **Modelo VLM**: RolmOCR/Qwen-VL 32–72B son fierros pesados; **no** en el camino crítico. El VLM es asistente
   a pedido (Tier 3); un Qwen-VL self-host sería *nice-to-have* para Tier 3 offline, no un cambio de arquitectura.
3. **Embeddings**: CLIP local, no field-by-field de un VLM. Lo visual capta tipo/logo/layout (identidad); los
   valores de campo los valida regex. Split correcto. Umbral = auto-calibrado del corpus (no un número fijo).
4. **Manejo de errores**: degradar con gracia — todo cae a `no_verificable`, **nunca** a un "ok" inventado.
5. **Fine-tuning del VLM**: **no, por ahora.** El "aprendizaje" vive en los **sets de referencia CLIP (kNN, pos/neg)**
   y el **feedback de reglas** — más barato, controlable y auditable que tocar pesos.
6. **Privacy/costo**: el camino crítico (CLIP + tesseract) ya es **100% local**; el VLM/LLM es a pedido.

## Métricas a monitorear en producción (recomendado sumar)
- Tasa de `no_verificable` por tipo (cobertura real de la revisión).
- Discrepancia humano-vs-gate (ya alimenta los **negativos** del embedding).
- Precisión del cajetín **por campo** (no solo global).

## Decisión registrada
Se mantiene la arquitectura actual. El VLM permanece como **asistente a pedido y no bloqueante**; el veredicto
del gate lo deciden **reglas deterministas + similitud CLIP**; el OCR es el fallback de texto. Revisar esta
decisión solo si aparece evidencia de que el determinista+CLIP no alcanza para un tipo de documento concreto
(y aun así, primero sumar reglas/criterios, no mover el VLM al camino crítico).

