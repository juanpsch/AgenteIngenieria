# Spec — Agente QA-Ingeniería

## Resumen
Revisa **entregas** de ingeniería que llegan por email. Una entrega puede exigir **uno o varios documentos** (p. ej. Plano + Lista de materiales). **Primero filtra admisibilidad y completitud** (¿están todos los documentos requeridos para esta entrega?, ¿cada uno es del tipo correcto, pertinente y en el formato esperado?); solo si la entrega está completa y admisible, contrasta el contenido contra un checklist por disciplina más hallazgos libres del revisor, y emite un informe de observaciones que un ingeniero senior aprueba antes de devolverlo al emisor. Versiona por ronda hasta aprobar.

## 1. Trigger
Email con entregable adjunto a `qa@<dominio-tenant>`.

Punto de entrada **condicional**:
- Email con adjunto sin `[REF:thread_id]` → **parser** (caso nuevo).
- Respuesta sobre un caso existente (`[REF:thread_id]` en asunto/cuerpo) → **clasificador** (corrección reenviada, pregunta, aprobación del senior, etc.).

## 2. Schema del caso (`graph/state.py`)

Campos del estado:
- `thread_id` — id del caso (la entrega).
- `proyecto` — identificador de obra/proyecto (opcional).
- `revision` — Rev A/B/C… (opcional).
- `tipo_entrega` — qué entrega es; define el **conjunto de documentos requeridos** (obligatorio).
- `disciplina` — estructural / eléctrica / sanitaria / mecánica / … (obligatorio).
- `emisor` — email de quien envió la entrega.
- `documentos[]` — un ítem por documento esperado de la entrega: `{tipo_doc, attachment_id, presente, formato_ok, relevante, motivo}`.
- `entrega_completa` — bool: están todos los documentos requeridos, válidos y relevantes.
- `norma_ref` — norma/checklist de referencia (opcional; default por disciplina).
- `doc_id`, `pdf_id` — referencias al informe generado.
- `admisibilidad` — `{es_admisible, completa, faltantes[], irrelevantes[], motivo}` (resultado del triage).
- `hallazgos[]` — lista de `{item, seccion, severidad, descripcion, norma, confidence}`.
- `dictamen` — APROBADO / APROBADO_CON_NOTAS / OBSERVADO / RECHAZADO.
- `ronda` — entero, número de vuelta de revisión.
- `rebotes_admisibilidad` — contador de veces que el caso cayó en NO_ADMISIBLE (para escalar al dueño tras el 2º).
- `status` — enum (abajo).

Enum **Status**:
`RECIBIDO → EN_TRIAGE → (INCOMPLETA | NO_ADMISIBLE | EN_REVISION) → ESPERANDO_APROBACION_SENIOR → (OBSERVADO | APROBADO | RECHAZADO)`
- `EN_TRIAGE` — gate de admisibilidad + completitud (¿están todos los documentos requeridos?, ¿cada uno correcto/pertinente/formato?) antes de revisar contenido.
- `INCOMPLETA` — faltan documentos requeridos de la entrega; reclama los faltantes al emisor y **acumula** los reenvíos (por `[REF:thread_id]`) en el mismo caso hasta completar.
- `NO_ADMISIBLE` — algún documento no corresponde / formato incorrecto / no pertinente; se devuelve al emisor con el motivo, **sin** revisar contenido.
- `OBSERVADO` espera corrección del emisor; al reenviar corregido vuelve a `EN_TRIAGE` con `ronda += 1` (la corrección también pasa por admisibilidad).
- `FALTAN_DATOS` — estado intermedio cuando faltan datos mínimos y se esperan del emisor.

## 3. Datos mínimos obligatorios
- **Al menos un documento adjunto.**
- **Tipo de entrega + disciplina** (para resolver el conjunto de documentos requeridos y el checklist/norma).

Opcionales: proyecto, revisión, norma de referencia (si falta, usa el default por disciplina).

> **Completitud ≠ datos mínimos.** Que falten *documentos requeridos* de la entrega no es "faltan datos mínimos": eso lo detecta el **triage** (estado `INCOMPLETA`), que reclama los documentos faltantes y acumula reenvíos. `FALTAN_DATOS` es solo cuando no se puede ni identificar la entrega (sin tipo de entrega/disciplina).

> **Proyecto y admisibilidad:** si el email trae `proyecto`, el triage verifica el adjunto contra el **catálogo de entregables esperados** de ese proyecto (Sheet maestro). Si no hay proyecto, el triage degrada con gracia y valida **solo formato** contra la plantilla por tipo/disciplina (no completitud del catálogo).

Si falta un obligatorio → el agente le pide los datos a **quien envió** (no al senior/dueño), pasa a `FALTAN_DATOS` y espera, sin revisar.

## 4. Prompts / agentes (`ai_agents/` + `prompts/`)
- **Parser** — del email entrante extrae `tipo_entrega`, `disciplina`, `proyecto`, `revision`, `emisor` y lista los adjuntos. Salida JSON con regex + fallback.
- **Triage / Admisibilidad + completitud** — gate previo a la revisión de contenido. Resuelve el **conjunto de documentos requeridos** de la entrega contra (a) el **catálogo del proyecto** (Sheet maestro) y (b) la **plantilla de la entrega** por tipo/disciplina (`knowledge/`). Para cada documento requerido y cada adjunto recibido decide:
  - **Completitud**: ¿están todos los documentos requeridos de la entrega (p. ej. Plano *y* Lista de materiales)? ¿cuáles faltan?
  - **Tipo/relevancia**: ¿cada adjunto es del tipo que dice ser y relevante a la entrega, o hay archivos equivocados/fuera de alcance?
  - **Formato**: ¿cada documento cumple el formato esperado (secciones, nomenclatura, tipo de archivo)?
  - Salida JSON `{es_admisible, completa, faltantes[], irrelevantes[], documentos[], motivo}` (regex + fallback).
  - Faltan requeridos → `INCOMPLETA`: reclama los faltantes al emisor y espera (acumula reenvíos). · Hay irrelevantes/formato mal → `NO_ADMISIBLE`: devuelve con el motivo. · Completa y válida → pasa a extractor/revisor.
- **Extractor** — lee el documento adjunto y extrae secciones/datos relevantes **con `confidence` por ítem**. Lo de baja confianza se marca para validación humana (resaltado al senior).
- **Revisor (generador)** — corre el **checklist de la disciplina** (de `knowledge/`) ítem por ítem **más hallazgos libres** (criterio del ingeniero, no cubiertos por el checklist). Emite el informe en **Markdown**; cada hallazgo con severidad **Bloqueante / No bloqueante**. El código convierte el Markdown a Doc (sin loops de tool-calling).
- **Clasificador** — categoriza respuestas sobre un caso existente: `correccion_reenviada`, `pregunta`, `no_acuerda`, `aprobacion_senior`, `rechazo_senior`, `desconoce_corta`.

## 5. Flujo (`graph/nodes.py`, `edges.py`)
```
entrada (parser | clasificador)
  → validación de datos mínimos
       ├─ faltan → pide al emisor → FALTAN_DATOS (espera)
       └─ ok → triage: admisibilidad + completitud (EN_TRIAGE)
                  ├─ faltan documentos requeridos → reclama faltantes → INCOMPLETA (acumula reenvíos)
                  │      └─ llega el faltante [REF] → re-triage → ¿completa? …
                  ├─ irrelevante / formato mal → devuelve al emisor con motivo → NO_ADMISIBLE (no revisa)
                  └─ completa y admisible → extractor → revisor → ESPERANDO_APROBACION_SENIOR
                       → [senior aprueba/edita]
                            ├─ ≥1 bloqueante → OBSERVADO: envía informe al emisor + vuelca a Sheet → espera corrección
                            │      └─ corrección reenviada → EN_TRIAGE (ronda += 1) → admisibilidad → extractor…
                            └─ solo no bloqueantes → APROBADO_CON_NOTAS / APROBADO: envía + vuelca a Sheet → cierra
```
Routers condicionales:
- **Por triage**: completa+admisible → extractor; faltan documentos → INCOMPLETA (reclama y espera); irrelevante/formato mal → NO_ADMISIBLE (devuelve y detiene).
- **Por severidad**: ≥1 bloqueante → OBSERVADO/RECHAZADO; solo no bloqueantes → APROBADO.
- **Por categoría de respuesta** (clasificador): rutea corrección / pregunta / no acuerda (→ escala senior) / desconoce-corta (→ avisa dueño y detiene).

## 6. Documento / acción generada
**Informe de revisión** en Google Doc → exportado a PDF y adjuntado al emisor:
- Encabezado: logo del tenant, proyecto, revisión, tipo/disciplina, emisor, fecha, ronda.
- Tabla de hallazgos: ítem · sección · severidad · descripción · norma aplicable.
- Dictamen (APROBADO / APROBADO_CON_NOTAS / OBSERVADO / RECHAZADO) + firma del revisor/senior.

**Además**: vuelca cada hallazgo como fila al **Sheet maestro del proyecto** (tenant) para seguimiento de cierre (columnas: caso, ronda, ítem, severidad, estado de corrección, fecha).

## 7. Reglas de negocio
- ≥1 hallazgo **Bloqueante** → `OBSERVADO` (vuelve al emisor) o `RECHAZADO`.
- Solo hallazgos **No bloqueantes** → `APROBADO_CON_NOTAS`; sin hallazgos → `APROBADO`.
- **Baja confianza** del extractor en un ítem → se marca destacado para el senior antes de aprobar.
- Versionado por `ronda`: cada reenvío corregido incrementa la ronda y re-revisa.

## 8. Integraciones y cron
Integraciones (base): email (Resend), Drive/Docs, Sheets.

**Sheet maestro = fuente de verdad (read + write-back):** el triage **lee** el catálogo de entregables esperados del proyecto; la revisión **escribe** los hallazgos y el estado de cierre por fila. Las columnas esperadas son un contrato por tenant.

**Cron con umbrales por etapa**:
- **Aprobación del senior pendiente** (`ESPERANDO_APROBACION_SENIOR`): umbral en **horas** — recuerda al senior a las X h; re-escala a las Y h.
- **Corrección del emisor pendiente** (`OBSERVADO`): umbral en **días** — recuerda al emisor a los X días; avisa al dueño a los Y días.

## 9. HITL y casos borde
- **Modo: aprobación previa siempre.** Ningún informe sale al emisor sin OK del senior por email (`[REF:thread_id]`). El senior puede aprobar o editar.
- Bloqueantes y baja confianza del extractor → **resaltados** en lo que recibe el senior.
- Emisor **no acuerda** con una observación → escala al senior.
- Emisor **no acuerda con el triage** (insiste en que el archivo es correcto) → escala al senior, que decide si se revisa igual o se mantiene el rechazo.
- **NO_ADMISIBLE:** se resuelve en silencio con el emisor (rebota con el motivo) las primeras 2 veces; al **3er rebote** del mismo caso (`rebotes_admisibilidad >= 2`) → notifica al dueño.
- Emisor **desconoce el caso / corta** → avisa al dueño y detiene el flujo.

## 10. Multi-empresa / config
Específico del agente (por tenant):
- **Checklists / normas por disciplina** y **plantillas de entrega** (qué documentos requiere cada tipo de entrega + su formato esperado) cargados en `knowledge/` por cada empresa.
- **Catálogo de entregas esperadas por proyecto** en el Sheet maestro (qué entregas, qué documentos por entrega, formato, estado).
- `DRIVE_ROOT` (carpeta raíz del tenant) y `SHEET_MAESTRO_ID` (Sheet de seguimiento + catálogo del proyecto).

Estándar de la base (por tenant):
- Identidad: logo, datos del estudio, remitente, dominio inbound (`qa@empresa.com`).
- Email del **ingeniero senior** aprobador y los **umbrales** del cron (horas de aprobación, días de corrección).
