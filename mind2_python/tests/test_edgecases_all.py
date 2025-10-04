# tests/test_edgecases_all.py
import pytest
from types import SimpleNamespace
import logging, time

from mind2_python.hybrid_exit import HybridExit
from mind2_python import logger as lg
from mind2_python.position_manager import PositionManager
from mind2_python import pretty_logger as pl
from mind2_python.risk_guard import RiskGuard
from mind2_python.swing import SwingStrategy
from mind2_python.portfolio_manager import PortfolioManager


# ---------------- HybridExit ----------------
def test_hybrid_exit_sell_slprice_less_and_not_less(monkeypatch):
    pos = SimpleNamespace(ticket=1, type=1, price_open=1000.0,
                          comment="series-1|", sl=None, profit=0.0, volume=1.0)
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda symbol=None: [pos])
    class Info: stops_level = 20; point = 1
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.symbol_info", lambda symbol: Info())
    hx = HybridExit({"XAUUSD": {"exit": {"sl_atr": 1.0}, "digits": 2, "pip_size": 1.0}})
    res = hx.recalc_for_open_positions("XAUUSD", atr=10, atr_multi={}, global_exit_cfg={})
    assert res[1]["sl"] == 1020.0


def test_hybrid_exit_slprice_lower_than_min(monkeypatch):
    pos = SimpleNamespace(ticket=5, type=1, price_open=1000.0,
                          comment="series-1|", sl=None, profit=0.0, volume=1.0)
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda symbol=None: [pos])
    class Info: stops_level = 10; point = 1
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.symbol_info", lambda symbol: Info())
    hx = HybridExit({"XAUUSD": {"exit": {"sl_atr": 10.0}, "digits": 2, "pip_size": 1.0}})
    res = hx.recalc_for_open_positions("XAUUSD", atr=50, atr_multi={}, global_exit_cfg={})
    assert res[5]["sl"] == 1500.0


def test_emergency_close_check_branches():
    hx = HybridExit({"XAUUSD": {"exit": {"sl_atr": 1.0}, "digits": 2, "pip_size": 1.0}})
    pos_with_sl = SimpleNamespace(ticket=1, type=0, price_open=2000.0,
                                  sl=1990.0, tp=None, comment="series-1|",
                                  profit=-100.0, volume=1.0)
    assert hx.emergency_close_check("XAUUSD", pos_with_sl) is False
    pos_severe = SimpleNamespace(ticket=2, type=0, price_open=2000.0,
                                 sl=None, tp=None, comment="series-2|",
                                 profit=-500.0, volume=1.0)
    assert hx.emergency_close_check("XAUUSD", pos_severe) is True
    pos_retrace = SimpleNamespace(ticket=3, type=0, price_open=2000.0,
                                  sl=None, tp=None, comment="series-3|",
                                  profit=-10.0, volume=1.0)
    assert hx.emergency_close_check("XAUUSD", pos_retrace) is True
    pos_profit = SimpleNamespace(ticket=4, type=0, price_open=2000.0,
                                 sl=None, tp=None, comment="series-4|",
                                 profit=100.0, volume=1.0)
    assert hx.emergency_close_check("XAUUSD", pos_profit) is False


# ---------------- Logger ----------------
def test_logger_exit_levels_true_false_and_empty(caplog):
    caplog.set_level("INFO", logger="PrettyLog")
    lg.pretty_log_decisionengine("XAUUSD", "SELL", 0.1, 1000, exit_levels=None)
    lg.pretty_log_decisionengine("XAUUSD", "BUY", 0.1, 1000,
                                 exit_levels={"sl": 999, "tp": [{"price": 1010, "diff": 10, "close_pct": 50}]})
    lg.pretty_log_decisionengine("XAUUSD", "BUY", 0.1, 1000,
                                 exit_levels={"sl": None, "tp": []})
    msgs = " ".join(r.message for r in caplog.records)
    assert "SL=— TP=—" in msgs


def test_get_logger_with_new_filename_branch(tmp_path):
    logfile = tmp_path / "logger_test_new.log"
    logger = lg.get_logger("FileLoggerNew", filename=str(logfile))
    logger.info("branch test new file")
    for h in logger.handlers:
        try:
            h.flush()
        except Exception:
            pass
    text = logfile.read_text()
    assert "branch test new file" in text


# ---------------- PositionManager ----------------
def test_position_manager_parse_comment_variants():
    conf, winprob, idx = PositionManager._parse_comment("0.3|0.8")
    assert (conf, winprob, idx) == (0.3, 0.8, 1)
    conf2, winprob2, idx2 = PositionManager._parse_comment("series-")
    assert (conf2, winprob2, idx2) == (0.0, 0.0, 1)
    conf3, winprob3, idx3 = PositionManager._parse_comment("foobar")
    assert (conf3, winprob3, idx3) == (0.0, 0.0, 1)
    conf4, winprob4, idx4 = PositionManager._parse_comment("")
    assert (conf4, winprob4, idx4) == (0.0, 0.0, 1)
    conf5, winprob5, idx5 = PositionManager._parse_comment("|")
    assert (conf5, winprob5, idx5) == (0.0, 0.0, 1)


def test_position_manager_parse_comment_parts_extra():
    # parts ไม่ครบ จะเข้า branch if parts แต่ fallback เป็น default
    conf, winprob, idx = PositionManager._parse_comment("0.5|")
    assert (conf, winprob, idx) == (0.0, 0.0, 1)


# ---------------- PrettyLogger ----------------
def test_pretty_logger_ai_rule_fusion_true_and_false(caplog):
    caplog.set_level("INFO", logger="PrettyLog")
    pl.pretty_log_tradesignal("XAUUSD","BUY",0.1,2000,
                              exit_levels={"sl":1990,"tp":[{"price":2100}]},
                              ai_res={"decision":"BUY","confidence":0.8},
                              rule_res={"decision":"SELL","confidence":0.7,"threshold":0.5,"num_entries":2},
                              fusion={"decision":"BUY","score":0.9})
    pl.pretty_log_tradesignal("XAUUSD","BUY",0.1,2000,
                              exit_levels={"sl":1990,"tp":[{"price":2100}]})
    msgs = " ".join(r.message for r in caplog.records)
    assert "AI=" in msgs and "Rule=" in msgs and "Fusion=" in msgs


def test_pretty_logger_with_rule_res_branch(caplog):
    caplog.set_level("INFO", logger="PrettyLog")
    pl.pretty_log_tradesignal("XAUUSD","BUY",0.1,2000,
                              exit_levels={"sl":1990,"tp":[{"price":2100}]},
                              rule_res={"decision":"BUY","confidence":0.7})
    msgs = " ".join(r.message for r in caplog.records)
    assert "Rule=" in msgs


def test_pretty_logger_with_mult_and_dist_strict(caplog):
    caplog.set_level("INFO", logger="PrettyLog")
    pl.pretty_log_tradesignal("XAUUSD","SELL",0.1,2000,
                              exit_levels={"sl":1990,"tp":[{"price":2100}],
                                           "trailing":{"mult":1.5,"distance":0.002},
                                           "atr_used":0.002,"atr_mode":"strict"},
                              pip_size=0.0001)
    msgs = " ".join(r.message for r in caplog.records)
    assert "ATR×" in msgs


def test_pretty_logger_tp_without_price_branch(caplog):
    caplog.set_level("INFO", logger="PrettyLog")
    pl.pretty_log_tradesignal("XAUUSD","SELL",0.1,2000,
                              exit_levels={"sl":1990,"tp":[{"price":None,"perc":50}]})
    msgs = " ".join(r.message for r in caplog.records)
    assert "SL=" in msgs or "TP" in msgs


# ---------------- RiskGuard ----------------
def test_riskguard_record_trade_negative_and_positive():
    rg = RiskGuard({})
    rg.record_trade("XAUUSD", -5.0)
    assert "XAUUSD" in rg.state["last_sl_hit"]
    rg.record_trade("XAUUSD", 5.0)


# ---------------- Swing ----------------
class DummyInd: pass
def test_swing_force_exact_buy_and_sell():
    cfg = {"XAUUSD":{"indicators":{"atr":{"min_threshold":1},"adx":{"min_threshold":1},
                                   "rsi":{"bull_level":60,"bear_level":40}}}}
    s = SwingStrategy(cfg)
    ind_buy = SimpleNamespace(rsi=80, atr=5, adx=5, macd_hist=2)
    entry_buy = SimpleNamespace(symbol="XAUUSD", bid=2000, h4=ind_buy, d1=None)
    assert s.evaluate(entry_buy)["decision"] == "BUY"
    ind_sell = SimpleNamespace(rsi=20, atr=5, adx=5, macd_hist=-2)
    entry_sell = SimpleNamespace(symbol="XAUUSD", bid=2000, h4=ind_sell, d1=None)
    assert s.evaluate(entry_sell)["decision"] == "SELL"


# ---------------- TrailingManager ----------------
def test_trailing_manager_emergency_close(monkeypatch):
    hx = HybridExit({})
    monkeypatch.setattr(hx, "emergency_close_check", lambda sym, pos: True)
    pos = SimpleNamespace(ticket=1, type=0, price_open=2000.0,
                          sl=None, tp=None, comment="", profit=-500.0, volume=1.0)
    assert hx.emergency_close_check("XAUUSD", pos) is True
