"""Cobertura determinista de reglas en la captura multi-doc (ai_agents.tipo_extractor)."""
from ai_agents.tipo_extractor import cobertura_reglas


def test_cobertura_cuenta_matches_por_doc():
    tpl = {"cajetin": {"reglas": [{"campo": "codigo", "patron": "ECA-BRD-[0-9]+"},
                                   {"campo": "rev", "patron": "R[0-9]+"}]}, "zonas": []}
    textos = ["doc ECA-BRD-22 R3", "ECA-BRD-99 sin revision", "nada relevante"]
    cob = {c["campo"]: (c["n"], c["total"]) for c in cobertura_reglas(tpl, textos)}
    assert cob["codigo"] == (2, 3)
    assert cob["rev"] == (1, 3)


def test_cobertura_incluye_reglas_de_zonas():
    tpl = {"zonas": [{"campo": "serie", "patron": "S-[0-9]+"}], "cajetin": {}}
    cob = cobertura_reglas(tpl, ["S-1", "S-2", "otro"])
    assert cob[0]["campo"] == "serie" and cob[0]["n"] == 2 and cob[0]["total"] == 3


def test_cobertura_patron_invalido_marca_error():
    tpl = {"cajetin": {"reglas": [{"campo": "x", "patron": "([" }]}}
    c = cobertura_reglas(tpl, ["a", "b"])[0]
    assert c.get("error") is True and c["n"] == 0


def test_cobertura_ignora_reglas_sin_patron():
    tpl = {"cajetin": {"reglas": [{"campo": "codigo", "tipo": "filename"}]}}  # sin patrón
    assert cobertura_reglas(tpl, ["x"]) == []
