"""Chequeo determinístico de reglas de campos del cajetín (Cotejar Fase A).

Aplica regex sobre el texto extraído del documento. NO usa LLM (los patrones son
determinísticos; lo cualitativo va por el triage). Degrada con gracia: si no hay
texto extraíble o el patrón es inválido, devuelve `warn` (nunca un `pass` inventado).

Devuelve `Check` de dimensión "completitud".
"""

from __future__ import annotations

import re
from typing import Any

Check = dict[str, Any]


def chequear_reglas(texto: str, reglas: list[dict[str, Any]] | None) -> list[Check]:
    checks: list[Check] = []
    hay_texto = bool((texto or "").strip())
    for r in reglas or []:
        campo = r.get("campo") or "(campo)"
        patron = (r.get("patron") or "").strip()
        requerido = bool(r.get("requerido"))
        label = f"Campo '{campo}' presente"

        if not hay_texto:
            checks.append(_chk(label, "warn", "sin texto extraíble — no verificable", requerido))
            continue

        if patron:
            try:
                ok = bool(re.search(patron, texto, re.IGNORECASE | re.MULTILINE))
            except re.error:
                checks.append(_chk(label, "warn", f"patrón inválido: {patron}", requerido))
                continue
            if ok:
                checks.append(_chk(label, "pass", f"cumple patrón {patron}", requerido))
            else:
                checks.append(_chk(label, "fail" if requerido else "warn",
                                   "Falta el campo o no cumple el patrón esperado", requerido))
        else:
            # Sin patrón: chequeo laxo de presencia del nombre del campo
            ok = campo.lower() in texto.lower()
            if ok:
                checks.append(_chk(label, "pass", "presente", requerido))
            else:
                checks.append(_chk(label, "warn", "no se pudo confirmar (sin patrón)", requerido))
    return checks


def _chk(label: str, state: str, detail: str, requerido: bool) -> Check:
    return {"dimension": "completitud", "label": label, "state": state,
            "detail": detail, "requerido": requerido}


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _tokens(s: Any) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", str(s or "").lower()) if t}


def _clave(s: Any, patron: str) -> str:
    """Si hay patrón, extrae la primera coincidencia (la 'clave' a comparar); si no, el valor tal cual."""
    s = str(s or "")
    if patron:
        try:
            m = re.search(patron, s, re.IGNORECASE)
            if m:
                return m.group(0)
        except re.error:
            pass
    return s


def _coincide_codigo(a: Any, b: Any) -> bool:
    """¿El código del documento y el nombre de archivo refieren al mismo doc? Tolerante:
    coincide si uno es substring del otro (normalizado) o si los TOKENS de uno son subconjunto
    de los del otro (p. ej. el filename es una versión corta del código)."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta) and bool(tb) and (ta <= tb or tb <= ta)


def chequear_campos(campos: dict[str, Any] | None, filename: str,
                    reglas: list[dict[str, Any]] | None) -> list[Check]:
    """Validación DETERMINISTA sobre valores YA extraídos por el LLM (extract-then-check).

    `campos`: {campo: valor} que el LLM encontró en el documento. `reglas`: cada una con
    `tipo`: 'regex' (default si hay patrón) | 'filename' (el valor debe coincidir con el nombre
    de archivo — señal de IDENTIDAD) | 'presencia'. El LLM solo *encuentra* el dato; acá se
    decide pass/fail sin LLM. Degrada con `warn` si no hay valor / patrón inválido.
    """
    checks: list[Check] = []
    fbase = str(filename or "").rsplit(".", 1)[0]  # nombre sin extensión
    for r in reglas or []:
        campo = r.get("campo") or "(campo)"
        patron = (r.get("patron") or "").strip()
        tipo = (r.get("tipo") or ("regex" if patron else "presencia")).lower()
        requerido = bool(r.get("requerido", True))
        valor = (campos or {}).get(campo)
        valor = valor.strip() if isinstance(valor, str) else valor
        # metadata que viaja en el check para el feedback (proponer variante de regla)
        m = {"campo": campo, "patron": patron, "valor": valor, "regla_tipo": tipo}

        if tipo == "filename":
            label = f"Código «{campo}» coincide con el nombre de archivo"
            if not valor:
                checks.append(_chki("identidad", label, "warn", "no se encontró el código en el documento", requerido, **m))
                continue
            ok = _coincide_codigo(_clave(valor, patron), _clave(fbase, patron))
            checks.append(_chki("identidad", label, "pass" if ok else ("fail" if requerido else "warn"),
                                f"«{valor}» {'coincide con' if ok else 'NO coincide con'} «{filename}»", requerido, **m))
            continue

        label = f"Campo «{campo}» presente"
        if not valor:
            checks.append(_chki("completitud", label, "fail" if requerido else "warn",
                                "no se encontró en el documento", requerido, **m))
            continue
        if tipo == "regex" and patron:
            try:
                ok = bool(re.search(patron, str(valor), re.IGNORECASE))
            except re.error:
                checks.append(_chki("completitud", label, "warn", f"patrón inválido: {patron}", requerido, **m))
                continue
            checks.append(_chki("completitud", label, "pass" if ok else ("fail" if requerido else "warn"),
                                f"«{valor}» {'cumple' if ok else 'NO cumple'} {patron}", requerido, **m))
        else:  # presencia
            checks.append(_chki("completitud", label, "pass", f"«{valor}»", requerido, **m))
    return checks


def _chki(dim: str, label: str, state: str, detail: str, requerido: bool, **extra: Any) -> Check:
    base = {"dimension": dim, "label": label, "state": state, "detail": detail, "requerido": requerido}
    base.update({k: v for k, v in extra.items() if v not in (None, "")})
    return base


def verificar_variante(patron: str, deben: list[str], no_deben: list[str]) -> dict[str, Any]:
    """Verifica DETERMINÍSTICAMENTE una regex candidata: ¿matchea todos los valores que DEBEN
    pasar y ninguno de los que NO? (núcleo de seguridad del feedback de reglas)."""
    d = [str(v) for v in (deben or []) if v]
    nd = [str(v) for v in (no_deben or []) if v]
    try:
        rx = re.compile(patron, re.IGNORECASE)
    except re.error:
        return {"ok": False, "error": True, "cubre": 0, "total": len(d), "matchea_negativos": 0}
    cubre = sum(1 for v in d if rx.search(v))
    neg = sum(1 for v in nd if rx.search(v))
    return {"ok": cubre == len(d) and neg == 0, "error": False,
            "cubre": cubre, "total": len(d), "matchea_negativos": neg}
