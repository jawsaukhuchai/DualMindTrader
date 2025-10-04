import pytest
from datetime import datetime, timedelta

from mind2_python.risk_guard import RiskGuard
from mind2_python.position_manager import PositionManager


def make_riskguard(cfg=None):
    """helper สำหรับสร้าง RiskGuard พร้อม config พื้นฐาน"""
    config = {
        "symbols": {
            "BTCUSDc": {
                "risk": {
                    "max_orders": 1,
                    "max_daily_loss_pct": 5,
                    "cooldown_minutes": 15,
                }
            }
        }
    }
    if cfg:
        config["symbols"]["BTCUSDc"]["risk"].update(cfg)
    return RiskGuard(config)


# ----------------------------------------------------------------------
# Max orders cases
# ----------------------------------------------------------------------
def test_max_orders_block(monkeypatch):
    rg = make_riskguard()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 5)

    ok, reasons = rg.check("BTCUSDc", balance=10000)
    assert not ok
    assert any("orders_blocked" in r for r in reasons)


def test_max_orders_override_replace(monkeypatch):
    rg = make_riskguard()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 5)
    monkeypatch.setattr(PositionManager, "get_open_positions", lambda _: [{"ticket": 111, "profit": -10}])
    monkeypatch.setattr(PositionManager, "close_position", lambda *a, **k: True)

    ok, reasons = rg.check("BTCUSDc", balance=10000, global_reversal=True)
    assert ok
    assert any("override_replace" in r for r in reasons)


def test_max_orders_override_allowed_no_replace(monkeypatch):
    rg = make_riskguard()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 5)
    monkeypatch.setattr(PositionManager, "get_open_positions", lambda _: [])

    ok, reasons = rg.check("BTCUSDc", balance=10000, global_reversal=True)
    assert ok
    assert "override_allowed(no_replace)" in reasons


# ----------------------------------------------------------------------
# Balance / Loss cases
# ----------------------------------------------------------------------
def test_balance_blocked(monkeypatch):
    rg = make_riskguard()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)
    ok, reasons = rg.check("BTCUSDc", balance=0)
    assert not ok
    assert "balance_blocked" in reasons


def test_loss_blocked(monkeypatch):
    rg = make_riskguard({"max_daily_loss_pct": 1})
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)
    rg.state["daily_loss"] = -200  # loss เกิน limit
    ok, reasons = rg.check("BTCUSDc", balance=1000)
    assert not ok
    assert any("loss_blocked" in r for r in reasons)


# ----------------------------------------------------------------------
# Cooldown cases
# ----------------------------------------------------------------------
def test_cooldown_blocked_and_override(monkeypatch):
    rg = make_riskguard()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)

    # last_sl เพิ่งเกิด -> cooldown
    rg.state["last_sl_hit"]["BTCUSDc"] = datetime.utcnow()

    ok, reasons = rg.check("BTCUSDc", balance=10000)
    assert not ok
    assert "cooldown_blocked" in reasons

    ok, reasons = rg.check("BTCUSDc", balance=10000, global_reversal=True)
    assert ok
    assert "cooldown_override" in reasons


# ----------------------------------------------------------------------
# Allowed path
# ----------------------------------------------------------------------
def test_allowed_path(monkeypatch):
    rg = make_riskguard()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)

    ok, reasons = rg.check("BTCUSDc", balance=10000)
    assert ok
    assert "orders_ok" in reasons
    assert "balance_ok" in reasons
    assert "loss_ok" in reasons
    assert "cooldown_ok" in reasons


# ----------------------------------------------------------------------
# Allow() wrapper logging
# ----------------------------------------------------------------------
class DummyEntry:
    def __init__(self, symbol="BTCUSDc"):
        self.symbol = symbol


def test_allow_blocked(monkeypatch, caplog):
    rg = make_riskguard()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 5)
    entry = DummyEntry()
    ok, reasons = rg.allow(entry, {"decision": "BUY", "lot": 0.1})
    assert not ok
    assert any("orders_blocked" in r for r in reasons)


def test_allow_override(monkeypatch, caplog):
    rg = make_riskguard()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 5)
    monkeypatch.setattr(PositionManager, "get_open_positions", lambda _: [{"ticket": 1, "profit": -50}])
    monkeypatch.setattr(PositionManager, "close_position", lambda *a, **k: True)
    entry = DummyEntry()
    ok, reasons = rg.allow(entry, {"decision": "BUY", "lot": 0.1, "global_reversal": True})
    assert ok
    assert any("override_replace" in r for r in reasons)


def test_allow_allowed(monkeypatch, caplog):
    rg = make_riskguard()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)
    entry = DummyEntry()
    ok, reasons = rg.allow(entry, {"decision": "BUY", "lot": 0.1})
    assert ok
    assert "orders_ok" in reasons


# ----------------------------------------------------------------------
# State management helpers
# ----------------------------------------------------------------------
def test_register_order_and_loss_and_trade():
    rg = make_riskguard()
    rg.register_order("BTCUSDc")
    assert rg.state["orders_count"]["BTCUSDc"] == 1

    rg.register_loss("BTCUSDc", -50)
    assert rg.state["daily_loss"] < 0
    assert "BTCUSDc" in rg.state["last_sl_hit"]

    rg.record_trade("BTCUSDc", -100)
    # daily_loss ต้องลดลงเพิ่ม
    assert rg.state["daily_loss"] < -50
    assert rg.state["orders_count"]["BTCUSDc"] >= 2
