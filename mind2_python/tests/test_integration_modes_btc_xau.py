import pytest
from mind2_python.integrate_decisions import integrate_decisions

# ---- Dummy Configs ----
BTC_CFG = {
    "integration_mode": "hybrid",
    "last_atr": 40.0,
    "atr_ma": 40.0,
    "max_num_entries": 2,
}

XAU_CFG = {
    "integration_mode": "priority",
    "priority_decision": "swing",
    "last_atr": 1.2,
    "atr_ma": 1.2,
    "max_num_entries": 3,
}


# ---- Fixtures ----
@pytest.fixture
def bullish_feed():
    return {
        "scalp": {"decision": "BUY", "confidence": 0.8},
        "day":   {"decision": "BUY", "confidence": 0.9},
        "swing": {"decision": "BUY", "confidence": 0.7},
    }

@pytest.fixture
def bearish_feed():
    return {
        "scalp": {"decision": "SELL", "confidence": 0.8},
        "day":   {"decision": "SELL", "confidence": 0.9},
        "swing": {"decision": "SELL", "confidence": 0.7},
    }


# ---- BTC Tests (Hybrid) ----
def test_btc_hybrid_num_entries_bullish(bullish_feed):
    res = integrate_decisions(
        scalp_res=bullish_feed["scalp"],
        day_res=bullish_feed["day"],
        swing_res=bullish_feed["swing"],
        sym_cfg=BTC_CFG,
        regime="normal",
        mode="hybrid"
    )
    assert res["decision"] == "BUY"
    assert 1 <= res["num_entries"] <= BTC_CFG["max_num_entries"]

def test_btc_hybrid_num_entries_bearish(bearish_feed):
    res = integrate_decisions(
        scalp_res=bearish_feed["scalp"],
        day_res=bearish_feed["day"],
        swing_res=bearish_feed["swing"],
        sym_cfg=BTC_CFG,
        regime="normal",
        mode="hybrid"
    )
    assert res["decision"] == "SELL"
    assert 1 <= res["num_entries"] <= BTC_CFG["max_num_entries"]


# ---- XAU Tests (Priority) ----
def test_xau_priority_num_entries_bullish(bullish_feed):
    res = integrate_decisions(
        scalp_res=bullish_feed["scalp"],
        day_res=bullish_feed["day"],
        swing_res=bullish_feed["swing"],
        sym_cfg=XAU_CFG,
        regime="normal",
        mode="priority"
    )
    assert res["decision"] in ("BUY", "SELL", "HOLD")
    assert res["num_entries"] == XAU_CFG["max_num_entries"]

def test_xau_priority_num_entries_bearish(bearish_feed):
    res = integrate_decisions(
        scalp_res=bearish_feed["scalp"],
        day_res=bearish_feed["day"],
        swing_res=bearish_feed["swing"],
        sym_cfg=XAU_CFG,
        regime="normal",
        mode="priority"
    )
    assert res["decision"] in ("BUY", "SELL", "HOLD")
    assert res["num_entries"] == XAU_CFG["max_num_entries"]
