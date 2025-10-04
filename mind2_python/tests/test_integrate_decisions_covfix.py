import sys
import importlib
import logging

def test_logger_handler_setup():
    """
    Ensure logger handler branch (if not logger.handlers) is covered.
    """
    # ลบโมดูลเก่าออกจาก sys.modules เพื่อบังคับ reload
    sys.modules.pop("mind2_python.integrate_decisions", None)
    mod = importlib.import_module("mind2_python.integrate_decisions")

    # ต้องมี handler ถูกเพิ่มขึ้นมา
    assert mod.logger.handlers
    assert isinstance(mod.logger.handlers[0], logging.StreamHandler)


def test_integrate_predict_exception():
    """
    Cover MetaIntegrator.integrate branch: model without predict_proba but predict() fails.
    """
    import mind2_python.integrate_decisions as mod

    class BadModelNoProba:
        def predict(self, X):
            raise RuntimeError("boom")

    m = mod.MetaIntegrator.__new__(mod.MetaIntegrator)
    m.model = BadModelNoProba()
    m.classes_ = ["BUY", "SELL", "HOLD"]

    scalp = {"decision": "BUY", "confidence": 0.1}
    day   = {"decision": "SELL", "confidence": 0.1}
    swing = {"decision": "HOLD", "confidence": 0.1}

    entry = type("E", (), {"atr": 1.0, "adx": 5})()

    res = m.integrate(scalp, day, swing, entry, regime="normal")

    assert res["decision"] == "HOLD"
    assert res["proba"] == 0.0
    assert res["raw"] == {}


def test_integrate_predict_branch_exception():
    """
    Explicitly cover MetaIntegrator.integrate fallback (lines 157-158):
    model without predict_proba, predict() raises exception → fallback HOLD.
    """
    import mind2_python.integrate_decisions as mod

    class BadPredictModel:
        def predict(self, X):
            raise RuntimeError("predict failed")

    m = mod.MetaIntegrator.__new__(mod.MetaIntegrator)
    m.model = BadPredictModel()
    m.classes_ = ["BUY", "SELL", "HOLD"]

    scalp = {"decision": "BUY", "confidence": 0.2}
    day   = {"decision": "SELL", "confidence": 0.3}
    swing = {"decision": "HOLD", "confidence": 0.4}
    entry = type("E", (), {"atr": 1.0, "adx": 5})()

    res = m.integrate(scalp, day, swing, entry, "normal")

    assert res["decision"] == "HOLD"
    assert res["proba"] == 0.0
    assert res["raw"] == {}


def test_priority_mode_with_fallback_triggers():
    """
    Cover branch: priority_fallback=True and no priority_decision match.
    Should force fallback HOLD.
    """
    import mind2_python.integrate_decisions as mod

    scalp = {"decision": "BUY", "confidence": 0.5}
    day   = {"decision": "SELL", "confidence": 0.5}
    swing = {"decision": "HOLD", "confidence": 0.5}

    sym_cfg = {
        "integration_mode": "priority",
        "priority_decision": "XXX",  # ไม่มี match
        "priority_fallback": True,   # เปิด fallback
    }

    res = mod.integrate_decisions(scalp, day, swing, sym_cfg=sym_cfg)

    assert res["decision"] == "HOLD"
    assert res["num_entries"] == 0
    assert res["confidence"] == 0.0
