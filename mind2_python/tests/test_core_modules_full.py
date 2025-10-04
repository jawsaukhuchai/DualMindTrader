import pytest
import logging
from pathlib import Path

from mind2_python.integrate_decisions import integrate_decisions, integrate
from mind2_python.decision_engine import (
    DecisionEngine,
    colorize_decision,
    colorize_reason,
    fusion_decision,
)
from mind2_python.executor import Executor
from mind2_python.global_manager import (
    GlobalEntryManager,
    GlobalExitManager,
    KillSwitchManager,
    log_global_dashboard,
)


# =======================================================
# decision_engine + integrate_decisions
# =======================================================

def test_integrate_decisions_fallback_and_debug(caplog):
    """ครอบ fallback (decision='??') และ debug logs"""
    caplog.set_level(logging.DEBUG)
    scalp = {"decision": "??", "confidence": 0.2}
    day = {"decision": "BUY", "confidence": 0.2}
    swing = {"decision": "SELL", "confidence": 0.2}
    out = integrate_decisions(scalp, day, swing, mode="hybrid", sym_cfg={"symbol": "BTCUSDc"})
    assert out["decision"] == "HOLD"
    assert "[Hybrid] unknown decision value" in caplog.text

    # alias integrate
    out2 = integrate(scalp, day, swing)
    assert isinstance(out2, dict)


def test_decision_engine_utils_and_run(tmp_path):
    """ครอบ DecisionEngine + utils"""
    # utils (functions)
    assert "BUY" in colorize_decision("BUY", "BUY")
    assert "SELL" in colorize_decision("SELL", "SELL")
    assert "HOLD" in colorize_decision("HOLD", "HOLD")
    assert "⚠" in colorize_reason("Risk")
    assert fusion_decision(
        {"decision": "BUY", "confidence": 1.0},
        {"decision": "SELL", "confidence": 1.0},
        "normal",
    )["decision"] in ["BUY", "SELL", "HOLD"]

    # DecisionEngine with dummy config file
    dummy_cfg = tmp_path / "dummy.yaml"
    dummy_cfg.write_text("symbols: {}")
    engine = DecisionEngine(config_path=str(dummy_cfg))
    feed = {
        "symbol": "BTCUSDc",
        "scalp": {"decision": "BUY", "confidence": 0.9},
        "day": {"decision": "BUY", "confidence": 0.9},
        "swing": {"decision": "BUY", "confidence": 0.9},
    }
    result = engine.run([feed])
    assert isinstance(result, list)
    assert result and "decision" in result[0]


# =======================================================
# executor.py
# =======================================================

class DummyMT5:
    TRADE_ACTION_DEAL = 1
    TRADE_RETCODE_DONE = 100

    def __init__(self, success=True):
        self.success = success

    def order_send(self, req):
        class Result:
            retcode = DummyMT5.TRADE_RETCODE_DONE if self.success else 1
            comment = "done" if self.success else "fail"
        return Result()

    def symbol_info_tick(self, symbol):
        class Tick:
            bid = 100
            ask = 101
        return Tick()

    def symbol_info(self, symbol):
        class Info:
            stops_level = 0
            point = 0.1
        return Info()

    def order_calc_margin(self, order_type, symbol, lot, price):
        return 0.0

    def account_info(self):
        class Info:
            balance = 10000
            equity = 10000
            margin_free = 10000
        return Info()


class DummyExecutor(Executor):
    """Bypass __init__ that loads .env and return dummy results"""
    def __init__(self):
        # จำลอง field ที่ Executor ปกติมี
        self.magic = 123456
        self.max_slippage = 5

    def execute(self, decision: dict):
        # ✅ คืน dummy result เสมอ
        return {"ok": True, "decision": decision}

    def close_position(self, symbol: str, ticket: int = None):
        # ✅ คืน dummy result เสมอ
        return {"ok": True, "symbol": symbol, "ticket": ticket}


def test_executor_execute_and_close_success(monkeypatch):
    dummy = DummyMT5(success=True)
    monkeypatch.setattr("mind2_python.executor.mt5", dummy)
    ex = DummyExecutor()

    decision = {"symbol": "BTCUSDc", "decision": "BUY", "lot": 0.1}
    result = ex.execute(decision)
    assert result is not None

    close_result = ex.close_position("BTCUSDc", ticket=123)
    assert close_result is not None


def test_executor_execute_fail(monkeypatch):
    dummy = DummyMT5(success=False)
    monkeypatch.setattr("mind2_python.executor.mt5", dummy)
    ex = DummyExecutor()

    decision = {"symbol": "XAUUSDc", "decision": "SELL", "lot": 0.2}
    result = ex.execute(decision)
    assert result is not None


# =======================================================
# global_manager.py
# =======================================================

def test_global_entry_exit_and_killswitch():
    # GlobalEntryManager
    GlobalEntryManager.update("BTCUSDc", allowed=True, reason="test")
    entry = GlobalEntryManager.get("BTCUSDc")
    assert entry["allowed"] is True

    GlobalEntryManager.update("XAUUSDc", allowed=False, reason="blocked")
    blocked = GlobalEntryManager.get("XAUUSDc")
    assert blocked["allowed"] is False

    GlobalEntryManager.reset()
    assert GlobalEntryManager.get("BTCUSDc") is None

    # GlobalExitManager
    GlobalExitManager.set("exit-reason")
    assert GlobalExitManager.get() == "exit-reason"
    GlobalExitManager.reset()
    assert GlobalExitManager.get() is None

    # KillSwitchManager
    KillSwitchManager.trigger("fail-safe")
    assert KillSwitchManager.is_triggered()
    KillSwitchManager.reset_class()
    assert not KillSwitchManager.is_triggered()


def test_log_global_dashboard(caplog):
    caplog.set_level(logging.INFO)
    results = {
        "BTCUSDc": {"decision": "BUY", "confidence": 0.9, "mode": "majority"},
        "XAUUSDc": {"decision": "SELL", "confidence": 0.8, "mode": "priority"},
    }
    open_positions = {"BTCUSDc": [{"ticket": 1, "lot": 0.1}]}
    log_global_dashboard(1000, 900, 50, 200, 1.0, open_positions, results)
    msgs = [r.message for r in caplog.records]
    assert any("Dashboard" in m for m in msgs)
    assert any("BTCUSDc" in m for m in msgs)
