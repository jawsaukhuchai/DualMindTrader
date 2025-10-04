# mind2_python/tests/test_executor_strictcover_final.py
import types
import pytest
import mind2_python.executor as ex


class DummyResult:
    def __init__(self, retcode=ex.TRADE_RETCODE_DONE, comment="ok"):
        self.retcode = retcode
        self.comment = comment


class DummyInfo:
    def __init__(self, digits=5):
        self.login = 123
        self.balance = 1000
        self.equity = 1000
        self.margin = 100
        self.margin_free = 900
        self.margin_level = 100
        self.currency = "USD"
        self.leverage = 100
        self.volume_min = 0.1
        self.volume_max = 5.0
        self.volume_step = 0.1
        self.digits = digits


class DummyTick:
    def __init__(self, bid=10, ask=11):
        self.bid = bid
        self.ask = ask


class DummyPos:
    def __init__(self, ticket=1, vol=0.5, type_=0, comment="series-1|entry", profit=10):
        self.ticket = ticket
        self.volume = vol
        self.type = type_
        self.comment = comment
        self.profit = profit


@pytest.fixture
def patch_mt5(monkeypatch):
    """Patch mt5 functions for deterministic behavior"""
    dummy_state = {"init_calls": 0}

    def initialize(**kwargs):
        dummy_state["init_calls"] += 1
        return dummy_state["init_calls"] >= 2  # fail once then succeed

    monkeypatch.setattr(ex, "mt5", types.SimpleNamespace(
        initialize=initialize,
        shutdown=lambda: True,
        account_info=lambda: DummyInfo(),
        symbol_info=lambda s: DummyInfo(),
        symbol_info_tick=lambda s: DummyTick(),
        order_calc_margin=lambda t, s, l, p: 10.0,
        positions_get=lambda symbol=None: [DummyPos()],
        order_send=lambda req: DummyResult(),
        last_error=lambda: "error"
    ))
    return ex.mt5


def test_init_missing_env(monkeypatch):
    monkeypatch.delenv("MT5_LOGIN", raising=False)
    monkeypatch.delenv("MT5_PASSWORD", raising=False)
    monkeypatch.delenv("MT5_SERVER", raising=False)
    with pytest.raises(RuntimeError):
        ex.Executor()


def test_connect_success_and_fail(monkeypatch):
    calls = {"c": 0}
    def fake_init(**kwargs):
        calls["c"] += 1
        return calls["c"] > 1
    monkeypatch.setattr(ex.mt5, "initialize", fake_init)
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "path")
    ex.Executor()  # should retry once and succeed


def test_get_account_info_ok(patch_mt5, monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "path")
    e = ex.Executor()
    acc = e.get_account_info()
    assert "balance" in acc


def test_normalize_lot_and_price(patch_mt5, monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "path")
    e = ex.Executor()
    # lot clamp
    assert e._normalize_lot("x", 0.001) >= 0.1
    assert e._normalize_lot("x", 99) <= 5.0
    # price
    assert e._normalize_price("x", 1.234567) == 1.23457
    assert e._normalize_price("x", None) is None


def test_check_margin_paths(monkeypatch):
    """Force initialize success to avoid MT5 IPC error"""
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "path")

    monkeypatch.setattr(ex.mt5, "initialize", lambda **k: True)
    monkeypatch.setattr(ex.mt5, "symbol_info_tick", lambda s: None)
    monkeypatch.setattr(ex.mt5, "account_info", lambda: None)
    monkeypatch.setattr(ex.mt5, "order_calc_margin", lambda *a, **k: 1.0)

    e = ex.Executor()
    assert not e._check_margin("x", 1, ex.ORDER_TYPE_BUY)


def test_execute_paths(monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "path")
    mt5 = types.SimpleNamespace(
        initialize=lambda **k: True,
        account_info=lambda: DummyInfo(),
        symbol_info=lambda s: DummyInfo(),
        symbol_info_tick=lambda s: DummyTick(),
        order_calc_margin=lambda t, s, l, p: 1.0,
        order_send=lambda req: DummyResult(),
        last_error=lambda: "err",
        positions_get=lambda **k: []
    )
    monkeypatch.setattr(ex, "mt5", mt5)
    e = ex.Executor()

    # tick None
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda s: None)
    assert e.execute({"symbol": "X", "decision": "BUY"}) is None
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda s: DummyTick())

    # margin fail
    monkeypatch.setattr(mt5, "order_calc_margin", lambda *a, **k: None)
    assert e.execute({"symbol": "X", "decision": "BUY"}) is None
    monkeypatch.setattr(mt5, "order_calc_margin", lambda *a, **k: 1.0)

    # single entry success
    r = e.execute({"symbol": "X", "decision": "BUY", "lot": 0.2, "tp": 12.3})
    assert isinstance(r, DummyResult)

    # multi entry margin fail
    monkeypatch.setattr(e, "_check_margin", lambda *a, **k: False)
    dec = {"symbol": "X", "decision": "BUY", "exit_levels": {"entries": {"1": {"lot": 0.1, "sl": 9}}}}
    assert e.execute(dec) is None


def test_close_position_paths(monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "path")

    # patch mt5
    mt5 = types.SimpleNamespace(
        initialize=lambda **k: True,
        account_info=lambda: DummyInfo(),
        symbol_info=lambda s: DummyInfo(),
        symbol_info_tick=lambda s: DummyTick(),
        order_calc_margin=lambda *a, **k: 1.0,
        order_send=lambda r: DummyResult(),
        last_error=lambda: "err",
        positions_get=lambda **k: []
    )
    monkeypatch.setattr(ex, "mt5", mt5)
    e = ex.Executor()

    # not found
    assert e.close_position(1, "X") is None

    # tick None
    mt5.positions_get = lambda **k: [DummyPos()]
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda s: None)
    assert e.close_position(1, "X") is None

    # success
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda s: DummyTick())
    r = e.close_position(1, "X")
    assert isinstance(r, DummyResult)


def test_process_result_variants(monkeypatch):
    e = object.__new__(ex.Executor)  # bypass init
    e.magic = 1
    # None
    assert e._process_result(None, {"symbol": "X"}) is None
    # retcode != DONE
    r = DummyResult(retcode=999, comment="bad")
    assert e._process_result(r, {"symbol": "X", "type": ex.ORDER_TYPE_BUY}) is None
    # success
    r = DummyResult(retcode=ex.TRADE_RETCODE_DONE)
    out = e._process_result(r, {"symbol": "X", "type": ex.ORDER_TYPE_BUY,
                                "price": 1.23, "volume": 1})
    assert out == r
