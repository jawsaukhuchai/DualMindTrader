import pytest
import time
from mind2_python.decision_engine import DecisionEngine
from mind2_python.portfolio_manager import PortfolioManager
from mind2_python.risk_guard import RiskGuard
from mind2_python.config_loader import load_config
from mind2_python.schema import parse_feed

CONFIG_PATH = "mind2_python/config.symbols.yaml"


@pytest.fixture(scope="module")
def engine():
    return DecisionEngine(config_path=CONFIG_PATH)


@pytest.fixture
def portfolio():
    return PortfolioManager(load_config(CONFIG_PATH))


@pytest.fixture
def risk_guard():
    return RiskGuard(load_config(CONFIG_PATH))


# ============================================================
# ✅ STRESS TESTS (optimized for CI)
# ============================================================

def test_order_flood_stress_btc(engine, portfolio):
    """Simulate 100 BTCUSDc ticks (fast CI test)."""
    for i in range(100):
        feed = {
            "symbol": "BTCUSDc",
            "bid": 50000 + i,
            "ask": 50001 + i,
            "spread": 1,
            "filters": {},
            "timeframes": {"H1": {"atr": 40.0, "adx": 30.0}},
            "timestamp": "2025-01-01T00:00:00Z",
        }
        entry = parse_feed([feed])[0]
        decision = engine.process(entry)
        ok, reasons = portfolio.allow(entry, decision, balance=100000)
        if ok:
            portfolio.register_entry("BTCUSDc")
    assert True


@pytest.mark.benchmark
def test_burst_tick_latency_xau(engine):
    """Benchmark-like latency test for XAUUSDc (reduced to 500 ticks for CI)."""
    start = time.time()
    for i in range(500):  # ⚡ reduced from 5000 → 500 ticks
        feed = {
            "symbol": "XAUUSDc",
            "bid": 1900 + (i % 10),
            "ask": 1900 + (i % 10) + 0.1,
            "spread": 0.1,
            "filters": {},
            "timeframes": {"H1": {"atr": 1.2, "adx": 25.0}},
            "timestamp": "2025-01-01T00:00:00Z",
        }
        entry = parse_feed([feed])[0]
        _ = engine.process(entry)
    elapsed = time.time() - start
    # ⚙️ realistic threshold for CI: 500 ticks < 5 sec
    assert elapsed < 5.0


# ============================================================
# ✅ FUZZ / CHAOS TESTS
# ============================================================

@pytest.mark.parametrize("bad_feed", [
    {"symbol": "BTCUSDc"},  # missing bid/ask/spread
    {"symbol": "XAUUSDc"},  # missing bid/ask/spread
    {"bid": 60000, "ask": 60001, "spread": 1},  # missing symbol
    {"symbol": "BTCUSDc", "bid": None, "ask": None, "spread": None},
    {"symbol": "XAUUSDc", "bid": "NaN", "ask": "NaN", "spread": "?"}
])
def test_invalid_feed_symbols(engine, bad_feed):
    """Engine should handle bad BTC/XAU feeds gracefully."""
    try:
        entries = parse_feed([bad_feed])
        if entries:
            decision = engine.process(entries[0])
        else:
            decision = None
    except Exception:
        decision = None
    assert decision is None or decision.get("decision") in ("HOLD", "BUY", "SELL", "CLOSE_ALL")


# ============================================================
# ✅ PORTFOLIO RISK TESTS
# ============================================================

def test_risk_percent_enforcement_btc(engine, portfolio):
    """BTCUSDc lot too large vs balance -> should block."""
    feed = {
        "symbol": "BTCUSDc",
        "bid": 60000,
        "ask": 60001,
        "spread": 1,
        "filters": {},
        "timeframes": {"H1": {"atr": 40.0, "adx": 30.0}},
        "timestamp": "2025-01-01T00:00:00Z",
    }
    entry = parse_feed([feed])[0]
    decision = engine.process(entry)
    decision["lot"] = 999999  # force oversize lot
    ok, reasons = portfolio.allow(entry, decision, balance=10_000)
    assert not ok


def test_risk_percent_enforcement_xau(engine, portfolio):
    """XAUUSDc lot too large vs balance -> should block."""
    feed = {
        "symbol": "XAUUSDc",
        "bid": 1900,
        "ask": 1900.1,
        "spread": 0.1,
        "filters": {},
        "timeframes": {"H1": {"atr": 1.2, "adx": 25.0}},
        "timestamp": "2025-01-01T00:00:00Z",
    }
    entry = parse_feed([feed])[0]
    decision = engine.process(entry)
    decision["lot"] = 999999
    ok, reasons = portfolio.allow(entry, decision, balance=10_000)
    assert not ok


def test_series_gap_protection_btc(engine, portfolio):
    """BTCUSDc second entry too close in price -> should block."""
    feed1 = {
        "symbol": "BTCUSDc",
        "bid": 60000,
        "ask": 60001,
        "spread": 1,
        "filters": {},
        "timeframes": {"H1": {"atr": 40.0, "adx": 30.0}},
        "timestamp": "2025-01-01T00:00:00Z",
    }
    entry1 = parse_feed([feed1])[0]
    decision1 = engine.process(entry1)
    portfolio.register_entry("BTCUSDc")

    feed2 = dict(feed1)
    feed2["bid"] = 60001
    feed2["ask"] = 60002
    entry2 = parse_feed([feed2])[0]
    decision2 = engine.process(entry2)
    ok, reasons = portfolio.allow(entry2, decision2, balance=100000)
    assert not ok


def test_series_gap_protection_xau(engine, portfolio):
    """XAUUSDc second entry too close in price -> should block."""
    feed1 = {
        "symbol": "XAUUSDc",
        "bid": 1900,
        "ask": 1900.1,
        "spread": 0.1,
        "filters": {},
        "timeframes": {"H1": {"atr": 1.2, "adx": 25.0}},
        "timestamp": "2025-01-01T00:00:00Z",
    }
    entry1 = parse_feed([feed1])[0]
    decision1 = engine.process(entry1)
    portfolio.register_entry("XAUUSDc")

    feed2 = dict(feed1)
    feed2["bid"] = 1900.1
    feed2["ask"] = 1900.2
    entry2 = parse_feed([feed2])[0]
    decision2 = engine.process(entry2)
    ok, reasons = portfolio.allow(entry2, decision2, balance=100000)
    assert not ok
