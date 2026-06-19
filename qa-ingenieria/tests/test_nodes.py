"""Ensamblado y dedup de checks (graph.nodes.armar_checks)."""
from graph.nodes import armar_checks


def test_dedup_por_dimension_y_label():
    llm = [{"dimension": "identidad", "label": "Es el tipo: X", "state": "fail", "requerido": True}]
    extra = [{"dimension": "identidad", "label": "Es el tipo: X", "state": "pass", "requerido": False}]
    checks = armar_checks(llm, extra)
    # gana el PRIMERO (autoritativo): el del LLM, no el extra duplicado.
    tipos = [c for c in checks if c["label"] == "Es el tipo: X"]
    assert len(tipos) == 1
    assert tipos[0]["state"] == "fail" and tipos[0]["requerido"] is True


def test_dedup_case_insensitive_y_trim():
    llm = [{"dimension": "completitud", "label": "Tiene rótulo", "state": "pass"}]
    extra = [{"dimension": "completitud", "label": "  tiene rótulo  ", "state": "warn"}]
    checks = armar_checks(llm, extra)
    assert len([c for c in checks if c["label"].lower().strip() == "tiene rótulo"]) == 1


def test_misma_label_distinta_dimension_no_colisiona():
    llm = [{"dimension": "identidad", "label": "Formato", "state": "pass"}]
    extra = [{"dimension": "completitud", "label": "Formato", "state": "warn"}]
    assert len(armar_checks(llm, extra)) == 2


def test_descarta_no_dicts_y_sin_label():
    checks = armar_checks([None, "x", {"dimension": "identidad", "label": ""}], [{"dimension": "identidad", "label": "OK"}])
    assert len(checks) == 1 and checks[0]["label"] == "OK"


def test_defaults_de_campos():
    c = armar_checks([{"label": "L"}], [])[0]
    assert c["dimension"] == "completitud" and c["state"] == "info" and c["requerido"] is False
