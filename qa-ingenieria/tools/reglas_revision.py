"""Motor de reglas Tier 2 de la revisión de contenido (determinista, sin LLM).

Opera sobre el TEXTO y las TABLAS extraídas del documento. Cada regla devuelve un `Hallazgo`
(ver `graph/revision`). Tipos de regla:
  - `presencia`        : un patrón/etiqueta debe aparecer.
  - `presencia_unidad` : un valor con su unidad (sección con mm², tensión con V).
  - `patron`           : el patrón aparece ≥ `min` veces (default 1).
  - `norma_lookup`     : extrae valores numéricos (grupo de `captura`) y verifica `max`/`min`
                         (p. ej. caída de tensión ≤ 5%, sección ≥ 1,5 mm²).
  - `tabla`            : una tabla con las `columnas` requeridas. Si no se extrajo tabla → no_verificable
                         (las tablas dibujadas no se tabulan — no se inventa un ok/fallo).
Lo no medible cae a `no_verificable` (nunca un `ok` inventado).
"""

from __future__ import annotations

import re
from typing import Any

from graph.revision import Hallazgo, mk

_DIM_DEFAULT = {"presencia": "contenido", "presencia_unidad": "norma", "patron": "norma",
                "norma_lookup": "norma", "tabla": "consistencia"}


def _compilar(patron: str) -> re.Pattern:
    try:
        return re.compile(patron, re.IGNORECASE)
    except re.error:
        return re.compile(re.escape(patron), re.IGNORECASE)


def _meta(regla: dict) -> dict:
    tipo = regla.get("tipo", "")
    return {
        "check_id": regla.get("id", tipo or "regla"),
        "dimension": regla.get("dimension") or _DIM_DEFAULT.get(tipo, "norma"),
        "severidad": regla.get("severidad", "menor"),
        "fuente": "reglas",
        "norma_ref": regla.get("norma_ref"),
        "desc": regla.get("descripcion") or regla.get("id") or tipo,
    }


def _h(m: dict, estado: str, evidencia: str, sugerencia: str = "") -> Hallazgo:
    return mk(m["check_id"], m["dimension"], m["severidad"], estado, fuente=m["fuente"],
              evidencia=evidencia, razonamiento=m["desc"], sugerencia=sugerencia, norma_ref=m.get("norma_ref"))


def _unidad_rx(unidad: str) -> re.Pattern:
    esc = re.escape(unidad).replace("2", "[2²]").replace("3", "[3³]")
    return re.compile(r"\d+[.,]?\d*\s*" + esc, re.IGNORECASE)


def _presencia(r: dict, texto: str, m: dict) -> Hallazgo:
    hay = bool(_compilar(r.get("patron", "")).search(texto))
    return _h(m, "ok" if hay else "fallo",
              "se encontró en el documento" if hay else f"no se encontró: {m['desc']}",
              "" if hay else f"Incluir: {m['desc']}.")


def _presencia_unidad(r: dict, texto: str, m: dict) -> Hallazgo:
    u = r.get("unidad", "")
    if not u:
        return _h(m, "no_verificable", "regla 'presencia_unidad' sin 'unidad' configurada")
    hay = bool(_unidad_rx(u).search(texto))
    return _h(m, "ok" if hay else "fallo",
              f"hay valores con unidad «{u}»" if hay else f"no se encontró ningún valor con unidad «{u}»",
              "" if hay else f"Declarar el valor con su unidad ({u}).")


def _patron(r: dict, texto: str, m: dict) -> Hallazgo:
    n = len(_compilar(r.get("patron", "")).findall(texto))
    minimo = int(r.get("min", 1))
    ok = n >= minimo
    return _h(m, "ok" if ok else "fallo",
              f"{n} coincidencia(s) (mínimo {minimo})",
              "" if ok else f"Se esperaban ≥{minimo} ocurrencias del patrón.")


def _norma_lookup(r: dict, texto: str, m: dict) -> Hallazgo:
    vals: list[float] = []
    for mm in _compilar(r.get("captura", "")).finditer(texto):
        try:
            vals.append(float(mm.group(1).replace(",", ".")))
        except (ValueError, IndexError):
            continue
    if not vals:
        return _h(m, "no_verificable", "no se pudo extraer ningún valor para el chequeo")
    mx, mn = r.get("max"), r.get("min")
    viol = [v for v in vals if (mx is not None and v > mx) or (mn is not None and v < mn)]
    if not viol:
        lim = f"≤{mx}" if mx is not None else f"≥{mn}"
        return _h(m, "ok", f"{len(vals)} valor(es), todos dentro del límite ({lim})")
    lim = (f"máx {mx}" if mx is not None else "") + (f" / mín {mn}" if mn is not None else "")
    fuera = sorted({round(v, 2) for v in viol})[:6]
    return _h(m, "fallo", f"{len(viol)} valor(es) fuera de límite ({lim.strip()}): {fuera}",
              "Corregir los valores que exceden el límite de la norma.")


def _flat(tabla: Any) -> str:
    filas = tabla.get("filas") if isinstance(tabla, dict) else tabla
    return " ".join(" ".join(str(c or "") for c in (fila or [])) for fila in (filas or [])).lower()


def _tabla(r: dict, tablas: list, m: dict) -> Hallazgo:
    cols = [str(c).lower() for c in (r.get("columnas") or [])]
    if not tablas:
        return _h(m, "no_verificable",
                  "no se extrajo ninguna tabla (puede estar dibujada, no tabulada)")
    if not cols:
        return _h(m, "ok", f"{len(tablas)} tabla(s) detectada(s)")
    match = next((t for t in tablas if all(c in _flat(t) for c in cols)), None)
    if match:
        return _h(m, "ok", f"columnas requeridas presentes: {cols}")
    return _h(m, "fallo", f"se extrajeron {len(tablas)} tabla(s) pero faltan columnas {cols}",
              "Verificar que la tabla incluya todas las columnas requeridas.")


_DISPATCH = {"presencia": _presencia, "presencia_unidad": _presencia_unidad, "patron": _patron,
             "norma_lookup": _norma_lookup}


def evaluar_regla(regla: dict, texto: str, tablas: list | None = None) -> Hallazgo:
    """Evalúa UNA regla Tier 2 sobre (texto, tablas) y devuelve su hallazgo."""
    m = _meta(regla)
    tipo = regla.get("tipo", "")
    if tipo == "tabla":
        return _tabla(regla, tablas or [], m)
    fn = _DISPATCH.get(tipo)
    if not fn:
        return _h(m, "no_verificable", f"tipo de regla desconocido: «{tipo}»")
    return fn(regla, texto or "", m)
