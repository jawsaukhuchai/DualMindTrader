import pytest
from mind2_python.integrate_decisions import integrate_decisions

def make_res(decision="HOLD", conf=0.0):
    return {"decision": decision, "confidence": conf}

def test_unknown_decision_value_triggers_fallback(caplog):
    scalp, day, swing = make_res("BUY"), make_res("??"), make_res("SELL")
    result = integrate_decisions(scalp, day, swing)
    assert result["decision"] == "HOLD"
    assert result["confidence"] == 0.0
    assert "[Hybrid] unknown decision value" in caplog.text

def test_unknown_mode_triggers_fallback(caplog):
    scalp, day, swing = make_res("BUY", 0.8), make_res("BUY", 0.9), make_res("BUY", 1.0)
    result = integrate_decisions(scalp, day, swing, mode="mystery")
    assert result["decision"] == "HOLD"
    assert result["confidence"] == 0.0
    assert "[Hybrid] unknown mode" in caplog.text

def test_priority_mode_overrides_decision():
    # priority_dec ตรงกับ scalp → ควร override
    scalp, day, swing = make_res("BUY", 0.3), make_res("HOLD", 0.3), make_res("SELL", 0.3)
    sym_cfg = {"priority_decision": "BUY", "max_num_entries": 2}
    result = integrate_decisions(scalp, day, swing, sym_cfg=sym_cfg, mode="priority")
    assert result["decision"] == "BUY"
    assert result["num_entries"] <= 2

def test_majority_mode_all_agree_high_confidence():
    scalp, day, swing = make_res("SELL", 1.0), make_res("SELL", 1.0), make_res("SELL", 1.0)
    result = integrate_decisions(scalp, day, swing, mode="majority")
    assert result["num_entries"] == 3

def test_hybrid_mode_confidence_branches():
    scalp, day, swing = make_res("BUY", 0.6), make_res("BUY", 0.6), make_res("BUY", 0.6)
    result = integrate_decisions(scalp, day, swing, mode="hybrid")
    assert result["num_entries"] == 2
