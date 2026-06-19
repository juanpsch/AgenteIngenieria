"""Revisión de contenido (Fase 1) — agregación, router de entrada, Tier 1 y nodos."""
from ai_agents.revisor import revisar
from graph.edges import route_post_admision
from graph.nodes import extractor_node, revisor_node
from graph.revision import agregar_revision, mk
from tools import legibilidad


# --- Agregación de severidad -> veredicto (§5.3) ---
def test_agregar_bloqueante_rechaza():
    h = [mk("x", "contenido", "bloqueante", "fallo", razonamiento="r", fuente="deterministico")]
    assert agregar_revision(h)["verdicto"] == "rechazado"


def test_agregar_mayor_observa():
    h = [mk("x", "norma", "mayor", "fallo", razonamiento="r", fuente="reglas")]
    out = agregar_revision(h)
    assert out["verdicto"] == "observado" and out["severidad_max"] == "mayor"


def test_agregar_solo_menor_aprueba_con_notas():
    h = [mk("x", "contenido", "menor", "fallo", razonamiento="r", fuente="deterministico")]
    assert agregar_revision(h)["verdicto"] == "aprobado_con_notas"


def test_agregar_limpio_aprueba():
    h = [mk("x", "legibilidad", "mayor", "ok", razonamiento="r", fuente="deterministico")]
    assert agregar_revision(h)["verdicto"] == "aprobado"


def test_no_verificable_no_es_fallo_pero_baja_confianza():
    h = [mk("x", "legibilidad", "mayor", "no_verificable", razonamiento="r", fuente="deterministico")]
    out = agregar_revision(h)
    assert out["verdicto"] == "aprobado" and out["confiabilidad"] == "parcial"


def test_advertencia_dura_mayor_escala_a_observado():
    # una advertencia mayor de fuente determinística/reglas igual escala (no solo los 'fallo')
    h = [mk("x", "consistencia", "mayor", "advertencia", razonamiento="r", fuente="reglas")]
    assert agregar_revision(h)["verdicto"] == "observado"


def test_vlm_nunca_bloquea_solo():
    # el VLM emite observaciones; aunque sugiera severidad alta, no escala más allá de con-notas (§2.2)
    h = [mk("x", "contenido", "mayor", "advertencia", razonamiento="r", fuente="vlm")]
    assert agregar_revision(h)["verdicto"] == "aprobado_con_notas"


# --- Tier 1 determinístico ---
def test_contiene_seccion_por_tokens():
    txt = "...\nCuadro de Cargas del tablero\n..."
    assert legibilidad.contiene_seccion(txt, "cuadro de cargas") is True
    assert legibilidad.contiene_seccion(txt, "diagrama unifilar") is False


def test_varianza_laplaciano_degrada_con_basura():
    assert legibilidad.varianza_laplaciano(b"no-es-imagen") is None


def test_revisar_sin_cfg_no_halla_nada():
    assert revisar({"contenido": "x"}, {}) == []


def test_revisar_presencia_detecta_faltante():
    cfg = {"contenido_requerido": [{"id": "unifilar", "detectar": "diagrama unifilar", "severidad_si_falta": "mayor"}]}
    doc = {"contenido": "documento sin esa seccion", "imagenes": [], "path": None}
    hall = revisar(doc, cfg)
    uni = [h for h in hall if h["check_id"] == "unifilar"][0]
    assert uni["estado"] == "fallo" and uni["severidad"] == "mayor"


# --- Router de entrada a revisión (toggle de interrupt) ---
def test_route_post_admision_toggle_off():
    assert route_post_admision({"status": "EN_REVISION", "tipo_objetivo": "esquematico_electronico",
                                "revisar_auto": False}) == "fin"


def test_route_post_admision_sin_tipo():
    assert route_post_admision({"revisar_auto": True}) == "fin"


def test_route_post_admision_tipo_con_revision():
    # esquematico_electronico declara bloque `revision:` -> entra
    assert route_post_admision({"tipo_objetivo": "esquematico_electronico", "revisar_auto": True}) == "revisar"


def test_route_post_admision_tipo_sin_revision():
    # hd_2 no declara revisión -> no entra
    assert route_post_admision({"tipo_objetivo": "hd_2", "revisar_auto": True}) == "fin"


# --- Nodos ---
def test_extractor_node_da_extracto():
    out = extractor_node({"documentos": [{"contenido": "abc", "imagenes": ["x"], "path": None}]})
    assert out["revision_extracto"]["texto_chars"] == 3
    assert "tablas" in out["revision_extracto"]   # Tier 2 las usa


def test_indices_muestra_robusto():
    # k=1 no debe romper (división por cero) y cubre casos chicos/grandes
    from ai_agents.revisor import _indices_muestra
    assert _indices_muestra(10, 1) == [0]          # antes: ZeroDivisionError
    assert _indices_muestra(0, 6) == []
    assert _indices_muestra(4, 6) == [0, 1, 2, 3]   # n <= k -> todas
    idx = _indices_muestra(100, 6)
    assert idx[0] == 0 and idx[-1] == 99 and len(idx) == len(set(idx))  # incluye portada y última, sin duplicados


def test_revision_max_pages_env(monkeypatch):
    from graph.nodes import _revision_max_pages
    monkeypatch.setenv("REVISION_MAX_PAGES", "12")
    assert _revision_max_pages() == 12
    monkeypatch.setenv("REVISION_MAX_PAGES", "no-num")
    assert _revision_max_pages() == 0   # degrada a "todas"


def test_revisor_node_sin_revision_en_template():
    out = revisor_node({"tipo_objetivo": "hd_2", "documentos": [{"contenido": "x"}]})
    assert out["verdicto_revision"] is None and out["hallazgos"] == []
