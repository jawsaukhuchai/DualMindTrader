# tests/test_decision_engine_gap.py
import types
import pytest
import mind2_python.decision_engine as de


def test_regime_detector_else_branch():
    """ใช้ NaN → comparisons ทั้งหมด False → trigger else branch (line 81)"""
    det = de.RegimeDetector({"atr_threshold": 1.0, "adx_threshold": 20.0})
    e = types.SimpleNamespace(atr=float("nan"), adx=float("nan"))
    assert det.detect(e) == "normal"


def test_fusion_decision_tie_ai_buy_rule_sell():
    """AI=BUY, Rule=SELL → tie → return AI decision (line 125)"""
    ai = {"decision": "BUY", "confidence": 1.0}
    rule = {"decision": "SELL", "confidence": 1.0}
    out = de.fusion_decision(ai, rule, "normal")
    assert out["decision"] == "BUY"
    assert "score" in out


# -------- helpers for process tests --------
class DummyStrategy:
    def __init__(self, res=None):
        self.res = res or {"decision": "HOLD", "confidence": 0.5}
    def evaluate(self, entry): return self.res


class DummyExit:
    def calc(self, *a, **k):
        return {"sl": 1.0, "tp": [{"price": 2.0}], "entries": {}}


def make_entry():
    return types.SimpleNamespace(
        symbol="XAUUSDc", bid=100.0, ask=102.0,
        atr=1.5, adx=25.0, balance=1000.0, equity=1000.0,
        margin=0.0, margin_level=1000.0, tf="H1", pnl=0.0
    )


def make_engine(monkeypatch, **overrides):
    cfg = {"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "global": {}}
    monkeypatch.setattr(de, "load_config", lambda path, overrides=None: cfg)
    eng = de.DecisionEngine("fake", balance=1000)
    # replace strategies with dummies
    eng.scalp = DummyStrategy()
    eng.day = DummyStrategy()
    eng.swing = DummyStrategy()
    eng.exit = overrides.get("exit", DummyExit())
    return eng


# -------- main tests --------
def test_process_sl_tp_logging(monkeypatch, caplog):
    """DummyExit คืน sl/tp → trigger debug SL/TP logging (399–410, 413)"""
    caplog.set_level("INFO")

    class ExitWithSLTP:
        def calc(self, *a, **k):
            return {
                "sl": 95.0,
                "tp": [{"price": 110.0}, {"price": 120.0}],
                "entries": {}
            }

    eng = make_engine(monkeypatch, exit=ExitWithSLTP())
    entry = make_entry()
    out = eng.process(entry)

    assert out["sl"] == 95.0
    assert out["tp"] == [110.0, 120.0]
    assert any("SL=" in r.message for r in caplog.records)
    assert any("TP=" in r.message for r in caplog.records)


# ======================================================
# Extra tests to close coverage gaps
# ======================================================

def test_select_mode_scaler_branch():
    """cover select_mode path ที่ return 'scaler' (line 66–67)"""
    sym_cfg = {"atr_threshold": 1.0, "adx_threshold": 20.0}
    entry = types.SimpleNamespace(atr=2.0, adx=25.0)
    assert de.select_mode(sym_cfg, entry) == "scaler"


def test_fusion_decision_tie_non_normal_regime():
    """AI=BUY, Rule=SELL → tie แต่ regime='event' → ต้องคืน AI decision (line 125)"""
    ai = {"decision": "BUY", "confidence": 1.0}
    rule = {"decision": "SELL", "confidence": 1.0}
    out = de.fusion_decision(ai, rule, "event")
    assert out["decision"] == "BUY"


def test_process_sl_tp_logging_force_buy(monkeypatch, caplog):
    """force AI+strategies = BUY → trigger SL/TP log branches"""
    caplog.set_level("INFO")

    class ExitWithSLTP:
        def calc(self, *a, **k):
            return {
                "sl": 95.0,
                "tp": [{"price": 110.0}, {"price": 120.0}],
                "entries": {}
            }

    class ForceAI:
        def evaluate(self, entry): return {"decision": "BUY", "confidence": 1.0}

    cfg = {"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "global": {}}
    monkeypatch.setattr(de, "load_config", lambda path, overrides=None: cfg)
    eng = de.DecisionEngine("fake", balance=1000)
    eng.scalp = eng.day = eng.swing = DummyStrategy({"decision": "BUY", "confidence": 1.0})
    eng.exit = ExitWithSLTP()
    eng.ai_manager = ForceAI()  # force BUY decision
    entry = make_entry()

    out = eng.process(entry)
    assert out["sl"] == 95.0
    assert out["tp"] == [110.0, 120.0]
    assert any("SL=" in r.message for r in caplog.records)
    assert any("TP=" in r.message for r in caplog.records)
# tests/test_decision_engine_gap.py (ต่อจากเดิม)
import types


def test_select_mode_scaler_strong_case():
    """entry มี atr/adx สูงมาก → ครอบ line 66–67 (return 'scaler')"""
    sym_cfg = {"atr_threshold": 1.0, "adx_threshold": 20.0}
    entry = types.SimpleNamespace(atr=10.0, adx=100.0)
    assert de.select_mode(sym_cfg, entry) == "scaler"


def test_fusion_decision_tie_exact_zero():
    """AI=BUY, Rule=SELL, weights=0.5:0.5 → total_score=0 → ครอบ line 125"""
    ai = {"decision": "BUY", "confidence": 1.0}
    rule = {"decision": "SELL", "confidence": 1.0}
    # regime=normal → weights ai=0.5, rule=0.5
    out = de.fusion_decision(ai, rule, "normal")
    assert out["decision"] == "BUY"   # tie → return ai decision
    assert out["score"] == 0.0


def test_process_sl_tp_logging_force_allows(monkeypatch, caplog):
    """force risk/portfolio allow → final=BUY → trigger SL/TP log (399–410, 413)"""
    caplog.set_level("INFO")

    class ExitWithSLTP:
        def calc(self, *a, **k):
            return {
                "sl": 90.0,
                "tp": [{"price": 110.0}, {"price": 120.0}],
                "entries": {}
            }

    class ForceAI:
        def evaluate(self, entry): return {"decision": "BUY", "confidence": 1.0}

    cfg = {"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "global": {}}
    monkeypatch.setattr(de, "load_config", lambda path, overrides=None: cfg)

    eng = de.DecisionEngine("fake", balance=1000)
    # force BUY across all
    eng.scalp = eng.day = eng.swing = DummyStrategy({"decision": "BUY", "confidence": 1.0})
    eng.exit = ExitWithSLTP()
    eng.ai_manager = ForceAI()
    # force allow
    eng.risk = types.SimpleNamespace(allow=lambda *a, **k: (True, []))
    eng.portfolio = types.SimpleNamespace(allow=lambda *a, **k: (True, []))

    entry = make_entry()
    out = eng.process(entry)

    assert out["decision"] == "BUY"
    assert out["sl"] == 90.0
    assert out["tp"] == [110.0, 120.0]
    assert any("SL=" in r.message for r in caplog.records)
    assert any("TP=" in r.message for r in caplog.records)
# tests/test_decision_engine_gap.py (เพิ่มท้ายไฟล์)

def test_select_mode_scaler_strong_values():
    """ค่า atr/adx ใหญ่มาก → ต้องเข้า scaler branch (66–67)"""
    sym_cfg = {"atr_threshold": 1.0, "adx_threshold": 20.0}
    entry = types.SimpleNamespace(atr=1000.0, adx=1000.0)
    mode = de.select_mode(sym_cfg, entry)
    assert mode == "scaler"


def test_fusion_decision_tie_exact_zero_score():
    """AI=BUY, Rule=SELL → weights balance → total_score=0 → line 125 (AI decision)"""
    ai = {"decision": "BUY", "confidence": 1.0}
    rule = {"decision": "SELL", "confidence": 1.0}
    # ใช้ regime="normal" → ai_weight=0.5, rule_weight=0.5
    out = de.fusion_decision(ai, rule, "normal")
    assert out["score"] == 0.0  # tie
    assert out["decision"] == "BUY"  # tie → AI decision


def test_process_sl_tp_logging_with_debug(monkeypatch, caplog):
    """force AI=BUY และ risk/portfolio allow → trigger SL/TP log (399–410, 413)"""
    caplog.set_level("DEBUG")

    class ExitWithSLTP:
        def calc(self, *a, **k):
            return {
                "sl": 50.0,
                "tp": [{"price": 150.0}, {"price": 160.0}],
                "entries": {}
            }

    class ForceAI:
        def evaluate(self, entry): return {"decision": "BUY", "confidence": 1.0}

    # fake config
    cfg = {"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "global": {}}
    monkeypatch.setattr(de, "load_config", lambda path, overrides=None: cfg)

    eng = de.DecisionEngine("fake", balance=1000)
    eng.scalp = eng.day = eng.swing = DummyStrategy({"decision": "BUY", "confidence": 1.0})
    eng.exit = ExitWithSLTP()
    eng.ai_manager = ForceAI()
    # risk/portfolio allow เสมอ
    eng.risk = types.SimpleNamespace(allow=lambda *a, **k: (True, []))
    eng.portfolio = types.SimpleNamespace(allow=lambda *a, **k: (True, []))

    entry = make_entry()
    out = eng.process(entry)

    assert out["decision"] == "BUY"
    assert out["sl"] == 50.0
    assert out["tp"] == [150.0, 160.0]
    # ตรวจว่า log ออกจริง
    messages = [r.message for r in caplog.records]
    assert any("SL=" in m for m in messages)
    assert any("TP=" in m for m in messages)
