import pytest
import sys
import types
import time
from mind2_python.global_manager import (
    GlobalEntryManager,
    GlobalExitManager,
    GlobalPnLGuard,
    KillSwitchManager,
)


# ----------------------------------------------------------------------
# GlobalEntryManager targeted tests (cover every return path)
# ----------------------------------------------------------------------
def test_entry_manager_balance_invalid_path():
    gm = GlobalEntryManager()
    ok, reasons = gm.check({"balance": 0, "equity": 0}, {})
    assert not ok
    assert reasons == ["balance_invalid"]


def test_entry_manager_symbol_blocked_path():
    gm = GlobalEntryManager()
    acc_info = {"balance": 1000, "equity": 1000}
    open_pos = {"symbol": "EURUSD"}
    ok, reasons = gm.check(acc_info, open_pos)
    assert not ok
    assert reasons == ["symbol_blocked(EURUSD)"]


def test_entry_manager_equity_low_path():
    gm = GlobalEntryManager(config={"global": {"min_equity_pct": 80}})
    acc_info = {"balance": 1000, "equity": 700}
    ok, reasons = gm.check(acc_info, {"symbol": "BTCUSDc"})
    assert not ok
    assert reasons[0].startswith("entry_blocked_equity_low")


def test_entry_manager_lots_exceed_path():
    gm = GlobalEntryManager(config={"global": {"max_lots_pct": 1}})
    acc_info = {"balance": 1000, "equity": 1000}
    open_pos = {"symbol": "BTCUSDc", "lots_local": 20.0}
    ok, reasons = gm.check(acc_info, open_pos)
    assert not ok
    assert reasons[0].startswith("entry_blocked_lots_exceed")


# ----------------------------------------------------------------------
# GlobalExitManager targeted tests (cover each exit return)
# ----------------------------------------------------------------------
def test_exit_manager_drawdown_exit():
    gm = GlobalExitManager(config={"global": {"max_drawdown_pct": 10}})
    acc_info = {"balance": 1000, "equity": 800}  # dd=20%
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert stop
    assert reason.startswith("drawdown_exceed")
    assert reasons == ["dd_exceed"]


def test_exit_manager_daily_target_exit():
    gm = GlobalExitManager(config={"global": {"daily_target_pct": 5}})
    acc_info = {"balance": 1000, "equity": 1100}
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert stop
    assert reason.startswith("daily_target_hit")
    assert reasons == ["daily_target_hit"]


def test_exit_manager_pnl_guard_exit():
    gm = GlobalExitManager(config={"global": {"max_daily_loss_abs": 50}})
    acc_info = {"balance": 1000, "equity": 900}
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=-100)
    assert stop
    assert "pnl_guard_blocked" in reasons


def test_exit_manager_equity_normal_exit():
    gm = GlobalExitManager()
    acc_info = {"balance": 1000, "equity": 1000}
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert not stop
    assert reason == "equity_normal"
    assert "equity_ok" in reasons


# ----------------------------------------------------------------------
# GlobalExitManager.force_exit_all targeted tests (_instance branches)
# ----------------------------------------------------------------------
def test_force_exit_all_with_instance_callable(monkeypatch):
    gm = GlobalExitManager(config={})
    closed = {}

    class DummyPM:
        @classmethod
        def get_open_positions_summary(cls):
            return {"BTCUSDc": "pos"}

        @classmethod
        def _instance(cls):
            class Inst:
                def __init__(self):
                    self.state = {"positions": {"BTCUSDc": "pos"}}
            return Inst()

    sys.modules["mind2_python.position_manager"] = types.SimpleNamespace(PositionManager=DummyPM)

    class DummyExecutor:
        def close_all(self):
            closed["exec"] = True

    gm.force_exit_all(DummyExecutor())
    assert "exec" in closed  # executor called


def test_force_exit_all_with_instance_attribute(monkeypatch):
    gm = GlobalExitManager(config={})
    closed = {}

    class Inst:
        def __init__(self):
            self.state = {"positions": {"XAUUSDc": "pos"}}

    class DummyPM:
        @classmethod
        def get_open_positions_summary(cls):
            return {"XAUUSDc": "pos"}

    DummyPM._instance = Inst()  # instance attribute
    sys.modules["mind2_python.position_manager"] = types.SimpleNamespace(PositionManager=DummyPM)

    class DummyExecutor:
        def close_all(self):
            closed["exec"] = True

    gm.force_exit_all(DummyExecutor())
    assert "exec" in closed
    assert DummyPM._instance.state["positions"] == {}


# ----------------------------------------------------------------------
# KillSwitchManager targeted tests
# ----------------------------------------------------------------------
def test_killswitch_trigger_and_is_triggered():
    ks = KillSwitchManager(config={"global": {"killswitch_dd_limit_pct": 1}})
    now = time.time()
    ks.check(100, now=now)
    stop, reason = ks.check(50, now=now + 1)
    assert stop
    KillSwitchManager.trigger("manual")
    assert KillSwitchManager.is_triggered()


def test_killswitch_reset_class_clears_state():
    KillSwitchManager.trigger("manual")
    assert KillSwitchManager.is_triggered()
    KillSwitchManager.reset_class()
    assert not KillSwitchManager.is_triggered()
