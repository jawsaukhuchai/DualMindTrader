import pytest
import logging
import types
import mind2_python.executor as executor_mod
from mind2_python.executor import Executor


class DummyMT5FailInit:
    """Dummy MT5 ที่ initialize ล้มเหลว"""
    def initialize(self, *a, **k):
        return False
    def last_error(self):
        return (-10003, "IPC initialize failed")
    def shutdown(self): return True


class DummyMT5CloseFail:
    """Dummy MT5 สำหรับ simulate close_position retcode != DONE"""
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 2
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 0
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self._positions = [
            types.SimpleNamespace(
                ticket=1,
                symbol="XAUUSDc",
                type=0,
                volume=0.1,
                comment="series-1|extra",
                profit=5.0,
            )
        ]

    def initialize(self, *a, **k): return True
    def shutdown(self): return True
    def last_error(self): return (-1, "dummy-error")

    def account_info(self):
        return types.SimpleNamespace(margin_free=1000)

    def symbol_info_tick(self, symbol):
        return types.SimpleNamespace(bid=99.0, ask=101.0)

    def order_calc_margin(self, *a, **k): return 1.0

    def order_send(self, request):
        # ส่งกลับ retcode ผิด
        return types.SimpleNamespace(retcode=99999, comment="fail")

    def positions_get(self, symbol=None):
        return self._positions


def test_connect_fail_raises(monkeypatch):
    # patch MT5 ให้ fail init
    monkeypatch.setitem(executor_mod.__dict__, "mt5", DummyMT5FailInit())
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "dummy")

    with pytest.raises(RuntimeError) as e:
        Executor()
    assert "❌ MT5 initialize failed" in str(e.value)


def test_shutdown_logs(monkeypatch, caplog):
    dummy = DummyMT5FailInit()
    monkeypatch.setitem(executor_mod.__dict__, "mt5", dummy)
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "dummy")

    # bypass _connect by patching initialize=True
    dummy.initialize = lambda *a, **k: True
    exe = Executor()
    caplog.set_level(logging.INFO)
    exe.shutdown()
    assert "Disconnected from MT5" in caplog.text


def test_close_position_fail(monkeypatch, caplog):
    dummy = DummyMT5CloseFail()
    monkeypatch.setitem(executor_mod.__dict__, "mt5", dummy)
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "dummy")

    exe = Executor()
    caplog.set_level(logging.ERROR)
    result = exe.close_position(ticket=1, symbol="XAUUSDc", lot=0.1)
    assert result is None
    assert "Order failed" in caplog.text or "❌" in caplog.text
