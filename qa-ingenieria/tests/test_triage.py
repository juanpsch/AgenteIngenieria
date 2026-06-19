"""Normalización del bbox del cajetín (ai_agents.triage._norm_bbox)."""
from ai_agents.triage import _norm_bbox


def test_norm_bbox_ok_coacciona_strings():
    assert _norm_bbox({"x": "0.6", "y": 0.9, "w": 0.4, "h": 0.1}) == {"x": 0.6, "y": 0.9, "w": 0.4, "h": 0.1}


def test_norm_bbox_clamp_a_0_1():
    b = _norm_bbox({"x": -0.5, "y": 2.0, "w": 0.5, "h": 0.5})
    assert b["x"] == 0.0 and b["y"] == 1.0


def test_norm_bbox_invalidos():
    assert _norm_bbox(None) is None
    assert _norm_bbox({"x": 0.1}) is None             # faltan claves
    assert _norm_bbox({"x": 0, "y": 0, "w": 0, "h": 0}) is None  # área nula
    assert _norm_bbox({"x": "a", "y": "b", "w": "c", "h": "d"}) is None  # no numérico
