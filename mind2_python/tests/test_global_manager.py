import pytest
import sys
import types
import time
from mind2_python.global_manager import (
    GlobalEntryManager,
    GlobalExitManager,
    GlobalPnLGuard,
    KillSwitchManager,
    log_global_dashboard,
    ALLOWED_SYMBOLS,
)


# ================================================================
#  GlobalEntryManager tests
# ================================================================
def test_entry_balance_invalid_none():
    gm = GlobalEntryManager()
    ok, reasons = gm.check({"balance": None, "equity": None}, {})
    assert not ok
    assert reasons == ["balance_invalid"]


def test_entry_symbol_blocked_isolated():
    gm = GlobalEntryManager()
    acc_info = {"balance": 1000, "equity": 1000}
    open_pos = {"symbol": "EURUSD"}
    ok, reasons = gm.check(acc_info, open_pos)
    assert not ok
    assert reasons == ["symbol_blocked(EURUSD)"]


def test_entry_equity_low_isolated():
    gm = GlobalEntryManager(config={"global": {"min_equity_pct": 80}})
    acc_info = {"balance": 1000, "equity": 400}
    ok, reasons = gm.check(acc_info, {"symbol": "BTCUSDc"})
    assert not ok
    assert reasons[0].startswith("entry_blocked_equity_low")


def test_entry_lots_exceed_isolated():
    gm = GlobalEntryManager(config={"global": {"max_lots_pct": 1}})
    acc_info = {"balance": 1000, "equity": 1000}
    open_pos = {"symbol": "BTCUSDc", "lots_local": 200.0}
    ok, reasons = gm.check(acc_info, open_pos)
    assert not ok
    assert reasons[0].startswith("entry_blocked_lots_exceed")


def test_entry_lots_ok_zero():
    gm = GlobalEntryManager()
    acc_info = {"balance": 1000, "equity": 1000}
    open_pos = {"symbol": "BTCUSDc", "lots_local": 0.0, "positions_feed": 0.0}
    ok, reasons = gm.check(acc_info, open_pos)
    assert ok
    assert "lots_ok" in reasons


# ================================================================
#  GlobalPnLGuard tests
# ================================================================
def test_pnl_guard_daily_loss_pct_trigger():
    guard = GlobalPnLGuard(config={"global": {"max_daily_loss_pct": 5}})
    blocked, reason = guard.check(balance=1000, daily_loss=-100)
    assert blocked
    assert "daily_loss_pct_exceed" in reason


def test_pnl_guard_daily_loss_abs_trigger():
    guard = GlobalPnLGuard(config={"global": {"max_daily_loss_abs": 50}})
    blocked, reason = guard.check(balance=1000, daily_loss=-60)
    assert blocked
    assert "daily_loss_abs_exceed" in reason


def test_pnl_guard_ok():
    guard = GlobalPnLGuard(config={"global": {"max_daily_loss_pct": 50}})
    blocked, reason = guard.check(balance=1000, daily_loss=-10)
    assert not blocked
    assert reason == "pnl_guard_ok"


# ================================================================
#  GlobalExitManager.check_exit tests (isolate all exit paths)
# ================================================================
def test_exit_balance_zero_invalid():
    gm = GlobalExitManager()
    acc_info = {"balance": 0, "equity": 0}
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert not stop
    assert "balance_invalid" in reasons


def test_exit_equity_low_path():
    gm = GlobalExitManager(config={"global": {"min_equity_pct": 70}})
    acc_info = {"balance": 1000, "equity": 400}
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert stop
    assert reason.startswith("equity_low")


def test_exit_drawdown_exceed_path():
    gm = GlobalExitManager(config={"global": {"max_drawdown_pct": 5}})
    acc_info = {"balance": 1000, "equity": 900}  # dd=10%
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert stop
    assert reason.startswith("drawdown_exceed")


def test_exit_daily_target_hit_path():
    gm = GlobalExitManager(config={"global": {"daily_target_pct": 1}})
    acc_info = {"balance": 1000, "equity": 1100}
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert stop
    assert reason.startswith("daily_target_hit")


def test_exit_pnl_guard_blocked_path():
    gm = GlobalExitManager(config={"global": {"max_daily_loss_abs": 10}})
    acc_info = {"balance": 1000, "equity": 950}
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=-20)
    assert stop
    assert "pnl_guard_blocked" in reasons


def test_exit_equity_normal_path():
    gm = GlobalExitManager()
    acc_info = {"balance": 1000, "equity": 1000}
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert not stop
    assert reason == "equity_normal"


# ================================================================
#  GlobalExitManager.force_exit_all tests
# ================================================================
def test_force_exit_all_no_positions(caplog):
    gm = GlobalExitManager()

    class DummyPM:
        @classmethod
        def get_open_positions_summary(cls):
            return {}

    sys.modules["mind2_python.position_manager"] = types.SimpleNamespace(PositionManager=DummyPM)

    class DummyExecutor:
        def close_all(self): raise AssertionError("should not be called")

    caplog.set_level("INFO")
    gm.force_exit_all(DummyExecutor())
    assert any("No positions to close" in rec.message for rec in caplog.records)


def test_force_exit_all_instance_callable_log(caplog):
    gm = GlobalExitManager()

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
        def close_all(self): return "closed"

    caplog.set_level("WARNING")
    gm.force_exit_all(DummyExecutor())
    assert any("Forced EXIT ALL triggered" in rec.message for rec in caplog.records)


def test_force_exit_all_instance_attribute_log(caplog):
    gm = GlobalExitManager()

    class Inst:
        def __init__(self):
            self.state = {"positions": {"XAUUSDc": "pos"}}

    class DummyPM:
        @classmethod
        def get_open_positions_summary(cls):
            return {"XAUUSDc": "pos"}

    DummyPM._instance = Inst()
    sys.modules["mind2_python.position_manager"] = types.SimpleNamespace(PositionManager=DummyPM)

    class DummyExecutor:
        def close_all(self): return "closed"

    caplog.set_level("WARNING")
    gm.force_exit_all(DummyExecutor())
    assert any("Forced EXIT ALL triggered" in rec.message for rec in caplog.records)
    assert DummyPM._instance.state["positions"] == {}


def test_force_exit_all_exception_path(caplog):
    gm = GlobalExitManager()

    class DummyPM:
        @classmethod
        def get_open_positions_summary(cls):
            return {"BTCUSDc": "pos"}

    sys.modules["mind2_python.position_manager"] = types.SimpleNamespace(PositionManager=DummyPM)

    class DummyExecutor:
        def close_all(self): raise RuntimeError("executor failed")

    caplog.set_level("ERROR")
    gm.force_exit_all(DummyExecutor())
    assert any("force_exit_all failed" in rec.message for rec in caplog.records)


# ================================================================
#  KillSwitchManager tests
# ================================================================
def test_killswitch_trigger_and_reset_class():
    KillSwitchManager.trigger("manual")
    assert KillSwitchManager.is_triggered()
    KillSwitchManager.reset_class()
    assert not KillSwitchManager.is_triggered()


def test_killswitch_reset_instance_and_idempotent():
    ks = KillSwitchManager()
    KillSwitchManager.trigger("manual")
    assert KillSwitchManager.is_triggered()
    ks.reset()
    assert not KillSwitchManager.is_triggered()
    ks.reset()
    assert not KillSwitchManager.is_triggered()


def test_killswitch_disabled_branch():
    ks = KillSwitchManager(config={"global": {"killswitch_enabled": False}})
    stop, reason = ks.check(1000)
    assert not stop
    assert reason == "disabled"


# ================================================================
#  Dashboard tests
# ================================================================
def test_dashboard_allowed_symbol_and_overlay(caplog):
    acc_info = {"balance": 1000, "equity": 1100, "open_pnl": 100, "margin_level": 200}
    open_pos = {"symbol": "BTCUSDc", "lots_local": 1.0, "positions_feed": 1.0}
    results = {"BTCUSDc": {"decision": "BUY", "confidence": 0.9, "mode": "majority"}}

    caplog.set_level("INFO")
    log_global_dashboard(acc_info, open_pos, results=results,
                         regime="trend",
                         ai_res={"decision": "BUY", "confidence": 0.9},
                         rule_res={"decision": "SELL", "confidence": 0.6},
                         fusion={"decision": "HOLD", "score": 0.5})
    msgs = " ".join([rec.message for rec in caplog.records])
    assert "BTCUSDc" in msgs
    assert "Regime=trend" in msgs
    assert "AI=BUY(0.90)" in msgs
    assert "Rule=SELL(0.60)" in msgs
    assert "Fusion=HOLD(0.50)" in msgs


def test_dashboard_no_allowed_symbol_overlay(caplog):
    acc_info = {"balance": 1000, "equity": 1000}
    open_pos = {"symbol": "EURUSD"}
    results = {"EURUSD": {"decision": "SELL", "confidence": 0.2, "mode": "priority"}}

    caplog.set_level("INFO")
    log_global_dashboard(acc_info, open_pos, results=results,
                         regime="sideway",
                         ai_res={"decision": "SELL", "confidence": 0.3},
                         rule_res={"decision": "BUY", "confidence": 0.4},
                         fusion={"decision": "HOLD", "score": 0.7})
    msgs = " ".join([rec.message for rec in caplog.records])
    assert "Regime=sideway" in msgs
    assert "AI=SELL(0.30)" in msgs
    assert "Rule=BUY(0.40)" in msgs
    assert "Fusion=HOLD(0.70)" in msgs


# ================================================================
#  ALLOWED_SYMBOLS test
# ================================================================
def test_allowed_symbols_set():
    assert ALLOWED_SYMBOLS == {"BTCUSDc", "XAUUSDc"}


# ================================================================
#  Extra coverage for compat layer + register_entry
# ================================================================
def test_entry_register_entry_and_get_time(monkeypatch):
    gm = GlobalEntryManager()
    monkeypatch.setattr(time, "time", lambda: 123456.0)
    gm.register_entry()
    assert GlobalEntryManager.get_last_entry_time() == 123456.0


def test_entry_update_get_reset():
    GlobalEntryManager.reset()
    GlobalEntryManager.update("BTCUSDc", True, "ok")
    data = GlobalEntryManager.get("BTCUSDc")
    assert data == {"allowed": True, "reason": "ok"}
    GlobalEntryManager.reset()
    assert GlobalEntryManager.get("BTCUSDc") is None


def test_exitmanager_set_get_reset():
    GlobalExitManager.reset()
    GlobalExitManager.set("force_exit_triggered")
    assert GlobalExitManager.get() == "force_exit_triggered"
    GlobalExitManager.reset()
    assert GlobalExitManager.get() is None


def test_killswitch_ok_branch(monkeypatch):
    ks = KillSwitchManager(config={"global": {"killswitch_dd_limit_pct": 50}})
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    stop, reason = ks.check(1000.0)
    assert not stop
    assert reason.startswith("ok(dd=")


# ================================================================
#  Extra coverage for missing branches in global_manager.py
# ================================================================
def test_entry_symbol_none_and_positions_feed_none():
    gm = GlobalEntryManager()
    acc_info = {"balance": 1000, "equity": 1000}
    open_pos = {"lots_local": 0.0, "positions_feed": None}
    ok, reasons = gm.check(acc_info, open_pos)
    assert ok
    assert "lots_ok" in reasons


def test_exit_drawdown_and_daily_target_ok_paths():
    gm = GlobalExitManager(config={"global": {"max_drawdown_pct": 50, "daily_target_pct": 200}})
    acc_info = {"balance": 1000, "equity": 900}  # dd=10% < 50
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert not stop
    assert "dd_ok" in reasons
    assert "daily_target_ok" in reasons


def test_exitmanager_balance_and_equity_paths():
    gm = GlobalExitManager(config={"global": {"min_equity_pct": 10}})
    acc_info = {"balance": 1000, "equity": 999}
    stop, reason, reasons = gm.check_exit(acc_info, daily_loss=0)
    assert not stop
    assert reason == "equity_normal"
    assert "equity_ok" in reasons


def test_force_exit_all_clear_all_positions(monkeypatch, caplog):
    gm = GlobalExitManager()

    cleared = {}
    class DummyPM:
        @classmethod
        def get_open_positions_summary(cls):
            return {"BTCUSDc": "pos"}

        @classmethod
        def clear_all_positions(cls):
            cleared["called"] = True

    sys.modules["mind2_python.position_manager"] = types.SimpleNamespace(PositionManager=DummyPM)

    class DummyExecutor:
        def close_all(self): return "closed"

    caplog.set_level("WARNING")
    gm.force_exit_all(DummyExecutor())
    assert cleared.get("called") is True
    assert any("Forced EXIT ALL triggered" in rec.message for rec in caplog.records)


def test_exitmanager_compat_layer_set_get_reset():
    GlobalExitManager.reset()
    assert GlobalExitManager.get() is None
    GlobalExitManager.set("test_reason")
    assert GlobalExitManager.get() == "test_reason"
    GlobalExitManager.reset()
    assert GlobalExitManager.get() is None


def test_killswitchmanager_trigger_and_check_ok(monkeypatch):
    ks = KillSwitchManager(config={"global": {"killswitch_dd_limit_pct": 99}})
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    stop, reason = ks.check(1000.0)
    assert not stop
    assert reason.startswith("ok(")
    KillSwitchManager.trigger("forced")
    assert KillSwitchManager.is_triggered()
    KillSwitchManager.reset_class()
    assert not KillSwitchManager.is_triggered()


# ================================================================
#  Targeted tests for every return/exit path
# ================================================================
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
