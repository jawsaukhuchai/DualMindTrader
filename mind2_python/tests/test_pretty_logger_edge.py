import logging
import pytest

from mind2_python.pretty_logger import (
    pretty_log_tradesignal,
    pretty_log_close_position,
    pretty_log_auto_update,
    pretty_log_dashboard,
)


def test_tradesignal_winprob_only(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    # แค่ winprob_raw → เข้าสาย elif winprob_raw is not None
    pretty_log_tradesignal(
        symbol="EURUSD",
        decision="BUY",
        lot=0.1,
        entry=1.2345,
        winprob_raw=0.65,
    )

    captured = capsys.readouterr()
    out = captured.out
    assert "WinProb raw" in out
    # ไม่ควรมี "norm≈"
    assert "norm≈" not in out


def test_tradesignal_hold_branch(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    pretty_log_tradesignal(
        symbol="EURUSD",
        decision="HOLD",
        lot=0.1,
        entry=1.2000,
        reason="Sideway",
    )

    captured = capsys.readouterr()
    out = captured.out
    assert "No Trade" in out
    assert "Sideway" in out
    # หลังจาก HOLD จะ return ไม่ log exit levels
    assert "Entry @" not in out


def test_tradesignal_tp_as_float_list(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    pretty_log_tradesignal(
        symbol="GBPUSD",
        decision="SELL",
        lot=0.2,
        entry=1.3000,
        exit_levels={"tp": [1.2500, 1.2000]},
    )

    captured = capsys.readouterr()
    out = captured.out
    # ต้องเห็น TP ราคาตัว float
    assert "TP1=1.25" in out
    assert "TP2=1.20" in out


def test_close_position_unknown_reason(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    pretty_log_close_position(
        symbol="XAUUSD",
        ticket=999,
        lot=0.05,
        price=2000.0,
        profit=5.0,
        reason="UNKNOWN",  # ไม่ตรงกับ NORMAL/SEVERE/RETRACE
    )

    captured = capsys.readouterr()
    out = captured.out
    # ควรเข้า Normal Close
    assert "Normal Close" in out


def test_auto_update_debug(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    pretty_log_auto_update("XAUUSD", ticket=111, sl=1900.0, tp=1950.0, entry_index=2)

    captured = capsys.readouterr()
    out = captured.out
    assert "AUTO-UPDATE" in out
    assert "ticket=111" in out

    records = [r for r in caplog.records if r.name == "PrettyLog"]
    # ต้องเป็น log level DEBUG
    assert any(r.levelno == logging.DEBUG for r in records)


def test_dashboard_non_compact_only(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    pretty_log_dashboard(
        balance=5000.0,
        equity=5100.0,
        pnl=100.0,
        margin_level=200.0,
        lots=0.5,
        results={},  # compact=False, results empty
        symbols_cfg={},
        compact=False,
    )

    captured = capsys.readouterr()
    out = captured.out
    assert "Dashboard" in out
    assert "Balance=5000.00" in out
    assert "Equity=5100.00" in out
