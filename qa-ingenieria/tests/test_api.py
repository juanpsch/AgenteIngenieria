"""Helpers de la API (api.main): saneo de nombres, validación de upload, mapeo de respuesta."""
import io

import pytest
from fastapi import HTTPException

from api import main


class FakeUpload:
    def __init__(self, name, data):
        self.filename = name
        self.file = io.BytesIO(data)


def test_safe_name_anti_traversal():
    assert main._safe_name("../../etc/passwd") == "passwd"
    assert main._safe_name(r"..\..\win.ini") == "win.ini"
    assert main._safe_name(None) == "documento"


def test_leer_upload_ok():
    safe, data = main._leer_upload(FakeUpload("doc.PDF", b"%PDF-1.4"))
    assert safe == "doc.PDF" and data == b"%PDF-1.4"


def test_leer_upload_extension_no_soportada():
    with pytest.raises(HTTPException) as e:
        main._leer_upload(FakeUpload("malicioso.txt", b"hola"))
    assert e.value.status_code == 415


def test_leer_upload_vacio():
    with pytest.raises(HTTPException) as e:
        main._leer_upload(FakeUpload("doc.pdf", b""))
    assert e.value.status_code == 400


def test_leer_upload_demasiado_grande(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", 0.000001)  # ~1 byte
    with pytest.raises(HTTPException) as e:
        main._leer_upload(FakeUpload("doc.pdf", b"0123456789"))
    assert e.value.status_code == 413


def test_map_validacion():
    st = {
        "thread_id": "t1", "status": "EN_REVISION", "tipo_objetivo": "esquematico",
        "score": 88.0, "no_concluyente": False, "score_veredicto": "revision_manual",
        "cajetin_bbox": {"x": 0, "y": 0.5, "w": 1, "h": 0.5}, "resumen": "ok",
        "checks": [{"dimension": "identidad", "label": "L"}],
        "documentos": [{"imagenes": ["data:image/png;base64,AAA"], "titulo": "d.pdf"}],
        "documentos_panel": [{"titulo": "d.pdf"}],
    }
    r = main._map_validacion(st)
    assert r["veredicto"] == "valido"          # EN_REVISION -> valido
    assert r["score"] == 88.0 and r["no_concluyente"] is False
    assert r["imagen"] == "data:image/png;base64,AAA"
    assert r["documento_panel"]["titulo"] == "d.pdf"
    assert r["cajetin_bbox"]["h"] == 0.5
    assert "maturity" in r


def test_map_validacion_sin_imagen_ni_panel():
    r = main._map_validacion({"status": "NO_ADMISIBLE", "documentos": []})
    assert r["veredicto"] == "invalido" and r["imagen"] is None and r["documento_panel"] is None
