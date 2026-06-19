"""Motor de reglas Tier 2 — casos VÁLIDO e INVÁLIDO (y que el hallazgo diga DÓNDE falla)."""
from tools.reglas_revision import evaluar_regla


def test_presencia_ok_y_fallo():
    r = {"id": "pat", "tipo": "presencia", "patron": "puesta a tierra", "severidad": "mayor"}
    assert evaluar_regla(r, "...con puesta a tierra por jabalina...", [])["estado"] == "ok"
    assert evaluar_regla(r, "memoria sin esa cláusula", [])["estado"] == "fallo"


def test_presencia_unidad_tolera_simbolo():
    r = {"id": "sec", "tipo": "presencia_unidad", "unidad": "mm2"}
    assert evaluar_regla(r, "sección 2,5 mm²", [])["estado"] == "ok"   # acepta mm²
    assert evaluar_regla(r, "sección 2.5 mm2", [])["estado"] == "ok"   # y mm2
    assert evaluar_regla(r, "no hay secciones", [])["estado"] == "fallo"


def test_patron_min_ocurrencias():
    r = {"id": "refs", "tipo": "patron", "patron": r"\b[RCU]\d{1,3}\b", "min": 3}
    assert evaluar_regla(r, "R1 C2 U3 R4", [])["estado"] == "ok"
    assert evaluar_regla(r, "solo R1", [])["estado"] == "fallo"


def test_norma_lookup_max_detecta_el_valor_que_falla():
    r = {"id": "caida", "tipo": "norma_lookup", "captura": r"ca[ií]da[^%\n]{0,40}?(\d+[.,]?\d*)\s*%",
         "max": 5, "severidad": "mayor"}
    ok = evaluar_regla(r, "caída de tensión 2,1 % en la línea", [])
    assert ok["estado"] == "ok"
    mal = evaluar_regla(r, "caída de tensión 7,5 % en el circuito", [])
    assert mal["estado"] == "fallo" and "7.5" in mal["evidencia"]   # dice DÓNDE falla


def test_norma_lookup_min_seccion():
    r = {"id": "sec", "tipo": "norma_lookup", "captura": r"(\d+[.,]?\d*)\s*mm2?\b", "min": 1.5}
    assert evaluar_regla(r, "conductor de 2,5 mm2", [])["estado"] == "ok"
    assert evaluar_regla(r, "conductor de 0,75 mm2", [])["estado"] == "fallo"


def test_norma_lookup_sin_valores_es_no_verificable():
    r = {"id": "caida", "tipo": "norma_lookup", "captura": r"caída.*?(\d+)\s*%", "max": 5}
    assert evaluar_regla(r, "documento sin datos de caída", [])["estado"] == "no_verificable"


def test_tabla_no_extraida_es_no_verificable():
    r = {"id": "cc", "tipo": "tabla", "columnas": ["circuito", "secci"]}
    assert evaluar_regla(r, "texto", [])["estado"] == "no_verificable"   # no inventa ok/fallo


def test_tabla_columnas_presentes_y_faltantes():
    r = {"id": "cc", "tipo": "tabla", "columnas": ["circuito", "secci"]}
    tablas_ok = [{"pagina": 1, "filas": [["Circuito", "Sección", "Protección"], ["C1", "2.5", "ITM"]]}]
    assert evaluar_regla(r, "", tablas_ok)["estado"] == "ok"
    tablas_mal = [{"pagina": 1, "filas": [["Item", "Cantidad"], ["x", "1"]]}]
    assert evaluar_regla(r, "", tablas_mal)["estado"] == "fallo"


def test_presencia_unidad_sin_unidad_es_no_verificable():
    # config inválida del template (sin 'unidad') no debe ensuciar el veredicto con un fallo
    assert evaluar_regla({"id": "u", "tipo": "presencia_unidad"}, "2,5 mm2", [])["estado"] == "no_verificable"


def test_tipo_desconocido_no_rompe():
    assert evaluar_regla({"id": "x", "tipo": "inexistente"}, "t", [])["estado"] == "no_verificable"


def test_hallazgo_lleva_norma_ref():
    r = {"id": "caida", "tipo": "norma_lookup", "captura": r"(\d+)\s*%", "max": 5, "norma_ref": "AEA 90364"}
    assert evaluar_regla(r, "caída 2 %", [])["norma_ref"] == "AEA 90364"
