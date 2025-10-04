import logging
import pytest

from mind2_python.pretty_logger import (
    pretty_log_dashboard,
    pretty_log_global_entry,
    pretty_log_global_exit,
    pretty_log_execution,
    Ansi,
)


def test_pretty_log_dashboard_normal_and_compact(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    results = {
        "XAUUSD": {
            "decision": "BUY",
            "signal": {"winprob": 0.7},
            "confidence": 0.8,
            "regime": "Bull",
            "votes": {"rule": {"threshold": 0.65, "num_entries": 3}},
        },
        "BTCUSD": {
            "decision": "SELL",
            "signal": {"winprob": 0.4},
            "confidence": 0.5,
            "regime": "Bear",
            "votes": {"rule": {"threshold": 0.45, "num_entries": 2}},
        },
    }

    # normal mode
    pretty_log_dashboard(
        balance=10000.0,
        equity=10250.0,
        pnl=250.0,
        margin_level=500.0,
        lots=1.2,
        results=results,
        symbols_cfg={},
        compact=False,
    )

    # compact mode
    pretty_log_dashboard(
        balance=10000.0,
        equity=10250.0,
        pnl=250.0,
        margin_level=500.0,
        lots=1.2,
        results=results,
        symbols_cfg={},
        compact=True,
    )

    captured = capsys.readouterr()
    out = captured.out

    assert "Dashboard" in out
    assert "Balance=10000.00" in out
    assert "Equity=10250.00" in out
    assert "XAUUSD" in out
    assert "BTCUSD" in out

    records = [r.message for r in caplog.records if r.name == "PrettyLog"]
    assert any("Dashboard" in r for r in records)
    assert any("XAUUSD" in r for r in records)
    assert any("BTCUSD" in r for r in records)


def test_pretty_log_global_entry_exit(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    # Global entry allowed + blocked
    pretty_log_global_entry("XAUUSD", reasons="Risk OK", allowed=True)
    pretty_log_global_entry("BTCUSD", reasons="Spread too high", allowed=False)

    # Global exit triggered + normal
    pretty_log_global_exit("StopLoss triggered", triggered=True)
    pretty_log_global_exit("TakeProfit reached", triggered=True)
    pretty_log_global_exit("Daily Reset", triggered=False)

    captured = capsys.readouterr()
    out = captured.out

    assert "GlobalEntry" in out
    assert "Allowed" in out
    assert "Blocked" in out
    assert "GlobalExit" in out
    assert "StopLoss" in out or "Stoploss" in out
    assert "TakeProfit" in out or "Takeprofit" in out
    assert "Daily Reset" in out

    records = [r.message for r in caplog.records if r.name == "PrettyLog"]
    assert any("GlobalEntry" in r for r in records)
    assert any("GlobalExit" in r for r in records)


@pytest.mark.parametrize("allowed", [True, False])
def test_pretty_log_execution(capsys, caplog, allowed):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    if allowed:
        pretty_log_execution("XAUUSD", decision="BUY", allowed=True)
    else:
        pretty_log_execution("BTCUSD", decision="SELL", allowed=False, blocker="RiskGuard", reasons="Max loss hit")

    captured = capsys.readouterr()
    out = captured.out

    assert "Execution" in out
    if allowed:
        assert "ALLOWED" in out
        assert "BUY" in out
    else:
        assert "BLOCKED" in out
        assert "SELL" in out
        assert "RiskGuard" in out

    records = [r.message for r in caplog.records if r.name == "PrettyLog"]
    assert any("Execution" in r for r in records)
