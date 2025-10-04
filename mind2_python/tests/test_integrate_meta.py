import pytest
import numpy as np
from types import SimpleNamespace

from mind2_python.integrate_decisions import MetaIntegrator

# ---------------- Dummy model ----------------
class DummyModel:
    def __init__(self):
        # กำหนด classes ลำดับ BUY, SELL, HOLD
        self.classes_ = np.array(["BUY", "SELL", "HOLD"])

    def predict_proba(self, X):
        # คืนค่า probability ตายตัว (always BUY strongest)
        n = X.shape[0]
        return np.tile(np.array([0.7, 0.2, 0.1]), (n, 1))

    def predict(self, X):
        return np.array(["BUY"] * X.shape[0])


# ---------------- Fixtures ----------------
@pytest.fixture
def meta():
    m = MetaIntegrator.__new__(MetaIntegrator)
    m.model = DummyModel()
    m.classes_ = list(m.model.classes_)
    return m


@pytest.fixture
def dummy_entry():
    return SimpleNamespace(atr=1.5, adx=25)


@pytest.fixture
def scalp_res():
    return {"decision": "BUY", "confidence": 0.6}


@pytest.fixture
def day_res():
    return {"decision": "SELL", "confidence": 0.5}


@pytest.fixture
def swing_res():
    return {"decision": "HOLD", "confidence": 0.4}


# ---------------- Tests ----------------
def test_meta_integrate_buy(meta, scalp_res, day_res, swing_res, dummy_entry):
    res = meta.integrate(scalp_res, day_res, swing_res, dummy_entry, regime="trend")
    assert isinstance(res, dict)
    assert res["decision"] == "BUY"
    assert pytest.approx(res["proba"], 0.01) == 0.7
    assert set(res["raw"].keys()) == {"BUY", "SELL", "HOLD"}


def test_meta_integrate_without_model(dummy_entry, scalp_res, day_res, swing_res):
    m = MetaIntegrator.__new__(MetaIntegrator)
    m.model = None
    m.classes_ = ["BUY", "SELL", "HOLD"]

    res = m.integrate(scalp_res, day_res, swing_res, dummy_entry, "normal")
    assert res["decision"] == "HOLD"
    assert res["proba"] == 0.33


def test_featurize_shape(meta, scalp_res, day_res, swing_res, dummy_entry):
    feats = meta._featurize(scalp_res, day_res, swing_res, dummy_entry, "range")
    # features: 8 base + 5 one-hot regimes = 13
    assert feats.shape == (13,)
    # one-hot encode regime="range" → index 1 == 1
    assert feats[9] == 1
