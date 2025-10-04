import pytest
from datetime import datetime

# ✅ ใช้ import ตาม path จริงในโปรเจกต์
from mind2_python.schema import Indicators, TradeEntry, parse_feed, DecisionReady

@pytest.fixture
def sample_feed():
    return [
        {
            "symbol": "BTCUSDc",
            "bid": 109349.63,
            "ask": 109367.63,
            "spread": 1800.0,
            "filters": {"spread": {"value": 1800.0, "limit": 1000, "pass": False}},
            "timeframes": {
                "M5": {"atr": 125.8, "rsi": 40.0, "ema_fast": 100, "ema_slow": 200},
                "H1": {"atr": 635.2, "rsi": 35.9, "adx": 70.5, "macd_main": -700},
            },
            "timestamp": "2025-09-26T04:35:13.337007Z",
        },
        {
            "symbol": "XAUUSDc",
            "bid": 3745.716,
            "ask": 3745.876,
            "spread": 160.0,
            "filters": {"spread": {"value": 160.0, "limit": 300, "pass": True}},
            "timeframes": {
                "M5": {"atr": 1.92, "rsi": 58.6, "ema_fast": 3744, "ema_slow": 3743},
            },
            "timestamp": "2025-09-26T04:35:13.337007",
        },
    ]

# ------------------------------------------------------------
# Tests: Indicators
# ------------------------------------------------------------
def test_indicators_from_dict():
    d = {"ema_fast": 10, "ema_slow": 20, "rsi": 70, "macd_main": 1.5}
    ind = Indicators.from_dict(d)
    assert ind.ema_fast == 10
    assert ind.ema_slow == 20
    assert ind.rsi == 70
    assert ind.macd_main == 1.5
    assert ind.trend_score == 0.0  # default

# ------------------------------------------------------------
# Tests: TradeEntry
# ------------------------------------------------------------
def test_tradeentry_with_h1_fallback(sample_feed):
    entry = parse_feed([sample_feed[0]])[0]

    # ใช้ H1 fallback
    assert isinstance(entry, TradeEntry)
    assert entry.symbol == "BTCUSDc"
    assert entry.indicators.rsi == 35.9  # จาก H1
    assert entry.volatility["atr_h1"] == pytest.approx(635.2)
    assert entry.volatility["atr_m5"] == pytest.approx(125.8)

    # decision_ready default
    assert isinstance(entry.decision_ready, DecisionReady)
    assert entry.decision_ready.bias == "HOLD"
    assert entry.decision_ready.confidence == 0.0

    # timestamp parse
    dt = entry.dt
    assert isinstance(dt, datetime)
    assert dt.year == 2025

def test_tradeentry_with_m5_fallback(sample_feed):
    entry = parse_feed([sample_feed[1]])[0]

    # ใช้ M5 fallback
    assert entry.indicators.rsi == 58.6
    assert entry.volatility["atr_m5"] == pytest.approx(1.92)
    assert entry.volatility["atr_h1"] == 0.0  # ไม่มี H1

# ------------------------------------------------------------
# Tests: parse_feed wrapper
# ------------------------------------------------------------
def test_parse_feed_dict_mode(sample_feed):
    feed_dict = {"symbols": sample_feed}
    entries = parse_feed(feed_dict)

    assert len(entries) == 2
    symbols = [e.symbol for e in entries]
    assert "BTCUSDc" in symbols and "XAUUSDc" in symbols

def test_parse_feed_skip_invalid():
    feed = [{"not_a_symbol": True}, "string_item"]
    entries = parse_feed(feed)
    assert entries == []

# ------------------------------------------------------------
# Tests: timeframe accessor
# ------------------------------------------------------------
def test_timeframe_accessors(sample_feed):
    entry = parse_feed([sample_feed[0]])[0]
    m5 = entry.m5
    h1 = entry.h1
    assert isinstance(m5, Indicators)
    assert isinstance(h1, Indicators)
    assert m5.atr == pytest.approx(125.8)
    assert h1.atr == pytest.approx(635.2)

# ✅ เพิ่ม coverage ให้ M1, M30, D1
def test_timeframe_accessors_extra(sample_feed):
    entry = parse_feed([sample_feed[0]])[0]

    m1 = entry.m1
    m30 = entry.m30
    d1 = entry.d1

    # ต้องเป็น Indicators เสมอ
    assert isinstance(m1, Indicators)
    assert isinstance(m30, Indicators)
    assert isinstance(d1, Indicators)

    # ตรวจว่า field หลักเป็น numeric (int/float)
    for ind in (m1, m30, d1):
        assert isinstance(ind.atr, (int, float))
        assert isinstance(ind.rsi, (int, float))
        assert isinstance(ind.ema_fast, (int, float))
        assert isinstance(ind.ema_slow, (int, float))

    # ✅ ค่า atr ต้องไม่ติดลบ
    assert m1.atr >= 0
    assert m30.atr >= 0
    assert d1.atr >= 0
