import pytest
import mind2_python.integrate_decisions as integ


def make_res(dec, conf=0.8):
    """Helper to create decision result dict."""
    return {"decision": dec, "confidence": conf}


def test_unknown_decision_triggers_fallback():
    # scalp decision ไม่รู้จัก → ต้อง fallback HOLD
    scalp = make_res("WTF")  # unknown
    day = make_res("BUY")
    swing = make_res("SELL")

    res = integ.integrate_decisions(
        scalp_res=scalp, day_res=day, swing_res=swing, mode="majority"
    )

    assert isinstance(res, dict)
    assert res["decision"] == "HOLD"
    assert res["num_entries"] == 0
    assert res["confidence"] == 0.0


def test_unknown_mode_triggers_fallback():
    # mode ไม่รู้จัก → fallback HOLD
    scalp = make_res("BUY")
    day = make_res("SELL")
    swing = make_res("HOLD")

    res = integ.integrate_decisions(
        scalp_res=scalp, day_res=day, swing_res=swing, mode="mystery"
    )

    assert isinstance(res, dict)
    assert res["decision"] == "HOLD"
    assert res["num_entries"] == 0


def test_priority_mode_no_match_use_score():
    # priority mode แต่ไม่มี priority_decision match → ใช้ score logic + num_entries=3
    scalp = make_res("BUY")
    day = make_res("SELL")
    swing = make_res("HOLD")

    sym_cfg = {"integration_mode": "priority", "priority_decision": "swing"}

    res = integ.integrate_decisions(
        scalp_res=scalp, day_res=day, swing_res=swing, sym_cfg=sym_cfg, mode="priority"
    )

    assert isinstance(res, dict)
    assert res["num_entries"] == 3  # enforce max entries
    assert res["decision"] in ("BUY", "SELL", "HOLD")  # decision มาจาก score logic


def test_hybrid_max_num_entries_cut():
    # hybrid ปกติ avg_conf สูง → ได้ num_entries=3
    scalp = make_res("BUY", 1.0)
    day = make_res("BUY", 1.0)
    swing = make_res("BUY", 1.0)

    sym_cfg = {"integration_mode": "hybrid", "max_num_entries": 2}

    res = integ.integrate_decisions(
        scalp_res=scalp, day_res=day, swing_res=swing, sym_cfg=sym_cfg, mode="hybrid"
    )

    # ถูก cut จาก 3 → 2
    assert res["decision"] == "BUY"
    assert res["num_entries"] == 2


def test_strict_mode_always_one_entry():
    scalp = make_res("SELL", 0.9)
    day = make_res("SELL", 0.9)
    swing = make_res("SELL", 0.9)

    res = integ.integrate_decisions(
        scalp_res=scalp, day_res=day, swing_res=swing, mode="strict"
    )

    assert res["decision"] == "SELL"
    assert res["num_entries"] == 1
