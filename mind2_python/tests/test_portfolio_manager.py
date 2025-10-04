import pytest
import time

from mind2_python.portfolio_manager import PortfolioManager
from mind2_python.position_manager import PositionManager


class DummyEntry:
    def __init__(self, symbol="BTCUSDc"):
        self.symbol = symbol


def make_pm(cfg=None):
    config = {
        "symbols": {
            "BTCUSDc": {
                "portfolio": {
                    "max_risk_pct": 1,   # 1% ของ balance
                    "max_orders": 1,
                }
            }
        },
        "global": {
            "max_orders_total": 2,
            "cooldown_seconds": 10,
            "correlation_risk": {},
        },
    }
    if cfg:
        config["symbols"]["BTCUSDc"]["portfolio"].update(cfg)
    return PortfolioManager(config)


# ----------------------------------------------------------------------
# Account info
# ----------------------------------------------------------------------
def test_get_account_info_success(monkeypatch):
    monkeypatch.setattr(
        PositionManager,
        "get_health",
        lambda: {"balance": 2000, "equity": 2100, "margin": 50, "margin_level": 200},
    )
    pm = make_pm()
    info = pm._get_account_info()
    assert info["balance"] == 2000
    assert info["equity"] == 2100


def test_get_account_info_fail(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_health", lambda: None)
    pm = make_pm()
    info = pm._get_account_info()
    assert info["balance"] == 1e6


# ----------------------------------------------------------------------
# Risk checks
# ----------------------------------------------------------------------
def test_risk_blocked(monkeypatch):
    pm = make_pm({"max_risk_pct": 0.1})  # 0.1% -> max 10%
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)
    lot, reasons = pm.check("BTCUSDc", lot=2000, balance=10000)  # 20% > 10%
    assert lot == 0
    assert any("risk_blocked" in r for r in reasons)


def test_risk_override(monkeypatch):
    pm = make_pm({"max_risk_pct": 0.1})
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)
    lot, reasons = pm.check("BTCUSDc", lot=2000, balance=10000, global_reversal=True)
    assert lot == 2000
    assert any("risk_override" in r for r in reasons)


# ----------------------------------------------------------------------
# Orders per symbol
# ----------------------------------------------------------------------
def test_orders_blocked(monkeypatch):
    pm = make_pm()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 5)
    lot, reasons = pm.check("BTCUSDc", lot=0.1, balance=10000)
    assert lot == 0
    assert any("orders_blocked" in r for r in reasons)


def test_orders_override(monkeypatch):
    pm = make_pm()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 5)
    lot, reasons = pm.check("BTCUSDc", lot=0.1, balance=10000, global_reversal=True)
    assert lot > 0
    assert any("orders_override" in r for r in reasons)


# ----------------------------------------------------------------------
# Global orders total
# ----------------------------------------------------------------------
def test_global_orders_blocked(monkeypatch):
    pm = make_pm()
    pm.config["global"]["max_orders_total"] = 2

    # ✅ ให้ BTCUSDc = 0 จะไม่ติด orders_blocked, ส่วน symbol อื่น = 5
    def fake_count(symbol):
        if symbol == "BTCUSDc":
            return 0
        return 5

    monkeypatch.setattr(PositionManager, "count_open_positions", fake_count)

    open_positions = {"BTCUSDc": [1], "XAUUSDc": [1]}

    lot, reasons = pm.check(
        "BTCUSDc",
        lot=0.1,
        balance=10000,
        open_positions=open_positions,
    )
    assert lot == 0
    assert any("global_orders_blocked" in r for r in reasons)


def test_global_orders_override(monkeypatch):
    pm = make_pm()
    pm.config["global"]["max_orders_total"] = 2
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda symbol: 5)

    open_positions = {"BTCUSDc": [1], "XAUUSDc": [1]}

    lot, reasons = pm.check(
        "BTCUSDc",
        lot=0.1,
        balance=10000,
        open_positions=open_positions,
        global_reversal=True,
    )
    assert lot == 0.1
    assert any("global_orders_override" in r for r in reasons)


def test_global_orders_ok(monkeypatch):
    pm = make_pm()
    pm.config["global"]["max_orders_total"] = 10

    # ✅ mock ให้ per-symbol open = 0 → จะไม่ติด orders_blocked
    def fake_count(symbol):
        if symbol == "BTCUSDc":
            return 0
        return 1

    monkeypatch.setattr(PositionManager, "count_open_positions", fake_count)

    open_positions = {"BTCUSDc": [1]}

    lot, reasons = pm.check(
        "BTCUSDc",
        lot=0.1,
        balance=10000,
        open_positions=open_positions,
    )
    assert lot == 0.1
    assert any("global_orders_ok" in r for r in reasons)


# ----------------------------------------------------------------------
# Cooldown
# ----------------------------------------------------------------------
def test_cooldown_blocked(monkeypatch):
    pm = make_pm()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)
    pm.register_entry("BTCUSDc")  # set last_entry_time
    lot, reasons = pm.check("BTCUSDc", lot=0.1, balance=10000)
    assert lot == 0
    assert any("cooldown_blocked" in r for r in reasons)


def test_cooldown_override(monkeypatch):
    pm = make_pm()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)
    pm.register_entry("BTCUSDc")
    lot, reasons = pm.check("BTCUSDc", lot=0.1, balance=10000, global_reversal=True)
    assert lot > 0
    assert any("cooldown_override" in r for r in reasons)


# ----------------------------------------------------------------------
# Correlation risk
# ----------------------------------------------------------------------
def test_corr_risk_blocked(monkeypatch):
    pm = make_pm()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)

    class FakeCorr:
        def update(self, symbol, entry): ...
        def check(self): return (False, "corr_blocked_mock")

    pm.corr_risk = FakeCorr()
    lot, reasons = pm.check("BTCUSDc", lot=0.1, balance=10000)
    assert lot == 0
    assert "corr_blocked_mock" in reasons


# ----------------------------------------------------------------------
# Allowed path
# ----------------------------------------------------------------------
def test_allowed(monkeypatch):
    pm = make_pm()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)

    class FakeCorr:
        def update(self, symbol, entry): ...
        def check(self): return (True, "corr_ok")

    pm.corr_risk = FakeCorr()
    lot, reasons = pm.check("BTCUSDc", lot=0.1, balance=10000)
    assert lot == 0.1
    assert "allowed" in reasons


# ----------------------------------------------------------------------
# Allow() wrapper
# ----------------------------------------------------------------------
def test_allow_blocked(monkeypatch, caplog):
    pm = make_pm()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 5)
    entry = DummyEntry()
    ok, reasons = pm.allow(entry, {"lot": 0.1, "decision": "BUY"})
    assert not ok
    assert any("orders_blocked" in r for r in reasons)


def test_allow_override(monkeypatch):
    pm = make_pm()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 5)
    entry = DummyEntry()
    ok, reasons = pm.allow(entry, {"lot": 0.1, "decision": "BUY", "global_reversal": True})
    assert ok
    assert any("orders_override" in r for r in reasons)


def test_allow_allowed(monkeypatch):
    pm = make_pm()
    monkeypatch.setattr(PositionManager, "count_open_positions", lambda _: 0)
    entry = DummyEntry()
    ok, reasons = pm.allow(entry, {"lot": 0.1, "decision": "BUY"})
    assert ok
    assert "allowed" in reasons
