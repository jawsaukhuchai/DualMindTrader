# tests/test_decision_engine_pinpoint.py
import types
import pytest
import mind2_python.decision_engine as de


# --------- cover select_mode line 66–67 ----------
def test_select_mode_scaler_pinpoint():
    """force atr/adx >> threshold → ต้อง return 'scaler' (66–67)"""
    sym_cfg = {"atr_threshold": 1.0, "adx_threshold": 20.0}
    entry = types.SimpleNamespace(atr=9999.0, adx=9999.0)
    result = de.select_mode(sym_cfg, entry)
    assert result == "scaler"


# --------- cover fusion_decision line 125 ----------
def test_fusion_decision_tie_pinpoint():
    """AI=BUY, Rule=SELL, weights สมดุล → score=0 → ครอบ line 125"""
    ai = {"decision": "BUY", "confidence": 1.0}
    rule = {"decision": "SELL", "confidence": 1.0}
    # regime="normal" → ai_weight=0.5, rule_weight=0.5
    out = de.fusion_decision(ai, rule, "normal")
    # ต้องได้ score=0.0 และตัดสินใจตาม AI (BUY)
    assert abs(out["score"] - 0.0) < 1e-9
    assert out["decision"] == "BUY"


# --------- cover process logging lines 399–410, 413 ----------
class DummyStrategy:
    def __init__(self, decision="BUY"):
        self.res = {"decision": decision, "confidence": 1.0}
    def evaluate(self, entry): return self.res


class ExitWithSLTP:
    def calc(self, *a, **k):
        return {
            "sl": 77.7,
            "tp": [{"price": 123.4}, {"price": 234.5}],
            "entries": {}
        }


def make_entry():
    return types.SimpleNamespace(
        symbol="XAUUSDc", bid=100.0, ask=102.0,
        atr=1.5, adx=25.0, balance=1000.0, equity=1000.0,
        margin=0.0, margin_level=1000.0, tf="H1", pnl=0.0
    )


def test_process_sl_tp_logs_pinpoint(monkeypatch, caplog):
    """force BUY + allow risk/portfolio → เดินถึง logger.info SL/TP (399–410, 413)"""
    caplog.set_level("INFO")

    cfg = {"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "global": {}}
    monkeypatch.setattr(de, "load_config", lambda path, overrides=None: cfg)

    eng = de.DecisionEngine("fake", balance=1000)
    eng.scalp = eng.day = eng.swing = DummyStrategy("BUY")
    eng.exit = ExitWithSLTP()
    # force AI BUY
    eng.ai_manager = types.SimpleNamespace(evaluate=lambda entry: {"decision": "BUY", "confidence": 1.0})
    # force allow
    eng.risk = types.SimpleNamespace(allow=lambda *a, **k: (True, []))
    eng.portfolio = types.SimpleNamespace(allow=lambda *a, **k: (True, []))

    entry = make_entry()
    out = eng.process(entry)

    assert out["decision"] == "BUY"
    assert out["sl"] == 77.7
    assert out["tp"] == [123.4, 234.5]

    messages = [r.message for r in caplog.records]
    assert any("SL=" in m for m in messages)
    assert any("TP=" in m for m in messages)
