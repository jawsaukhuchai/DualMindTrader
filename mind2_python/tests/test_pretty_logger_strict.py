import logging
import pytest

from mind2_python.pretty_logger import (
    pretty_log_tradesignal,
    pretty_log_auto_update,
    pretty_log_dashboard,
)


def test_tradesignal_winprob_only_branch(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    # ✅ แค่ winprob_raw อย่างเดียว
    pretty_log_tradesignal(
        symbol="AUDUSD",
        decision="BUY",
        lot=0.1,
        entry=1.0000,
        winprob_raw=0.55,  # ไม่มี score_raw, conf_raw
    )

    captured = capsys.readouterr()
    out = captured.out

    # ควรเข้า elif branch → แสดง WinProb raw แต่ไม่มี norm≈
    assert "WinProb raw=0.55" in out
    assert "norm≈" not in out


def test_auto_update_debug_is_logged(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    pretty_log_auto_update("AUDUSD", ticket=333, sl=1.1111, tp=1.2222, entry_index=5)

    captured = capsys.readouterr()
    out = captured.out
    assert "AUTO-UPDATE" in out
    assert "ticket=333" in out

    # ✅ ตรวจว่า log level เป็น DEBUG
    records = [r for r in caplog.records if r.name == "PrettyLog"]
    assert any("AUTO-UPDATE" in r.message and r.levelno == logging.DEBUG for r in records)


def test_dashboard_non_compact_with_results(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    results = {
        "AUDUSD": {
            "decision": "HOLD",
            "signal": {"winprob": 0.0},
            "confidence": 0.0,
            "regime": "Flat",
            "votes": {"rule": {"threshold": None, "num_entries": None}},
        }
    }

    pretty_log_dashboard(
        balance=2000.0,
        equity=2000.0,
        pnl=0.0,
        margin_level=1000.0,
        lots=0.0,
        results=results,
        symbols_cfg={},
        compact=False,  # ✅ non-compact + results มีข้อมูล
    )

    captured = capsys.readouterr()
    out = captured.out
    # ✅ ต้องเห็น Dashboard + Balance/Equity
    assert "Dashboard" in out
    assert "Balance=2000.00" in out
    assert "Equity=2000.00" in out
    # ✅ ใน non-compact mode ไม่ควรมี wp= (เฉพาะ compact เท่านั้นที่ iterate results)
    assert "wp=" not in out
