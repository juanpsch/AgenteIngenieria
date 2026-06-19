"""Motor determinista extract-then-check (tools.reglas.chequear_campos)."""
from tools.reglas import chequear_campos, verificar_variante


def test_filename_match():
    r = [{"campo": "codigo", "tipo": "filename", "requerido": True}]
    assert chequear_campos({"codigo": "HD-CAREM25XT-1"}, "HD-CAREM25XT-1-r4.pdf", r)[0]["state"] == "pass"
    assert chequear_campos({"codigo": "OTRO-9"}, "HD-CAREM25XT-1-r4.pdf", r)[0]["state"] == "fail"
    # el match es por normalización (ignora guiones/espacios/caso)
    assert chequear_campos({"codigo": "hd carem25xt 1"}, "HD-CAREM25XT-1-r4.pdf", r)[0]["state"] == "pass"


def test_filename_check_es_identidad():
    r = [{"campo": "codigo", "tipo": "filename"}]
    assert chequear_campos({"codigo": "A1"}, "A1.pdf", r)[0]["dimension"] == "identidad"


def test_filename_tolerante_subconjunto_de_tokens():
    # el filename es una versión CORTA del código (le falta un segmento) -> debe coincidir
    r = [{"campo": "codigo", "tipo": "filename"}]
    assert chequear_campos({"codigo": "HD-CAREM25XT-2-B1900-r4"}, "HD-CAREM25XT-2-r4.pdf", r)[0]["state"] == "pass"
    # documentos claramente distintos -> no coincide
    assert chequear_campos({"codigo": "OTRO-DOC-99"}, "HD-CAREM25XT-2-r4.pdf", r)[0]["state"] == "fail"


def test_filename_con_patron_extrae_clave():
    # el patrón extrae la clave comparable de ambos lados (ignora sufijos variables)
    r = [{"campo": "codigo", "tipo": "filename", "patron": r"HD-CAREM25XT-\d+"}]
    res = chequear_campos({"codigo": "HD-CAREM25XT-2-B1900-r4"}, "HD-CAREM25XT-2-r9.pdf", r)
    assert res[0]["state"] == "pass"  # ambos extraen «HD-CAREM25XT-2»


def test_regex():
    r = [{"campo": "rev", "patron": r"^r\d+$"}]
    assert chequear_campos({"rev": "r4"}, "x.pdf", r)[0]["state"] == "pass"
    assert chequear_campos({"rev": "rev-cuatro"}, "x.pdf", r)[0]["state"] == "fail"


def test_regex_invalido_es_warn():
    r = [{"campo": "x", "patron": "([", "requerido": True}]
    assert chequear_campos({"x": "v"}, "f.pdf", r)[0]["state"] == "warn"


def test_presencia():
    r = [{"campo": "firma", "tipo": "presencia", "requerido": True}]
    assert chequear_campos({"firma": "Juan"}, "x.pdf", r)[0]["state"] == "pass"
    assert chequear_campos({}, "x.pdf", r)[0]["state"] == "fail"


def test_no_requerido_es_warn_no_fail():
    r = [{"campo": "opt", "patron": "X", "requerido": False}]
    assert chequear_campos({"opt": "Y"}, "x.pdf", r)[0]["state"] == "warn"


def test_valor_faltante_requerido_falla():
    r = [{"campo": "c", "patron": "X", "requerido": True}]
    assert chequear_campos({}, "x.pdf", r)[0]["state"] == "fail"


def test_check_lleva_metadata_de_regla():
    c = chequear_campos({"codigo": "X9"}, "f.pdf", [{"campo": "codigo", "patron": "ECA-[0-9]+"}])[0]
    assert c["campo"] == "codigo" and c["patron"] == "ECA-[0-9]+" and c["valor"] == "X9" and c["state"] == "fail"


def test_verificar_variante():
    # cubre todos los 'deben' y ninguno de 'no_deben' -> ok
    v = verificar_variante(r"ECA-BRD-\d+(/\d+)?", ["ECA-BRD-22", "ECA-BRD-0022/2016"], ["OTRO-1"])
    assert v["ok"] is True and v["cubre"] == 2 and v["matchea_negativos"] == 0
    # matchea un negativo -> no ok
    v2 = verificar_variante(r"\w+-\d+", ["A-1"], ["B-2"])
    assert v2["ok"] is False and v2["matchea_negativos"] == 1
    # regex inválida -> error
    assert verificar_variante("([", ["A"], [])["error"] is True
