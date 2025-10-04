import logging
import pytest

from mind2_python.pretty_logger import (
    pretty_log_tradesignal,
    pretty_log_close_position,
    Ansi,
    ICONS,
)


def test_pretty_log_tradesignal_buy(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    pretty_log_tradesignal(
        symbol="XAUUSD",
        decision="BUY",
        lot=0.10,
        entry=1900.50,
        exit_levels={
            "sl": 1890.0,
            "tp": [{"price": 1920.0, "perc": 50, "raw_pips": 200}],
            "trailing": {"mult": 2.0, "distance": 1.5},
            "atr_used": True,
            "atr_mode": "classic",
        },
        winprob_raw=0.7,
        score_raw=0.4,
        conf_raw=0.8,
        timeframe="H1",
        reason="Trend-follow",
        pip_size=0.1,
        entry_index=1,
        regime="Bull",
        ai_res={"decision": "BUY", "confidence": 0.85},
        rule_res={"decision": "BUY", "confidence": 0.7, "threshold": 0.65, "num_entries": 3},
        fusion={"decision": "BUY", "score": 0.9},
    )

    captured = capsys.readouterr()

    # --- snapshot checks (stdout) ---
    out = captured.out
    assert "TRADE SIGNAL" in out
    assert "BUY" in out
    assert ICONS["TP"] in out
    assert ICONS["SL"] in out
    assert ICONS["TRAIL"] in out
    assert "Trend-follow" in out
    assert Ansi.GREEN in out  # สีเขียว

    # --- snapshot checks (logger) ---
    records = [r.message for r in caplog.records if r.name == "PrettyLog"]
    assert any("TRADE SIGNAL" in r for r in records)
    assert any("Entry @" in r for r in records)
    assert any("SL=" in r for r in records)
    assert any("TP1=" in r for r in records)
    assert any("ATR×" in r for r in records)


@pytest.mark.parametrize(
    "reason,expected_icon",
    [
        ("NORMAL", "Normal Close"),
        ("SEVERE", "EMERGENCY CLOSE"),
        ("RETRACE", "EMERGENCY CLOSE"),
    ],
)
def test_pretty_log_close_position(capsys, caplog, reason, expected_icon):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    pretty_log_close_position(
        symbol="BTCUSD",
        ticket=12345,
        lot=0.05,
        price=27000.0,
        conf=0.75,
        winprob=0.60,
        profit=150.0,
        reason=reason,
        entry_index=2,
    )

    captured = capsys.readouterr()
    out = captured.out

    # --- snapshot checks (stdout) ---
    assert "CLOSE" in out
    assert "BTCUSD" in out
    assert expected_icon in out
    assert f"ticket=12345" in out
    assert f"Lot=0.0500" in out
    assert f"P/L=150.00" in out

    # --- snapshot checks (logger) ---
    records = [r.message for r in caplog.records if r.name == "PrettyLog"]
    assert any("CLOSE" in r for r in records)
    assert any("BTCUSD" in r for r in records)
