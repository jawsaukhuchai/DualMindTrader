# tests/test_edgecases_final.py
import pytest
from types import SimpleNamespace
from mind2_python.hybrid_exit import HybridExit
from mind2_python import logger as lg
from mind2_python.position_manager import PositionManager
from mind2_python import pretty_logger as pl
from mind2_python.risk_guard import RiskGuard
from mind2_python.swing import SwingStrategy
from mind2_python.trailing_manager import TrailingManager


# ---------------- hybrid_exit.py (157->160) ----------------
def test_hybrid_exit_scaling_branch():
    cfg = {
        "XAUUSD": {
            "exit": {"sl_atr": 1.0, "tp_steps": [1], "tp_perc": [100]},
            "digits": 2,
            "pip_size": 0.1,
            "portfolio": {"series_mode": "scaling"},
        }
    }
    hx = HybridExit(cfg)
    decision = {"decision": "BUY", "num_entries": 2, "lot": 1.0}
    exits = hx.calc(decision, 100, "XAUUSD", atr=1.0, atr_multi={}, global_exit_cfg={})
    assert len(exits["entries"]) == 2
    assert exits["entries"][2]["lot"] < exits["entries"][1]["lot"]


# ---------------- logger.py (61->68) ----------------
def test_logger_branch_no_exit_levels(caplog):
    caplog.set_level("INFO", logger="PrettyLog")
    lg.pretty_log_decisionengine("XAUUSD", "SELL", 0.1, 1000, exit_levels=None, reason="NO_EXIT")
    found = any("SL=— TP=—" in rec.message for rec in caplog.records)
    assert found


# ---------------- position_manager.py (178->180) ----------------
def test_position_manager_parse_comment_parts_empty():
    conf, winprob, idx = PositionManager._parse_comment("series-")
    assert (conf, winprob, idx) == (0.0, 0.0, 1)


# ---------------- pretty_logger.py (6 branches) ----------------
def test_pretty_logger_ai_rule_fusion_trailing_tp(caplog):
    caplog.set_level("INFO", logger="PrettyLog")
    pl.pretty_log_tradesignal(
        "XAUUSD", "BUY", 0.1, 2000,
        exit_levels={
            "sl": 1990,
            "tp": [{"price": 2100, "perc": 50}],
            "trailing": {"mult": 1.5, "distance": 0.002},
            "atr_used": 0.002,
            "atr_mode": "strict",
        },
        ai_res={"decision": "BUY", "confidence": 0.8},
        rule_res={"decision": "BUY", "confidence": 0.7, "threshold": 0.2, "num_entries": 1},
        fusion={"decision": "BUY", "score": 0.9},
    )
    msgs = " ".join(rec.message for rec in caplog.records)
    assert "AI=BUY" in msgs
    assert "Rule=BUY" in msgs
    assert "Fusion=BUY" in msgs
    assert "Integration" in msgs
    assert "TP1" in msgs
    assert "ATR×1.5" in msgs


# ---------------- risk_guard.py (179->exit) ----------------
def test_risk_guard_record_trade_exit_branch():
    rg = RiskGuard({})
    rg.record_trade("XAUUSD", -5.0)
    assert "XAUUSD" in rg.state["last_sl_hit"]


# ---------------- swing.py (57->61) ----------------
class DummyInd: pass
def test_swing_hold_no_confidence():
    cfg = {"XAUUSD":{"indicators":{"atr":{"min_threshold":1},"adx":{"min_threshold":1},"rsi":{"bull_level":70,"bear_level":30}}}}
    s = SwingStrategy(cfg)
    ind = DummyInd()
    ind.rsi=50; ind.atr=2; ind.adx=2; ind.macd_hist=None; ind.bos=None; ind.bb=None
    entry = SimpleNamespace(symbol="XAUUSD", bid=1000, h4=ind, d1=None)
    res = s.evaluate(entry)
    assert res["decision"]=="HOLD"


# ---------------- trailing_manager.py (50->49) ----------------
def test_trailing_manager_adjust_trailing_profit_nonpositive():
    hx = HybridExit({})
    sl = hx.adjust_trailing(current_price=100, side="BUY", entry=200, sl=None,
                            trailing_cfg={"atr_mult":1.5}, pip_size=0.1)
    assert sl is None
    sl2 = hx.adjust_trailing(current_price=200, side="SELL", entry=200, sl=None,
                             trailing_cfg={"atr_mult":1.5}, pip_size=0.1)
    assert sl2 is None
