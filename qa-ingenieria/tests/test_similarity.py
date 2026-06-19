"""Núcleo numérico del score (ai_agents.similarity) — sin modelo CLIP."""
import pytest

from ai_agents import similarity as S


def test_cos():
    assert S._cos([1, 0], [1, 0]) == pytest.approx(1.0)
    assert S._cos([1, 0], [0, 1]) == pytest.approx(0.0)
    assert S._cos([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert S._cos([0, 0], [1, 0]) == 0.0  # vector nulo -> 0, no NaN


def test_topk_mean(monkeypatch):
    monkeypatch.setenv("SIM_TOPK", "3")
    assert S._topk_mean([[1, 0]], [[1, 0], [0, 1]]) == pytest.approx(0.5)
    assert S._topk_mean([], [[1, 0]]) is None
    assert S._topk_mean([[1, 0]], []) is None


def test_score_grupos_identico_es_100(monkeypatch):
    monkeypatch.setenv("SIM_TOPK", "3")
    cand = {"paginas": [[1, 0]], "cajetin": [[1, 0]]}
    refs = [{"paginas": [[1, 0]], "cajetin": [[1, 0]]}]
    assert S.score_grupos(cand, refs) == pytest.approx(100.0)


def test_score_grupos_pondera_cajetin(monkeypatch):
    monkeypatch.setenv("SIM_TOPK", "3")
    monkeypatch.setenv("SIM_WEIGHT_CAJETIN", "0.7")
    monkeypatch.setenv("SIM_WEIGHT_PAGINA", "0.3")
    # cajetín idéntico (sim=1), página ortogonal (sim=0) -> 0.7*1 + 0.3*0 = 70
    cand = {"paginas": [[1, 0]], "cajetin": [[1, 0]]}
    refs = [{"paginas": [[0, 1]], "cajetin": [[1, 0]]}]
    assert S.score_grupos(cand, refs) == pytest.approx(70.0)


def test_score_grupos_fallback_a_pagina_si_no_hay_cajetin(monkeypatch):
    monkeypatch.setenv("SIM_TOPK", "3")
    cand = {"paginas": [[1, 0]], "cajetin": []}
    refs = [{"paginas": [[1, 0]], "cajetin": [[1, 0]]}]
    assert S.score_grupos(cand, refs) == pytest.approx(100.0)  # usa solo página


def test_score_grupos_sin_datos_es_none():
    assert S.score_grupos({"paginas": [], "cajetin": []}, []) is None


def test_umbrales_calibrados_identicos(monkeypatch):
    monkeypatch.setenv("SIM_TOPK", "3")
    monkeypatch.setenv("SIM_WEIGHT_CAJETIN", "0.7")
    monkeypatch.setenv("SIM_WEIGHT_PAGINA", "0.3")
    grupos = [{"paginas": [[1, 0]], "cajetin": [[1, 0]]} for _ in range(3)]
    appr, rev = S.umbrales_calibrados(grupos)
    assert appr == pytest.approx(99.0) and rev == pytest.approx(96.0)


def test_umbrales_calibrados_pocas_refs_es_none():
    assert S.umbrales_calibrados([{"paginas": [[1, 0]]}, {"paginas": [[1, 0]]}]) is None


def test_pesos_normaliza(monkeypatch):
    monkeypatch.setenv("SIM_WEIGHT_CAJETIN", "3")
    monkeypatch.setenv("SIM_WEIGHT_PAGINA", "1")
    wc, wp = S._pesos()
    assert wc == pytest.approx(0.75) and wp == pytest.approx(0.25)
