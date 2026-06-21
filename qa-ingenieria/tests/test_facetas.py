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


def test_familia_generica_desde_faceta():
    assert facetas.familia_generica("pid") == "pid_instrumentacion"
    assert facetas.familia_generica("inexistente") is None


def test_referencias_heredadas_en_cold_start(monkeypatch):
    # familia con 0 ejemplos propios hereda los de su familia genérica; con muchos propios, NO
    from tools import refs
    monkeypatch.setattr(refs, "_familia_generica", lambda t: "padre" if t == "hijo" else None)
    padre_refs = [{"ref_id": "p1"}, {"ref_id": "p2"}]
    monkeypatch.setattr(refs, "vectores_por_referencia",
                        lambda t: [] if t == "hijo" else (padre_refs if t == "padre" else []))
    grupos, heredado = refs.referencias_resueltas("hijo")
    assert heredado == "padre" and len(grupos) == 2          # 0 propios -> hereda

    monkeypatch.setattr(refs, "vectores_por_referencia",
                        lambda t: [{"ref_id": f"h{i}"} for i in range(6)] if t == "hijo" else padre_refs)
    grupos2, heredado2 = refs.referencias_resueltas("hijo")
    assert heredado2 is None and len(grupos2) == 6          # >=5 propios -> NO hereda


def test_override_severidad_template():
    res = normas.resolver_requisitos({"facetas": {"tipo": "pid"}, "severidad": {"isa_tags_instrumento": "observacion"}})
    isa = next(r for r in res if r["id"] == "isa_tags_instrumento")
    assert isa["severidad"] == "observacion"          # el template baja la severidad de una regla de faceta


def test_severidad_norma_declarada_por_tipo():
    # "declarar la norma": mayor en memoria, menor en plano/pid (el ejemplo del usuario, vía faceta tipo)
    assert normas.severidad_overrides({"facetas": {"tipo": "memoria"}}).get("norma_declarada") == "mayor"
    assert normas.severidad_overrides({"facetas": {"tipo": "plano"}}).get("norma_declarada") == "menor"
    # y la familia puntual puede overridear a la faceta
    ov = normas.severidad_overrides({"facetas": {"tipo": "memoria"}, "severidad": {"norma_declarada": "observacion"}})
    assert ov.get("norma_declarada") == "observacion"


def test_template_pisa_a_faceta():
    # una regla inline del template (lo más específico) gana sobre la misma id traída por una faceta
    rev = {"facetas": {"tipo": "pid"},
           "reglas": [{"id": "isa_tags_instrumento", "tipo": "presencia", "patron": "x"}]}
    res = [r for r in normas.resolver_requisitos(rev) if r["id"] == "isa_tags_instrumento"]
    assert len(res) == 1 and res[0]["tipo"] == "presencia" and res[0]["origen"] == "template"
