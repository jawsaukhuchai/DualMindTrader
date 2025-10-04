import pytest
from types import SimpleNamespace
from mind2_python.day import DayStrategy


class DummyEntry:
    """Mock TradeEntry สำหรับทดสอบ DayStrategy"""
    def __init__(self, symbol="XAUUSD", bid=100, **indicators):
        self.symbol = symbol
        self.bid = bid
        if indicators:
            self.h1 = SimpleNamespace(**indicators)
        else:
            self.h1 = None


@pytest.fixture
def cfg():
    return {
        "XAUUSD": {
            "indicators": {
                "atr": {"min_threshold": 1},
                "adx": {"min_threshold": 20},
                "rsi": {"bull_level": 60, "bear_level": 40},
            }
        }
    }


def test_no_indicators(cfg):
    entry = DummyEntry()
    entry.h1 = None
    result = DayStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["no_indicators"]


def test_low_volatility(cfg):
    entry = DummyEntry(rsi=70, atr=0.5, adx=25)
    result = DayStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert "low_volatility" in result["reason"]


def test_weak_trend(cfg):
    entry = DummyEntry(rsi=70, atr=2, adx=10)
    result = DayStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert "weak_trend" in result["reason"]


def test_buy_with_confirms(cfg):
    entry = DummyEntry(
        rsi=70, atr=2, adx=25,
        ema_fast=120, ema_slow=100,
        macd_hist=1,
        stoch_k=15, stoch_d=10,
        vwap=110, bid=100,
    )
    result = DayStrategy(cfg).evaluate(entry)
    assert result["decision"] == "BUY"
    assert "rsi_bull" in result["reason"]
    assert "ema_uptrend" in result["reason"]
    assert "macd_bull" in result["reason"]
    assert "stoch_buy" in result["reason"]
    assert "below_vwap" in result["reason"]
    assert result["confidence"] > 0.5


def test_sell_with_confirms(cfg):
    entry = DummyEntry(
        rsi=20, atr=2, adx=25,
        ema_fast=80, ema_slow=100,
        macd_hist=-1,
        stoch_k=85, stoch_d=90,
        vwap=90, bid=100,
    )
    result = DayStrategy(cfg).evaluate(entry)
    assert result["decision"] == "SELL"
    assert "rsi_bear" in result["reason"]
    assert "ema_downtrend" in result["reason"]
    assert "macd_bear" in result["reason"]
    assert "stoch_sell" in result["reason"]
    assert "above_vwap" in result["reason"]
    assert result["confidence"] > 0.5


def test_flat_zone(cfg):
    entry = DummyEntry(rsi=50, atr=2, adx=25)
    result = DayStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["flat_zone"]


def test_day_strategy_rsi_midpoint_triggers_flat_zone(cfg):
    entry = DummyEntry(rsi=50, atr=5, adx=30)
    result = DayStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["flat_zone"]


def test_day_strategy_rsi_exact_bear_level(cfg):
    entry = DummyEntry(rsi=40, atr=5, adx=30)
    result = DayStrategy(cfg).evaluate(entry)
    assert result["decision"] == "SELL"
    assert "rsi_bear" in result["reason"]


def test_day_strategy_rsi_between_bear_and_bull(cfg):
    """Case rsi > bear_level แต่ < bull_level → ไม่เข้า elif branch"""
    custom_cfg = {
        "XAUUSD": {
            "indicators": {
                "atr": {"min_threshold": 1},
                "adx": {"min_threshold": 20},
                "rsi": {"bull_level": 80, "bear_level": 40},
            }
        }
    }
    entry = DummyEntry(rsi=70, atr=5, adx=30)
    result = DayStrategy(custom_cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["flat_zone"]


# ✅ Patch ใหม่: ปิดกรณี rsi=0 → if rsi: เป็น False
def test_day_strategy_rsi_zero_skips_block(cfg):
    entry = DummyEntry(rsi=0, atr=5, adx=30)
    result = DayStrategy(cfg).evaluate(entry)
    assert result["decision"] == "HOLD"
    assert result["reason"] == ["flat_zone"]
