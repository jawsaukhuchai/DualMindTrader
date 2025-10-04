import pytest
import logging
import os
import types

import mind2_python.decision_engine as decision_engine
from mind2_python.executor import Executor


# ------------------------
# Dummy MT5 module
# ------------------------
class DummyMT5:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 2
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 0
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self._connected = False
        self._orders = []
        self._positions = []

    def initialize(self, *a, **k):
        self._connected = True
        return True

    def shutdown(self):
        self._connected = False
        return True

    def last_error(self):
        return (-1, "dummy-error")

    def account_info(self):
        return types.SimpleNamespace(
            login=123,
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            margin_free=10000.0,
            margin_level=1000.0,
            currency="USD",
            leverage=100,
        )

    def symbol_info(self, symbol):
        return types.SimpleNamespace(
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            digits=2,
        )

    def symbol_info_tick(self, symbol):
        return types.SimpleNamespace(
            bid=99.5,
            ask=100.5,
        )

    def order_calc_margin(self, order_type, symbol, lot, price):
        return 10.0  # always affordable

    def order_send(self, request):
        result = types.SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE,
            comment="done",
            order_id=len(self._orders) + 1,
        )
        self._orders.append((request, result))
        return result

    def positions_get(self, symbol=None):
        return self._positions


# ------------------------
# Helper: patch env + mt5
# ------------------------
def _patch_mt5_and_env(monkeypatch, dummy: DummyMT5):
    # patch mt5 in decision_engine
    monkeypatch.setitem(decision_engine.__dict__, "mt5", dummy)
    # patch mt5 in executor
    import mind2_python.executor as executor_mod
    monkeypatch.setitem(executor_mod.__dict__, "mt5", dummy)

    # patch env vars required by Executor
    monkeypatch.setenv("MT5_LOGIN", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "pass")
    monkeypatch.setenv("MT5_SERVER", "server")
    monkeypatch.setenv("MT5_PATH", "dummy_path")


# ------------------------
# Fixture
# ------------------------
@pytest.fixture(autouse=True)
def patched_mt5(monkeypatch):
    dummy = DummyMT5()
    _patch_mt5_and_env(monkeypatch, dummy)
    return dummy


# ------------------------
# Test: E2E integration
# ------------------------
def test_integration_e2e_trade_flow(caplog, patched_mt5):
    caplog.set_level(logging.INFO)

    # 1. simulate feed (Mind1)
    feed = {
        "symbol": "XAUUSDc",
        "decision": "BUY",
        "lot": 0.1,
        "sl": 98.0,
        "tp": 105.0,
    }

    # 2. decision engine (simplified passthrough for now)
    decision = feed

    # 3. executor run
    executor = Executor()
    result = executor.execute(decision)

    # 4. assert result
    assert result is not None
    assert result.retcode == patched_mt5.TRADE_RETCODE_DONE
    assert patched_mt5._orders, "order should be recorded"

    # 5. assert logs
    logs = caplog.text
    assert "Order success" in logs
    assert "XAUUSDc" in logs
    assert "BUY" in logs
