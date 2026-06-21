"""Facetas (Fase 1): el resolvedor une reglas de varios ejes, con override e id de origen."""
from tools import facetas, normas


def test_cadena_y_bundle():
    assert facetas.cadena("tipo", "pid") == ["diagrama", "pid"]   # ancestro primero
    assert "iram-instrumentacion" in (facetas.bundle("tipo", "pid").get("normas") or [])


def test_resolver_une_ejes():
    # P&ID de Camuzzi = tipo:pid (iram-instrumentacion) ∪ organizacion:camuzzi (camuzzi)
    rev = {"facetas": {"tipo": "pid", "organizacion": "camuzzi"}}
    ids = {r.get("norma_id") for r in normas.resolver_requisitos(rev)}
    assert ids == {"iram-instrumentacion", "camuzzi"}


def test_cada_regla_lleva_origen():
    res = normas.resolver_requisitos({"facetas": {"tipo": "pid", "organizacion": "camuzzi"}})
    assert res and all(r.get("origen") for r in res)            # explicabilidad: de qué faceta vino


def test_excluir_saca_regla_de_faceta():
    rev = {"facetas": {"tipo": "pid"}, "excluir": ["iram-instrumentacion:isa_tags_instrumento"]}
    ids = {r["id"] for r in normas.resolver_requisitos(rev)}
    assert "isa_tags_instrumento" not in ids


def test_familia_plana_legacy_sigue_andando():
    # sin facetas, con revision.normas directo (como antes)
    ids = {r.get("norma_id") for r in normas.resolver_requisitos({"normas": ["aea-90364"]})}
    assert "aea-90364" in ids


def test_template_pisa_a_faceta():
    # una regla inline del template (lo más específico) gana sobre la misma id traída por una faceta
    rev = {"facetas": {"tipo": "pid"},
           "reglas": [{"id": "isa_tags_instrumento", "tipo": "presencia", "patron": "x"}]}
    res = [r for r in normas.resolver_requisitos(rev) if r["id"] == "isa_tags_instrumento"]
    assert len(res) == 1 and res[0]["tipo"] == "presencia" and res[0]["origen"] == "template"
