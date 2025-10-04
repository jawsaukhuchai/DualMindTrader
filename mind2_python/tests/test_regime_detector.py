import pytest
import numpy as np
from types import SimpleNamespace

from mind2_python.regime_detector import RegimeDetector


# --------------------------
# Fixtures
# --------------------------
@pytest.fixture
def fallback_detector():
    """Detector without model_path -> fallback rule-based"""
    return RegimeDetector()


@pytest.fixture
def fake_model(monkeypatch):
    """Mock model with predict and predict_proba"""
    class FakeModel:
        classes_ = np.array(["trend", "range", "high_vol", "low_vol"])

        def predict_proba(self, X):
            # Always return "trend" with high proba
            return np.array([[0.9, 0.05, 0.03, 0.02]])

        def predict(self, X):
            return ["range"]

    return FakeModel()


# --------------------------
# Tests fallback rule-based
# --------------------------
def test_fallback_trend(fallback_detector):
    ind = {"atr": 20, "atr_ma": 10, "adx": 30}
    res = fallback_detector.predict(ind)
    assert res["regime"] == "trend"
    assert 0 <= res["proba"] <= 1


def test_fallback_range(fallback_detector):
    ind = {"atr": 5, "atr_ma": 10, "adx": 15}
    res = fallback_detector.predict(ind)
    assert res["regime"] == "range"


def test_fallback_high_vol(fallback_detector):
    ind = {"atr": 30, "atr_ma": 10, "adx": 18}
    res = fallback_detector.predict(ind)
    assert res["regime"] == "high_vol"


def test_fallback_low_vol(fallback_detector):
    ind = {"atr": 10, "atr_ma": 10, "adx": 22}
    res = fallback_detector.predict(ind)
    assert res["regime"] == "low_vol"


# --------------------------
# Tests with fake ML model
# --------------------------
def test_predict_with_model_predict_proba(monkeypatch, fake_model):
    det = RegimeDetector()
    det.model = fake_model
    det.classes_ = list(fake_model.classes_)
    ind = {"atr": 10, "atr_ma": 10, "adx": 25}
    res = det.predict(ind)
    assert res["regime"] == "trend"
    assert pytest.approx(res["proba"], 0.01) == 0.9


def test_predict_with_model_predict(monkeypatch):
    class FakePredictOnly:
        def predict(self, X):
            return ["range"]

    det = RegimeDetector()
    det.model = FakePredictOnly()
    det.classes_ = ["trend", "range", "high_vol", "low_vol"]

    ind = {"atr": 10, "atr_ma": 10, "adx": 25}
    res = det.predict(ind)
    assert res["regime"] == "range"
    assert res["proba"] == 0.5
