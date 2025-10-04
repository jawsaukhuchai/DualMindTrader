import time
import sys
import pytest

import mind2_python.global_manager as gm
from mind2_python.global_manager import (
    GlobalEntryManager,
    GlobalExitManager,
    GlobalPnLGuard,
    KillSwitchManager,
)


# -------------------------------------------------------------------
# GlobalEntryManager tests
# -------------------------------------------------------------------

def test_entry_balance_invalid():
    m = GlobalEntryManager()
    ok, reasons = m.check({"balance": 0, "equity": 0}, {})
    assert not ok
    assert "balance_invalid" in reasons


def test_entry_symbol_blocked():
    m = GlobalEntryManager()
    acc = {"balance": 1000, "equity": 1000}
    open_pos = {"symbol": "EURUSDc"}
    ok, reasons = m.check(acc, open_pos)
    assert not ok
    assert "symbol_blocked" in reasons[0]


def test_entry_equity_low():
    m = GlobalEntryManager({"global": {"min_equity_pct": 80}})
    acc = {"balance": 1000, "equity": 100}
    ok, reasons = m.check(acc, {"symbol": "BTCUSDc"})
    assert not ok
    assert "entry_blocked_equity_low" in reasons[0]


def test_entry_lots_exceed():
    m = GlobalEntryManager({"global": {"max_lots_pct": 1}})
    acc = {"balance": 1000, "equity": 1000}
    open_pos = {"symbol": "BTCUSDc", "lots_local": 20, "positions_feed": 0}
    ok, reasons = m.check(acc, open_pos)
    assert not ok
    assert "entry_blocked_lots_exceed" in reasons[0]


def test_entry_ok_and_register_time():
    m = GlobalEntryManager()
    acc = {"balance": 1000, "equity": 1000}
    open_pos = {"symbol": "BTCUSDc", "lots_local": 0, "positions_feed": 0}
    ok, reasons = m.check(acc, open_pos)
    assert ok
    assert "equity_ok" in reasons
    m.register_entry()
    assert GlobalEntryManager.get_last_entry_time() is not None


def test_entry_open_positions_not_dict():
    m = GlobalEntryManager()
    acc = {"balance": 1000, "equity": 1000}
    ok, reasons = m.check(acc, "notadict")
    assert ok
    assert "lots_ok" in reasons


# -------------------------------------------------------------------
# GlobalPnLGuard tests
# -------------------------------------------------------------------

def test_pnl_guard_balance_invalid():
    g = GlobalPnLGuard()
    blocked, reason = g.check(0, -10)
    assert blocked and reason == "balance_invalid"


def test_pnl_guard_daily_loss_pct_exceed():
    g = GlobalPnLGuard({"global": {"max_daily_loss_pct": 1}})
    blocked, reason = g.check(1000, -50)
    assert blocked and "daily_loss_pct_exceed" in reason


def test_pnl_guard_daily_loss_abs_exceed():
    g = GlobalPnLGuard({"global": {"max_daily_loss_abs": 10}})
    blocked, reason = g.check(1000, -20)
    assert blocked and "daily_loss_abs_exceed" in reason


def test_pnl_guard_ok():
    g = GlobalPnLGuard({"global": {"max_daily_loss_pct": 10, "max_daily_loss_abs": 100}})
    blocked, reason = g.check(1000, -20)
    assert not blocked and reason == "pnl_guard_ok"


# -------------------------------------------------------------------
# GlobalExitManager tests
# -------------------------------------------------------------------

def test_exit_balance_invalid():
    m = GlobalExitManager()
    ok, reason, details = m.check_exit({"balance": 0, "equity": 0})
    assert not ok and "balance_invalid" in details


def test_exit_equity_low():
    m = GlobalExitManager({"global": {"min_equity_pct": 80}})
    ok, reason, details = m.check_exit({"balance": 1000, "equity": 100})
    assert ok and "equity_low" in details


def test_exit_drawdown_exceed():
    m = GlobalExitManager({"global": {"max_drawdown_pct": 10, "min_equity_pct": 0}})
    ok, reason, details = m.check_exit({"balance": 1000, "equity": 100})
    assert ok and "drawdown_exceed" in reason


def test_exit_daily_target_hit():
    m = GlobalExitManager({"global": {"daily_target_pct": 1}})
    ok, reason, details = m.check_exit({"balance": 1000, "equity": 1100})
    assert ok and "daily_target_hit" in details


def test_exit_pnl_guard_blocked():
    m = GlobalExitManager({"global": {"max_daily_loss_abs": 10}})
    ok, reason, details = m.check_exit({"balance": 1000, "equity": 1000}, daily_loss=-20)
    assert ok and "pnl_guard_blocked" in details


def test_exit_equity_normal():
    m = GlobalExitManager()
    ok, reason, details = m.check_exit({"balance": 1000, "equity": 1000})
    assert not ok and reason == "equity_normal"


class DummyExecutor:
    def __init__(self):
        self.closed = False

    def close_all(self):
        self.closed = True


def test_force_exit_all_no_positions(monkeypatch):
    class DummyPos:
        @staticmethod
        def get_open_positions_summary():
            return []

    monkeypatch.setitem(sys.modules, "mind2_python.position_manager", type("pm", (), {"PositionManager": DummyPos}))
    m = GlobalExitManager()
    executor = DummyExecutor()
    m.force_exit_all(executor)
    assert not executor.closed


def test_force_exit_all_with_positions(monkeypatch):
    called = {}

    class DummyPos:
        @staticmethod
        def get_open_positions_summary():
            return [1]

        @staticmethod
        def clear_all_positions():
            called["cleared"] = True

    monkeypatch.setitem(sys.modules, "mind2_python.position_manager", type("pm", (), {"PositionManager": DummyPos}))
    m = GlobalExitManager()
    executor = DummyExecutor()
    m.force_exit_all(executor)
    assert executor.closed
    assert "cleared" in called


def test_force_exit_all_with_clear_all_positions_only(monkeypatch):
    """ครอบกรณีมี clear_all_positions แต่ไม่มี _instance → branch 163 exit (True)"""
    called = {}

    class DummyPM:
        @staticmethod
        def get_open_positions_summary():
            return {"BTCUSDc": "pos"}

        @staticmethod
        def clear_all_positions():
            called["cleared"] = True

    if hasattr(DummyPM, "_instance"):
        delattr(DummyPM, "_instance")

    monkeypatch.setitem(
        sys.modules,
        "mind2_python.position_manager",
        type("pm", (), {"PositionManager": DummyPM})
    )

    class DummyExecutor:
        def __init__(self): self.called = False
        def close_all(self): self.called = True

    gm_exit = GlobalExitManager()
    executor = DummyExecutor()
    gm_exit.force_exit_all(executor)

    assert executor.called
    assert "cleared" in called


def test_force_exit_all_no_clear_all_positions_and_no_instance(monkeypatch):
    """ครอบกรณีไม่มี clear_all_positions และไม่มี _instance → branch 163 exit (False)"""
    class DummyPM:
        @staticmethod
        def get_open_positions_summary():
            return {"BTCUSDc": "pos"}

    for attr in ["_instance", "clear_all_positions"]:
        if hasattr(DummyPM, attr):
            delattr(DummyPM, attr)

    monkeypatch.setitem(
        sys.modules,
        "mind2_python.position_manager",
        type("pm", (), {"PositionManager": DummyPM})
    )

    class DummyExecutor:
        def __init__(self): self.called = False
        def close_all(self): self.called = True

    gm_exit = GlobalExitManager()
    executor = DummyExecutor()
    gm_exit.force_exit_all(executor)

    assert executor.called


def test_force_exit_all_with_instance_callable(monkeypatch):
    """กรณี _instance เป็น callable"""
    class DummyInstance:
        def __init__(self):
            self.state = {"positions": {"BTCUSDc": 1}}

    class DummyPM:
        @staticmethod
        def get_open_positions_summary():
            return {"BTCUSDc": "pos"}

    inst = DummyInstance()
    DummyPM._instance = lambda: inst

    if hasattr(DummyPM, "clear_all_positions"):
        delattr(DummyPM, "clear_all_positions")

    monkeypatch.setitem(
        sys.modules,
        "mind2_python.position_manager",
        type("pm", (), {"PositionManager": DummyPM}),
    )

    class DummyExecutor:
        def __init__(self):
            self.called = False
        def close_all(self):
            self.called = True

    gm_exit = GlobalExitManager()
    executor = DummyExecutor()
    gm_exit.force_exit_all(executor)

    assert executor.called
    assert inst.state["positions"] == {}


def test_force_exit_all_instance_object_exit_flow(monkeypatch, caplog):
    """กรณี _instance เป็น object ตรง ๆ → 163/168/170 True"""
    class DummyInst:
        def __init__(self):
            self.state = {"positions": {"XAUUSDc": 5}}

    class DummyPM:
        @staticmethod
        def get_open_positions_summary():
            return {"XAUUSDc": "pos"}

    DummyPM._instance = DummyInst()

    if hasattr(DummyPM, "clear_all_positions"):
        delattr(DummyPM, "clear_all_positions")

    monkeypatch.setitem(
        sys.modules,
        "mind2_python.position_manager",
        type("pm", (), {"PositionManager": DummyPM}),
    )

    class DummyExecutor:
        def __init__(self):
            self.closed = False
        def close_all(self):
            self.closed = True

    gm_exit = GlobalExitManager()
    caplog.set_level("WARNING")
    executor = DummyExecutor()
    gm_exit.force_exit_all(executor)

    assert executor.closed
    assert DummyPM._instance.state["positions"] == {}
    assert any("Forced EXIT ALL triggered" in rec.message for rec in caplog.records)


def test_force_exit_all_instance_no_state(monkeypatch):
    """กรณี _instance ไม่มี .state → branch 168 exit"""
    class DummyInst:
        pass

    class DummyPM:
        @staticmethod
        def get_open_positions_summary():
            return {"BTCUSDc": "pos"}

    DummyPM._instance = DummyInst()
    monkeypatch.setitem(
        sys.modules, "mind2_python.position_manager",
        type("pm", (), {"PositionManager": DummyPM})
    )

    class DummyExecutor:
        def __init__(self): self.called = False
        def close_all(self): self.called = True

    gm_exit = GlobalExitManager()
    executor = DummyExecutor()
    gm_exit.force_exit_all(executor)

    assert executor.called


def test_force_exit_all_instance_positions_not_dict(monkeypatch):
    """กรณี positions ไม่ใช่ dict → branch 170 exit"""
    class DummyInst:
        def __init__(self):
            self.state = {"positions": ["notadict"]}

    class DummyPM:
        @staticmethod
        def get_open_positions_summary():
            return {"BTCUSDc": "pos"}

    DummyPM._instance = DummyInst()
    monkeypatch.setitem(
        sys.modules, "mind2_python.position_manager",
        type("pm", (), {"PositionManager": DummyPM})
    )

    class DummyExecutor:
        def __init__(self): self.called = False
        def close_all(self): self.called = True

    gm_exit = GlobalExitManager()
    executor = DummyExecutor()
    gm_exit.force_exit_all(executor)

    assert executor.called
    assert DummyPM._instance.state["positions"] == ["notadict"]


# -------------------------------------------------------------------
# KillSwitchManager tests
# -------------------------------------------------------------------

def test_killswitch_disabled():
    ks = KillSwitchManager({"global": {"killswitch_enabled": False}})
    stop, reason = ks.check(1000)
    assert not stop and reason == "disabled"


def test_killswitch_triggered(monkeypatch):
    ks = KillSwitchManager({"global": {"killswitch_dd_limit_pct": 1}})
    now = time.time()
    ks.history = [(now, 1000)]
    stop, reason = ks.check(900, now=now + 1)
    assert stop and "killswitch_triggered" in reason


def test_killswitch_ok(monkeypatch):
    ks = KillSwitchManager({"global": {"killswitch_dd_limit_pct": 50}})
    now = time.time()
    ks.history = [(now, 1000)]
    stop, reason = ks.check(990, now=now + 1)
    assert not stop and reason.startswith("ok(")


def test_killswitch_no_data_skip_append():
    ks = gm._BaseKillSwitchManager()
    ks.history.clear()
    stop, reason = ks.check(1000, now=time.time(), skip_append=True)
    assert not stop
    assert reason == "no_data"


def test_killswitch_ok_branch():
    ks = gm._BaseKillSwitchManager({"global": {"killswitch_dd_limit_pct": 50}})
    now = time.time()
    ks.history = [(now, 1000)]
    stop, reason = ks.check(990, now=now + 1)
    assert not stop
    assert reason.startswith("ok(")


# -------------------------------------------------------------------
# Dashboard tests
# -------------------------------------------------------------------

def test_dashboard_full_args(capsys):
    gm.log_global_dashboard(
        1000,
        1100,
        50,
        120.5,
        0.5,
        {"symbol": "BTCUSDc"},
        {"BTCUSDc": {"decision": "BUY", "confidence": 0.9, "mode": "scalp"}},
    )
    out = capsys.readouterr().out
    assert "Balance=1000.00" in out
    assert "BTCUSDc → BUY" in out


def test_dashboard_open_positions_not_dict_logs_baseline(capsys):
    gm.log_global_dashboard({"balance": 1000, "equity": 1000}, "notadict", results={})
    out = capsys.readouterr().out
    assert "Balance=1000.00" in out


def test_dashboard_overlay_regime_only(capsys):
    gm.log_global_dashboard({"balance": 1000, "equity": 1000}, {}, results={}, regime="Bull")
    out = capsys.readouterr().out
    assert "Regime=Bull" in out


def test_dashboard_overlay_ai_only(capsys):
    gm.log_global_dashboard(
        {"balance": 1000, "equity": 1000},
        {},
        results={},
        ai_res={"decision": "BUY", "confidence": 0.9},
    )
    out = capsys.readouterr().out
    assert "AI=BUY(0.90)" in out


def test_dashboard_overlay_rule_only(capsys):
    gm.log_global_dashboard(
        {"balance": 1000, "equity": 1000},
        {},
        results={},
        rule_res={"decision": "SELL", "confidence": 0.8},
    )
    out = capsys.readouterr().out
    assert "Rule=SELL(0.80)" in out


def test_dashboard_overlay_fusion_only(capsys):
    gm.log_global_dashboard(
        {"balance": 1000, "equity": 1000},
        {},
        results={},
        fusion={"decision": "HOLD", "score": 0.7},
    )
    out = capsys.readouterr().out
    assert "Fusion=HOLD(0.70)" in out
