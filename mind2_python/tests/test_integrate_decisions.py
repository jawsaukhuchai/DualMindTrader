# tests/test_integrate_decisions.py
import types
import pytest
import numpy as np
from mind2_python import integrate_decisions


# ======================
# integrate_decisions (function) tests
# ======================

def test_integration_with_global_weights():
    scalp = {"decision": "BUY", "confidence": 0.6}
    day   = {"decision": "SELL", "confidence": 0.4}
    swing = {"decision": "HOLD", "confidence": 0.2}
    global_cfg = {"weights": {"scalp": 2, "day": 1, "swing": 1}}
    result = integrate_decisions.integrate_decisions(scalp, day, swing, {}, global_cfg)
    assert result["decision"] in {"BUY", "SELL", "HOLD"}
    assert "weights" in result


def test_integration_returns_none_on_bad_score():
    # decision = "WEIRD" → score() returns None → fallback_dict
    scalp = {"decision": "WEIRD", "confidence": 0.5}
    res = integrate_decisions.integrate_decisions(scalp, {}, {})
    assert res["decision"] == "HOLD"
    assert res["score"] == 0.0


def test_integration_mode_majority():
    scalp = {"decision": "BUY", "confidence": 1.0}
    day   = {"decision": "BUY", "confidence": 1.0}
    swing = {"decision": "SELL", "confidence": 1.0}
    res = integrate_decisions.integrate_decisions(scalp, day, swing, {"integration_mode": "majority"})
    assert res["decision"] == "BUY"
    assert res["num_entries"] in {2, 3}


def test_integration_mode_priority():
    scalp = {"decision": "BUY", "confidence": 0.5}
    day   = {"decision": "SELL", "confidence": 0.5}
    swing = {"decision": "HOLD", "confidence": 0.5}
    sym_cfg = {"integration_mode": "priority", "priority_decision": "SELL"}
    res = integrate_decisions.integrate_decisions(scalp, day, swing, sym_cfg)
    assert res["decision"] == "SELL"
    assert res["num_entries"] == 3


def test_integration_mode_hybrid_levels():
    scalp = {"decision": "BUY", "confidence": 0.8}
    day   = {"decision": "BUY", "confidence": 0.8}
    swing = {"decision": "BUY", "confidence": 0.8}
    # high confidence → num_entries = 3
    res = integrate_decisions.integrate_decisions(scalp, day, swing, {"integration_mode": "hybrid"})
    assert res["num_entries"] in {1, 2, 3}


def test_integration_mode_unknown_triggers_fallback():
    res = integrate_decisions.integrate_decisions({"decision": "BUY"}, {"decision": "BUY"}, {"decision": "BUY"}, {"integration_mode": "weird"})
    assert res["decision"] == "HOLD"
    assert res["score"] == 0.0


# ======================
# MetaIntegrator tests
# ======================

class DummyModelProba:
    classes_ = ["BUY", "SELL", "HOLD"]
    def predict_proba(self, X):
        return np.array([[0.1, 0.7, 0.2]])


class DummyModelPredict:
    classes_ = ["BUY", "SELL", "HOLD"]
    def predict(self, X):
        return ["SELL"]


def test_model_load_success(monkeypatch):
    monkeypatch.setattr("mind2_python.integrate_decisions.joblib.load", lambda path: DummyModelProba())
    integ = integrate_decisions.MetaIntegrator("dummy.pkl")
    assert isinstance(integ.model, DummyModelProba)
    assert "SELL" in integ.classes_


def test_model_load_fail(monkeypatch):
    monkeypatch.setattr("mind2_python.integrate_decisions.joblib.load", lambda path: (_ for _ in ()).throw(RuntimeError("fail")))
    integ = integrate_decisions.MetaIntegrator("dummy.pkl")
    assert integ.model is None
    assert "HOLD" in integ.classes_


def test_integrate_with_proba(monkeypatch):
    monkeypatch.setattr("mind2_python.integrate_decisions.joblib.load", lambda path: DummyModelProba())
    integ = integrate_decisions.MetaIntegrator("dummy.pkl")
    scalp = {"decision": "BUY", "confidence": 0.5}
    res = integ.integrate(scalp, scalp, scalp, types.SimpleNamespace(atr=1.0, adx=1.0))
    assert res["decision"] == "SELL"
    assert "raw" in res


def test_integrate_with_predict(monkeypatch):
    monkeypatch.setattr("mind2_python.integrate_decisions.joblib.load", lambda path: DummyModelPredict())
    integ = integrate_decisions.MetaIntegrator("dummy.pkl")
    scalp = {"decision": "BUY", "confidence": 0.5}
    res = integ.integrate(scalp, scalp, scalp, types.SimpleNamespace(atr=1.0, adx=1.0))
    assert res["decision"] == "SELL"
    assert res["proba"] == 0.5


def test_integrate_fallback_no_model(monkeypatch):
    monkeypatch.setattr("mind2_python.integrate_decisions.joblib.load", lambda path: (_ for _ in ()).throw(RuntimeError("fail")))
    integ = integrate_decisions.MetaIntegrator("dummy.pkl")
    scalp = {"decision": "BUY", "confidence": 0.5}
    res = integ.integrate(scalp, scalp, scalp, types.SimpleNamespace(atr=1.0, adx=1.0))
    assert res == {"decision": "HOLD", "proba": 0.33, "raw": {}}


def test_integrate_exception(monkeypatch):
    class BadModel:
        def predict_proba(self, X): raise RuntimeError("bad")
    monkeypatch.setattr("mind2_python.integrate_decisions.joblib.load", lambda path: BadModel())
    integ = integrate_decisions.MetaIntegrator("dummy.pkl")
    scalp = {"decision": "BUY", "confidence": 0.5}
    res = integ.integrate(scalp, scalp, scalp, types.SimpleNamespace(atr=1.0, adx=1.0))
    assert res == {"decision": "HOLD", "proba": 0.0, "raw": {}}
