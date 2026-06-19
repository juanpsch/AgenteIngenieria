"""Evaluación POR ZONA (observabilidad): estado visual + lectura per-zona de las referencias."""
from graph.nodes import _estado_visual


def test_estado_visual_calibrado():
    # calibrado: el score DECIDE (pass/warn/fail por umbrales)
    assert _estado_visual(98, "calibrado", 96, 85) == "pass"
    assert _estado_visual(90, "calibrado", 96, 85) == "warn"   # zona de revisión
    assert _estado_visual(40, "calibrado", 96, 85) == "fail"   # logo tapado -> no cumple


def test_estado_visual_calibrando_marca_lo_bajo():
    # calibrando: informativo, pero lo claramente bajo se marca (para que SE VEA)
    assert _estado_visual(95, "calibrando", 96, 85) == "info"
    assert _estado_visual(40, "calibrando", 96, 85) == "warn"


def test_estado_visual_sin_score():
    assert _estado_visual(None, "calibrado", 96, 85) == "info"


def test_vectores_por_referencia_lee_zonas_si_existen():
    # No rompe aunque no haya backend/refs: devuelve lista (posiblemente vacía) con la clave 'zonas'.
    from tools import refs
    out = refs.vectores_por_referencia("hd_2")
    assert isinstance(out, list)
    for g in out:
        assert "zonas" in g and isinstance(g["zonas"], list)
