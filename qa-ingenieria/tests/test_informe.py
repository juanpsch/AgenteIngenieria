"""Informe de revisión en PDF — genera bytes válidos y sanitiza glifos fuera de Latin-1."""
from tools.informe import generar_informe


def test_informe_pdf_valido():
    datos = {
        "fecha": "2026-06-20", "filename": "plano.pdf", "tipo": "pid_instrumentacion",
        "admision": "valido", "score": 88.7,
        "revision": {"verdicto": "observado", "severidad_max": "mayor", "confiabilidad": "parcial", "resuelta": False},
        "hallazgos": [
            {"check_id": "isa_tags", "dimension": "norma", "severidad": "mayor", "estado": "ok", "fuente": "reglas",
             "razonamiento": "tags ISA presentes", "evidencia": "51 coincidencias",
             "estado_previo": "fallo", "nota_vlm": "verificado por visión → ok"},
            {"check_id": "vlm:1", "dimension": "norma", "severidad": "observacion", "estado": "advertencia",
             "fuente": "vlm", "evidencia": "símbolos coherentes con la norma ✓"},
        ],
        "decision": "rejected", "notas": "página de libro — sección 2,5 mm²",
    }
    pdf = generar_informe(datos)
    assert pdf[:5] == b"%PDF-" and len(pdf) > 800   # PDF real con contenido


def test_informe_minimo_no_rompe():
    assert generar_informe({})[:5] == b"%PDF-"     # sin data igual genera un PDF
