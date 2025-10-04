import pytest
from mind2_python.schema import TradeEntry, Indicators, parse_feed
from mind2_python.day import DayStrategy
from mind2_python.scalp import ScalpStrategy
from mind2_python.swing import SwingStrategy
from mind2_python.global_manager import GlobalEntryManager, GlobalPnLGuard, GlobalExitManager, KillSwitchManager, log_global_dashboard
import mind2_python.safe_print as safe_print
import mind2_python.pretty_logger as pretty_logger
from mind2_python.regime_detector import RegimeDetector


@pytest.fixture
def dummy_entry():
    tf = {
        "H1": {"rsi": 70, "atr": 5.0, "adx": 25, "ema_fast": 110, "ema_slow": 100, "macd_hist": 1.0},
        "M5": {"rsi": 55, "atr": 2.0, "adx": 20, "stoch_k": 10, "stoch_d": 5, "vwap": 120},
        "H4": {"rsi": 30, "atr": 5.0, "adx": 20, "macd_hist": -1.0, "bos": "bearish",
               "bb": {"upper": 150, "lower": 90}},
    }
    return TradeEntry(
        symbol="TEST",
        bid=100,
        ask=101,
        spread=1,
        filters={},
        timeframes=tf,
        timestamp="2025-09-26T04:35:13.337007",
        indicators=Indicators.from_dict(tf["H1"]),
    )

# ------------------------------------------------------------
# Strategies
# ------------------------------------------------------------
def test_day_strategy(dummy_entry):
    strat = DayStrategy({"TEST": {"indicators": {"atr": {"min_threshold": 1}, "adx": {"min_threshold": 10}}}})
    res = strat.evaluate(dummy_entry)
    assert res["decision"] in ["BUY", "SELL", "HOLD"]

def test_scalp_strategy(dummy_entry):
    strat = ScalpStrategy({"TEST": {"indicators": {"atr": {"min_threshold": 1}, "adx": {"min_threshold": 10}}}})
    res = strat.evaluate(dummy_entry)
    assert res["decision"] in ["BUY", "SELL", "HOLD"]

def test_swing_strategy(dummy_entry):
    strat = SwingStrategy({"TEST": {"indicators": {"atr": {"min_threshold": 1}, "adx": {"min_threshold": 10}}}})
    res = strat.evaluate(dummy_entry)
    assert res["decision"] in ["BUY", "SELL", "HOLD"]

# ------------------------------------------------------------
# Global Manager
# ------------------------------------------------------------
def test_global_entry_manager_allows():
    mgr = GlobalEntryManager({"global": {"min_equity_pct": 50}})
    ok, reasons = mgr.check({"balance": 1000, "equity": 800}, {})
    assert ok is True
    assert "equity_ok" in reasons

def test_global_pnl_guard_blocks():
    guard = GlobalPnLGuard({"global": {"max_daily_loss_abs": 10}})
    blocked, reason = guard.check(1000, daily_loss=-20)
    assert blocked is True
    assert "abs" in reason

def test_global_exit_manager_equity_low():
    mgr = GlobalExitManager({"global": {"min_equity_pct": 90}})
    blocked, reason, reasons = mgr.check_exit({"balance": 1000, "equity": 800})
    assert blocked is True
    assert "equity_low" in reason

def test_killswitch_triggers():
    ks = KillSwitchManager({"global": {"killswitch_dd_limit_pct": 5}})
    # add history of high equity then drop
    ks.check(1000, now=1.0)
    stop, reason = ks.check(900, now=2.0)
    assert stop is True
    assert "killswitch" in reason

def test_log_global_dashboard(capsys):
    log_global_dashboard({"balance": 1000, "equity": 1000}, {"symbol":"BTCUSDc","lots_local":1,"positions_feed":2})
    out, _ = capsys.readouterr()
    assert "Dashboard" in out

# ------------------------------------------------------------
# Schema quick-win
# ------------------------------------------------------------
def test_parse_feed_invalid_item(caplog):
    caplog.set_level("WARNING")
    feed = ["not_a_dict"]
    result = parse_feed(feed)
    assert result == []
    assert "Skip invalid item" in caplog.text

def test_tradeentry_invalid_timestamp():
    entry = TradeEntry("XAUUSDc",1.0,2.0,0.1,{},{},"bad-ts")
    assert entry.dt.year == 1

# ------------------------------------------------------------
# Pretty Logger
# ------------------------------------------------------------
def test_pretty_logger_tradesignal(capsys):
    pretty_logger.pretty_log_tradesignal("TEST","BUY",lot=0.1,entry=100,
        exit_levels={"sl":95,"tp":[{"price":110}]},conf_raw=0.7,winprob_raw=0.5,score_raw=0.3,reason="ok")
    out, _ = capsys.readouterr()
    assert "TRADE SIGNAL" in out

def test_pretty_logger_close(capsys):
    pretty_logger.pretty_log_close_position("TEST",1,0.1,100,conf=0.5,winprob=0.6,profit=10,reason="NORMAL")
    out, _ = capsys.readouterr()
    assert "CLOSE" in out

# ------------------------------------------------------------
# Regime Detector
# ------------------------------------------------------------
def test_regime_detector_predict_trend():
    det = RegimeDetector()
    res = det.predict({"atr":2.0,"atr_ma":1.0,"adx":30})
    assert res["regime"] in ["trend","range","high_vol","low_vol"]

# ------------------------------------------------------------
# Safe Print
# ------------------------------------------------------------
def test_safe_print_handles_none(capsys):
    safe_print.safe_print(None)
    out, _ = capsys.readouterr()
    assert "None" in out

def test_safe_print_unicode(capsys):
    safe_print.safe_print("ทดสอบ")
    out, _ = capsys.readouterr()
    assert "ทดสอบ" in out
