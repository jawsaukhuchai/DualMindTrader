import pytest
from types import SimpleNamespace
from mind2_python.executor import Executor, ORDER_TYPE_BUY, ORDER_TYPE_SELL, TRADE_RETCODE_DONE


# ---------------- Fixtures ----------------
@pytest.fixture
def setup_env(monkeypatch):
    # fake env vars
    monkeypatch.setenv("MT5_LOGIN", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "pwd")
    monkeypatch.setenv("MT5_SERVER", "demo-server")
    monkeypatch.setenv("MT5_PATH", "/fake/path/terminal64.exe")


# ---------------- Helpers ----------------
class DummyResult:
    def __init__(self, retcode=TRADE_RETCODE_DONE, comment="ok"):
        self.retcode = retcode
        self.comment = comment
        self.ticket = 111
        self.profit = 5.0
        self.type = 0
        self.volume = 0.1
        self.comment = "series-1|conf=0.5"


# ---------------- _normalize_price ----------------
def test_normalize_price_with_info(monkeypatch, setup_env):
    import mind2_python.executor as ex
    monkeypatch.setattr(ex.mt5, "symbol_info", lambda s: SimpleNamespace(digits=3))
    executor = Executor.__new__(Executor)
    price = executor._normalize_price("EURUSD", 1.23456)
    assert price == round(1.23456, 3)


def test_normalize_price_no_info(monkeypatch, setup_env):
    import mind2_python.executor as ex
    monkeypatch.setattr(ex.mt5, "symbol_info", lambda s: None)
    executor = Executor.__new__(Executor)
    assert executor._normalize_price("EURUSD", 1.23456) == 1.23456


# ---------------- _check_margin ----------------
def test_check_margin_success(monkeypatch, setup_env):
    import mind2_python.executor as ex

    class DummyTick:
        ask = 1.2345
        bid = 1.2344

    class DummyAcc:
        margin_free = 1000

    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: DummyTick())
    monkeypatch.setattr(ex.mt5, "order_calc_margin", lambda *a, **k: 10.0)
    monkeypatch.setattr(ex.mt5, "account_info", lambda: DummyAcc())

    executor = Executor.__new__(Executor)
    assert executor._check_margin("EURUSD", 0.1, ORDER_TYPE_BUY)


def test_check_margin_fail(monkeypatch, setup_env):
    import mind2_python.executor as ex
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: None)
    executor = Executor.__new__(Executor)
    assert executor._check_margin("EURUSD", 0.1, ORDER_TYPE_BUY) is False


# ---------------- execute ----------------
def test_execute_single_success(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex

    tick = SimpleNamespace(ask=1.2345, bid=1.2344)
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: tick)
    monkeypatch.setattr(ex.mt5, "symbol_info", lambda s: SimpleNamespace(volume_min=0.01, volume_max=1.0, volume_step=0.01, digits=5))
    monkeypatch.setattr(ex.mt5, "order_calc_margin", lambda *a, **k: 10.0)
    monkeypatch.setattr(ex.mt5, "account_info", lambda: SimpleNamespace(margin_free=1000))
    monkeypatch.setattr(ex.mt5, "order_send", lambda req: DummyResult())

    executor = Executor.__new__(Executor)
    executor.magic = 123
    executor.max_slippage = 0.0005

    caplog.set_level("INFO")
    decision = {"symbol": "EURUSD", "decision": "SELL", "lot": 0.1, "sl": None, "tp": None}
    res = executor.execute(decision)
    assert res is not None
    assert any("Order success" in rec.message for rec in caplog.records)


def test_execute_multi_entry(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex

    tick = SimpleNamespace(ask=1.2345, bid=1.2344)
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: tick)
    monkeypatch.setattr(ex.mt5, "symbol_info", lambda s: SimpleNamespace(volume_min=0.01, volume_max=1.0, volume_step=0.01, digits=5))
    monkeypatch.setattr(ex.mt5, "order_calc_margin", lambda *a, **k: 10.0)
    monkeypatch.setattr(ex.mt5, "account_info", lambda: SimpleNamespace(margin_free=1000))
    monkeypatch.setattr(ex.mt5, "order_send", lambda req: DummyResult())

    executor = Executor.__new__(Executor)
    executor.magic = 123
    executor.max_slippage = 0.0005

    caplog.set_level("INFO")
    decision = {
        "symbol": "EURUSD",
        "decision": "SELL",
        "exit_levels": {
            "entries": {
                1: {"lot": 0.1, "sl": None, "tp": []},
                2: {"lot": 0.2, "sl": None, "tp": []},
            }
        },
    }
    res = executor.execute(decision)
    assert isinstance(res, list)
    assert any("entry#1" in rec.message for rec in caplog.records)


# ---------------- close_position ----------------
def test_close_position_success(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex

    pos = SimpleNamespace(ticket=111, type=0, volume=0.1, profit=5.0, comment="series-1|conf=0.5")
    tick = SimpleNamespace(bid=1.2345, ask=1.2346)

    monkeypatch.setattr(ex.mt5, "positions_get", lambda symbol=None: [pos])
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: tick)
    monkeypatch.setattr(ex.mt5, "order_send", lambda req: DummyResult())
    monkeypatch.setattr(ex.mt5, "account_info", lambda: SimpleNamespace(margin_free=1000))

    executor = Executor.__new__(Executor)
    executor.magic = 123
    executor.max_slippage = 0.0005

    caplog.set_level("INFO")
    res = executor.close_position(111, "EURUSD")
    assert res is not None
    assert any("CLOSE success" in rec.message for rec in caplog.records)


def test_close_position_not_found(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex
    monkeypatch.setattr(ex.mt5, "positions_get", lambda symbol=None: [])
    executor = Executor.__new__(Executor)
    caplog.set_level("WARNING")
    res = executor.close_position(999, "EURUSD")
    assert res is None
    assert any("not found" in rec.message for rec in caplog.records)


# ---------------- _process_result ----------------
def test_process_result_none(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex
    monkeypatch.setattr(ex.mt5, "last_error", lambda: (1, "err"))
    executor = Executor.__new__(Executor)
    caplog.set_level("ERROR")
    res = executor._process_result(None, {"symbol": "EURUSD"})
    assert res is None
    assert any("order_send failed" in rec.message for rec in caplog.records)


def test_process_result_fail(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex
    class BadResult:
        retcode = 999
        comment = "fail"
    monkeypatch.setattr(ex.mt5, "last_error", lambda: (1, "err"))
    executor = Executor.__new__(Executor)
    caplog.set_level("ERROR")
    res = executor._process_result(BadResult(), {"symbol": "EURUSD"})
    assert res is None
    assert any("Order failed" in rec.message for rec in caplog.records)
