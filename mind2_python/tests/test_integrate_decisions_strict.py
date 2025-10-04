import pytest
import mind2_python.integrate_decisions as integ


def test_unknown_decision_value(monkeypatch):
    # force unknown decision
    decisions = {"scalp": "???", "day": "BUY", "swing": "SELL"}
    result = integ.integrate_decisions(
        decisions,
        mode="majority",
        weights={"scalp": 1, "day": 1, "swing": 1},
    )
    # unknown → fallback HOLD
    assert isinstance(result, dict)
    assert result["decision"] == "HOLD"


def test_unknown_mode(monkeypatch):
    # force unknown integration mode
    decisions = {"scalp": "BUY", "day": "BUY", "swing": "SELL"}
    result = integ.integrate_decisions(
        decisions,
        mode="mystery",  # ไม่รู้จัก
        weights={"scalp": 1, "day": 1, "swing": 1},
    )
    assert isinstance(result, dict)
    assert result["decision"] == "HOLD"


def test_priority_mode_no_match(monkeypatch):
    # priority mode แต่ไม่มี priority_decision match
    decisions = {"scalp": "BUY", "day": "SELL", "swing": "HOLD"}
    result = integ.integrate_decisions(
        decisions,
        mode="priority",
        weights={"xxx": 1, "yyy": 2},  # ไม่มี key ตรง
    )
    assert isinstance(result, dict)
    assert result["decision"] == "HOLD"


def test_default_fallback(monkeypatch):
    # default return fallback
    decisions = {}
    result = integ.integrate_decisions(
        decisions,
        mode="majority",
        weights={},
    )
    assert isinstance(result, dict)
    assert result["decision"] == "HOLD"
