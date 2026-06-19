"""OCR opcional (tools.ocr) — degradación con gracia (no debe romper si tesseract no está)."""
from tools import ocr


def test_disponible_es_bool():
    assert isinstance(ocr.disponible(), bool)


def test_ocr_no_lanza_con_entrada_invalida():
    # con o sin binario instalado, nunca debe lanzar; degrada a ""/[]
    assert ocr.ocr_texto(b"esto-no-es-una-imagen") == ""
    assert ocr.ocr_lineas(b"esto-no-es-una-imagen") == []


def test_provider_none_desactiva(monkeypatch):
    monkeypatch.setenv("OCR_PROVIDER", "none")
    ocr._engine.cache_clear()
    assert ocr.disponible() is False
    ocr._engine.cache_clear()  # no contaminar otros tests
