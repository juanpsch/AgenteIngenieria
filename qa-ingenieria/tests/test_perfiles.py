"""Perfiles de cumplimiento (tools.perfiles) — bundle de normas/requisitos + expansión en el resolvedor."""
from tools import normas, perfiles


def test_cargar_perfiles():
    p = perfiles.cargar_perfiles()
    assert "edificio-ar" in p
    assert p["edificio-ar"]["jurisdiccion"] == "AR"


def test_requisitos_de_perfil_expande_normas():
    reqs = perfiles.requisitos_de_perfil(perfiles.cargar_perfiles()["edificio-ar"])
    # edificio-ar bundlea AEA + CIRSOC -> requisitos de ambas
    assert any(r.startswith("aea-90364:") for r in reqs)
    assert any(r.startswith("cirsoc-201:") for r in reqs)


def test_expandir_revision_merge():
    rev = perfiles.expandir_revision({"perfiles": ["edificio-ar"], "requisitos": ["x:y"]})
    assert "aea-90364" in rev["normas"] and "cirsoc-201" in rev["normas"]
    assert "x:y" in rev["requisitos"]


def test_expandir_sin_perfiles_es_noop():
    assert perfiles.expandir_revision({"normas": ["aea-90364"]}) == {"normas": ["aea-90364"]}


def test_resolver_expande_perfil():
    # un template que solo referencia un perfil resuelve los requisitos de las normas del perfil
    reglas = normas.resolver_requisitos({"perfiles": ["edificio-ar"]})
    nids = {r.get("norma_id") for r in reglas}
    assert "aea-90364" in nids and "cirsoc-201" in nids
