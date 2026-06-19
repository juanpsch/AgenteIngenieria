"""Aprendedor de requisitos (api.aprendizaje.computar_sugerencias) — la matriz §5, pura."""
from api.aprendizaje import computar_sugerencias

CAT = [
    {"req_id": "aea-90364:caida", "descripcion": "caída ≤5%", "norma_ref": "AEA 90364"},
    {"req_id": "aea-90364:seccion", "descripcion": "sección ≥1.5", "norma_ref": "AEA 90364"},
    {"req_id": "aea-90364:cuadro", "descripcion": "cuadro de cargas", "norma_ref": "AEA 90364"},
]


def _corpus(*filas):
    # cada fila: (admitido, {req_id: estado})
    return [{"admitido": a, "requisitos": r} for a, r in filas]


def test_sugerir_agregar_si_aprobados_cumplen():
    # 'caida' no asignado, pasa en 3/3 aprobados -> sugerir agregar
    corpus = _corpus((True, {"aea-90364:caida": "ok"}), (True, {"aea-90364:caida": "ok"}),
                     (True, {"aea-90364:caida": "ok"}))
    s = computar_sugerencias(set(), corpus, {}, CAT, set())
    ids = {x["req_id"] for x in s["agregar"]}
    assert "aea-90364:caida" in ids


def test_sugerir_quitar_si_falla_en_aprobados():
    # 'cuadro' asignado pero falla en los aprobados -> sugerir quitar (celda B)
    corpus = _corpus((True, {"aea-90364:cuadro": "fallo"}), (True, {"aea-90364:cuadro": "fallo"}))
    s = computar_sugerencias({"aea-90364:cuadro"}, corpus, {}, CAT, set())
    assert {x["req_id"] for x in s["quitar"]} == {"aea-90364:cuadro"}


def test_no_verificable_no_cuenta():
    # solo no_verificable -> sin datos suficientes -> no sugiere nada
    corpus = _corpus((True, {"aea-90364:caida": "no_verificable"}), (True, {"aea-90364:caida": "no_verificable"}))
    s = computar_sugerencias(set(), corpus, {}, CAT, set())
    assert not s["agregar"] and not s["quitar"]


def test_feedback_no_aplica_sugiere_quitar():
    s = computar_sugerencias({"aea-90364:seccion"}, [], {"aea-90364:seccion": {"no_aplica": 2}}, CAT, set())
    assert {x["req_id"] for x in s["quitar"]} == {"aea-90364:seccion"}


def test_prior_por_disciplina_en_frio():
    # sin corpus, el prior sugiere lo usado por otras familias de la disciplina
    s = computar_sugerencias(set(), [], {}, CAT, {"aea-90364:caida"})
    assert {x["req_id"] for x in s["prior_disciplina"]} == {"aea-90364:caida"}


def test_lo_ya_asignado_no_se_re_sugiere():
    corpus = _corpus((True, {"aea-90364:caida": "ok"}), (True, {"aea-90364:caida": "ok"}))
    s = computar_sugerencias({"aea-90364:caida"}, corpus, {}, CAT, {"aea-90364:caida"})
    assert not any(x["req_id"] == "aea-90364:caida" for x in s["agregar"])
    assert not any(x["req_id"] == "aea-90364:caida" for x in s["prior_disciplina"])
