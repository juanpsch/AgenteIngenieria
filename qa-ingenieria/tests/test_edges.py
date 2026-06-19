"""Routers del grafo (graph.edges), ambos modos."""
from graph.edges import route_entry, route_post_triage, route_triage, route_validation


# ---------- entrada / validación ----------
def test_route_entry():
    assert route_entry({}) == "parser"
    assert route_entry({"ref_thread_id": "t1"}) == "clasificador"


def test_route_validation():
    assert route_validation({}) == "ok"
    assert route_validation({"faltan_minimos": ["proyecto"]}) == "faltan"


# ---------- Cotejar (single-doc) ----------
def _ident(state_ok=True, compl_ok=True, score_v=None):
    checks = [
        {"dimension": "identidad", "label": "Es el tipo", "state": "pass" if state_ok else "fail", "requerido": True},
        {"dimension": "completitud", "label": "Campos", "state": "pass" if compl_ok else "fail", "requerido": True},
    ]
    return {"tipo_objetivo": "x", "checks": checks, "score_veredicto": score_v}


def test_cotejar_identidad_falla_es_invalido():
    assert route_post_triage(_ident(state_ok=False)) == "invalido"


def test_cotejar_score_invalido_pesa_aunque_identidad_pase():
    assert route_post_triage(_ident(score_v="invalido")) == "invalido"


def test_cotejar_score_revision():
    assert route_post_triage(_ident(score_v="revision_manual")) == "revision_manual"


def test_cotejar_completitud_falla_es_revision():
    assert route_post_triage(_ident(compl_ok=False)) == "revision_manual"


def test_cotejar_todo_ok_es_valido():
    assert route_post_triage(_ident(score_v="valido")) == "valido"
    assert route_post_triage(_ident(score_v=None)) == "valido"  # no calibrado: decide por reglas


# ---------- Entrega (multi-doc) ----------
def test_entrega_irrelevantes_invalido():
    st = {"admisibilidad": {"irrelevantes": ["a.pdf"]}, "documentos": []}
    assert route_post_triage(st) == "invalido"


def test_entrega_formato_malo_invalido():
    st = {"admisibilidad": {}, "documentos": [{"formato_ok": False}]}
    assert route_post_triage(st) == "invalido"


def test_entrega_faltantes_incompleta():
    st = {"admisibilidad": {"faltantes": ["plano"]}, "documentos": [{"relevante": True}]}
    assert route_post_triage(st) == "incompleta"


def test_entrega_ok_valido():
    st = {"admisibilidad": {}, "documentos": [{"relevante": True, "formato_ok": True}]}
    assert route_post_triage(st) == "valido"


def test_route_triage_legacy():
    assert route_triage({"admisibilidad": {"irrelevantes": ["x"]}}) == "no_admisible"
    assert route_triage({"admisibilidad": {"faltantes": ["y"]}}) == "incompleta"
    assert route_triage({"admisibilidad": {}}) == "revision"
