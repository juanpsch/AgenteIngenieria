"""Tier 3 (observación VLM) — parseo de observaciones + gating (sin llamar al LLM)."""
from ai_agents.revisor import _a_hallazgos_vlm, _tier3_vlm
from graph.revision import agregar_revision


def test_parseo_observaciones_a_hallazgos():
    obs = [
        {"observacion": "la escala no condice con las cotas", "severidad": "mayor", "dimension": "consistencia",
         "pagina": 3, "razonamiento": "r", "norma_ref": "AEA 90364"},
        {"descripcion": "anotaciones incompletas"},          # sin severidad/dim -> defaults
        {"observacion": ""},                                  # vacía -> se descarta
        "no-dict",                                            # basura -> se descarta
    ]
    h = _a_hallazgos_vlm(obs)
    assert len(h) == 2
    assert h[0]["fuente"] == "vlm" and h[0]["estado"] == "advertencia"
    assert h[0]["severidad"] == "mayor" and h[0]["ubicacion"]["pagina"] == 3
    assert h[1]["severidad"] == "observacion" and h[1]["dimension"] == "norma"  # defaults


def test_vlm_no_bloquea_aunque_sea_mayor():
    # una observación VLM 'mayor' NO debe pasar de aprobado_con_notas (§2.2)
    h = _a_hallazgos_vlm([{"observacion": "x", "severidad": "mayor"}])
    assert agregar_revision(h)["verdicto"] == "aprobado_con_notas"


def test_tier3_apagado_devuelve_vacio(monkeypatch):
    monkeypatch.setenv("REVISION_VLM", "0")
    assert _tier3_vlm({"contenido": "x", "imagenes": []}, {"normas": ["aea-90364"]}) == []


def test_tier3_sin_criterios_devuelve_vacio(monkeypatch):
    monkeypatch.setenv("REVISION_VLM", "1")
    # template sin normas ni instrucciones -> no hay criterios -> [] sin llamar al LLM
    assert _tier3_vlm({"contenido": "x", "imagenes": []}, {"reglas": []}) == []
