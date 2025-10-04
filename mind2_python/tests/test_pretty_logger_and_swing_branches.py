import pytest


# -----------------------------
# pretty_logger.py branches
# -----------------------------
def test_pretty_log_positions_summary_none(capsys):
    """cover branch: summary=None → should return early"""
    from mind2_python import pretty_logger

    pretty_logger.pretty_log_positions_summary(None)
    out, _ = capsys.readouterr()
    # ไม่มี output เพราะ return ทันที
    assert out == ""


def test_pretty_log_positions_summary_not_dict(capsys):
    """cover branch: summary not a dict → return early"""
    from mind2_python import pretty_logger

    pretty_logger.pretty_log_positions_summary("notadict")
    out, _ = capsys.readouterr()
    assert out == ""


# -----------------------------
# swing.py branches
# -----------------------------
class DummyInd:
    def __init__(self, rsi=70, atr=5, adx=20, macd_hist=1, bos=True, bb=None):
        self.rsi = rsi
        self.atr = atr
        self.adx = adx
        self.macd_hist = macd_hist
        self.bos = bos
        self.bb = bb or {"upper": 50, "lower": 10}


class DummyEntry:
    def __init__(self, symbol="XAUUSDc"):
        self.symbol = symbol
        self.h4 = DummyInd()
        self.d1 = None
        self.bid = 60


def test_swing_atr_above_threshold():
    """cover branch: atr >= min_atr → not trigger low_volatility"""
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
    entry = DummyEntry()
    res = strat.evaluate(entry)

    # RSI=70 > bull_level=65 → decision=BUY
    assert res["decision"] == "BUY"
    assert "rsi_bull" in res["reason"]
    # confidence ต้องมากกว่า 0 เพราะมี checks
    assert res["confidence"] > 0


# -----------------------------
# position_manager.py branches
# -----------------------------
def test_get_open_positions_false_branch_empty(monkeypatch):
    """mt5.positions_get → [] → isinstance True, len==0"""
    import mind2_python.position_manager as pm

    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: [])
    result = pm.PositionManager.get_open_positions("XAUUSDc")
    assert result == []


def test_get_open_positions_false_branch_none(monkeypatch):
    """mt5.positions_get → None → isinstance False"""
    import mind2_python.position_manager as pm

    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: None)
    result = pm.PositionManager.get_open_positions("XAUUSDc")
    assert result == []
