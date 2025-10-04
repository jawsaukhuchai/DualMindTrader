import pytest
from types import SimpleNamespace
from mind2_python.executor import Executor, ORDER_TYPE_BUY, TRADE_RETCODE_DONE


@pytest.fixture
def setup_env(monkeypatch):
    # fake env vars
    monkeypatch.setenv("MT5_LOGIN", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "pwd")
    monkeypatch.setenv("MT5_SERVER", "demo-server")
    monkeypatch.setenv("MT5_PATH", "/fake/path/terminal64.exe")


# ---------------- _normalize_price ----------------
def test_normalize_price_none_price(monkeypatch, setup_env):
    import mind2_python.executor as ex
    executor = Executor.__new__(Executor)
    assert executor._normalize_price("EURUSD", None) is None


# ---------------- execute: tick None ----------------
def test_execute_no_tick(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: None)
    executor = Executor.__new__(Executor)
    caplog.set_level("ERROR")
    res = executor.execute({"symbol": "EURUSD", "decision": "BUY"})
    assert res is None
    assert any("No tick data" in rec.message for rec in caplog.records)


# ---------------- execute: margin not enough ----------------
def test_execute_margin_not_enough_single(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex
    tick = SimpleNamespace(ask=1.2345, bid=1.2344)
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: tick)
    monkeypatch.setattr(ex.mt5, "symbol_info", lambda s: SimpleNamespace(volume_min=0.01, volume_max=1.0, volume_step=0.01, digits=5))
    monkeypatch.setattr(ex.mt5, "order_calc_margin", lambda *a, **k: 10000.0)  # too high
    monkeypatch.setattr(ex.mt5, "account_info", lambda: SimpleNamespace(margin_free=1.0))

    executor = Executor.__new__(Executor)
    executor.magic = 123
    executor.max_slippage = 0.0005

    caplog.set_level("ERROR")
    res = executor.execute({"symbol": "EURUSD", "decision": "BUY", "lot": 0.1})
    assert res is None
    assert any("Margin not enough" in rec.message for rec in caplog.records)


def test_execute_margin_not_enough_multi(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex
    tick = SimpleNamespace(ask=1.2345, bid=1.2344)
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: tick)
    monkeypatch.setattr(ex.mt5, "symbol_info", lambda s: SimpleNamespace(volume_min=0.01, volume_max=1.0, volume_step=0.01, digits=5))
    monkeypatch.setattr(ex.mt5, "order_calc_margin", lambda *a, **k: 10000.0)  # too high
    monkeypatch.setattr(ex.mt5, "account_info", lambda: SimpleNamespace(margin_free=1.0))

    executor = Executor.__new__(Executor)
    executor.magic = 123
    executor.max_slippage = 0.0005

    caplog.set_level("ERROR")
    decision = {
        "symbol": "EURUSD",
        "decision": "BUY",
        "exit_levels": {"entries": {1: {"lot": 0.1, "sl": None, "tp": []}}},
    }
    res = executor.execute(decision)
    assert res is None
    assert any("Margin not enough" in rec.message for rec in caplog.records)


# ---------------- execute: TP list logging ----------------
def test_execute_tp_list_logging(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex

    tick = SimpleNamespace(ask=1.2345, bid=1.2344)
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: tick)
    monkeypatch.setattr(ex.mt5, "symbol_info", lambda s: SimpleNamespace(volume_min=0.01, volume_max=1.0, volume_step=0.01, digits=5))
    monkeypatch.setattr(ex.mt5, "order_calc_margin", lambda *a, **k: 10.0)
    monkeypatch.setattr(ex.mt5, "account_info", lambda: SimpleNamespace(margin_free=1000))
    monkeypatch.setattr(ex.mt5, "order_send", lambda req: SimpleNamespace(retcode=TRADE_RETCODE_DONE))

    executor = Executor.__new__(Executor)
    executor.magic = 123
    executor.max_slippage = 0.0005

    caplog.set_level("INFO")
    decision = {"symbol": "EURUSD", "decision": "BUY", "lot": 0.1, "tp": [1.25, 1.26]}
    res = executor.execute(decision)
    assert res is not None
    assert any("TP levels" in rec.message for rec in caplog.records)


# ---------------- execute: result fail ----------------
def test_execute_result_fail(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex

    tick = SimpleNamespace(ask=1.2345, bid=1.2344)
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: tick)
    monkeypatch.setattr(ex.mt5, "symbol_info", lambda s: SimpleNamespace(volume_min=0.01, volume_max=1.0, volume_step=0.01, digits=5))
    monkeypatch.setattr(ex.mt5, "order_calc_margin", lambda *a, **k: 10.0)
    monkeypatch.setattr(ex.mt5, "account_info", lambda: SimpleNamespace(margin_free=1000))
    monkeypatch.setattr(ex.mt5, "order_send", lambda req: SimpleNamespace(retcode=999, comment="bad"))

    executor = Executor.__new__(Executor)
    executor.magic = 123
    executor.max_slippage = 0.0005

    caplog.set_level("ERROR")
    decision = {"symbol": "EURUSD", "decision": "BUY", "lot": 0.1}
    res = executor.execute(decision)
    assert res is None
    assert any("Order failed" in rec.message for rec in caplog.records)


# ---------------- close_position: tick None ----------------
def test_close_position_tick_none(monkeypatch, setup_env):
    import mind2_python.executor as ex
    pos = SimpleNamespace(ticket=111, type=0, volume=0.1, profit=5.0)
    monkeypatch.setattr(ex.mt5, "positions_get", lambda symbol=None: [pos])
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: None)
    monkeypatch.setattr(ex.mt5, "order_send", lambda req: None)

    executor = Executor.__new__(Executor)
    res = executor.close_position(111, "EURUSD")
    assert res is None


# ---------------- _process_result: success with sl/tp ----------------
def test_process_result_success_with_sl_tp(monkeypatch, setup_env, caplog):
    import mind2_python.executor as ex

    class DummyResult:
        retcode = TRADE_RETCODE_DONE

    executor = Executor.__new__(Executor)
    caplog.set_level("INFO")
    result = executor._process_result(
        DummyResult(),
        {"symbol": "EURUSD", "type": ORDER_TYPE_BUY, "volume": 0.1, "price": 1.2345, "sl": 1.23, "tp": 1.25},
    )
    assert result is not None
    assert any("sl=" in rec.message and "tp=" in rec.message for rec in caplog.records)
