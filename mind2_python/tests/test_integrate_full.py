import pytest
from types import SimpleNamespace

from mind2_python import integrate_decisions as integ


# ---------------- Fixtures ----------------
@pytest.fixture
def dummy_entry():
    return SimpleNamespace(atr=1.5, adx=25)


@pytest.fixture
def scalp_buy():
    return {"decision": "BUY", "confidence": 0.9}


@pytest.fixture
def day_sell():
    return {"decision": "SELL", "confidence": 0.9}


@pytest.fixture
def swing_hold():
    return {"decision": "HOLD", "confidence": 0.9}


# ---------------- dynamic_threshold ----------------
def test_dynamic_threshold_cases():
    assert integ.dynamic_threshold(0.1, atr=2.0, atr_ma=1.0) < 0.1  # ATR > ATR_MA
    assert integ.dynamic_threshold(0.1, atr=1.0, atr_ma=2.0) > 0.1  # ATR < ATR_MA
    assert integ.dynamic_threshold(0.1, atr=1.0, atr_ma=0.0) == 0.1  # ATR_MA=0


# ---------------- integrate_decisions ----------------
def test_force_buy_branch():
    scalp = {"decision": "BUY", "confidence": 1.0}
    day = {"decision": "BUY", "confidence": 1.0}
    swing = {"decision": "BUY", "confidence": 1.0}
    res = integ.integrate_decisions(
        scalp,
        day,
        swing,
        sym_cfg={"last_atr": 1.0, "atr_ma": 1.0},
        global_cfg={"decision_threshold": 0.01},
        regime="trend",
    )
    assert res["decision"] == "BUY"
    assert res["score"] > res["threshold"]  # ensure branch taken


def test_force_sell_branch():
    scalp = {"decision": "SELL", "confidence": 1.0}
    day = {"decision": "SELL", "confidence": 1.0}
    swing = {"decision": "SELL", "confidence": 1.0}
    res = integ.integrate_decisions(
        scalp,
        day,
        swing,
        sym_cfg={"last_atr": 1.0, "atr_ma": 1.0},
        global_cfg={"decision_threshold": 0.01},
        regime="range",
    )
    assert res["decision"] == "SELL"
    assert res["score"] < -res["threshold"]  # ensure branch taken


def test_integrate_hold_all_flat():
    res = integ.integrate_decisions(
        {"decision": "HOLD", "confidence": 0.0},
        {"decision": "HOLD", "confidence": 0.0},
        {"decision": "HOLD", "confidence": 0.0},
        sym_cfg={"last_atr": 1.0, "atr_ma": 1.0},
        global_cfg={"decision_threshold": 0.05},
        regime="normal",
    )
    assert res["decision"] == "HOLD"


def test_integrate_high_confidence_num_entries():
    res = integ.integrate_decisions(
        {"decision": "BUY", "confidence": 1.0},
        {"decision": "BUY", "confidence": 1.0},
        {"decision": "BUY", "confidence": 1.0},
        sym_cfg={"last_atr": 1.0, "atr_ma": 1.0},
        global_cfg={"decision_threshold": 0.01},
        regime="trend",
    )
    assert res["num_entries"] == 3


@pytest.mark.parametrize("mode,expected", [
    ("strict", 1),
    ("majority", 2),
    ("priority", 3),
    ("hybrid", None),
])
def test_num_entries_modes(mode, expected, scalp_buy, day_sell, swing_hold):
    sym_cfg = {"last_atr": 1.0, "atr_ma": 1.0, "integration_mode": mode}
    res = integ.integrate_decisions(
        scalp_buy,
        day_sell,
        swing_hold,
        sym_cfg=sym_cfg,
        global_cfg={},
        regime="normal",
    )
    if mode != "hybrid":
        assert res["num_entries"] == expected
    else:
        assert 1 <= res["num_entries"] <= 3


# ---------------- MetaIntegrator encode ----------------
def test_encode_dec_buy():
    m = integ.MetaIntegrator.__new__(integ.MetaIntegrator)
    assert m._encode_dec("BUY") == 1


def test_encode_dec_sell():
    m = integ.MetaIntegrator.__new__(integ.MetaIntegrator)
    assert m._encode_dec("SELL") == -1


def test_encode_dec_hold():
    m = integ.MetaIntegrator.__new__(integ.MetaIntegrator)
    assert m._encode_dec("HOLD") == 0


def test_encode_dec_other():
    m = integ.MetaIntegrator.__new__(integ.MetaIntegrator)
    assert m._encode_dec("XXX") == 0


# ---------------- MetaIntegrator exception paths ----------------
class FailingProbaModel:
    classes_ = ["BUY", "SELL", "HOLD"]

    def predict_proba(self, X):
        raise RuntimeError("fail")


class FailingPredictModel:
    classes_ = ["BUY", "SELL", "HOLD"]

    def predict(self, X):
        raise RuntimeError("fail")


def test_meta_integrator_fail_proba(dummy_entry, scalp_buy, day_sell, swing_hold, caplog):
    m = integ.MetaIntegrator.__new__(integ.MetaIntegrator)
    m.model = FailingProbaModel()
    m.classes_ = list(m.model.classes_)
    caplog.set_level("ERROR")
    res = m.integrate(scalp_buy, day_sell, swing_hold, dummy_entry, "normal")
    assert res["decision"] == "HOLD"
    assert res["proba"] == 0.0
    assert any("predict fail" in rec.message or "fail" in rec.message for rec in caplog.records)


def test_meta_integrator_fail_predict(dummy_entry, scalp_buy, day_sell, swing_hold, caplog):
    m = integ.MetaIntegrator.__new__(integ.MetaIntegrator)
    m.model = FailingPredictModel()
    m.classes_ = list(m.model.classes_)
    caplog.set_level("ERROR")
    res = m.integrate(scalp_buy, day_sell, swing_hold, dummy_entry, "normal")
    assert res["decision"] == "HOLD"
    assert res["proba"] == 0.0
    assert any("predict fail" in rec.message or "fail" in rec.message for rec in caplog.records)
