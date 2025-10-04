# tests/test_edge_cases.py
import pytest
import pandas as pd
import numpy as np
import logging
from types import SimpleNamespace
from mind2_python.hybrid_exit import HybridExit
from mind2_python import indicators_efficient as ind
from mind2_python import logger as lg
from mind2_python.lotsizer import LotSizer, AdaptiveLotSizer
from mind2_python.position_manager import PositionManager
from mind2_python import pretty_logger as pl
from mind2_python import schema
from mind2_python.swing import SwingStrategy

# -------------------------------
# HybridExit edge cases
# -------------------------------
def test_hybridexit_invalid_atr_warns(caplog):
    he = HybridExit({"BTC": {"digits": 2}})
    with caplog.at_level(logging.WARNING):
        res = he.calc({"decision": "BUY", "lot": 1}, entry=100, symbol="BTC",
                      atr=0, atr_multi={}, global_exit_cfg={})
    assert "invalid ATR" in caplog.text
    assert res["entries"]

def test_hybridexit_emergency_close_paths():
    he = HybridExit({})
    pos = SimpleNamespace(ticket=1, symbol="BTC", type=0, price_open=100,
                          profit=-1000, volume=1, sl=None, comment="series-2|0.5|0.9")
    assert he.emergency_close_check("BTC", pos, severe_loss_pct=-0.05)

    pos2 = SimpleNamespace(ticket=2, symbol="BTC", type=0, price_open=100,
                           profit=-1, volume=1, sl=None, comment="bad")
    assert he.emergency_close_check("BTC", pos2)

# -------------------------------
# indicators_efficient edge cases
# -------------------------------
def make_df(n=30):
    return pd.DataFrame({
        "high": np.linspace(1, 2, n),
        "low": np.linspace(0.5, 1.5, n),
        "close": np.linspace(0.8, 1.8, n),
        "tick_volume": np.arange(1, n+1)
    })

def test_compute_atr_symbol_thresholds():
    df = make_df(50)
    assert ind.compute_atr_last(df, symbol="XAU") >= 0.1
    assert ind.compute_atr_last(df, symbol="BTC") >= 10.0
    assert ind.compute_atr_last(df, symbol="EURUSD") >= 0.0001

def test_detect_bos_last_short_df_and_exception():
    df = make_df(5)
    assert ind.detect_bos_last(df, swing_bars=20) == ""
    # malformed df
    assert ind.detect_bos_last(None) == ""

def test_add_indicators_last_invalid_df():
    # Missing columns to trigger except
    bad_df = pd.DataFrame({"x": [1,2,3]})
    out = ind.add_indicators_last(bad_df)
    assert out == {}

# -------------------------------
# logger pretty functions
# -------------------------------
def test_logger_pretty_decision_trade_paths(caplog):
    lg.pretty_log_decisionengine("BTC", "BUY", 0.1, 100, exit_levels={
        "sl": 90, "tp": [{"price": 110, "diff": 10, "close_pct": 50}],
        "trailing": {"mult":1.5, "value":5.0}
    }, mode="priority", votes={"a":1}, details={"x":1})
    lg.pretty_log_tradesignal("XAU", "SELL", 0.2, 200, exit_levels={
        "sl": 195, "tps":[{"price":190,"pips":-10,"weight":50}],
        "atr_mult":1.5,"atr":2.0
    }, winprob=55.5)

def test_logger_risk_and_portfolio(caplog):
    lg.pretty_log_risk("BTC", "blocked test")
    lg.pretty_log_portfolio("BTC", 0.1, reason="BLOCKED")
    lg.pretty_log_portfolio("BTC", 0.1, reason="OK")

# -------------------------------
# LotSizer edge cases
# -------------------------------
class DummyEntry:
    def __init__(self, symbol="BTC", global_reversal=True):
        self.symbol = symbol
        self.global_reversal = global_reversal

def test_lotsizer_with_global_reversal(monkeypatch):
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda sym: 5)
    ls = LotSizer(balance=10000)
    entry = DummyEntry()
    lot = ls.compute(entry, {"risk":{"risk_percent":1.0,"min_lot":0.1,"max_lot":1.0}})
    assert lot <= 1.0

def test_adaptivelotsizer_regimes(monkeypatch):
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda sym: 0)
    entry = DummyEntry()
    ls = AdaptiveLotSizer(10000)
    for regime in ["high_vol","low_vol","trend","normal"]:
        lot = ls.compute(entry, {"risk":{"risk_percent":1.0,"min_lot":0.1,"max_lot":1.0}}, regime)
        assert lot > 0

# -------------------------------
# PositionManager edge cases
# -------------------------------
def test_positionmanager_parse_comment_and_summary(monkeypatch):
    comment = "series-2|0.7|0.8"
    conf, wp, idx = PositionManager._parse_comment(comment)
    assert idx==2 and conf==0.7 and wp==0.8

    # invalid comment
    conf, wp, idx = PositionManager._parse_comment("bad")
    assert idx==1

def test_positionmanager_summary_and_open(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: [])
    out = PositionManager.summary()
    assert "total" in out
    out2 = PositionManager.get_open_positions_summary()
    assert isinstance(out2, dict)

# -------------------------------
# PrettyLogger edge cases
# -------------------------------
def test_pretty_logger_tradesignal_and_close():
    pl.pretty_log_tradesignal("BTC","HOLD",0.1,100,reason="test")
    pl.pretty_log_close_position("BTC",1,0.1,100,profit=-10,reason="SEVERE")
    pl.pretty_log_close_position("BTC",2,0.1,100,profit=-5,reason="RETRACE")
    pl.pretty_log_close_position("BTC",3,0.1,100,profit=5,reason="NORMAL")
    pl.pretty_log_auto_update("BTC",1,90,[100],1)
    pl.pretty_log_trailing("BTC",1,90,95)
    pl.pretty_log_positions_summary({"total":1,"symbols":{"BTC":[{"profit":1,"entry_index":1}]}})
    pl.pretty_log_global_entry("BTC","reason",allowed=False)
    pl.pretty_log_global_exit("stoploss",triggered=True)
    pl.pretty_log_execution("BTC","BUY",allowed=False,blocker="risk",reasons="test")
    pl.pretty_log_dashboard(10000,9900,-100,150,0.5,
                            {"BTC":{"decision":"BUY","signal":{"winprob":0.5},"confidence":0.8,"regime":"up",
                                    "votes":{"rule":{"threshold":0.7,"num_entries":2}}}},
                            {},compact=True)

# -------------------------------
# Schema edge cases
# -------------------------------
def test_schema_invalid_item_and_dt():
    feed = [{"bad":"data"}]
    out = schema.parse_feed(feed)
    assert out == []
    te = schema.TradeEntry(symbol="BTC", bid=1, ask=2, spread=0.1,
                           filters={}, timeframes={}, timestamp="bad")
    assert te.dt.year == 1  # datetime.min

# -------------------------------
# Swing edge cases
# -------------------------------
class DummyInd:
    def __init__(self, rsi=70, atr=2, adx=20, macd_hist=1, bos="bullish", bb={"upper":0,"lower":2}):
        self.rsi=rsi; self.atr=atr; self.adx=adx; self.macd_hist=macd_hist; self.bos=bos; self.bb=bb

def test_swing_low_vol_and_weak_trend():
    entry = schema.TradeEntry("BTC",1,2,0.1,{}, {}, "2020-01-01")
    entry.timeframes["H4"]={"atr":0,"adx":0}
    strat = SwingStrategy({"BTC":{"indicators":{"atr":{"min_threshold":1},"adx":{"min_threshold":1}}}})
    res = strat.evaluate(entry)
    assert "low_volatility" in res["reason"] or "weak_trend" in res["reason"]

def test_swing_buy_sell_paths():
    entry = schema.TradeEntry("BTC",1,2,0.1,{}, {}, "2020-01-01")
    entry.timeframes["H4"]={"rsi":80,"atr":2,"adx":20,"macd_hist":1,"bos":"bullish","bb":{"upper":0,"lower":2}}
    strat = SwingStrategy({"BTC":{"indicators":{"atr":{"min_threshold":1},"adx":{"min_threshold":1},
                                              "rsi":{"bull_level":65,"bear_level":35}}}})
    res = strat.evaluate(entry)
    assert res["decision"] in ["BUY","SELL"]
