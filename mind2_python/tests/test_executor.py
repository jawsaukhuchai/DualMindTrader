import pytest
from mind2_python.executor import Executor


# ----------------------------------------------------------------------
# Connect + Shutdown
# ----------------------------------------------------------------------
def test_connect_and_shutdown(caplog, monkeypatch):
    """
    Ensure Executor connects and shuts down with proper log messages.
    Uses caplog to capture logs instead of relying on stdout capture.
    """

    import mind2_python.executor as ex

    # --- Mock MT5 methods ---
    monkeypatch.setattr(ex.mt5, "initialize", lambda **kwargs: True)
    monkeypatch.setattr(ex.mt5, "shutdown", lambda: True)
    monkeypatch.setattr(ex.mt5, "last_error", lambda: (0, "ok"))

    # --- Fake env vars ---
    monkeypatch.setenv("MT5_LOGIN", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "pwd")
    monkeypatch.setenv("MT5_SERVER", "demo-server")
    monkeypatch.setenv("MT5_PATH", "/fake/path/terminal64.exe")

    caplog.set_level("INFO")

    executor = Executor()  # will trigger _connect()

    # Verify connection log
    assert any("Connected to MT5" in rec.message for rec in caplog.records)

    executor.shutdown()

    # Verify shutdown log
    assert any("Disconnected from MT5" in rec.message for rec in caplog.records)


# ----------------------------------------------------------------------
# Normalize lot & price
# ----------------------------------------------------------------------
def test_normalize_lot_and_price(monkeypatch):
    import mind2_python.executor as ex

    monkeypatch.setattr(ex.mt5, "symbol_info", lambda symbol: type("S", (), {
        "volume_min": 0.01,
        "volume_max": 1.0,
        "volume_step": 0.01,
        "digits": 5,
    })())

    # --- Fake env vars ---
    monkeypatch.setenv("MT5_LOGIN", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "pwd")
    monkeypatch.setenv("MT5_SERVER", "demo-server")
    monkeypatch.setenv("MT5_PATH", "/fake/path/terminal64.exe")

    executor = Executor.__new__(Executor)
    executor.magic = 123456
    executor.max_slippage = 0.0005

    lot = executor._normalize_lot("EURUSD", 0.345)
    assert 0.01 <= lot <= 1.0
    assert round(lot, 2) == lot

    price = executor._normalize_price("EURUSD", 1.23456)
    assert isinstance(price, float)
    assert round(price, 5) == price


# ----------------------------------------------------------------------
# Check margin
# ----------------------------------------------------------------------
def test_check_margin(monkeypatch):
    import mind2_python.executor as ex

    class DummyAcc:
        margin_free = 1000

    class DummyTick:
        ask = 1.2345
        bid = 1.2344

    def fake_margin(order_type, symbol, lot, price):
        return 10.0

    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: DummyTick())
    monkeypatch.setattr(ex.mt5, "order_calc_margin", fake_margin)
    monkeypatch.setattr(ex.mt5, "account_info", lambda: DummyAcc())

    # --- Fake env vars ---
    monkeypatch.setenv("MT5_LOGIN", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "pwd")
    monkeypatch.setenv("MT5_SERVER", "demo-server")
    monkeypatch.setenv("MT5_PATH", "/fake/path/terminal64.exe")

    executor = Executor.__new__(Executor)
    assert executor._check_margin("EURUSD", 0.1, ex.ORDER_TYPE_BUY)


# ----------------------------------------------------------------------
# Process result
# ----------------------------------------------------------------------
def test_process_result_success(monkeypatch, caplog):
    import mind2_python.executor as ex

    class DummyResult:
        retcode = ex.TRADE_RETCODE_DONE

    # --- Fake env vars ---
    monkeypatch.setenv("MT5_LOGIN", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "pwd")
    monkeypatch.setenv("MT5_SERVER", "demo-server")
    monkeypatch.setenv("MT5_PATH", "/fake/path/terminal64.exe")

    executor = Executor.__new__(Executor)
    executor.magic = 123456
    executor.max_slippage = 0.0005

    caplog.set_level("INFO")
    result = executor._process_result(
        DummyResult(),
        {"symbol": "EURUSD", "type": ex.ORDER_TYPE_SELL, "volume": 0.1, "price": 1.2345},
    )
    assert result is not None
    assert any("Order success" in rec.message for rec in caplog.records)


def test_process_result_fail(monkeypatch, caplog):
    import mind2_python.executor as ex

    class DummyResult:
        retcode = 99999
        comment = "fail"

    monkeypatch.setattr(ex.mt5, "last_error", lambda: (1, "err"))

    # --- Fake env vars ---
    monkeypatch.setenv("MT5_LOGIN", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "pwd")
    monkeypatch.setenv("MT5_SERVER", "demo-server")
    monkeypatch.setenv("MT5_PATH", "/fake/path/terminal64.exe")

    executor = Executor.__new__(Executor)

    caplog.set_level("ERROR")
    result = executor._process_result(DummyResult(), {"symbol": "EURUSD"})
    assert result is None
    assert any("Order failed" in rec.message or "order_send failed" in rec.message for rec in caplog.records)
