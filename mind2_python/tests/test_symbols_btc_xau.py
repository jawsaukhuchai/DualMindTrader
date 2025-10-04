import pytest
from mind2_python import integrate_decisions as integ


@pytest.fixture
def scalp_res():
    return {"decision": "BUY", "confidence": 0.65}


@pytest.fixture
def day_res():
    return {"decision": "SELL", "confidence": 0.70}


@pytest.fixture
def swing_res():
    return {"decision": "BUY", "confidence": 0.80}


@pytest.fixture
def btc_cfg():
    return {
        "integration_mode": "majority",
        "last_atr": 150.0,
        "atr_ma": 120.0,
        "weights": {"scalp": 0.4, "day": 0.3, "swing": 0.3},
    }


@pytest.fixture
def xau_cfg():
    return {
        "integration_mode": "priority",
        "last_atr": 20.0,
        "atr_ma": 22.0,
        "weights": {"scalp": 0.2, "day": 0.3, "swing": 0.5},
    }


@pytest.fixture
def global_cfg():
    return {"decision_threshold": 0.05}


# ---------------- BTCUSDc ----------------
def test_btcusdc_majority_mode(scalp_res, day_res, swing_res, btc_cfg, global_cfg):
    res = integ.integrate_decisions(scalp_res, day_res, swing_res, btc_cfg, global_cfg, regime="trend")
    # Majority BUY signals should dominate
    assert res["decision"] == "BUY"
    assert res["regime"] == "trend"
    assert res["num_entries"] in (2, 3)


def test_confidence_scaling_btc(btc_cfg, global_cfg):
    scalp = {"decision": "BUY", "confidence": 1.0}
    day = {"decision": "BUY", "confidence": 1.0}
    swing = {"decision": "BUY", "confidence": 1.0}
    res = integ.integrate_decisions(scalp, day, swing, btc_cfg, global_cfg, regime="trend")
    assert res["decision"] == "BUY"
    assert res["num_entries"] == 3


# ---------------- XAUUSDc ----------------
def test_xauusdc_priority_mode(scalp_res, day_res, swing_res, xau_cfg, global_cfg):
    res = integ.integrate_decisions(scalp_res, day_res, swing_res, xau_cfg, global_cfg, regime="range")
    # Swing weight is priority
    assert res["decision"] in ("BUY", "SELL", "HOLD")
    assert res["regime"] == "range"
    assert res["num_entries"] in (2, 3)


def test_confidence_scaling_xau(xau_cfg, global_cfg):
    scalp = {"decision": "SELL", "confidence": 1.0}
    day = {"decision": "SELL", "confidence": 1.0}
    swing = {"decision": "SELL", "confidence": 1.0}
    res = integ.integrate_decisions(scalp, day, swing, xau_cfg, global_cfg, regime="normal")
    assert res["decision"] == "SELL"
    assert res["num_entries"] == 3
