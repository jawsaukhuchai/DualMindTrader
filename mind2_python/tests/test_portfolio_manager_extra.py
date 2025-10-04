import time
import pytest
from mind2_python.portfolio_manager import PortfolioManager, colorize_reason


class DummyEntry:
    def __init__(self, symbol="BTCUSD"):
        self.symbol = symbol
        self.entry = 1000.0
        self.exit_levels = {}
        self.open_positions = {}
        self.signal = {}
        self.global_reversal = False


@pytest.fixture(autouse=True)
def patch_position_manager(monkeypatch):
    """Patch PositionManager methods with dummy versions"""
    monkeypatch.setattr(
        "mind2_python.portfolio_manager.PositionManager.get_health",
        staticmethod(lambda: {"balance": 1000, "equity": 1000, "margin_level": 5000}),
    )
    monkeypatch.setattr(
        "mind2_python.portfolio_manager.PositionManager.count_open_positions",
        staticmethod(lambda symbol=None: 0),
    )
    yield


def make_pm(cfg=None, monkeypatch=None, corr_ok=True):
    """Helper to create PortfolioManager with mocked CorrelationRisk"""
    pm = PortfolioManager(cfg or {"symbols": {"BTCUSD": {"portfolio": {}}}})
    if monkeypatch:
        monkeypatch.setattr(
            pm.corr_risk, "check", lambda: (corr_ok, "corr_ok" if corr_ok else "corr_blocked")
        )
    return pm


# ----------------------------------------------------------
# Tests
# ----------------------------------------------------------

def test_risk_blocked(monkeypatch):
    pm = make_pm(monkeypatch=monkeypatch)
    lot, reasons = pm.check("BTCUSD", lot=10000.0)
    assert lot == 0.0
    assert any("risk_blocked" in r for r in reasons)


def test_risk_override(monkeypatch):
    pm = make_pm(monkeypatch=monkeypatch)
    lot, reasons = pm.check("BTCUSD", lot=10000.0, global_reversal=True)
    assert lot == 10000.0
    assert any("risk_override" in r for r in reasons)


def test_orders_blocked(monkeypatch):
    monkeypatch.setattr(
        "mind2_python.portfolio_manager.PositionManager.count_open_positions",
        staticmethod(lambda symbol=None: 5),
    )
    cfg = {"symbols": {"BTCUSD": {"portfolio": {"max_orders": 1}}}}
    pm = make_pm(cfg=cfg, monkeypatch=monkeypatch)
    lot, reasons = pm.check("BTCUSD", lot=0.1)
    assert lot == 0.0
    assert any("orders_blocked" in r for r in reasons)


def test_orders_override(monkeypatch):
    monkeypatch.setattr(
        "mind2_python.portfolio_manager.PositionManager.count_open_positions",
        staticmethod(lambda symbol=None: 5),
    )
    cfg = {"symbols": {"BTCUSD": {"portfolio": {"max_orders": 1}}}}
    pm = make_pm(cfg=cfg, monkeypatch=monkeypatch)
    lot, reasons = pm.check("BTCUSD", lot=0.1, global_reversal=True)
    assert lot == 0.1
    assert any("orders_override" in r for r in reasons)


def test_global_orders_blocked(monkeypatch):
    # ให้ count_open_positions return 5 → total_open จะเยอะ
    monkeypatch.setattr(
        "mind2_python.portfolio_manager.PositionManager.count_open_positions",
        staticmethod(lambda symbol=None: 5),
    )
    cfg = {
        "symbols": {"BTCUSD": {"portfolio": {"max_orders": 999}}},
        "global": {"max_orders_total": 3},
    }
    pm = make_pm(cfg=cfg, monkeypatch=monkeypatch)
    # ส่ง open_positions หลายตัวเพื่อให้ loop รวม
    lot, reasons = pm.check("BTCUSD", lot=0.1, open_positions={"BTCUSD": 1, "XAUUSD": 1})
    assert lot == 0.0
    assert any("global_orders_blocked" in r for r in reasons), reasons


def test_global_orders_override(monkeypatch):
    monkeypatch.setattr(
        "mind2_python.portfolio_manager.PositionManager.count_open_positions",
        staticmethod(lambda symbol=None: 5),
    )
    cfg = {"symbols": {"BTCUSD": {"portfolio": {}}}, "global": {"max_orders_total": 1}}
    pm = make_pm(cfg=cfg, monkeypatch=monkeypatch)
    lot, reasons = pm.check(
        "BTCUSD", lot=0.1, open_positions={"BTCUSD": 123}, global_reversal=True
    )
    assert lot == 0.1
    assert any("global_orders_override" in r for r in reasons)


def test_cooldown_blocked(monkeypatch):
    cfg = {"symbols": {"BTCUSD": {"portfolio": {}}}, "global": {"cooldown_seconds": 60}}
    pm = make_pm(cfg=cfg, monkeypatch=monkeypatch)
    pm.last_entry_time["GLOBAL"] = time.time()
    lot, reasons = pm.check("BTCUSD", lot=0.1)
    assert lot == 0.0
    assert any("cooldown_blocked" in r for r in reasons)


def test_cooldown_override(monkeypatch):
    cfg = {"symbols": {"BTCUSD": {"portfolio": {}}}, "global": {"cooldown_seconds": 60}}
    pm = make_pm(cfg=cfg, monkeypatch=monkeypatch)
    pm.last_entry_time["GLOBAL"] = time.time()
    lot, reasons = pm.check("BTCUSD", lot=0.1, global_reversal=True)
    assert lot == 0.1
    assert any("cooldown_override" in r for r in reasons)


def test_correlation_blocked(monkeypatch):
    pm = make_pm(monkeypatch=monkeypatch, corr_ok=False)
    lot, reasons = pm.check("BTCUSD", lot=0.1)
    assert lot == 0.0
    assert "corr_blocked" in reasons


def test_allow_blocked_and_allowed(monkeypatch):
    pm = make_pm(monkeypatch=monkeypatch)
    entry = DummyEntry("BTCUSD")

    # blocked case: lot ใหญ่พอให้ risk_blocked
    monkeypatch.setattr(
        "mind2_python.portfolio_manager.PositionManager.get_health",
        staticmethod(lambda: {"balance": 1000, "equity": 1000, "margin_level": 5000}),
    )
    ok, reasons = pm.allow(entry, {"lot": 10000.0, "decision": "BUY"})
    assert not ok
    assert any("risk_blocked" in r for r in reasons)

    # allowed case: lot เล็ก
    ok, reasons = pm.allow(entry, {"lot": 0.1, "decision": "BUY"})
    assert ok
    assert "allowed" in reasons


def test_colorize_reason_variants():
    assert "\033[31m" in colorize_reason("risk_blocked")
    assert "\033[32m" in colorize_reason("risk_ok")
    assert "\033[33m" in colorize_reason("rotation_low")
    assert "\033[90m" in colorize_reason("something_else")
