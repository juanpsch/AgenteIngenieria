"""Regla de admisión de la métrica (api.historial._admitido)."""
from api.historial import _admitido


def test_aprobacion_humana_manda_sobre_veredicto_automatico():
    assert _admitido({"decision": "approved", "veredicto": "invalido"}) is True


def test_rechazo_humano_manda_sobre_valido_automatico():
    assert _admitido({"decision": "rejected", "veredicto": "valido"}) is False


def test_sin_decision_usa_el_veredicto():
    assert _admitido({"veredicto": "valido"}) is True
    assert _admitido({"veredicto": "revision_manual"}) is False
    assert _admitido({"veredicto": "invalido"}) is False


def test_validacion_una_fila_por_thread(tmp_path, monkeypatch):
    import api.historial as hist
    monkeypatch.setattr(hist, "_DB", tmp_path / "h.sqlite")
    hist.init()
    hist.registrar_validacion("t1", "a.pdf", "tipo", "EN_TRIAGE", "valido", 90, "api", "f1")
    hist.registrar_validacion("t1", "a.pdf", "tipo", "EN_TRIAGE", "invalido", 40, "api", "f2")  # reenvío
    filas = [r for r in hist.listar() if r["thread_id"] == "t1"]
    assert len(filas) == 1 and filas[0]["veredicto"] == "invalido"  # una fila, la última


def test_requisito_feedback_persistencia_y_upsert(tmp_path, monkeypatch):
    import api.historial as hist
    monkeypatch.setattr(hist, "_DB", tmp_path / "h.sqlite")
    hist.init()
    rid = "aea-90364:aea_caida_tension"
    hist.registrar_requisito_feedback("t1", rid, "no_aplica", "2026-01-01",
                                      tipo_doc="memoria_electrica", estado="fallo", nota="no es de potencia")
    assert hist.feedback_de("t1")[rid]["juicio"] == "no_aplica"
    # re-juzgar la MISMA regla reemplaza (no duplica)
    hist.registrar_requisito_feedback("t1", rid, "de_acuerdo", "2026-01-02")
    fb = hist.feedback_de("t1")
    assert fb[rid]["juicio"] == "de_acuerdo" and len(fb) == 1
