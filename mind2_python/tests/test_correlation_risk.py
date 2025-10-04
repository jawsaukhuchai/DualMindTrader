import pytest
from mind2_python.correlation_risk import CorrelationRisk


def test_check_no_entries():
    corr = CorrelationRisk()
    ok, reason = corr.check()
    assert ok is True
    assert reason == "corr_ok"


def test_check_single_symbol():
    corr = CorrelationRisk()
    corr.update("BTCUSDc", 1.0)
    ok, reason = corr.check()
    assert ok is True
    assert reason == "corr_ok"


def test_check_both_symbols_block():
    corr = CorrelationRisk()
    corr.update("BTCUSDc", 1.0)
    corr.update("XAUUSDc", 2.0)
    ok, reason = corr.check()
    assert ok is False
    assert "corr_blocked" in reason
