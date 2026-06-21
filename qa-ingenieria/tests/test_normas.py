"""Catálogo de normas: carga, detección del vínculo, merge, e integración VÁLIDO vs INVÁLIDO."""
from ai_agents.revisor import revisar
from graph.revision import agregar_revision
from tools import normas

# Texto de memoria eléctrica que CUMPLE (declara AEA + valores en límite)
MEMORIA_OK = (
    "2. NORMAS Y REGLAMENTOS. Para este cálculo se han seguido los lineamientos del reglamento "
    "AEA 90364, parte 7: 771, y de las normas IRAM e IEC que de él se derivan. "
    "Circuito IUG: sección 1,5 mm2, caída de tensión 2,1 %. "
    "Circuito TUG: sección 2,5 mm2, protección diferencial 4 x 25 A, 30 mA. "
    "Puesta a tierra mediante jabalina. Caída de tensión total 4,2 %."
)
# Texto que NO cumple (no declara la norma + caída 7,5% + sección 0,75 + sin 30 mA ni PAT)
MEMORIA_MAL = (
    "Memoria de cálculo eléctrico. Circuito A: sección 0,75 mm2, caída de tensión 7,5 %. "
    "Sin más datos."
)


def test_cargar_y_detectar():
    cat = normas.cargar_normas()
    assert "aea-90364" in cat
    det = {d["id"]: d for d in normas.detectar_normas(MEMORIA_OK, ["aea-90364"])}
    assert det["aea-90364"]["declarada"] is True
    det2 = {d["id"]: d for d in normas.detectar_normas(MEMORIA_MAL, ["aea-90364"])}
    assert det2["aea-90364"]["declarada"] is False


def test_auto_detectar_barre_catalogo():
    assert "aea-90364" in normas.auto_detectar(MEMORIA_OK)


def test_reglas_de_normas_llevan_norma_ref():
    rs = normas.reglas_de_normas(["aea-90364"])
    assert rs and all(r.get("norma_ref") for r in rs)
    assert any(r["tipo"] == "norma_lookup" for r in rs)


def test_catalogo_y_requisito_por_id():
    cat = normas.catalogo_requisitos()
    assert cat and all(q.get("req_id") and ":" in q["req_id"] for q in cat)
    q = normas.requisito_por_id("aea-90364:aea_caida_tension")
    assert q and q["tipo"] == "norma_lookup" and q["norma_ref"] == "AEA 90364"
    assert normas.requisito_por_id("inexistente:x") is None


def test_resolver_norma_entera():
    reglas = normas.resolver_requisitos({"normas": ["aea-90364"]})
    ids = {r["id"] for r in reglas}
    assert "aea_caida_tension" in ids and "aea_seccion_minima" in ids


def test_resolver_granular_mezcla_normas():
    reglas = normas.resolver_requisitos({"requisitos": ["aea-90364:aea_diferencial_30ma",
                                                        "cirsoc-201:cirsoc_resistencia_hormigon"]})
    ids = {r["id"] for r in reglas}
    assert ids == {"aea_diferencial_30ma", "cirsoc_resistencia_hormigon"}  # un doc, dos normas


def test_resolver_excluir_por_id_local_o_global():
    base = normas.resolver_requisitos({"normas": ["aea-90364"]})
    assert any(r["id"] == "aea_cuadro_cargas" for r in base)
    sin1 = normas.resolver_requisitos({"normas": ["aea-90364"], "excluir": ["aea_cuadro_cargas"]})
    sin2 = normas.resolver_requisitos({"normas": ["aea-90364"], "excluir": ["aea-90364:aea_cuadro_cargas"]})
    assert not any(r["id"] == "aea_cuadro_cargas" for r in sin1)
    assert not any(r["id"] == "aea_cuadro_cargas" for r in sin2)


def test_resolver_template_inline_pisa_a_norma():
    reglas = normas.resolver_requisitos({"normas": ["aea-90364"],
                                         "reglas": [{"id": "aea_caida_tension", "tipo": "presencia", "patron": "x"}]})
    caida = [r for r in reglas if r["id"] == "aea_caida_tension"]
    assert len(caida) == 1 and caida[0]["tipo"] == "presencia"  # el template gana


def test_deteccion_severidad_configurable():
    # 'declarar la norma' es MENOR en dibujo (los planos no la citan) y MAYOR por defecto (memorias)
    det = {d["id"]: d for d in normas.detectar_normas("texto", ["iram-dibujo", "iram-instrumentacion", "aea-90364"])}
    assert det["iram-dibujo"]["severidad"] == "menor"           # los planos no citan IRAM
    assert det["iram-instrumentacion"]["severidad"] == "menor"  # los P&ID no citan ISA/IRAM
    assert det["aea-90364"]["severidad"] == "mayor"             # las memorias sí deben citar AEA


def test_iram_catalogos_deteccion_y_reglas():
    from tools import reglas_revision as rr
    cat = normas.cargar_normas()
    assert {"iram-dibujo", "iram-instrumentacion"} <= set(cat)
    # transversal: dibujo aplica a todas las disciplinas
    assert (cat["iram-dibujo"].get("aplica_a") or {}).get("disciplinas") == ["*"]
    # detección por anclas
    t = "Plano según IRAM 4504. Escala 1:50. Simbología ISA-5.1. TIC-101 FT-203 LIC-205."
    det = {d["id"]: d["declarada"] for d in normas.detectar_normas(t, ["iram-dibujo", "iram-instrumentacion"])}
    assert det["iram-dibujo"] and det["iram-instrumentacion"]
    # todas las reglas IRAM compilan y evalúan sin romper
    for r in normas.reglas_de_normas(["iram-dibujo", "iram-instrumentacion"]):
        assert rr.evaluar_regla(r, t, [])["estado"] in ("ok", "fallo", "no_verificable")


def test_camuzzi_norma_rotulo_determinista_y_simbolos_vlm():
    cat = normas.cargar_normas()
    assert "camuzzi" in cat
    reglas = {r["id"]: r for r in normas.reglas_de_normas(["camuzzi"])}
    assert reglas["camuzzi_rotulo"]["tipo"] == "presencia"          # lo de texto, determinista
    assert reglas["camuzzi_simbolos_estandar"]["tipo"] == "vlm"     # lo gráfico, lo juzga el VLM


def test_vlm_de_normas_expone_referencia_imagen():
    # la norma camuzzi declara su leyenda como referencia visual del VLM (ground-truth gráfico)
    v = normas.vlm_de_normas(["camuzzi"])
    assert v and v[0].get("referencia_imagen")


def test_familia_epa_wwtp_desde_un_juego():
    # un juego de planos completo da norma (leyendas) + familia (P&IDs). La norma trae varias referencias.
    from tools.tipos import cargar_tipos
    assert "epa-wwtp" in normas.cargar_normas()
    assert "pid_efluentes" in cargar_tipos()
    ri = normas.vlm_de_normas(["epa-wwtp"])[0]["referencia_imagen"]
    assert isinstance(ri, list) and len(ri) == 3   # 3 hojas de leyenda como ground-truth


def test_cargar_referencia_degrada_si_falta(monkeypatch):
    from ai_agents.revisor import _cargar_referencia
    assert _cargar_referencia(None) is None
    assert _cargar_referencia("knowledge/normas/refs/no_existe_xyz.png") is None


def test_ancla_con_regex_invalido_no_rompe():
    # un ancla mal escrita (paréntesis sin cerrar) no debe crashear la detección
    assert normas._ancla_match("(AEA sin cerrar", "texto (AEA sin cerrar aquí") is True
    assert normas._ancla_match("[malformada", "otra cosa") is False


def test_seccion_minima_capta_mm2_y_simbolo_no_cotas():
    from tools.reglas_revision import evaluar_regla
    r = next(x for x in normas.reglas_de_normas(["aea-90364"]) if x["id"] == "aea_seccion_minima")
    assert evaluar_regla(r, "conductor de 2,5 mm²", [])["estado"] == "ok"      # acepta mm² (símbolo)
    assert evaluar_regla(r, "conductor de 0,75 mm2", [])["estado"] == "fallo"  # < 1,5
    assert evaluar_regla(r, "una cota de 10 mm de largo", [])["estado"] == "no_verificable"  # no es sección


def test_merge_template_pisa_a_norma():
    # una regla del template con el mismo id que una de la norma debe ganar (no duplicar)
    cfg = {"normas": ["aea-90364"], "reglas": [{"id": "aea_caida_tension", "tipo": "presencia", "patron": "x"}]}
    hall = revisar({"contenido": MEMORIA_OK, "imagenes": []}, cfg)
    ids = [h["check_id"] for h in hall]
    assert ids.count("aea_caida_tension") == 1


def test_integracion_valido():
    cfg = {"normas": ["aea-90364"]}
    hall = revisar({"contenido": MEMORIA_OK, "imagenes": [], "path": None}, cfg)
    agg = agregar_revision(hall)
    # cumple todo lo determinista (Tier 1 sin imagen => no_verificable, no bloquea)
    assert agg["verdicto"] in ("aprobado", "aprobado_con_notas")
    assert not [h for h in hall if h["estado"] == "fallo"]


def test_integracion_invalido_dice_donde_falla():
    cfg = {"normas": ["aea-90364"]}
    hall = revisar({"contenido": MEMORIA_MAL, "imagenes": [], "path": None}, cfg)
    agg = agregar_revision(hall)
    assert agg["verdicto"] == "observado"            # hay fallos mayores
    porid = {h["check_id"]: h for h in hall}
    assert porid["norma_declarada:aea-90364"]["estado"] == "fallo"   # no declara la norma
    assert porid["aea_caida_tension"]["estado"] == "fallo" and "7.5" in porid["aea_caida_tension"]["evidencia"]
    assert porid["aea_seccion_minima"]["estado"] == "fallo"          # 0,75 < 1,5
    assert porid["aea_caida_tension"]["norma_ref"] == "AEA 90364"    # trazabilidad
