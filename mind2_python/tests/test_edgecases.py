import pytest
import pandas as pd
import numpy as np
import logging
from types import SimpleNamespace
from datetime import datetime

from mind2_python.hybrid_exit import HybridExit
from mind2_python import indicators_efficient as ie
from mind2_python import logger as lg
from mind2_python.position_manager import PositionManager
from mind2_python import pretty_logger as pl
from mind2_python.risk_guard import RiskGuard
from mind2_python.swing import SwingStrategy
from mind2_python.trailing_manager import TrailingManager


def test_trailing_manager_emergency_close_false(monkeypatch):
    cfg = {"symbols": {"XAUUSD": {"pip_size": 0.1}}}
    tm = TrailingManager(cfg)
    pos = {"ticket": 123, "entry_index": 1}
    monkeypatch.setattr("mind2_python.trailing_manager.PositionManager.get_open_positions", lambda sym: [pos])
    monkeypatch.setattr("mind2_python.trailing_manager.HybridExit.recalc_for_open_positions", lambda *a, **k: {})
    monkeypatch.setattr("mind2_python.trailing_manager.HybridExit.emergency_close_check", lambda *a, **k: False)
    monkeypatch.setattr("mind2_python.trailing_manager.mt5.symbol_info_tick", lambda sym: None)
    tm.loop_trailing()


# ---------------- Extra branch coverage ----------------
def test_logger_with_filename(tmp_path):
    """cover branch: if filename (logger.py line 61)"""
    import logging
    from mind2_python import logger as lg

    file = tmp_path / "logx.log"
    log = lg.get_logger("FileLoggerEdge", filename=str(file))
    log.info("msg-edge")

    # ✅ cleanup ป้องกัน ResourceWarning (ปิด handler)
    logging.shutdown()

    assert "msg-edge" in file.read_text()


def test_parse_comment_empty_string():
    """cover branch: if parts: (position_manager.py line 178)"""
    conf, winprob, idx = PositionManager._parse_comment("")
    assert (conf, winprob, idx) == (0.0, 0.0, 1)


def test_pretty_logger_with_rule_res(capsys):
    """cover branch: if rule_res: (pretty_logger.py line 138)"""
    rule_res = {"decision": "BUY", "confidence": 0.7, "threshold": 0.2}
    pl.pretty_log_tradesignal("XAUUSD", "BUY", 0.1, 2000, rule_res=rule_res)
    out = capsys.readouterr().out
    assert "Rule=BUY" in out


def test_pretty_logger_with_trailing_mult_and_dist(capsys):
    """cover branch: if mult and dist (pretty_logger.py line 180)"""
    exit_levels = {"trailing": {"mult": 2.0, "distance": 0.005}}
    pl.pretty_log_tradesignal("XAUUSD", "BUY", 0.1, 2000, exit_levels=exit_levels)
    out = capsys.readouterr().out
    assert "ATR×2.0" in out


def test_trailing_manager_with_atr_map():
    """ครอบ global_atr โดย set หลัง init"""
    cfg = {"symbols": {"XAUUSDc": {"pip_size": 0.1}}}
    tm = TrailingManager(cfg)
    tm.global_atr = {"XAUUSDc": 5.0}
    assert tm.global_atr["XAUUSDc"] == 5.0
