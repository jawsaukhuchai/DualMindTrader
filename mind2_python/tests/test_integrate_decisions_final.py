import pytest
import logging
from mind2_python import integrate_decisions as idc

def make_res(decision="HOLD", conf=0.0):
    return {"decision": decision, "confidence": conf}

def test_unknown_decision_value_triggers_fallback(caplog):
    caplog.set_level(logging.WARNING)
    res = idc.integrate_decisions(
        scalp_res=make_res("WTF"),  # unknown decision
        day_res=make_res("BUY"),
        swing_res=make_res("SELL"),
    )
    assert res["decision"] == "HOLD"
    assert res["confidence"] == 0.0
    assert "unknown decision value" in caplog.text

def test_unknown_mode_triggers_fallback(caplog):
    caplog.set_level(logging.WARNING)
    res = idc.integrate_decisions(
        scalp_res=make_res("BUY"),
        day_res=make_res("SELL"),
        swing_res=make_res("HOLD"),
        mode="strange_mode"  # unknown mode
    )
    assert res["decision"] == "HOLD"
    assert res["num_entries"] == 0  # fallback dict
    assert "unknown mode" in caplog.text
