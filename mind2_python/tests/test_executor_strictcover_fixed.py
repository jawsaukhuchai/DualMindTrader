import pytest
import mind2_python.executor as executor


@pytest.fixture(autouse=True)
def patch_env(monkeypatch):
    """Default env for all tests, safe dummy values."""
    monkeypatch.setattr("os.getenv", lambda key, default=None: {
        "MT5_LOGIN": "123456",
        "MT5_PASSWORD": "pass",
        "MT5_SERVER": "demo-server",
        "MT5_PATH": "fakepath.exe",
    }.get(key, default))


@pytest.fixture
def safe_mt5(monkeypatch):
    """Provide dummy mt5 that won't crash IPC and has needed constants."""
    class DummyMT5:
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        TRADE_RETCODE_DONE = 10009
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 0

        def initialize(self, **kwargs): return True
        def shutdown(self): return True
        def last_error(self): return (-1, "mock-error")
        def account_info(self): return type("A", (), {"margin_free": 9999})()
        def symbol_info(self, s): return None
        def symbol_info_tick(self, s): return None
        def order_calc_margin(self, *a, **k): return None
        def order_send(self, req): return None
        def positions_get(self, symbol=None): return []

    mt5 = DummyMT5()
    monkeypatch.setattr(executor, "mt5", mt5)
    return mt5


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------

def test_connect_and_shutdown(safe_mt5, capsys):
    ex = executor.Executor()
    out = capsys.readouterr().out
    # Flexible assert
    assert "Connected to MT5" in out
    ex.shutdown()
    out = capsys.readouterr().out
    assert "Disconnected" in out


def test_init_missing_creds(monkeypatch):
    # ให้ค่า None สำหรับ credentials เพื่อ trigger RuntimeError
    monkeypatch.setattr("os.getenv", lambda key, default=None: None)

    class FakeMT5:
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        def initialize(self, **kwargs): return True
        def shutdown(self): return True
        def last_error(self): return (1, "mock")
    monkeypatch.setattr(executor, "mt5", FakeMT5())

    with pytest.raises(RuntimeError) as e:
        executor.Executor()
    assert "Missing MT5 credentials" in str(e.value)


def test_connect_fail_twice(monkeypatch, patch_env):
    class DummyMT5:
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        def __init__(self): self.calls = 0
        def initialize(self, **kwargs):
            self.calls += 1
            return False
        def shutdown(self): return True
        def last_error(self): return (1, "init-error")
    dummy = DummyMT5()
    monkeypatch.setattr(executor, "mt5", dummy)
    with pytest.raises(RuntimeError) as e:
        executor.Executor()
    assert dummy.calls == 2
    assert "MT5 initialize failed" in str(e.value)


def test_normalize_price_none(safe_mt5):
    ex = executor.Executor()
    assert ex._normalize_price("EURUSD", None) is None


def test_check_margin_no_calc(monkeypatch, safe_mt5):
    ex = executor.Executor()
    class DummyMT5:
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        def initialize(self, **kwargs): return True
        def shutdown(self): return True
        def symbol_info_tick(self, s): return type("T", (), {"ask":1.0, "bid":1.0})()
        def order_calc_margin(self, *a, **k): return None
        def account_info(self): return type("A", (), {"margin_free": 100})()
    monkeypatch.setattr(executor, "mt5", DummyMT5())
    assert ex._check_margin("EURUSD", 0.1, 0) is False


def test_check_margin_no_account(monkeypatch, safe_mt5):
    ex = executor.Executor()
    class DummyMT5:
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        def initialize(self, **kwargs): return True
        def shutdown(self): return True
        def symbol_info_tick(self, s): return type("T", (), {"ask":1.0, "bid":1.0})()
        def order_calc_margin(self, *a, **k): return 50.0
        def account_info(self): return None
    monkeypatch.setattr(executor, "mt5", DummyMT5())
    assert ex._check_margin("EURUSD", 0.1, 0) is False


def test_process_result_retcode_not_done(safe_mt5, capsys):
    ex = executor.Executor()
    class FakeResult: retcode = 100; comment = "fail"
    res = ex._process_result(FakeResult(), {"symbol": "EURUSD"})
    assert res is None
    assert "Order failed" in capsys.readouterr().out


def test_process_result_success(safe_mt5, capsys):
    ex = executor.Executor()
    class FakeResult: retcode = executor.mt5.TRADE_RETCODE_DONE
    res = ex._process_result(FakeResult(), {
        "symbol": "EURUSD", "type": executor.mt5.ORDER_TYPE_BUY,
        "volume": 0.1, "price": 1.2345
    })
    assert res is not None
    assert "Order success" in capsys.readouterr().out
