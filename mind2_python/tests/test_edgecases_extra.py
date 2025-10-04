# tests/test_edgecases_extra.py
import pytest
from types import SimpleNamespace
from datetime import datetime
from mind2_python.hybrid_exit import HybridExit
from mind2_python import logger as lg
from mind2_python.position_manager import PositionManager
from mind2_python import pretty_logger as pl
from mind2_python.risk_guard import RiskGuard
from mind2_python.swing import SwingStrategy
from mind2_python.trailing_manager import TrailingManager


# ---------------- HybridExit scaling ----------------
def test_hybrid_exit_scaling_mode():
    cfg = {
        "XAUUSD": {
            "exit": {"sl_atr": 1.5, "tp_steps": [1, 2], "tp_perc": [50, 50]},
            "digits": 2,
            "pip_size": 0.1,
            "portfolio": {"series_mode": "scaling"},
        }
    }
    hx = HybridExit(cfg)
    decision = {"decision": "BUY", "num_entries": 2, "lot": 1.0}
    exits = hx.calc(decision, entry=2000, symbol="XAUUSD", atr=1.0, atr_multi={}, global_exit_cfg={})
    assert len(exits["entries"]) == 2
    assert exits["entries"][1]["lot"] != exits["entries"][2]["lot"]


# ---------------- Logger pretty_log_decisionengine else branch ----------------
def test_logger_pretty_log_decisionengine_no_exit_levels():
    lg.pretty_log_decisionengine("XAUUSD", "BUY", 0.1, 2000, exit_levels=None, reason="NO_EXIT")


# ---------------- PositionManager edge branches ----------------
def test_position_manager_parse_comment_exception():
    assert PositionManager._parse_comment("series-abc|bad|data") == (0.0, 0.0, 1)

def test_position_manager_summary_no_positions(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: [])
    s = PositionManager.summary()
    assert s == {"total": 0, "symbols": {}}

def test_position_manager_get_open_positions_fallback(monkeypatch):
    cls = PositionManager
    monkeypatch.setattr(cls, "get_positions", lambda symbol=None: None)
    inst = cls._instance()
    inst.state["positions"]["XAUUSD"] = [{"ticket": 1, "symbol": "XAUUSD"}]
    res = cls.get_open_positions("XAUUSD")
    assert isinstance(res, list)

def test_position_manager_parse_comment_empty_parts():
    assert PositionManager._parse_comment("series-") == (0.0, 0.0, 1)

def test_position_manager_open_position_with_extra():
    pm = PositionManager()
    pos = pm.open_position("XAUUSD",0.1,"BUY",2000,extra={"custom":"yes"})
    assert "custom" in pos


# ---------------- PrettyLogger missing branches ----------------
def test_pretty_log_tradesignal_with_trailing_and_hold():
    pl.pretty_log_tradesignal("XAUUSD", "HOLD", 0.1, 2000, reason="flat")
    pl.pretty_log_tradesignal(
        "XAUUSD", "BUY", 0.1, 2000,
        exit_levels={
            "sl": 1990,
            "tp": [{"price": 2010, "perc": 50}],
            "trailing": {"mult": 1.5, "distance": 0.002},
            "atr_used": 0.002,
            "atr_mode": "strict"
        },
        ai_res={"decision":"BUY","confidence":0.8},
        rule_res={"decision":"BUY","confidence":0.9,"threshold":0.5,"num_entries":1},
        fusion={"decision":"BUY","score":0.7}
    )


# ---------------- RiskGuard exit branch ----------------
def test_risk_guard_exit_branch(monkeypatch):
    rg = RiskGuard({"symbols": {"XAUUSD": {"risk": {}}}})
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda sym: 0)
    import sys
    def fake_check(*a, **k): sys.exit(1)
    rg.check = fake_check
    with pytest.raises(SystemExit):
        rg.allow(SimpleNamespace(symbol="XAUUSD"), {"decision": "BUY"})

def test_riskguard_record_trade_negative_pnl():
    rg = RiskGuard({})
    rg.record_trade("XAUUSD", -10)
    assert "XAUUSD" in rg.state["last_sl_hit"]


# ---------------- SwingStrategy ----------------
class DummyInd: pass

def test_swing_strategy_bb_breakout():
    cfg = {"XAUUSD": {"indicators": {"atr": {"min_threshold": 1}, "adx": {"min_threshold": 1}, "rsi": {"bull_level": 60, "bear_level": 40}}}}
    s = SwingStrategy(cfg)
    ind = DummyInd()
    ind.rsi = 70
    ind.atr = 2
    ind.adx = 2
    ind.macd_hist = 1
    ind.bos = "bullish"
    ind.bb = {"upper": 1990, "lower": 2010}
    entry = SimpleNamespace(symbol="XAUUSD", bid=2020, h4=ind, d1=None)
    res = s.evaluate(entry)
    assert "bb_breakout_up" in res["reason"]

def test_swing_strategy_hold_case():
    s = SwingStrategy({"XAUUSD":{"indicators":{"atr":{"min_threshold":1},"adx":{"min_threshold":1},"rsi":{"bull_level":70,"bear_level":30}}}})
    ind = DummyInd()
    ind.rsi=50; ind.atr=2; ind.adx=2; ind.macd_hist=None; ind.bos=None; ind.bb=None
    entry = SimpleNamespace(symbol="XAUUSD", bid=2000, h4=ind, d1=None)
    res = s.evaluate(entry)
    assert res["decision"]=="HOLD"


# ---------------- TrailingManager ----------------
def test_trailing_manager_loop_triggers_emergency(monkeypatch):
    cfg={"symbols":{"XAUUSD":{"pip_size":0.1}}}
    tm=TrailingManager(cfg)
    pos=SimpleNamespace(ticket=1, sl=None, profit=-100, volume=1.0, price_open=1000, comment="")
    monkeypatch.setattr("mind2_python.trailing_manager.PositionManager.get_open_positions", lambda sym:[pos])
    monkeypatch.setattr("mind2_python.trailing_manager.mt5.symbol_info_tick", lambda sym: None)
    monkeypatch.setattr(HybridExit, "recalc_for_open_positions", lambda self, **k: {})
    tm.loop_trailing()

def test_trailing_manager_adjust_trailing_profit_not_positive():
    hx = HybridExit({})
    sl = hx.adjust_trailing(current_price=2000, side="BUY", entry=2000, sl=None, trailing_cfg={"atr_mult":1.5}, pip_size=0.1)
    sl2 = hx.adjust_trailing(current_price=2000, side="SELL", entry=2000, sl=None, trailing_cfg={"atr_mult":1.5}, pip_size=0.1)
    assert sl is None or sl==None
    assert sl2 is None or sl2==None
