import logging
import pytest

from mind2_python.pretty_logger import (
    pretty_log_tradesignal,
    pretty_log_auto_update,
    pretty_log_dashboard,
)


def test_tradesignal_winprob_only_branch_force(capsys):
    """
    ครอบ line 73: elif winprob_raw is not None
    ต้องไม่ส่ง score_raw และ conf_raw เลย
    """
    pretty_log_tradesignal(
        symbol="XAUUSD",
        decision="BUY",
        lot=0.1,
        entry=1.0000,
        winprob_raw=0.42,  # ✅ only this
    )
    out = capsys.readouterr().out
    assert "WinProb raw=0.42" in out
    assert "norm≈" not in out


def test_auto_update_force_handler(capsys):
    """
    ครอบ line 211: pretty_log_auto_update
    บังคับ logger PrettyLog ให้มี handler และ DEBUG level
    """
    log = logging.getLogger("PrettyLog")
    handler = logging.StreamHandler()
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)

    try:
        pretty_log_auto_update("EURUSD", ticket=456, sl=1.1111, tp=1.2222)
    finally:
        log.removeHandler(handler)

    out = capsys.readouterr().out
    assert "AUTO-UPDATE" in out
    assert "ticket=456" in out


def test_dashboard_non_compact_force(capsys):
    """
    ครอบ line 250: pretty_log_dashboard non-compact
    ใช้ results ที่ไม่ว่างและ compact=False
    """
    results = {
        "USDJPY": {
            "decision": "BUY",
            "signal": {"winprob": 0.5},
            "confidence": 0.6,
            "regime": "Neutral",
            "votes": {"rule": {"threshold": 0.1, "num_entries": 1}},
        }
    }

    pretty_log_dashboard(
        balance=5000.0,
        equity=5050.0,
        pnl=50.0,
        margin_level=300.0,
        lots=0.3,
        results=results,
        symbols_cfg={},
        compact=False,  # ✅ non-compact
    )

    out = capsys.readouterr().out
    assert "Dashboard" in out
    assert "Balance=5000.00" in out
    assert "Equity=5050.00" in out
