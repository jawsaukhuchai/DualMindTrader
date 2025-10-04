import pytest
import logging
from mind2_python import pretty_logger as pl


@pytest.fixture(autouse=True)
def setup_logging():
    """Reset PrettyLog handlers before each test"""
    log = logging.getLogger("PrettyLog")
    log.handlers.clear()
    log.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    log.addHandler(handler)
    yield
    log.handlers.clear()


def test_normalize_winprob_and_colorize():
    # normalize_winprob
    val = pl.normalize_winprob(0.5, 0.5)
    assert 30 <= val <= 95
    # bounds
    assert pl.normalize_winprob(2.0, -1.0) >= 30
    assert pl.normalize_winprob(-2.0, 5.0) <= 95

    # colorize_decision
    txt_buy = pl.colorize_decision("BUY", "X")
    txt_sell = pl.colorize_decision("SELL", "X")
    txt_hold = pl.colorize_decision("HOLD", "X")
    txt_other = pl.colorize_decision("???", "X")
    assert "\033" in txt_buy and "\033" in txt_sell and "\033" in txt_hold
    assert txt_other == "X"


def test_pretty_log_tradesignal_full(capsys):
    exit_levels = {
        "sl": 1.111,
        "tp": [
            {"price": 1.2, "raw_pips": 20, "perc": 50},
            {"price": 1.25, "raw_pips": 70, "perc": 50},
        ],
        "trailing": {"mult": 2.0, "distance": 0.001},
        "atr_used": 0.001,
        "atr_mode": "hybrid",
    }
    pl.pretty_log_tradesignal(
        symbol="BTCUSD",
        decision="BUY",
        lot=0.1,
        entry=25000.0,
        exit_levels=exit_levels,
        winprob_raw=70.0,
        score_raw=0.5,
        conf_raw=0.8,
        timeframe="M15",
        reason="Strong signal",
        regime="trend",
        ai_res={"decision": "BUY", "confidence": 0.9},
        rule_res={"decision": "SELL", "confidence": 0.4, "threshold": 0.05, "num_entries": 2},
        fusion={"decision": "BUY", "score": 0.7},
    )
    out, _ = capsys.readouterr()
    assert "TRADE SIGNAL" in out
    assert "TP1" in out
    assert "ATR×2.0" in out
    assert "Integration" in out
    assert "Reason" in out


def test_pretty_log_tradesignal_hold(capsys):
    pl.pretty_log_tradesignal(
        symbol="ETHUSD",
        decision="HOLD",
        lot=0.2,
        entry=1500.0,
        reason="Sideway",
    )
    out, _ = capsys.readouterr()
    assert "No Trade" in out
    assert "Sideway" in out


def test_pretty_log_close_position_variants(capsys):
    pl.pretty_log_close_position("XAUUSD", ticket=1, lot=0.1, price=1900.0, reason="NORMAL")
    pl.pretty_log_close_position("XAUUSD", ticket=2, lot=0.1, price=1900.0, reason="SEVERE")
    pl.pretty_log_close_position("XAUUSD", ticket=3, lot=0.1, price=1900.0, reason="RETRACE")
    out, _ = capsys.readouterr()
    assert "CLOSE" in out
    assert "EMERGENCY" in out or "Normal" in out


def test_pretty_log_auto_and_trailing(capsys):
    pl.pretty_log_auto_update("BTCUSD", ticket=1, sl=100, tp=200)
    pl.pretty_log_trailing("BTCUSD", ticket=1, old_sl=100, new_sl=150)
    out, _ = capsys.readouterr()
    assert "AUTO-UPDATE" in out
    assert "TRAILING" in out


def test_pretty_log_positions_summary(capsys):
    # empty
    pl.pretty_log_positions_summary({})
    # with orders
    summary = {
        "total": 2,
        "symbols": {
            "XAUUSD": [{"profit": 10.0, "entry_index": 1}, {"profit": -5.0, "entry_index": 2}],
            "BTCUSD": [{"profit": 20.0, "entry_index": 1}],
        },
    }
    pl.pretty_log_positions_summary(summary)
    out, _ = capsys.readouterr()
    assert "Positions" in out
    assert "XAUUSD" in out
    assert "BTCUSD" in out


def test_pretty_log_global_entry_exit(capsys):
    pl.pretty_log_global_entry("XAUUSD", "all good", allowed=True)
    pl.pretty_log_global_entry("XAUUSD", "margin low", allowed=False)
    pl.pretty_log_global_exit("Daily stoploss hit", triggered=True)
    pl.pretty_log_global_exit("Takeprofit hit", triggered=True)
    pl.pretty_log_global_exit("Manual close", triggered=False)
    out, _ = capsys.readouterr()
    assert "GlobalEntry" in out
    assert "GlobalExit" in out


def test_pretty_log_execution(capsys):
    pl.pretty_log_execution("BTCUSD", decision="BUY", allowed=True)
    pl.pretty_log_execution("BTCUSD", decision="SELL", allowed=False, blocker="RiskGuard", reasons="margin low")
    out, _ = capsys.readouterr()
    assert "Execution" in out
    assert "ALLOWED" in out or "BLOCKED" in out


def test_pretty_log_dashboard(capsys):
    results = {
        "BTCUSD": {
            "decision": "BUY",
            "signal": {"winprob": 0.75},
            "confidence": 0.8,
            "regime": "trend",
            "votes": {"rule": {"threshold": 0.05, "num_entries": 2}},
        }
    }
    pl.pretty_log_dashboard(
        balance=1000.0,
        equity=1100.0,
        pnl=100.0,
        margin_level=200.0,
        lots=0.5,
        results=results,
        symbols_cfg={},
        compact=True,
    )
    out, _ = capsys.readouterr()
    assert "Dashboard" in out
    assert "BTCUSD" in out
    assert "wp=" in out
