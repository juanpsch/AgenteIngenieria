"""Zonas ancladas a texto (tools.layout) — rutas sin depender de un PDF concreto."""
from tools.layout import _extraer_valor, _valor_tras_ancla, bbox_efectivo, localizar_bbox


def test_sin_anclas_es_none():
    assert localizar_bbox("x.pdf", 0, None, None) is None


def test_archivo_inexistente_es_none():
    assert localizar_bbox("no_existe_zzz.pdf", 0, "Código") is None


def test_bbox_efectivo_sin_anclas_usa_estatico():
    z = {"bbox": {"x": 0, "y": 0, "w": 1, "h": 0.2}}
    assert bbox_efectivo(z, "cualquier.pdf") == {"x": 0, "y": 0, "w": 1, "h": 0.2}


def test_bbox_efectivo_con_ancla_pero_sin_path_cae_a_estatico():
    z = {"bbox": {"x": 0, "y": 0, "w": 1, "h": 0.2}, "ancla_inicio": "Código"}
    assert bbox_efectivo(z, None) == {"x": 0, "y": 0, "w": 1, "h": 0.2}


def test_valor_tras_ancla_misma_linea():
    lineas = ["Proyecto: CAREM", "Código: ECA-BRD-0022/2016", "Rev.: B"]
    assert _valor_tras_ancla(lineas, "Código") == "ECA-BRD-0022/2016"
    assert _valor_tras_ancla(lineas, r"Rev\.?") == "B"


def test_valor_tras_ancla_linea_siguiente():
    lineas = ["CÓDIGO", "HD-CAREM25XT-2", "otra cosa"]
    assert _valor_tras_ancla(lineas, "CÓDIGO") == "HD-CAREM25XT-2"


def test_valor_tras_ancla_no_encontrado():
    assert _valor_tras_ancla(["nada", "que ver"], "Código") is None


def test_extraer_valor_entre_anclas():
    lineas = ["Proyecto: CAREM", "Código: ECA-BRD-0022 Rev.: B"]
    assert _extraer_valor(lineas, "Código:", "Rev", None) == "ECA-BRD-0022"


def test_extraer_valor_refina_con_patron():
    # el ancla ubica la línea; el patrón extrae el token preciso (ignora ruido)
    lineas = ["Código: ECA-BRD-0022 (provisorio)"]
    assert _extraer_valor(lineas, "Código", None, r"ECA-[A-Z]+-\d+") == "ECA-BRD-0022"


def test_extraer_valor_solo_inicio_sin_patron():
    assert _extraer_valor(["Rev.: B"], "Rev\\.?", None, None) == "B"
