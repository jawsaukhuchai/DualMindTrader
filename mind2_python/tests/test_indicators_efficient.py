import pandas as pd
import numpy as np
import pytest

import mind2_python.indicators_efficient as ind


# ----------------------------
# Helper dataset
# ----------------------------
def make_df(rows=100, seed=42, with_volume=True):
    """สร้าง DataFrame mock สำหรับ indicators"""
    np.random.seed(seed)
    close = np.linspace(100, 120, rows) + np.random.normal(0, 1, rows)
    high = close + np.random.uniform(0.5, 2.0, rows)
    low = close - np.random.uniform(0.5, 2.0, rows)
    data = {
        "open": close - 0.5,
        "high": high,
        "low": low,
        "close": close,
    }
    if with_volume:
        data["tick_volume"] = np.random.randint(100, 1000, rows)
    return pd.DataFrame(data)


# ----------------------------
# ATR
# ----------------------------
def test_compute_atr_last_basic():
    df = make_df()
    atr = ind.compute_atr_last(df, period=14, symbol="XAUUSDc")
    assert isinstance(atr, float)
    assert atr > 0.0


def test_compute_atr_last_short_df():
    df = make_df(rows=5)
    atr = ind.compute_atr_last(df, period=14)
    assert atr == 1.0


def test_compute_atr_last_error(monkeypatch):
    df = make_df()
    # force error inside concat
    monkeypatch.setattr("pandas.concat", lambda *a, **k: (_ for _ in ()).throw(Exception("concat fail")))
    atr = ind.compute_atr_last(df, 14)
    assert atr == 1.0


# ----------------------------
# BOS realtime
# ----------------------------
def test_detect_bos_last_bullish():
    df = make_df(rows=30)
    df.loc[df.index[-1], "close"] = df["high"].iloc[-20:].max() + 1
    assert ind.detect_bos_last(df, swing_bars=20) == "bullish"


def test_detect_bos_last_bearish():
    df = make_df(rows=30)
    df.loc[df.index[-1], "close"] = df["low"].iloc[-20:].min() - 1
    assert ind.detect_bos_last(df, swing_bars=20) == "bearish"


def test_detect_bos_last_neutral():
    df = make_df(rows=30)
    assert ind.detect_bos_last(df, swing_bars=20) == ""


def test_detect_bos_last_short_df():
    df = make_df(rows=5)
    assert ind.detect_bos_last(df, swing_bars=20) == ""


# ----------------------------
# BOS labeling
# ----------------------------
def test_detect_bos_label_assigns_column():
    df = make_df(rows=250)
    out = ind.detect_bos_label(df, past=20, future=20)
    assert "bos_label" in out.columns
    assert len(out) == len(df)


def test_detect_bos_label_error(monkeypatch):
    df = make_df(rows=50)
    monkeypatch.setattr(df, "copy", lambda: (_ for _ in ()).throw(Exception("copy fail")))
    out = ind.detect_bos_label(df, past=20, future=20)
    assert "bos_label" in out.columns
    assert all(out["bos_label"] == "")


# ----------------------------
# add_indicators_last
# ----------------------------
@pytest.mark.parametrize("symbol", ["XAUUSDc", "BTCUSDc", "EURUSDc", None])
def test_add_indicators_last_basic(symbol):
    df = make_df(rows=100)
    out = ind.add_indicators_last(df, symbol=symbol)
    expected_keys = {
        "ema_fast", "ema_slow", "rsi", "macd_main", "macd_signal", "macd_hist",
        "atr", "bb", "stoch_k", "stoch_d", "vwap", "bos", "bos_val",
        "bb_mid", "bb_upper", "bb_lower", "bos_label"
    }
    assert set(out.keys()) == expected_keys
    assert 0 <= out["rsi"] <= 100
    assert isinstance(out["ema_fast"], float)


def test_add_indicators_last_no_volume():
    df = make_df(rows=100, with_volume=False)
    out = ind.add_indicators_last(df)
    assert "vwap" in out


def test_add_indicators_last_with_bos_label():
    df = make_df(rows=100)
    df["bos_label"] = [""] * (len(df) - 1) + ["bullish"]
    out = ind.add_indicators_last(df)
    assert out["bos_label"] in ("", "bullish")


def test_add_indicators_last_error(monkeypatch):
    df = make_df()
    # force error in Series.ewm (used in EMA, RSI, MACD)
    monkeypatch.setattr(pd.Series, "ewm", lambda *a, **k: (_ for _ in ()).throw(Exception("ewm fail")))
    out = ind.add_indicators_last(df)
    assert out == {}
