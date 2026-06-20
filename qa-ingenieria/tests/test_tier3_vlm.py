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


def _mock_llm(monkeypatch, json_out):
    import ai_agents.provider
    import ai_agents.util
    monkeypatch.setattr(ai_agents.provider, "build_agent", lambda *a, **k: object())
    monkeypatch.setattr(ai_agents.util, "run_agent", lambda *a, **k: json_out)


def test_revisar_no_corre_vlm_aunque_este_disponible(monkeypatch):
    # El VLM es A PEDIDO: revisar() (auto) NO debe incluir hallazgos fuente=vlm aunque el LLM responda.
    from ai_agents.revisor import revisar
    monkeypatch.setenv("REVISION_VLM", "1")
    _mock_llm(monkeypatch, '{"observaciones":[{"observacion":"x","severidad":"mayor"}]}')
    h = revisar({"contenido": "memoria", "imagenes": [], "path": None}, {"normas": ["aea-90364"]})
    assert not any(x.get("fuente") == "vlm" for x in h)


def test_observar_vlm_fuerza_aunque_flag_off(monkeypatch):
    # observar_vlm ignora REVISION_VLM=0 y sí produce la observación (es la acción a pedido).
    from ai_agents.revisor import observar_vlm
    monkeypatch.setenv("REVISION_VLM", "0")
    _mock_llm(monkeypatch, '{"observaciones":[{"observacion":"símbolo sin leyenda","severidad":"menor"}]}')
    h = observar_vlm({"contenido": "y", "imagenes": []}, {"normas": ["iram-instrumentacion"]})
    assert h and h[0]["fuente"] == "vlm" and h[0]["estado"] == "advertencia"
