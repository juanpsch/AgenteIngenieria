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


def test_vlm_payload_adjunta_la_leyenda_de_referencia(monkeypatch):
    # si la norma trae vlm.referencia_imagen, _vlm_payload se la pasa al VLM ANTES del documento
    from ai_agents import revisor
    import ai_agents.provider
    import ai_agents.util
    cap = {}
    monkeypatch.setattr(ai_agents.provider, "build_agent", lambda *a, **k: object())
    monkeypatch.setattr(ai_agents.util, "build_input", lambda text, images: cap.update(imgs=images) or {})
    monkeypatch.setattr(ai_agents.util, "run_agent", lambda agent, inp: '{"reglas":[],"observaciones":[]}')
    monkeypatch.setattr(revisor, "_cargar_referencia", lambda r: "data:image/png;base64,REF")
    revisor._vlm_payload({"contenido": "x", "imagenes": ["DOC"]}, {"normas": ["camuzzi"]}, [])
    assert cap["imgs"][0] == "data:image/png;base64,REF"   # la leyenda va primero
    assert "DOC" in cap["imgs"]                            # el documento, después


def test_observar_vlm_fuerza_aunque_flag_off(monkeypatch):
    # observar_vlm ignora REVISION_VLM=0 y sí produce la observación (es la acción a pedido).
    from ai_agents.revisor import observar_vlm
    monkeypatch.setenv("REVISION_VLM", "0")
    _mock_llm(monkeypatch, '{"observaciones":[{"observacion":"símbolo sin leyenda","severidad":"menor"}]}')
    h = observar_vlm({"contenido": "y", "imagenes": []}, {"normas": ["iram-instrumentacion"]})
    assert h and h[0]["fuente"] == "vlm" and h[0]["estado"] == "advertencia"


def _regla_fallo():
    from graph.revision import mk
    return mk("isa_tags", "norma", "mayor", "fallo", razonamiento="tags ISA presentes",
              fuente="reglas", req_id="iram-instrumentacion:isa_tags_instrumento", norma_ref="ISA-5.1")


def test_verificar_reglas_vlm_actualiza_marca_y_recalcula(monkeypatch):
    from ai_agents.revisor import verificar_reglas_vlm
    from graph.revision import agregar_revision
    _mock_llm(monkeypatch, '{"reglas":[{"id":"isa_tags","veredicto":"ok","razon":"se ven tags TIC/FT"}],"observaciones":[]}')
    base = [_regla_fallo()]
    assert agregar_revision(base)["verdicto"] == "observado"          # por texto: falla
    out = verificar_reglas_vlm({"contenido": "x", "imagenes": []}, {"normas": ["iram-instrumentacion"]}, base)
    h = next(x for x in out if x["check_id"] == "isa_tags")
    assert h["estado"] == "ok" and h["estado_previo"] == "fallo" and h["nota_vlm"]  # cambió + marcado
    assert h["fuente"] == "reglas"                                    # sigue siendo "dura"
    assert agregar_revision(out)["verdicto"] in ("aprobado", "aprobado_con_notas")  # veredicto recalculado


def test_verificar_reglas_vlm_idempotente(monkeypatch):
    # re-pedir parte del estado por-texto: no acumula ni pierde la marca del cambio.
    from ai_agents.revisor import verificar_reglas_vlm
    _mock_llm(monkeypatch, '{"reglas":[{"id":"isa_tags","veredicto":"ok","razon":"ok"}],"observaciones":[]}')
    cfg = {"normas": ["iram-instrumentacion"]}
    once = verificar_reglas_vlm({"contenido": "x", "imagenes": []}, cfg, [_regla_fallo()])
    twice = verificar_reglas_vlm({"contenido": "x", "imagenes": []}, cfg, once)
    tags = [x for x in twice if x["check_id"] == "isa_tags"]
    assert len(tags) == 1 and tags[0]["estado"] == "ok" and tags[0]["estado_previo"] == "fallo"
