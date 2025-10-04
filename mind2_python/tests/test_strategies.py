import pytest
from types import SimpleNamespace

from mind2_python.scalp import ScalpStrategy
from mind2_python.day import DayStrategy
from mind2_python.swing import SwingStrategy
from mind2_python.schema import TradeEntry, Indicators


# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture
def scalp_strategy():
    cfg = {
        "EURUSD": {
            "indicators": {
                "atr": {"min_threshold": 0.0001},
                "adx": {"min_threshold": 10},
                "rsi": {"bull_level": 55, "bear_level": 45},
            }
        }
    }
    return ScalpStrategy(cfg)


@pytest.fixture
def day_strategy():
    cfg = {
        "EURUSD": {
            "indicators": {
                "atr": {"min_threshold": 0.0001},
                "adx": {"min_threshold": 10},
                "rsi": {"bull_level": 60, "bear_level": 40},
            }
        }
    }
    return DayStrategy(cfg)


@pytest.fixture
def swing_strategy():
    cfg = {
        "EURUSD": {
            "indicators": {
                "atr": {"min_threshold": 0.0001},
                "adx": {"min_threshold": 10},
                "rsi": {"bull_level": 65, "bear_level": 35},
            }
        }
    }
    return SwingStrategy(cfg)


# -----------------------------
# Helpers
# -----------------------------
def make_entry(symbol="EURUSD", tf="M5", **ind_kwargs):
    indicators = Indicators.from_dict(ind_kwargs)
    return TradeEntry(
        symbol=symbol,
        bid=ind_kwargs.get("bid", 1.2345),
        ask=ind_kwargs.get("ask", 1.2346),
        spread=0.0001,
        filters={},
        timeframes={tf: ind_kwargs},
        timestamp="2025-09-26T00:00:00",
        indicators=indicators,
    )


# -----------------------------
# ScalpStrategy Tests
# -----------------------------
def test_scalp_buy_signal(scalp_strategy):
    entry = make_entry(
        rsi=70, atr=0.001, adx=20, stoch_k=10, stoch_d=5, vwap=2.0, bid=1.0
    )
    res = scalp_strategy.evaluate(entry)
    assert res["decision"] == "BUY"
    assert res["confidence"] > 0


def test_scalp_sell_signal(scalp_strategy):
    entry = make_entry(rsi=30, atr=0.001, adx=20, stoch_k=90, stoch_d=95, vwap=0.5, bid=1.0)
    res = scalp_strategy.evaluate(entry)
    assert res["decision"] == "SELL"
    assert res["confidence"] > 0


def test_scalp_low_volatility(scalp_strategy):
    entry = make_entry(rsi=60, atr=0.0, adx=20)
    res = scalp_strategy.evaluate(entry)
    assert res["decision"] == "HOLD"
    assert "low_volatility" in res["reason"]


# -----------------------------
# DayStrategy Tests
# -----------------------------
def test_day_buy_with_ema_macd(day_strategy):
    entry = make_entry(
        tf="H1",
        rsi=70, atr=0.01, adx=25,
        ema_fast=2.0, ema_slow=1.0,
        macd_hist=0.5, vwap=2.0, bid=1.0
    )
    res = day_strategy.evaluate(entry)
    assert res["decision"] == "BUY"
    assert "ema_uptrend" in res["reason"] or "macd_bull" in res["reason"]


def test_day_sell_with_stoch(day_strategy):
    entry = make_entry(
        tf="H1",
        rsi=20, atr=0.01, adx=25,
        ema_fast=0.5, ema_slow=1.0,
        macd_hist=-0.5,
        stoch_k=85, stoch_d=90,
        vwap=0.5, bid=1.0
    )
    res = day_strategy.evaluate(entry)
    assert res["decision"] == "SELL"
    assert res["confidence"] > 0


def test_day_weak_trend(day_strategy):
    entry = make_entry(tf="H1", rsi=60, atr=0.01, adx=5)
    res = day_strategy.evaluate(entry)
    assert res["decision"] == "HOLD"
    assert "weak_trend" in res["reason"]


# -----------------------------
# SwingStrategy Tests
# -----------------------------
def test_swing_buy_with_bos(swing_strategy):
    entry = make_entry(
        tf="H4",
        rsi=80, atr=1.0, adx=30,
        macd_hist=1.0,
        bos="bullish",
        bb={"upper": 1.0, "lower": 0.5},
        bid=2.0,
    )
    res = swing_strategy.evaluate(entry)
    assert res["decision"] == "BUY"
    assert "bos_confirm" in res["reason"] or "macd_bull" in res["reason"]


def test_swing_sell_with_bb(swing_strategy):
    entry = make_entry(
        tf="H4",
        rsi=20, atr=1.0, adx=30,
        macd_hist=-1.0,
        bos="bearish",
        bb={"upper": 2.0, "lower": 1.0},
        bid=0.5,
    )
    res = swing_strategy.evaluate(entry)
    assert res["decision"] == "SELL"
    assert res["confidence"] > 0


def test_swing_low_volatility(swing_strategy):
    entry = make_entry(tf="H4", rsi=70, atr=0.0, adx=30)
    res = swing_strategy.evaluate(entry)
    assert res["decision"] == "HOLD"
    assert "low_volatility" in res["reason"]
