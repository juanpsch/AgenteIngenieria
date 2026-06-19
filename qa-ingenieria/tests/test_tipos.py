"""Helpers de zonas y reglas derivadas (tools.tipos)."""
from tools.tipos import _norm_zona, reglas_de, zona_identidad_de


def test_norm_zona_acepta_bbox_anidado_o_plano():
    z = _norm_zona({"nombre": "Enc", "bbox": {"x": 0, "y": 0, "w": 1, "h": 0.2}, "identidad": True})
    assert z["bbox"] == {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.2} and z["identidad"] is True
    z2 = _norm_zona({"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.5})
    assert z2["bbox"]["w"] == 0.5 and z2["nombre"] == "Zona"


def test_norm_zona_campo_setea_requerido():
    z = _norm_zona({"nombre": "C", "bbox": {"x": 0, "y": 0, "w": 1, "h": 1}, "campo": "codigo", "tipo": "filename"})
    assert z["campo"] == "codigo" and z["tipo"] == "filename" and z["requerido"] is True


def test_zona_identidad_de_prefiere_zona_marcada():
    tpl = {"zonas": [
        {"nombre": "A", "bbox": {"x": 0, "y": 0, "w": 1, "h": 0.1}},
        {"nombre": "B", "bbox": {"x": 0, "y": 0.9, "w": 1, "h": 0.1}, "identidad": True},
    ]}
    assert zona_identidad_de(tpl)["y"] == 0.9


def test_zona_identidad_de_fallback_legacy():
    assert zona_identidad_de({"zona_identidad": {"x": 0, "y": 0, "w": 1, "h": 1}})["w"] == 1
    assert zona_identidad_de({}) is None


def test_reglas_de_combina_zonas_y_cajetin():
    tpl = {
        "zonas": [{"nombre": "C", "bbox": {"x": 0, "y": 0, "w": 1, "h": 0.2}, "campo": "codigo", "tipo": "filename"}],
        "cajetin": {"reglas": [{"campo": "rev", "patron": r"r\d+"}]},
    }
    reglas = reglas_de(tpl)
    campos = {r["campo"] for r in reglas}
    assert campos == {"codigo", "rev"}
    codigo = next(r for r in reglas if r["campo"] == "codigo")
    assert codigo["tipo"] == "filename" and codigo["zona"] == "C"
