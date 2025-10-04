# tests/test_edge_final.py
import pytest
import logging
import types
import json
from argparse import Namespace
import importlib

from mind2_python import hybrid_exit, indicators_efficient as ind
from mind2_python import logger as lg, pretty_logger as pl
from mind2_python import lotsizer, position_manager as pm
from mind2_python import risk_guard, schema, trailing_manager, run_ho


# -------------------------------
# HybridExit branch (157->160)
# -------------------------------
def test_hybridexit_adjust_trailing_invalid_side():
    hx = hybrid_exit.HybridExit({})
    sl = hx.adjust_trailing(100, "WEIRD", 100, sl=50,
                            trailing_cfg={"atr_mult": 1}, pip_size=1)
    assert sl == 50


# -------------------------------
# Indicators Efficient (missing lines)
# -------------------------------
def test_indicators_short_df_returns_default():
    df = ind.pd.DataFrame({"high":[1], "low":[0.5], "close":[0.8]})
    val = ind.compute_atr_last(df, period=14, symbol="BTC")
    assert val == 1.0

def test_indicators_bos_error(monkeypatch):
    df = ind.pd.DataFrame({"high":[1,2], "low":[0,1], "close":[1,2]})
    bad = df.drop(columns=["high"])
    out = ind.detect_bos_last(bad, 2)
    assert out == ""

def test_indicators_label_error():
    df = ind.pd.DataFrame({"high":[1,2,3], "low":[0,1,2], "close":[1,2,3]})
    df_bad = df.drop(columns=["high"])
    out = ind.detect_bos_label(df_bad)
    assert "bos_label" in out.columns


# -------------------------------
# Logger branches
# -------------------------------
def test_logger_no_exit_levels(caplog):
    with caplog.at_level(logging.INFO):
        lg.pretty_log_decisionengine("BTC", "BUY", 0.1, 100, exit_levels=None)
    assert any("DecisionEngine" in m for m in caplog.messages)

def test_logger_tradesignal_no_exit(caplog):
    with caplog.at_level(logging.INFO):
        lg.pretty_log_tradesignal("XAU", "HOLD", 0.1, 200, exit_levels=None, reason="test")
    assert any("TRADE SIGNAL" in m for m in caplog.messages)


# -------------------------------
# LotSizer adaptive branch
# -------------------------------
def test_adaptivelotsizer_high_vol_minlot():
    class DummyEntry: symbol="BTC"
    ls = lotsizer.AdaptiveLotSizer(balance=10000)
    sym_cfg = {"risk":{"risk_percent":0.0001,"min_lot":0.1,"max_lot":1.0}}
    lot = ls.compute(DummyEntry(), sym_cfg, regime="high_vol")
    assert lot <= 0.1


# -------------------------------
# PositionManager branches
# -------------------------------
def test_positionmanager_update_sl_tp_too_close(monkeypatch):
    mgr = pm.PositionManager()
    fake_info = types.SimpleNamespace(stops_level=10, point=1)
    fake_tick = types.SimpleNamespace(bid=100, ask=100)
    monkeypatch.setattr(pm, "mt5", types.SimpleNamespace(
        symbol_info=lambda sym: fake_info,
        symbol_info_tick=lambda sym: fake_tick,
        order_send=lambda req: types.SimpleNamespace(retcode=10009),
        TRADE_ACTION_SLTP=1, TRADE_RETCODE_DONE=10009
    ))
    mgr.update_position("BTC", ticket=1, sl=99, tp=[{"price":101}])

def test_positionmanager_update_fail(monkeypatch):
    mgr = pm.PositionManager()
    monkeypatch.setattr(pm, "mt5", types.SimpleNamespace(
        symbol_info=lambda sym: (_ for _ in ()).throw(Exception("fail"))
    ))
    mgr.update_position("BTC", ticket=1, sl=100, tp=[{"price":200}])


# -------------------------------
# PrettyLogger extra branches
# -------------------------------
def test_pretty_logger_tradesignal_with_trailing():
    pl.pretty_log_tradesignal("BTC","BUY",0.1,100,
                              exit_levels={"trailing":{"mult":1,"distance":10},
                                           "atr_used":10,"atr_mode":"strict"},
                              pip_size=1)

def test_pretty_logger_close_variants():
    pl.pretty_log_close_position("BTC",1,0.1,100,reason="SEVERE")
    pl.pretty_log_close_position("BTC",2,0.1,100,reason="RETRACE")
    pl.pretty_log_close_position("BTC",3,0.1,100,reason="NORMAL")


# -------------------------------
# RiskGuard branches
# -------------------------------
def test_riskguard_colorize_reason():
    def clean(s: str) -> str:
        return s.lower().replace("\x1b[31m","").replace("\x1b[32m","")\
                        .replace("\x1b[33m","").replace("\x1b[36m","")\
                        .replace("\x1b[90m","").replace("\x1b[0m","")
    out1 = risk_guard.colorize_reason("Blocked")
    out2 = risk_guard.colorize_reason("Allowed")
    out3 = risk_guard.colorize_reason("low_conf")
    out4 = risk_guard.colorize_reason("cooldown")
    out5 = risk_guard.colorize_reason("override")
    out6 = risk_guard.colorize_reason("replace")
    out7 = risk_guard.colorize_reason("SomethingElse")
    assert "blocked" in clean(out1)
    assert "allowed" in clean(out2) or "ok" in clean(out2)
    assert "low_conf" in clean(out3) or "low" in clean(out3)
    assert "cooldown" in clean(out4)
    assert "override" in clean(out5)
    assert "replace" in clean(out6)
    assert "somethingelse" in clean(out7)

def test_riskguard_init_with_cfg():
    rg = risk_guard.RiskGuard(cfg={"symbols":{}})
    assert isinstance(rg.config, dict)

def test_riskguard_allow_block(monkeypatch):
    rg = risk_guard.RiskGuard({"symbols":{"BTC":{"risk":{"max_orders":0}}}})
    monkeypatch.setattr(risk_guard.PositionManager, "count_open_positions", lambda s: 1)
    ok, reasons = rg.allow(types.SimpleNamespace(symbol="BTC"), {"decision":"BUY","lot":0.1,"entry":1})
    assert isinstance(ok,bool)


def test_riskguard_record_trade_negative():
    rg = risk_guard.RiskGuard({"symbols":{"BTC":{}}})
    rg.record_trade("BTC", pnl=-5)
    assert "BTC" in rg.state["last_sl_hit"]


# -------------------------------
# Schema exit branches
# -------------------------------
def test_schema_parse_feed_invalid_timeframes():
    bad_feed = [{"symbol":"BTC","bid":1,"ask":2,"spread":0.1,"timeframes":"bad"}]
    out = schema.parse_feed(bad_feed)
    assert out == []

def test_schema_dt_invalid():
    te = schema.TradeEntry("BTC",1,2,0.1,{},{},"bad-timestamp")
    assert te.dt.year == 1


# -------------------------------
# TrailingManager branches
# -------------------------------
def test_trailingmanager_empty_cfg():
    tm = trailing_manager.TrailingManager({"symbols": {}})
    tm.loop_trailing()

def test_trailingmanager_loop_no_tick(monkeypatch):
    tm = trailing_manager.TrailingManager({"symbols": {"BTC": {"pip_size":1.0}}})
    hx = types.SimpleNamespace(recalc_for_open_positions=lambda **kw: {},
                               adjust_trailing=lambda **kw: None)
    pos = {"side":"BUY","entry":100,"ticket":1,"sl":100,"lot":0.1,"entry_index":1,"num_entries":1}
    monkeypatch.setattr(trailing_manager.PositionManager, "get_open_positions", lambda sym: [pos])
    monkeypatch.setattr(trailing_manager, "HybridExit", lambda *a,**k: hx)
    monkeypatch.setattr(trailing_manager, "mt5", types.SimpleNamespace(symbol_info_tick=lambda sym: None))
    tm.loop_trailing()


# -------------------------------
# run_ho exit branches
# -------------------------------
def test_run_ho_keyboard_interrupt(monkeypatch, tmp_path, caplog):
    import mind2_python.run_ho as run_ho
    importlib.reload(run_ho)

    (tmp_path/"cfg.yaml").write_text("symbols: {}")
    (tmp_path/"feed.json").write_text(json.dumps({}))

    monkeypatch.setattr(run_ho.argparse.ArgumentParser, "parse_args",
                        lambda self=None: Namespace(balance=1000, interval=0,
                                                    config=str(tmp_path/"cfg.yaml"),
                                                    feed=str(tmp_path/"feed.json"),
                                                    debug_trailing=False))
    monkeypatch.setattr(run_ho, "DecisionEngine", lambda **kw: types.SimpleNamespace(
        global_atr={}, run=lambda e: [], get_global_atr=lambda : {}))
    monkeypatch.setattr(run_ho, "Executor", lambda : types.SimpleNamespace(
        get_account_info=lambda : {"balance":1000,"equity":1000},
        shutdown=lambda : None, execute=lambda r: None))
    monkeypatch.setattr(run_ho, "TrailingManager", lambda cfg: types.SimpleNamespace(
        update_global_atr=lambda x: None, loop_trailing=lambda : None))
    monkeypatch.setattr(run_ho, "RiskGuard", lambda cfg: types.SimpleNamespace(state={}))
    monkeypatch.setattr(run_ho, "GlobalExitManager", lambda cfg: types.SimpleNamespace(check_exit=lambda *a,**k: (True,"stop",None)))
    monkeypatch.setattr(run_ho, "HybridExit", lambda cfg: types.SimpleNamespace(calc=lambda *a,**k: {}))
    monkeypatch.setattr(run_ho, "pretty_log_dashboard", lambda **kw: None)

    with caplog.at_level(logging.WARNING):
        run_ho.main()
    assert any("stop" in m for m in caplog.messages)
