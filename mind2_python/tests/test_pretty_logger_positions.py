import logging
import pytest

from mind2_python.pretty_logger import pretty_log_positions_summary


def test_positions_summary_none(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    # None input
    pretty_log_positions_summary(None)

    captured = capsys.readouterr()
    # ไม่มี output อะไร
    assert captured.out == ""
    assert not caplog.records


def test_positions_summary_empty(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    summary = {"total": 0, "symbols": {}}
    pretty_log_positions_summary(summary)

    captured = capsys.readouterr()
    out = captured.out

    assert "Positions" in out
    assert "none" in out
    assert "total=0" in out

    records = [r.message for r in caplog.records if r.name == "PrettyLog"]
    assert any("Positions" in r for r in records)


def test_positions_summary_with_orders(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    summary = {
        "total": 3,
        "symbols": {
            "XAUUSD": [
                {"profit": 10.5, "entry_index": 1},
                {"profit": -5.0, "entry_index": 2},
            ],
            "BTCUSD": [
                {"profit": 20.0, "entry_index": 1},
            ],
        },
    }
    pretty_log_positions_summary(summary)

    captured = capsys.readouterr()
    out = captured.out

    assert "Positions" in out
    assert "total=3" in out
    assert "XAUUSD" in out
    assert "BTCUSD" in out
    assert "PnL=" in out
    assert "idx=" in out

    records = [r.message for r in caplog.records if r.name == "PrettyLog"]
    assert any("XAUUSD" in r for r in records)
    assert any("BTCUSD" in r for r in records)
    assert any("total=3" in r for r in records)
