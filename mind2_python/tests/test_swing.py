import pytest
from types import SimpleNamespace
from mind2_python.swing import SwingStrategy, safe_float


class DummyEntry:
    """Mock TradeEntry สำหรับทดสอบ SwingStrategy"""
    def __init__(self, symbol="XAUUSD", bid=100, **indicators):
        self.symbol = symbol
        self.bid = bid
        if indicators:
            self.h4 = SimpleNamespace(**indicators)
        else:
            self.h4 = None
        self.d1 = None


@pytest.fixture
def cfg():
    return {
        "XAUUSD": {
            "indicators": {
                "atr": {"min_threshold": 1},
                "adx": {"min_threshold": 20},
                "rsi": {"bull_level": 65, "bear_level": 35},
            }
        }
    }


# --- safe_float unit tests ---
def test_safe_float_function():
    assert safe_float("3.14") == 3.14   # cover line 38
    assert safe_float(42) == 42.0       # cover line 38
    assert safe_float(None) is None
    assert safe_float("abc") is None


# --- indicator missing (cover line 16-17) ---
def test_no_indicators(cfg):
    entry = DummyEntry()
    entry.h4 = None
    entry.d1 = None
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["no_indicators"]


# --- ATR/ADX robustness (cover line 49-50, 55->64) ---
def test_low_volatility(cfg):
    entry = DummyEntry(rsi=70, atr=0.5, adx=25)  # atr < min_threshold
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert "low_volatility" in result["reason"]


def test_weak_trend(cfg):
    entry = DummyEntry(rsi=70, atr=2, adx=10)  # adx < min_threshold
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert "weak_trend" in result["reason"]


# --- BUY cases (cover 80-81) ---
def test_buy_with_breakout(cfg):
    entry = DummyEntry(
        rsi=70, atr=2, adx=25, macd_hist=1, bos=True,
        bb={"upper": 90, "lower": 80}, bid=100  # bid > upper
    )
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "BUY"
    assert "bb_breakout_up" in result["reason"]


def test_buy_without_breakout(cfg):
    entry = DummyEntry(
        rsi=70, atr=2, adx=25,
        bb={"upper": 110, "lower": 90}, bid=100  # bid <= upper
    )
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "BUY"
    assert "bb_breakout_up" not in result["reason"]


# --- SELL cases (cover 80-84 false/true) ---
def test_sell_with_breakout(cfg):
    entry = DummyEntry(
        rsi=20, atr=2, adx=25, macd_hist=-1, bos=True,
        bb={"upper": 120, "lower": 80}, bid=70  # bid < lower
    )
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "SELL"
    assert "bb_breakout_down" in result["reason"]


def test_sell_without_breakout(cfg):
    entry = DummyEntry(
        rsi=20, atr=2, adx=25,
        bb={"upper": 120, "lower": 50}, bid=100  # bid > lower
    )
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "SELL"
    assert "bb_breakout_down" not in result["reason"]


# --- Flat/neutral ---
def test_flat_zone(cfg):
    entry = DummyEntry(rsi=50, atr=2, adx=25)
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["flat_zone"]


def test_rsi_none_flat_zone(cfg):
    entry = DummyEntry(rsi=None, atr=5, adx=25)
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["flat_zone"]


def test_hold_confidence_not_set(cfg):
    entry = DummyEntry(rsi=50, atr=5, adx=30)
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["confidence"] == 0.0
    assert result["reason"] == ["flat_zone"]


# --- Confidence calc ---
def test_buy_without_confirms(cfg):
    entry = DummyEntry(rsi=70, atr=2, adx=25, bid=95)
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "BUY"
    assert pytest.approx(result["confidence"], 0.01) == 0.55
    assert "rsi_bull" in result["reason"]


def test_sell_without_confirms(cfg):
    entry = DummyEntry(rsi=30, atr=2, adx=25, bid=105)
    result = SwingStrategy(cfg).evaluate(entry)
    assert result["decision"] == "SELL"
    assert pytest.approx(result["confidence"], 0.01) == 0.55
    assert "rsi_bear" in result["reason"]
