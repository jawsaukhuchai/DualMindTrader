import numpy as np
import types
import pytest

import mind2_python.regime_detector as rd


# -------------------------
# Fixtures
# -------------------------
@pytest.fixture
def sample_entry():
    return {
        "ema_slope": 0.1,
        "rsi": 55,
        "atr": 2.0,
        "atr_ma": 1.0,
        "adx": 30,
        "bb_width": 0.5,
        "volume_profile_imb": 0.1,
    }


# -------------------------
# Init & load model
# -------------------------
def test_init_no_model():
    det = rd.RegimeDetector()
    assert det.model is None
    assert det.classes_ == rd.REGIME_CLASSES


def test_init_load_fail(monkeypatch):
    monkeypatch.setattr(rd.joblib, "load", lambda path: (_ for _ in ()).throw(Exception("fail")))
    det = rd.RegimeDetector("fake_path")
    assert det.model is None
    assert det.classes_ == rd.REGIME_CLASSES


def test_init_load_success_with_proba(monkeypatch, sample_entry):
    class DummyModel:
        classes_ = ["trend", "range", "high_vol", "low_vol"]

        def predict_proba(self, X):
            return np.array([[0.1, 0.2, 0.6, 0.1]])

    monkeypatch.setattr(rd.joblib, "load", lambda path: DummyModel())
    det = rd.RegimeDetector("fake_model")
    out = det.predict(sample_entry)
    assert out["regime"] == "high_vol"
    assert out["proba"] == pytest.approx(0.6)


def test_init_load_success_without_proba(monkeypatch, sample_entry):
    class DummyModel:
        def predict(self, X):
            return ["trend"]

    monkeypatch.setattr(rd.joblib, "load", lambda path: DummyModel())
    det = rd.RegimeDetector("fake_model")
    out = det.predict(sample_entry)
    assert out["regime"] == "trend"
    assert out["proba"] == 0.5


def test_predict_exception(monkeypatch, sample_entry):
    class BadModel:
        def predict_proba(self, X):
            raise Exception("boom")

    det = rd.RegimeDetector()
    det.model = BadModel()
    out = det.predict(sample_entry)
    assert "regime" in out and out["regime"] in rd.REGIME_CLASSES


# -------------------------
# Fallback rule-based
# -------------------------
def test_fallback_trend():
    det = rd.RegimeDetector()
    entry = {"atr": 2.0, "atr_ma": 1.0, "adx": 30}
    out = det.predict(entry)
    assert out["regime"] == "trend"


def test_fallback_range():
    det = rd.RegimeDetector()
    entry = {"atr": 0.5, "atr_ma": 1.0, "adx": 15}
    out = det.predict(entry)
    assert out["regime"] == "range"


def test_fallback_high_vol():
    det = rd.RegimeDetector()
    entry = {"atr": 2.0, "atr_ma": 1.0, "adx": 10}
    out = det.predict(entry)
    assert out["regime"] == "high_vol"


def test_fallback_low_vol():
    det = rd.RegimeDetector()
    entry = {"atr": 1.0, "atr_ma": 1.0, "adx": 22}
    out = det.predict(entry)
    assert out["regime"] == "low_vol"
