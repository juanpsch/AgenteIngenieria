"""Aprendedor de aplicabilidad de requisitos (Fase 1, Paso 5).

Mina el corpus de una familia (resultado por requisito × decisión humana — la matriz §5 del diseño) y
PROPONE ajustar el set de requisitos. Nada se auto-aplica: el humano confirma (PUT /tipos/{id}/requisitos).

Señal principal (decidida): que los **aprobados lo cumplan**. Secundarias: feedback explícito por regla
(`no_aplica`/`de_acuerdo`) y, para familias nuevas, **prior por disciplina**.
"""

from __future__ import annotations

from typing import Any

from api import historial


def _minq(q: dict[str, Any], req_id: str) -> dict[str, Any]:
    return {"req_id": req_id, "descripcion": q.get("descripcion") or q.get("id") or req_id,
            "norma_ref": q.get("norma_ref"), "severidad": q.get("severidad")}


def computar_sugerencias(asignados: set[str], corpus: list[dict], feedback: dict[str, dict[str, int]],
                         catalogo: list[dict], prior: set[str],
                         min_casos: int = 2, umbral: float = 0.8) -> dict[str, list]:
    """Pura (testeable sin DB). `corpus` = [{admitido, requisitos:{req_id:estado}}]; `feedback` =
    {req_id:{juicio:n}}; `prior` = req_ids usados por familias de la misma disciplina."""
    cat = {q["req_id"]: q for q in catalogo}
    aprob = [c for c in corpus if c.get("admitido")]

    # cumplimiento por requisito en APROBADOS (solo estados verificables ok/fallo)
    stats: dict[str, dict[str, int]] = {}
    for c in aprob:
        for rid, est in (c.get("requisitos") or {}).items():
            if est in ("ok", "fallo"):
                s = stats.setdefault(rid, {"ok": 0, "tot": 0})
                s["tot"] += 1
                s["ok"] += int(est == "ok")

    agregar: list[dict] = []
    quitar: list[dict] = []
    ag_ids: set[str] = set()
    qu_ids: set[str] = set()

    for rid, s in stats.items():
        if s["tot"] < min_casos:
            continue
        rate = s["ok"] / s["tot"]
        q = cat.get(rid, {})
        if rid not in asignados and rate >= umbral:           # A: los aprobados lo cumplen
            agregar.append({**_minq(q, rid), "motivo": "aprobados_cumplen",
                            "evidencia": f"{s['ok']}/{s['tot']} aprobados lo cumplen", "n": s["ok"], "total": s["tot"]})
            ag_ids.add(rid)
        elif rid in asignados and rate <= (1 - umbral):       # B: falla en aprobados
            quitar.append({**_minq(q, rid), "motivo": "falla_en_aprobados",
                           "evidencia": f"{s['tot'] - s['ok']}/{s['tot']} aprobados NO lo cumplen", "n": s["tot"] - s["ok"], "total": s["tot"]})
            qu_ids.add(rid)

    # Feedback humano explícito por regla (más fuerte que inferir).
    for rid, fb in (feedback or {}).items():
        q = cat.get(rid, {})
        if fb.get("no_aplica", 0) >= min_casos and rid in asignados and rid not in qu_ids:
            quitar.append({**_minq(q, rid), "motivo": "feedback_no_aplica",
                           "evidencia": f"{fb['no_aplica']} marcas «no aplica»"})
            qu_ids.add(rid)
        if fb.get("de_acuerdo", 0) >= min_casos and rid not in asignados and rid not in ag_ids:
            agregar.append({**_minq(q, rid), "motivo": "feedback_de_acuerdo",
                            "evidencia": f"{fb['de_acuerdo']} marcas «de acuerdo»"})
            ag_ids.add(rid)

    # Prior por disciplina (arranque en frío): usados por otras familias de la disciplina, sin datos acá.
    prior_sug = [{**_minq(cat.get(rid, {}), rid), "motivo": "prior_disciplina",
                  "evidencia": "usado por templates de la misma disciplina"}
                 for rid in sorted(prior) if rid not in asignados and rid not in stats and rid not in ag_ids]

    return {"agregar": agregar, "quitar": quitar, "prior_disciplina": prior_sug}


def sugerir_requisitos(tipo_doc: str) -> dict[str, list]:
    """Arma las sugerencias para una familia desde su corpus + catálogo + prior por disciplina."""
    from tools import normas
    from tools.tipos import cargar_tipos

    tpls = cargar_tipos()
    tpl = tpls.get(tipo_doc) or {}
    asignados = {r["req_id"] for r in normas.resolver_requisitos(tpl.get("revision") or {}) if r.get("req_id")}

    discs = {d.lower() for d in tpl.get("disciplinas") or []}
    prior: set[str] = set()
    for tid, t in tpls.items():
        if tid == tipo_doc or not (discs & {d.lower() for d in t.get("disciplinas") or []}):
            continue
        prior |= {r["req_id"] for r in normas.resolver_requisitos(t.get("revision") or {}) if r.get("req_id")}

    return computar_sugerencias(asignados, historial.corpus_requisitos(tipo_doc),
                                historial.feedback_agg(tipo_doc), normas.catalogo_requisitos(), prior)
