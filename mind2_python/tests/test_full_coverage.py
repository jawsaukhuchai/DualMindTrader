# tests/test_full_coverage.py (patched full)
import pytest, importlib, sys, logging, subprocess
import pandas as pd, numpy as np

from mind2_python import logger as lg
from mind2_python.position_manager import PositionManager
from mind2_python import pretty_logger as pl
from mind2_python import swing, schema

# ---------------- integrate_decisions logger init ----------------
def test_integrate_logger_init_branch():
    sys.modules.pop("mind2_python.integrate_decisions", None)
    log = logging.getLogger("Integrate")
    log.handlers.clear()
    mod = importlib.import_module("mind2_python.integrate_decisions")
    assert hasattr(mod, "logger")
    scalp = {"decision": "BUY", "confidence": 0.5}
    day = {"decision": "SELL", "confidence": 0.5}
    swing_res = {"decision": "HOLD", "confidence": 0.5}
    out = mod.integrate_decisions(scalp, day, swing_res, regime="normal")
    assert "decision" in out

# ---------------- subprocess tests to force init branches ----------------
def test_integrate_decisions_logger_branch_subprocess():
    code = "import mind2_python.integrate_decisions as m; print(m.logger.name)"
    out = subprocess.check_output([sys.executable, "-c", code])
    assert b"Integrate" in out

def test_integrate_decisions_logger_branch_force():
    import sys, logging
    import importlib
    sys.modules.pop("mind2_python.integrate_decisions", None)
    log = logging.getLogger("Integrate")
    log.handlers.clear()
    mod = importlib.import_module("mind2_python.integrate_decisions")
    assert hasattr(mod, "logger")

# ---------------- logger.py atr_mult branch ----------------
def test_logger_tradesignal_atr_mult_branch(caplog):
    sys.modules.pop("mind2_python.logger", None)
    mod = importlib.import_module("mind2_python.logger")
    with caplog.at_level(logging.INFO):
        mod.pretty_log_tradesignal("BTCUSDc", "BUY", 0.1, 100,
                                   exit_levels={"atr_mult": 1.5, "atr": 2.0})
    assert any("ATR×1.5" in m for m in caplog.messages)

def test_logger_pretty_log_tradesignal_atr_mult_false(caplog):
    sys.modules.pop("mind2_python.logger", None)
    mod = importlib.import_module("mind2_python.logger")
    with caplog.at_level(logging.INFO):
        mod.pretty_log_tradesignal("BTCUSDc", "BUY", 0.1, 100,
                                   exit_levels={"atr_mult": None, "atr": None})
    assert any("TRADE SIGNAL" in m for m in caplog.messages)

def test_logger_get_logger_no_filename_reload():
    sys.modules.pop("mind2_python.logger", None)
    mod = importlib.import_module("mind2_python.logger")
    log = mod.get_logger("LoggerNoFile")
    assert log.name == "LoggerNoFile"

# ---------------- position_manager.py parts branch ----------------
def test_position_manager_parse_comment_parts():
    conf, wp, idx = PositionManager._parse_comment("|")
    assert (conf, wp, idx) == (0.0, 0.0, 1)

def test_position_manager_parse_comment_series_index():
    comment = "series-2|0.7|0.8"
    conf, winprob, idx = PositionManager._parse_comment(comment)
    assert conf == 0.7
    assert winprob == 0.8
    assert idx == 2

def test_position_manager_parse_comment_series_parts():
    conf, wp, idx = PositionManager._parse_comment("series-5|0.9|0.8")
    assert conf == 0.9
    assert wp == 0.8
    assert idx == 5

def test_position_manager_parse_comment_empty():
    conf, wp, idx = PositionManager._parse_comment("")
    assert (conf, wp, idx) == (0.0, 0.0, 1)

def test_position_manager_parse_comment_none():
    conf, wp, idx = PositionManager._parse_comment(None)
    assert (conf, wp, idx) == (0.0, 0.0, 1)

# ---------------- pretty_logger rule_res + trailing fallback ----------------
def test_pretty_logger_rule_res_branch(capsys):
    rule_res = {"decision": "BUY", "confidence": 0.8}
    pl.pretty_log_tradesignal("XAUUSDc", "BUY", 0.1, 2000, rule_res=rule_res)
    out = capsys.readouterr().out
    assert "Rule=BUY" in out

def test_pretty_logger_trailing_fallback_no_distance(capsys):
    exit_levels = {"trailing": {"mult": 1.5}, "atr_used": 1.0}
    pl.pretty_log_tradesignal("XAUUSDc", "BUY", 0.1, 2000,
                              exit_levels=exit_levels, pip_size=0.1)
    out = capsys.readouterr().out
    assert "ATR×1.5" in out

def test_pretty_logger_rule_res_full(capsys):
    rule_res = {"decision": "BUY", "confidence": 0.9,
                "threshold": 0.2, "num_entries": 2}
    pl.pretty_log_tradesignal("XAUUSDc", "BUY", 0.2, 2000, rule_res=rule_res)
    out = capsys.readouterr().out
    assert "Rule=BUY" in out

def test_pretty_logger_rule_res_none(capsys):
    pl.pretty_log_tradesignal("XAUUSDc", "SELL", 0.1, 1800, rule_res=None)
    out = capsys.readouterr().out
    assert "TRADE SIGNAL" in out

def test_pretty_logger_rule_res_empty_dict(capsys):
    pl.pretty_log_tradesignal("BTCUSDc", "BUY", 0.1, 20000, rule_res={})
    out = capsys.readouterr().out
    assert "TRADE SIGNAL" in out

# ---------------- swing.py buy/sell + bos confirm branch ----------------
def test_swing_strategy_buy_sell():
    entry = schema.TradeEntry("BTCUSDc", 1, 2, 0.1, {}, {}, "2020-01-01")
    entry.timeframes["H4"] = {"rsi": 80, "atr": 5, "adx": 10,
                              "macd_hist": 1, "bos": "bullish",
                              "bb": {"upper": 0, "lower": 2}}
    strat = swing.SwingStrategy({"BTCUSDc": {"indicators": {"atr": {"min_threshold": 1},
                                                            "adx": {"min_threshold": 1},
                                                            "rsi": {"bull_level": 70, "bear_level": 30}}}})
    res = strat.evaluate(entry)
    assert res["decision"] in ["BUY", "SELL"]

def test_swing_strategy_bos_confirm():
    entry = schema.TradeEntry("XAUUSDc", 1, 2, 0.1, {}, {}, "2020-01-01")
    entry.timeframes["H4"] = {"rsi": 80, "atr": 10, "adx": 20,
                              "macd_hist": 1, "bos": "bullish",
                              "bb": {"upper": 0, "lower": -1}}
    entry.bid = 2
    strat = swing.SwingStrategy({"XAUUSDc": {"indicators": {"atr": {"min_threshold": 1},
                                                            "adx": {"min_threshold": 1},
                                                            "rsi": {"bull_level": 65, "bear_level": 35}}}})
    res = strat.evaluate(entry)
    assert res["decision"] == "BUY"
    assert "bos_confirm" in res["reason"]

def test_swing_strategy_bos_confirm_strict():
    entry = schema.TradeEntry("BTCUSDc", 1, 2, 0.1, {}, {}, "2020-01-01")
    entry.timeframes["H4"] = {"rsi": 85, "atr": 15, "adx": 20,
                              "macd_hist": 1, "bos": "bullish",
                              "bb": {"upper": 0, "lower": -1}}
    entry.bid = 5
    strat = swing.SwingStrategy({"BTCUSDc": {"indicators": {"atr": {"min_threshold": 1},
                                                            "adx": {"min_threshold": 1},
                                                            "rsi": {"bull_level": 70, "bear_level": 30}}}})
    res = strat.evaluate(entry)
    assert res["decision"] == "BUY"
    assert "bos_confirm" in res["reason"]

def test_swing_strategy_no_bos():
    entry = schema.TradeEntry("BTCUSDc", 1, 2, 0.1, {}, {}, "2020-01-01")
    entry.timeframes["H4"] = {"rsi": 80, "atr": 10, "adx": 15,
                              "macd_hist": 1, "bos": "",
                              "bb": {"upper": 0, "lower": -1}}
    entry.bid = 2
    strat = swing.SwingStrategy({"BTCUSDc": {"indicators": {"atr": {"min_threshold": 1},
                                                            "adx": {"min_threshold": 1},
                                                            "rsi": {"bull_level": 70, "bear_level": 30}}}})
    res = strat.evaluate(entry)
    assert "bos_confirm" not in res["reason"]

def test_swing_strategy_bos_none():
    entry = schema.TradeEntry("XAUUSDc", 1, 2, 0.1, {}, {}, "2020-01-01")
    entry.timeframes["H4"] = {"rsi": 85, "atr": 5, "adx": 10,
                              "macd_hist": 1, "bos": None,
                              "bb": {"upper": 0, "lower": -1}}
    entry.bid = 2
    strat = swing.SwingStrategy({"XAUUSDc": {"indicators": {"atr": {"min_threshold": 1},
                                                            "adx": {"min_threshold": 1},
                                                            "rsi": {"bull_level": 70, "bear_level": 30}}}})
    res = strat.evaluate(entry)
    assert "bos_confirm" not in res["reason"]

# ---------------- extra gap closing tests ----------------
def test_integrate_decisions_logger_branch_subprocess_force():
    code = (
        "import logging; import sys; "
        "sys.modules.pop('mind2_python.integrate_decisions',None); "
        "import importlib; "
        "m=importlib.import_module('mind2_python.integrate_decisions'); "
        "print(hasattr(m,'logger'))"
    )
    out = subprocess.check_output([sys.executable, "-c", code])
    assert b"True" in out

def test_position_manager_parse_comment_force_empty_parts():
    conf, wp, idx = PositionManager._parse_comment([])  # type: ignore
    assert (conf, wp, idx) == (0.0, 0.0, 1)

def test_pretty_logger_rule_res_append_branch(capsys):
    rule_res = {"decision": "BUY", "confidence": 0.9}
    pl.pretty_log_tradesignal("BTCUSDc", "BUY", 0.1, 20000, rule_res=rule_res)
    out = capsys.readouterr().out
    assert "Rule=BUY" in out

def test_swing_strategy_bos_and_decision_buy():
    entry = schema.TradeEntry("BTCUSDc", 1, 2, 0.1, {}, {}, "2020-01-01")
    entry.timeframes["H4"] = {"rsi": 90, "atr": 10, "adx": 15,
                              "macd_hist": 1, "bos": "bullish",
                              "bb": {"upper": 0, "lower": -1}}
    entry.bid = 5
    strat = swing.SwingStrategy({"BTCUSDc": {"indicators": {"atr": {"min_threshold": 1}, "adx": {"min_threshold": 1}, "rsi": {"bull_level": 70, "bear_level": 30}}}})
    res = strat.evaluate(entry)
    assert res["decision"] == "BUY"
    assert "bos_confirm" in res["reason"]
