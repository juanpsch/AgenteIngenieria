"""Tipos de documento + sus templates (knowledge/tipos/*.yaml).

Cada tipo de documento es de primera clase: tiene un template híbrido (campos
estructurados + notas en prosa) contra el que el triage chequea cada documento
recibido. Fuente de verdad = archivos YAML en knowledge/tipos/.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_TIPOS_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "tipos"
# Orden de campos al serializar (lectura más natural del YAML)
_ORDEN = [
    "tipo_doc", "nombre", "disciplinas", "formatos_archivo", "cajetin",
    "zona_identidad",
    "secciones_requeridas", "columnas_requeridas", "caracteristicas", "nomenclatura",
    "bloqueante", "senales_reconocimiento", "criterios_aceptacion", "no_corresponde",
]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", (s or "").strip().lower()).strip("_")


def to_yaml(data: dict[str, Any]) -> str:
    """Serializa un template a YAML, con los campos conocidos primero."""
    ordenado = {k: data[k] for k in _ORDEN if k in data}
    ordenado.update({k: v for k, v in data.items() if k not in ordenado})
    return yaml.safe_dump(ordenado, allow_unicode=True, sort_keys=False)


def eliminar_tipo(tipo_doc: str) -> bool:
    """Borra knowledge/tipos/<tipo_doc>.yaml. Devuelve True si existía."""
    path = _TIPOS_DIR / f"{slug(tipo_doc)}.yaml"
    if path.exists():
        path.unlink()
        cargar_tipos.cache_clear()
        return True
    return False


def guardar_template(tipo_doc: str, yaml_text: str) -> Path:
    """Valida y guarda un template en knowledge/tipos/<tipo_doc>.yaml. Lanza si el YAML
    es inválido o no trae tipo_doc. Limpia la cache para que aparezca enseguida."""
    parsed = yaml.safe_load(yaml_text)
    if not isinstance(parsed, dict):
        raise ValueError("el contenido no es un YAML de objeto válido")
    tid = slug(tipo_doc or parsed.get("tipo_doc", ""))
    if not tid:
        raise ValueError("falta un tipo_doc válido (id en minúsculas)")
    _TIPOS_DIR.mkdir(parents=True, exist_ok=True)
    path = _TIPOS_DIR / f"{tid}.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    cargar_tipos.cache_clear()
    return path


def _norm_bbox(b: dict) -> dict[str, float]:
    return {k: round(float(b.get(k, 0)), 4) for k in ("x", "y", "w", "h")}


def _norm_zona(z: dict) -> dict[str, Any]:
    """Normaliza una zona gráfica:
    {nombre, pagina, bbox, identidad, campo, patron, tipo, requerido, ancla_inicio, ancla_fin}."""
    out: dict[str, Any] = {
        "nombre": (z.get("nombre") or "Zona").strip(),
        "pagina": max(1, int(z.get("pagina", 1) or 1)),
        "bbox": _norm_bbox(z.get("bbox") or z),
    }
    if z.get("identidad"):
        out["identidad"] = True
    for k in ("campo", "patron", "tipo", "ancla_inicio", "ancla_fin", "comparar"):
        if z.get(k):
            out[k] = str(z[k]).strip()
    if z.get("campo"):
        out["requerido"] = bool(z.get("requerido", True))
    return out


def guardar_zonas(tipo_doc: str, zonas: list[dict] | None) -> dict[str, Any] | None:
    """Reescribe las `zonas` gráficas de un template (regiones donde buscar lo importante).
    Cada zona: {nombre, bbox{x,y,w,h}, identidad?, campo?, patron?, tipo?, requerido?}.
    La zona con `identidad:true` se usa para el score visual; las que tienen `campo` definen
    una regla determinista sobre el valor que el LLM extraiga de ahí. Devuelve el template."""
    tipo = cargar_tipos().get(tipo_doc)
    if not tipo:
        return None
    tipo = {k: v for k, v in tipo.items() if k not in ("zonas", "zona_identidad")}
    if zonas:
        tipo["zonas"] = [_norm_zona(z) for z in zonas]
    guardar_template(tipo_doc, to_yaml(tipo))
    return cargar_tipos().get(tipo_doc)


def zonas_identidad_de(tipo: dict[str, Any]) -> list[dict[str, Any]]:
    """Todas las zonas de identidad (para el score visual): las marcadas identidad:true (pueden
    estar en distintas páginas). Fallback al campo legacy `zona_identidad` como una zona pág. 1."""
    ident = [z for z in (tipo.get("zonas") or []) if z.get("identidad") and z.get("bbox")]
    if ident:
        return ident
    legacy = tipo.get("zona_identidad")
    return [{"nombre": "Identidad", "pagina": 1, "bbox": legacy, "identidad": True}] if legacy else []


def zonas_visuales_de(tipo: dict[str, Any]) -> list[dict[str, Any]]:
    """Zonas que alimentan el SCORE VISUAL: las de identidad + las marcadas `comparar: visual`
    (ej. logo/sello de posición variable). Cada una se recorta y embebe."""
    vis = [z for z in (tipo.get("zonas") or [])
           if (z.get("identidad") or z.get("comparar") == "visual") and z.get("bbox")]
    return vis or zonas_identidad_de(tipo)


def zona_identidad_de(tipo: dict[str, Any]) -> dict[str, float] | None:
    """Bbox de la primera zona de identidad (compat / display en página 1)."""
    zs = zonas_identidad_de(tipo)
    return zs[0]["bbox"] if zs else None


def set_patron_regla(tipo_doc: str, campo: str, patron: str) -> dict[str, Any] | None:
    """Aplica una variante de patrón a la regla de un campo (en zonas o cajetin.reglas); si no
    existe, la agrega a cajetin.reglas. Reescribe el YAML. Para el feedback de reglas."""
    import copy

    base = cargar_tipos().get(tipo_doc)
    if not base:
        return None
    tipo = copy.deepcopy(base)
    encontrada = False
    for z in tipo.get("zonas") or []:
        if z.get("campo") == campo:
            z["tipo"] = "regex"
            z["patron"] = patron
            encontrada = True
    caj = tipo.get("cajetin") or {}
    for r in caj.get("reglas") or []:
        if r.get("campo") == campo:
            r["patron"] = patron
            encontrada = True
    if not encontrada:
        caj.setdefault("reglas", []).append({"campo": campo, "patron": patron, "requerido": True})
        tipo["cajetin"] = caj
    guardar_template(tipo_doc, to_yaml(tipo))
    return cargar_tipos().get(tipo_doc)


def reglas_de(tipo: dict[str, Any]) -> list[dict[str, Any]]:
    """Reglas deterministas del template: las derivadas de zonas con `campo` + `cajetin.reglas`.
    Cada una: {campo, patron?, tipo?, requerido, zona?}."""
    out: list[dict[str, Any]] = []
    for z in tipo.get("zonas") or []:
        if z.get("campo"):
            out.append({"campo": z["campo"], "patron": z.get("patron"), "tipo": z.get("tipo"),
                        "requerido": bool(z.get("requerido", True)), "zona": z.get("nombre")})
    for r in (tipo.get("cajetin") or {}).get("reglas") or []:
        out.append(r)
    return out


@lru_cache(maxsize=1)
def cargar_tipos() -> dict[str, dict[str, Any]]:
    """Devuelve {tipo_doc: template}. Cachea; usar `cargar_tipos.cache_clear()` al editar."""
    tipos: dict[str, dict[str, Any]] = {}
    if not _TIPOS_DIR.exists():
        return tipos
    for f in sorted(_TIPOS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            # La identidad es el NOMBRE DE ARCHIVO (no el campo interno): así
            # ver/editar/borrar siempre apuntan al mismo archivo. Normalizamos
            # tipo_doc para que coincida y no diverja.
            tid = f.stem
            data["tipo_doc"] = tid
            tipos[tid] = data
        except Exception:
            continue  # un template roto no tumba el resto
    return tipos


def template_de(tipo_doc: str) -> dict[str, Any] | None:
    return cargar_tipos().get(tipo_doc)


def render_template(tipo: dict[str, Any]) -> str:
    """Render legible (para el prompt del LLM y para la UI)."""
    L: list[str] = [f"### {tipo.get('tipo_doc')} — {tipo.get('nombre', '')}"]
    if tipo.get("formatos_archivo"):
        L.append(f"- Formatos de archivo aceptados: {', '.join(tipo['formatos_archivo'])}")
    caj = tipo.get("cajetin") or {}
    if caj.get("requerido") or caj.get("campos_requeridos"):
        campos = ", ".join(caj.get("campos_requeridos", []))
        logo = "; con logo de la empresa" if caj.get("logo_empresa") else ""
        L.append(f"- Cajetín/rótulo requerido. Campos: {campos or '(no especificados)'}{logo}")
    if caj.get("reglas"):
        L.append("- Reglas de campos del cajetín (patrón regex):")
        for r in caj["reglas"]:
            req = "requerido" if r.get("requerido") else "opcional"
            pat = f" · patrón `{r['patron']}`" if r.get("patron") else ""
            L.append(f"    · {r.get('campo')} ({req}){pat}")
    if tipo.get("secciones_requeridas"):
        L.append(f"- Secciones requeridas: {', '.join(tipo['secciones_requeridas'])}")
    if tipo.get("columnas_requeridas"):
        L.append(f"- Columnas requeridas: {', '.join(tipo['columnas_requeridas'])}")
    if tipo.get("caracteristicas"):
        L.append("- Características requeridas:")
        L += [f"    · {c}" for c in tipo["caracteristicas"]]
    if tipo.get("nomenclatura"):
        L.append(f"- Nomenclatura (orientativa): {tipo['nomenclatura']}")
    if tipo.get("bloqueante"):
        L.append("- BLOQUEANTE (si pasa algo de esto, NO admisible):")
        L += [f"    · {b}" for b in tipo["bloqueante"]]
    for campo, etiqueta in (
        ("senales_reconocimiento", "Señales para reconocerlo"),
        ("criterios_aceptacion", "Criterios de aceptación"),
        ("no_corresponde", "Qué NO corresponde"),
    ):
        if tipo.get(campo):
            L.append(f"- {etiqueta}: {str(tipo[campo]).strip()}")
    return "\n".join(L)
