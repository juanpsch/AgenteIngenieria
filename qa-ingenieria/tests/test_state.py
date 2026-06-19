"""Umbralado del score + mapeo de veredicto (graph.state)."""
from graph.state import clasificar_score, umbrales_score, veredicto_ui


def test_clasificar_score_global(monkeypatch):
    monkeypatch.setenv("APPROVAL_THRESHOLD", "96")
    monkeypatch.setenv("REVISION_THRESHOLD", "85")
    assert clasificar_score(99) == "valido"
    assert clasificar_score(96) == "valido"          # límite inclusivo
    assert clasificar_score(95.9) == "revision_manual"
    assert clasificar_score(85) == "revision_manual"
    assert clasificar_score(84.9) == "invalido"
    assert clasificar_score(0) == "invalido"


def test_clasificar_score_umbrales_por_template():
    # Los umbrales auto-calibrados se pasan explícitos y mandan sobre el entorno.
    um = (69.0, 60.0)
    assert clasificar_score(70, um) == "valido"
    assert clasificar_score(65, um) == "revision_manual"
    assert clasificar_score(59, um) == "invalido"


def test_umbrales_score_lee_entorno(monkeypatch):
    monkeypatch.setenv("APPROVAL_THRESHOLD", "90")
    monkeypatch.setenv("REVISION_THRESHOLD", "70")
    assert umbrales_score() == (90.0, 70.0)


def test_veredicto_ui():
    assert veredicto_ui("EN_REVISION") == "valido"
    assert veredicto_ui("APROBADO") == "valido"
    assert veredicto_ui("REQUIERE_DECISION") == "revision_manual"
    assert veredicto_ui("NO_ADMISIBLE") == "invalido"
    assert veredicto_ui("RECHAZADO") == "invalido"
    assert veredicto_ui("INCOMPLETA") == "faltan_datos"
    assert veredicto_ui("DESCONOCIDO") == "faltan_datos"  # default conservador
