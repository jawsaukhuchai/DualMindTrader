import pytest
from mind2_python import integrate_decisions as idc

def make_res(decision="HOLD", conf=0.0):
    return {"decision": decision, "confidence": conf}

def test_priority_mode_btc_no_match():
    sym_cfg = {"integration_mode": "priority", "priority_decision": "BUY",
               "max_num_entries": 3}
    res = idc.integrate_decisions(
        scalp_res=make_res("SELL", 0.7),
        day_res=make_res("SELL", 0.7),
        swing_res=make_res("SELL", 0.7),
        sym_cfg=sym_cfg,
        regime="normal",
    )
    assert res["decision"] == "SELL"
    assert res["regime"] == "normal"
    assert res["num_entries"] == 3

def test_majority_mode_xau_low_confidence():
    sym_cfg = {"integration_mode": "majority"}
    res = idc.integrate_decisions(
        scalp_res=make_res("BUY", 0.3),
        day_res=make_res("SELL", 0.3),
        swing_res=make_res("HOLD", 0.2),
        sym_cfg=sym_cfg,
        regime="normal",
    )
    assert res["mode"] == "majority"
    # low confidence → num_entries=2
    assert res["num_entries"] == 2

def test_strict_mode_btc():
    sym_cfg = {"integration_mode": "strict"}
    res = idc.integrate_decisions(
        scalp_res=make_res("BUY", 0.8),
        day_res=make_res("SELL", 0.8),
        swing_res=make_res("HOLD", 0.8),
        sym_cfg=sym_cfg,
        regime="normal",
    )
    assert res["mode"] == "strict"
    assert res["num_entries"] == 1
