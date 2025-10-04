import pytest
from mind2_python.pretty_logger import (
    pretty_log_tradesignal,
    pretty_log_close_position,
    pretty_log_auto_update,
    pretty_log_trailing,
    pretty_log_positions_summary,
    pretty_log_global_entry,
    pretty_log_global_exit,
    pretty_log_execution,
    pretty_log_dashboard,
)


def test_pretty_log_tradesignal_buy(capsys):
    pretty_log_tradesignal(
        symbol="BTCUSDc",
        decision="BUY",
        lot=0.1,
        entry=50000.1234,
        exit_levels={
            "sl": 49000.0,
            "tp": [{"price": 51000.0, "raw_pips": 100.0, "perc": 50}],
            "trailing": {"mult": 2.0, "distance": 200.0},
            "atr_used": 100.0,
            "atr_mode": "classic",
        },
        winprob_raw=0.55,
        score_raw=0.2,
        conf_raw=0.7,
        timeframe="H1",
        reason="OK",
        regime="trend",
        ai_res={"decision": "BUY", "confidence": 0.8},
        rule_res={"decision": "BUY", "confidence": 0.6, "threshold": 0.75, "num_entries": 3},
        fusion={"decision": "BUY", "score": 0.7},
    )
    out = capsys.readouterr().out
    assert "BUY" in out
    assert "SL" in out
    assert "TP1" in out
    assert "Integration" in out
    assert "ATR×" in out


def test_pretty_log_tradesignal_sell_hold(capsys):
    # HOLD decision
    pretty_log_tradesignal(
        symbol="XAUUSDc",
        decision="HOLD",
        lot=0.2,
        entry=1900.5678,
        reason="sideway",
    )
    out = capsys.readouterr().out
    assert "No Trade" in out
    assert "sideway" in out


def test_tradesignal_without_rule_res_btc(capsys):
    pretty_log_tradesignal(
        symbol="BTCUSDc",
        decision="BUY",
        lot=0.1,
        entry=55000.1234,
        exit_levels={"sl": 54000.0, "tp": [{"price": 56000.0}]},
        winprob_raw=0.65,
        score_raw=0.3,
        conf_raw=0.8,
        timeframe="H1",
        reason="OK",
        rule_res=None,
    )
    out = capsys.readouterr().out
    assert "Entry" in out
    assert "SL" in out
    assert "TP1" in out
    assert "Integration" not in out


def test_tradesignal_without_rule_res_xau(capsys):
    pretty_log_tradesignal(
        symbol="XAUUSDc",
        decision="SELL",
        lot=0.2,
        entry=1900.5678,
        exit_levels={"sl": 1920.0, "tp": [{"price": 1880.0}]},
        winprob_raw=0.40,
        score_raw=-0.2,
        conf_raw=0.6,
        timeframe="H4",
        reason="OK",
        rule_res=None,
    )
    out = capsys.readouterr().out
    assert "Entry" in out
    assert "SL" in out
    assert "TP1" in out
    assert "Integration" not in out


def test_tradesignal_with_empty_rule_res(capsys):
    pretty_log_tradesignal(
        symbol="BTCUSDc",
        decision="BUY",
        lot=0.1,
        entry=55500.0,
        exit_levels={"sl": 54000.0, "tp": [{"price": 56500.0}]},
        winprob_raw=0.5,
        score_raw=0.0,
        conf_raw=0.5,
        timeframe="M15",
        reason="empty_rule_res",
        rule_res={},  # dict ว่าง
    )
    out = capsys.readouterr().out
    assert "Entry" in out
    assert "Integration" not in out


def test_tradesignal_rule_res_none_branch(capsys):
    # กรณี rule_res=None → if rule_res: False → jump ไป line 140
    pretty_log_tradesignal(
        symbol="BTCUSDc",
        decision="BUY",
        lot=0.1,
        entry=55600.0,
        exit_levels={"sl": 54000.0, "tp": [{"price": 56600.0}]},
        reason="rule_res_none_branch",
        rule_res=None,
    )
    out = capsys.readouterr().out
    assert "Entry" in out
    assert "Integration" not in out


def test_pretty_log_close_position_normal(capsys):
    pretty_log_close_position(
        symbol="BTCUSDc", ticket=12345, lot=0.1, price=50500.0, conf=0.8, winprob=0.7, profit=100.0
    )
    out = capsys.readouterr().out
    assert "Normal Close" in out


def test_pretty_log_close_position_severe(capsys):
    pretty_log_close_position(
        symbol="BTCUSDc",
        ticket=12346,
        lot=0.1,
        price=49000.0,
        conf=0.4,
        winprob=0.2,
        profit=-200.0,
        reason="SEVERE",
    )
    out = capsys.readouterr().out
    assert "EMERGENCY CLOSE" in out


def test_pretty_log_auto_update_and_trailing(capsys):
    pretty_log_auto_update("BTCUSDc", 123, 49000.0, 51000.0)
    pretty_log_trailing("BTCUSDc", 123, 49000.0, 49500.0)
    out = capsys.readouterr().out
    assert "AUTO-UPDATE" in out
    assert "TRAILING" in out


def test_pretty_log_positions_summary_none(capsys):
    pretty_log_positions_summary({"total": 0, "symbols": {}})
    out = capsys.readouterr().out
    assert "none" in out


def test_pretty_log_positions_summary_some(capsys):
    summary = {
        "total": 2,
        "symbols": {
            "BTCUSDc": [
                {"profit": 10.0, "entry_index": 1},
                {"profit": -5.0, "entry_index": 2},
            ]
        },
    }
    pretty_log_positions_summary(summary)
    out = capsys.readouterr().out
    assert "PnL" in out


def test_pretty_log_global_entry_exit(capsys):
    pretty_log_global_entry("BTCUSDc", "risk_ok", allowed=True)
    pretty_log_global_entry("BTCUSDc", "blocked", allowed=False)
    pretty_log_global_exit("StopLoss Hit", triggered=True)
    pretty_log_global_exit("Normal Condition", triggered=False)
    out = capsys.readouterr().out
    assert "GlobalEntry" in out
    assert "GlobalExit" in out


def test_pretty_log_execution(capsys):
    pretty_log_execution("BTCUSDc", "BUY", allowed=True)
    pretty_log_execution("XAUUSDc", "SELL", allowed=False, blocker="RiskGuard", reasons="spread high")
    out = capsys.readouterr().out
    assert "Execution" in out


def test_pretty_log_dashboard(capsys):
    results = {
        "BTCUSDc": {
            "decision": "BUY",
            "signal": {"winprob": 0.7},
            "confidence": 0.8,
            "regime": "trend",
            "votes": {"rule": {"threshold": 0.5, "num_entries": 2}},
        }
    }
    pretty_log_dashboard(
        balance=10000.0,
        equity=10200.0,
        pnl=200.0,
        margin_level=150.0,
        lots=0.5,
        results=results,
        symbols_cfg={},
        compact=True,
    )
    out = capsys.readouterr().out
    assert "Dashboard" in out
    assert "BTCUSDc" in out


def test_tradesignal_rule_res_none_branch(capsys):
    pretty_log_tradesignal(
        symbol="BTCUSDc",
        decision="BUY",
        lot=0.1,
        entry=55600.0,
        exit_levels={"sl": 54000.0, "tp": [{"price": 56600.0}]},
        reason="rule_res_none_branch",
        rule_res=None,   # 👈 บังคับให้ False
    )
    out = capsys.readouterr().out
    assert "Entry" in out
    assert "Integration" not in out
