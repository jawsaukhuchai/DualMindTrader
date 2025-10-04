import pytest
from types import SimpleNamespace
from mind2_python.scalp import ScalpStrategy


class DummyEntry:
    """Mock TradeEntry สำหรับทดสอบ ScalpStrategy"""
    def __init__(self, symbol="XAUUSD", bid=100, **indicators):
        self.symbol = symbol
        self.bid = bid
        if indicators:
            self.m5 = SimpleNamespace(**indicators)
        else:
            self.m5 = None


@pytest.fixture
def cfg():
    return {
        "XAUUSD": {
            "indicators": {
                "atr": {"min_threshold": 1},
                "adx": {"min_threshold": 20},
                "rsi": {"bull_level": 55, "bear_level": 45},
            }
        }
    }


def test_no_indicators(cfg):
    entry = DummyEntry()
    entry.m5 = None
    result = ScalpStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["no_indicators"]


def test_low_volatility(cfg):
    entry = DummyEntry(rsi=60, atr=0.5, adx=25)
    result = ScalpStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert "low_volatility" in result["reason"]


def test_weak_trend(cfg):
    entry = DummyEntry(rsi=60, atr=2, adx=10)
    result = ScalpStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert "weak_trend" in result["reason"]


def test_buy_with_confirms(cfg):
    entry = DummyEntry(
        rsi=70, atr=2, adx=30,
        stoch_k=15, stoch_d=10,
        vwap=110, bid=100,
    )
    result = ScalpStrategy(cfg).evaluate(entry)
    assert result["decision"] == "BUY"
    assert "rsi_bull" in result["reason"]
    assert "stoch_confirm_buy" in result["reason"]
    assert "below_vwap_buy" in result["reason"]
    assert result["confidence"] > 0.6


def test_sell_with_confirms(cfg):
    entry = DummyEntry(
        rsi=30, atr=2, adx=30,
        stoch_k=90, stoch_d=95,
        vwap=90, bid=100,
    )
    result = ScalpStrategy(cfg).evaluate(entry)
    assert result["decision"] == "SELL"
    assert "rsi_bear" in result["reason"]
    assert "stoch_confirm_sell" in result["reason"]
    assert "above_vwap_sell" in result["reason"]
    assert result["confidence"] > 0.6


def test_flat_zone(cfg):
    entry = DummyEntry(rsi=50, atr=2, adx=30)
    result = ScalpStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["flat_zone"]


# ✅ Patch ใหม่: ปิด branch rsi=None (ไม่เข้า RSI logic)
def test_scalp_strategy_rsi_none_skips_block(cfg):
    entry = DummyEntry(rsi=None, atr=5, adx=30)
    result = ScalpStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["flat_zone"]
    assert result["confidence"] == 0.0
