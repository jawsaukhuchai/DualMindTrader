# tests/test_edge_final2.py
import pytest
import logging
import types
from mind2_python import hybrid_exit, indicators_efficient as ind
from mind2_python import logger as lg, pretty_logger as pl
from mind2_python import lotsizer, position_manager as pm
from mind2_python import risk_guard, schema, swing, trailing_manager

# -------------------------------
# HybridExit (sl_price < min_sl)
# -------------------------------
def test_hybridexit_sl_price_adjust(monkeypatch):
    hx = hybrid_exit.HybridExit({"BTC": {"digits": 2}})
    pos = types.SimpleNamespace(
        ticket=1, type=0, price_open=100, comment="series-1|", sl=None
    )
    monkeypatch.setattr(hybrid_exit.mt5, "positions_get", lambda symbol=None: [pos])
    monkeypatch.setattr(hybrid_exit.mt5, "symbol_info", lambda sym: types.SimpleNamespace(stops_level=5))
    res = hx.recalc_for_open_positions("BTC", atr=1.0, atr_multi={}, global_exit_cfg={})
    assert isinstance(res, dict)


# -------------------------------
# Indicators Efficient (EURUSD + bullish label)
# -------------------------------
def test_indicators_eurusd_threshold():
    import pandas as pd, numpy as np
    df = pd.DataFrame({
        "high": np.linspace(1, 2, 30),
        "low": np.linspace(0.5, 1.5, 30),
        "close": np.linspace(1.0, 2.0, 30),
    })
    val = ind.compute_atr_last(df, period=14, symbol="EURUSD")
    assert val >= 0.0001

def test_indicators_bos_label_bullish():
    import pandas as pd
    df = pd.DataFrame({
        "high": [1,2,3,4,5,6],
        "low": [0,1,1,1,1,1],
        "close": [10,10,10,10,10,10],  # force bullish
    })
    out = ind.detect_bos_label(df, past=2, future=2)
    assert "bos_label" in out.columns
    assert any(lbl == "bullish" for lbl in out["bos_label"])


# -------------------------------
# Logger (filename + atr_mult branch)
# -------------------------------
def test_logger_get_logger_with_file(tmp_path):
    log_file = tmp_path / "test.log"
    lg.get_logger("X", filename=str(log_file))
    assert log_file.exists()

def test_logger_tradesignal_with_atr_mult(caplog):
    with caplog.at_level(logging.INFO):
        lg.pretty_log_tradesignal("BTC","BUY",0.1,100,
                                  exit_levels={"atr_mult":1.5,"atr":2.0})
    assert any("ATR×" in m for m in caplog.messages)


# -------------------------------
# Lotsizer exception path (Adaptive)
# -------------------------------
def test_adaptivelotsizer_exception():
    class BadEntry: 
        @property
        def symbol(self): raise Exception("boom")
    ls = lotsizer.AdaptiveLotSizer()
    lot = ls.compute(BadEntry(), {"risk":{"risk_percent":1.0}}, regime="trend")
    assert isinstance(lot, float)


# -------------------------------
# PositionManager fallbacks
# -------------------------------
def test_positionmanager_get_open_positions_fallback(monkeypatch):
    inst = pm.PositionManager._instance()
    inst.state["positions"]["BTC"] = [{"ticket":1,"symbol":"BTC","volume":0.1,
                                       "type":0,"price_open":100,"profit":0.0}]
    monkeypatch.setattr(pm, "mt5", types.SimpleNamespace(positions_get=lambda **kw: (_ for _ in ()).throw(Exception("fail"))))
    out = pm.PositionManager.get_open_positions("BTC")
    assert isinstance(out, list)

def test_positionmanager_summary_empty(monkeypatch):
    monkeypatch.setattr(pm.PositionManager, "get_positions", lambda symbol=None: [])
    out = pm.PositionManager.summary()
    assert out["total"] == 0


# -------------------------------
# PrettyLogger complex branches
# -------------------------------
def test_pretty_logger_tradesignal_ai_rule_fusion():
    pl.pretty_log_tradesignal("BTC","BUY",0.1,100,
        exit_levels={"tp":[{"price":110,"perc":40,"raw_pips":10}]},
        ai_res={"decision":"BUY","confidence":0.9},
        rule_res={"decision":"BUY","confidence":0.8,"threshold":0.7,"num_entries":2},
        fusion={"decision":"BUY","score":0.5},
        pip_size=1, winprob_raw=0.6, score_raw=0.5, conf_raw=0.7)

def test_pretty_logger_tradesignal_hold_branch():
    pl.pretty_log_tradesignal("BTC","HOLD",0.1,100,reason="blocked")


# -------------------------------
# RiskGuard exit branch (record_trade with pnl<0)
# -------------------------------
def test_riskguard_record_trade_exit():
    rg = risk_guard.RiskGuard({"symbols":{"BTC":{}}})
    rg.record_trade("BTC", pnl=-100)
    assert rg.state["daily_loss"] < 0


# -------------------------------
# Schema tf() exit branches
# -------------------------------
def test_schema_tf_invalid_key():
    te = schema.TradeEntry("BTC",1,2,0.1,{},{},"2020-01-01")
    indc = te.tf("ZZZ")
    assert isinstance(indc, schema.Indicators)


# -------------------------------
# Swing decision branch (BUY/SELL)
# -------------------------------
def test_swing_buy_branch():
    entry = schema.TradeEntry("BTC",1,2,0.1,{}, {}, "2020-01-01")
    entry.timeframes["H4"] = {"rsi":80,"atr":10,"adx":30,"macd_hist":1,"bos":"bullish",
                              "bb":{"upper":0,"lower":2}}
    strat = swing.SwingStrategy({"BTC":{"indicators":{"atr":{"min_threshold":1},
                                                     "adx":{"min_threshold":1},
                                                     "rsi":{"bull_level":70,"bear_level":30}}}})
    res = strat.evaluate(entry)
    assert res["decision"] in ["BUY","SELL"]


# -------------------------------
# TrailingManager branches
# -------------------------------
def test_trailingmanager_line19_empty_cfg():
    tm = trailing_manager.TrailingManager({"symbols": {}})
    tm.loop_trailing()

def test_trailingmanager_no_tick_continue(monkeypatch):
    tm = trailing_manager.TrailingManager({"symbols": {"BTC": {"pip_size":1.0}}})
    hx = types.SimpleNamespace(recalc_for_open_positions=lambda **kw: {},
                               adjust_trailing=lambda **kw: None)
    pos = {"side":"BUY","entry":100,"ticket":1,"sl":100,"lot":0.1,"entry_index":1,"num_entries":1}
    monkeypatch.setattr(trailing_manager.PositionManager, "get_open_positions", lambda sym: [pos])
    monkeypatch.setattr(trailing_manager, "HybridExit", lambda *a,**k: hx)
    monkeypatch.setattr(trailing_manager, "mt5", types.SimpleNamespace(symbol_info_tick=lambda sym: None))
    tm.loop_trailing()
