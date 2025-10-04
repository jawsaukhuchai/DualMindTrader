import logging
import pytest

from mind2_python.pretty_logger import (
    pretty_log_tradesignal,
    pretty_log_auto_update,
    pretty_log_dashboard,
)


def test_tradesignal_winprob_raw_only_branch(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    # มีแค่ winprob_raw → เข้า elif branch
    pretty_log_tradesignal(
        symbol="EURUSD",
        decision="BUY",
        lot=0.1,
        entry=1.2345,
        winprob_raw=0.55,   # ✅ มีค่า
        # ไม่ส่ง score_raw / conf_raw
    )

    captured = capsys.readouterr()
    out = captured.out
    assert "WinProb raw=0.55" in out
    # ต้องไม่มีคำว่า norm≈
    assert "norm≈" not in out


def test_auto_update_debug_branch(capsys, caplog):
    # ตั้ง level DEBUG ให้ logger PrettyLog
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    pretty_log_auto_update("XAUUSD", ticket=222, sl=1800.0, tp=1850.0, entry_index=3)

    captured = capsys.readouterr()
    out = captured.out
    assert "AUTO-UPDATE" in out
    assert "ticket=222" in out

    # ตรวจว่า log level เป็น DEBUG
    records = [r for r in caplog.records if r.name == "PrettyLog"]
    assert any("AUTO-UPDATE" in r.message and r.levelno == logging.DEBUG for r in records)


def test_dashboard_results_non_compact(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    results = {
        "XAUUSD": {
            "decision": "BUY",
            "signal": {"winprob": 0.6},
            "confidence": 0.7,
            "regime": "Bull",
            "votes": {"rule": {"threshold": 0.5, "num_entries": 2}},
        }
    }

    pretty_log_dashboard(
        balance=12000.0,
        equity=12100.0,
        pnl=100.0,
        margin_level=400.0,
        lots=1.0,
        results=results,
        symbols_cfg={},
        compact=False,  # ✅ non-compact
    )

    captured = capsys.readouterr()
    out = captured.out
    assert "Dashboard" in out
    assert "Balance=12000.00" in out
    assert "Equity=12100.00" in out
    # ใน non-compact mode, results ไม่ถูก iterate → ไม่มี "wp=" ใน stdout
    assert "wp=" not in out
