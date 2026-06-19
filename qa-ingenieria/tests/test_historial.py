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
