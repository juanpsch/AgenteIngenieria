# Fixtures de prueba — Fase 0 (admisión de documentos)

Archivos para probar el agente en el sandbox (http://127.0.0.1:7860).
En el chat: tocá 📎, subí el archivo, escribí el mensaje y enviá.

> Los archivos los regenerás con: `uv run python scripts/make_fixtures.py`

---

## Escenario 1 — Entrega de cálculo (camino feliz)
- **Adjuntar:** `memoria_calculo_P102.pdf`
- **Escribir:** `Envío la memoria de cálculo estructural del proyecto P-102 rev B para revisar`
- **Esperado:** `EN_REVISION` — admisible y completa, lista para revisión.

## Escenario 2 — Entrega incompleta
- **Adjuntar:** `plano_P102.pdf`
- **Escribir:** `Envío el plano de fabricación del proyecto P-102, disciplina estructural`
- **Esperado:** `INCOMPLETA` — responde que falta `lista_materiales`.

## Escenario 3 — No admisible (archivo irrelevante)
- **Adjuntar:** `presupuesto.pdf`
- **Escribir:** `Envío la memoria de cálculo estructural del proyecto P-102`
- **Esperado:** `NO_ADMISIBLE` — es un presupuesto, fuera de alcance.

## Escenario 4 — Faltan datos mínimos
- **Adjuntar:** *(nada)*
- **Escribir:** `Hola, les mando algo para que revisen cuando puedan`
- **Esperado:** `FALTAN_DATOS` — pide adjunto + tipo de entrega + disciplina.

---

## Escenario 5 — Ida y vuelta (completar una entrega en 2 turnos)
En el **mismo chat**, uno tras otro:

1. **Adjuntar:** `plano_P102.pdf` · **Escribir:** `Envío el plano de fabricación del P-102, estructural`
   → `INCOMPLETA` (falta la lista de materiales).
2. **Adjuntar:** `lista_materiales_P102.xlsx` · **Escribir:** `Ahí va la lista de materiales que faltaba`
   → `EN_REVISION` — el caso acumuló ambos documentos y quedó completo.

## Escenario 6 — Varios documentos en UN solo mensaje
Para mandar Plano + Lista juntos en el mismo turno:

1. 📎 adjuntá `plano_P102.pdf` (se sube).
2. 📎 adjuntá `lista_materiales_P102.xlsx` (se sube también).
   > El chip "adjunto pendiente" muestra solo el último, pero **ambos quedaron subidos** y entran juntos.
3. **Escribir:** `Entrega de fabricación del P-102, estructural: plano y lista de materiales`
   → `EN_REVISION` — completa de una.

---

## Variante por CLI (entrega multi-documento en un solo tiro)
La UI sube de a un archivo por turno; para mandar varios juntos:

```
uv run python scripts/run_local.py ^
  sandbox/test_fixtures/plano_P102.pdf ^
  sandbox/test_fixtures/lista_materiales_P102.xlsx ^
  --text "Entrega de fabricación P-102, disciplina estructural"
```
→ `EN_REVISION` (completa en un solo paso).

---

## Inventario de archivos
| Archivo | Qué es | Sirve para |
|---|---|---|
| `memoria_calculo_P102.pdf` | Memoria de cálculo (texto) | Escenario 1 (cálculo completo) |
| `plano_P102.pdf` | Plano de fabricación (texto/rótulo) | Escenarios 2 y 5 |
| `lista_materiales_P102.xlsx` | Lista de materiales (planilla) | Escenario 5 / CLI |
| `presupuesto.pdf` | Presupuesto comercial | Escenario 3 (irrelevante) |
