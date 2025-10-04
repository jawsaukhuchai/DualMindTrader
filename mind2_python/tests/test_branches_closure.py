import pytest


# =====================================================
# PositionManager branch coverage (178->180)
# =====================================================
def test_position_manager_branch_false_emptylist(monkeypatch):
    """force mt5.positions_get to return [] → isinstance True, len=0 → branch False"""
    import mind2_python.position_manager as pm

    # Mock ให้ return [] → isinstance True แต่ len=0
    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: [])
    res = pm.PositionManager.get_open_positions("XAUUSDc")
    assert res == []


# =====================================================
# PrettyLogger branch coverage (138->140)
# =====================================================
def test_pretty_logger_branch_false_default_rule_res():
    """call pretty_log_tradesignal without rule_res → branch False"""
    from mind2_python import pretty_logger

    # ไม่ส่ง rule_res → default=None → if rule_res = False
    pretty_logger.pretty_log_tradesignal(
        symbol="XAUUSDc",
        decision="BUY",
        lot=0.1,
        entry=2000.0,
        reason="no_rule_res_case"
    )
    # ไม่มี exception → ผ่าน, branch False ถูก cover


# =====================================================
# Swing branch coverage (57->61)
# =====================================================
class DummyIndHold:
    """indicator mock that keeps decision as HOLD until the end"""
    def __init__(self):
        self.rsi = 50          # ไม่ trigger buy/sell
        self.atr = 5           # >= min_atr
        self.adx = 20          # >= min_adx
        self.macd_hist = 0     # ไม่มี MACD signal
        self.bos = False       # ไม่ confirm BOS
        self.bb = {"upper": 100, "lower": 0}


class DummyEntryHold:
    def __init__(self):
        self.symbol = "XAUUSDc"
        self.h4 = DummyIndHold()
        self.d1 = None
        self.bid = 50


def test_swing_decision_hold_branch_false():
    """craft indicators so SwingStrategy keeps decision = HOLD → branch False"""
    from mind2_python.swing import SwingStrategy

    cfg = {
        "XAUUSDc": {
            "indicators": {
                "atr": {"min_threshold": 1},
                "adx": {"min_threshold": 10},
                "rsi": {"bull_level": 65, "bear_level": 35},
            }
        }
    }

    strat = SwingStrategy(cfg)
    res = strat.evaluate(DummyEntryHold())

    # เนื่องจากไม่มีสัญญาณชัดเจน → decision ต้อง HOLD
    assert res["decision"] == "HOLD"
    assert res["confidence"] == 0.0
    assert res["reason"] == ["flat_zone"]
