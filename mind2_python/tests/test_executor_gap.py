import pytest
import types
import mind2_python.executor as executor


# ------------------------------
# Dummy MT5 stub (configurable)
# ------------------------------
class DummyMT5:
    def __init__(self, init_seq=None, send_result=None, positions=None, tick=None):
        # init_seq: sequence ของค่า True/False ที่ initialize จะ return
        self.init_seq = init_seq or [True]
        self.send_result = send_result
        self.positions = positions or []
        self.tick = tick if tick is not None else types.SimpleNamespace(bid=100.0, ask=101.0)
        self.calls = {"initialize": 0, "order_send": 0}

    def initialize(self, **kwargs):
        self.calls["initialize"] += 1
        return self.init_seq.pop(0) if self.init_seq else True

    def shutdown(self): return True
    def last_error(self): return (500, "dummy-error")

    def account_info(self):
        return types.SimpleNamespace(
            login=123, balance=1000, equity=1000,
            margin=0, margin_free=500, margin_level=200,
            currency="USD", leverage=100
        )

    def symbol_info(self, symbol):
        return types.SimpleNamespace(volume_min=0.01, volume_max=2.0,
                                     volume_step=0.01, digits=5)

    def symbol_info_tick(self, symbol): return self.tick
    def order_calc_margin(self, order_type, symbol, lot, price): return 1.0

    def order_send(self, request):
        self.calls["order_send"] += 1
        return self.send_result

    def positions_get(self, **kwargs): return self.positions


# ------------------------------
# Helper: create Executor with dummy
# ------------------------------
def make_executor(monkeypatch, dummy):
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "x")
    monkeypatch.setenv("MT5_SERVER", "demo")
    monkeypatch.setenv("MT5_PATH", "fake")
    monkeypatch.setattr(executor, "mt5", dummy)
    return executor.Executor()


# ------------------------------
# _connect branches
# ------------------------------
def test_connect_success_direct(monkeypatch):
    dummy = DummyMT5(init_seq=[True])
    ex = make_executor(monkeypatch, dummy)
    assert ex.login == "1"
    assert dummy.calls["initialize"] == 1  # success on first try


def test_connect_retry_success(monkeypatch):
    dummy = DummyMT5(init_seq=[False, True])
    ex = make_executor(monkeypatch, dummy)
    assert ex.login == "1"
    assert dummy.calls["initialize"] == 2  # fail then success


def test_connect_fail_twice(monkeypatch):
    dummy = DummyMT5(init_seq=[False, False])
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "x")
    monkeypatch.setenv("MT5_SERVER", "demo")
    monkeypatch.setenv("MT5_PATH", "fake")
    monkeypatch.setattr(executor, "mt5", dummy)
    with pytest.raises(RuntimeError):
        executor.Executor()


# ------------------------------
# _process_result branches
# ------------------------------
def test_process_result_fail(monkeypatch):
    dummy = DummyMT5()
    ex = make_executor(monkeypatch, dummy)
    bad = types.SimpleNamespace(retcode=999, comment="bad")
    assert ex._process_result(bad,
        {"symbol": "XAUUSD", "type": executor.ORDER_TYPE_BUY,
         "volume": 0.1, "price": 100}) is None


def test_process_result_success(monkeypatch):
    dummy = DummyMT5()
    ex = make_executor(monkeypatch, dummy)
    good = types.SimpleNamespace(retcode=executor.TRADE_RETCODE_DONE,
                                 comment="ok")
    out = ex._process_result(good,
        {"symbol": "XAUUSD", "type": executor.ORDER_TYPE_BUY,
         "volume": 0.1, "price": 100})
    assert out is good


# ------------------------------
# execute branch
# ------------------------------
def test_execute_no_tick(monkeypatch):
    dummy = DummyMT5(tick=None)
    ex = make_executor(monkeypatch, dummy)
    decision = {"symbol": "XAUUSD", "decision": "BUY", "lot": 0.1}
    assert ex.execute(decision) is None


# ------------------------------
# close_position branches
# ------------------------------
def test_close_position_no_pos(monkeypatch):
    dummy = DummyMT5(positions=[])
    ex = make_executor(monkeypatch, dummy)
    assert ex.close_position(ticket=1, symbol="XAUUSD") is None


def test_close_position_tick_none(monkeypatch):
    pos = types.SimpleNamespace(ticket=1, type=0, volume=0.1)
    dummy = DummyMT5(positions=[pos], tick=None)
    ex = make_executor(monkeypatch, dummy)
    assert ex.close_position(ticket=1, symbol="XAUUSD") is None


def test_close_position_order_send_none(monkeypatch):
    pos = types.SimpleNamespace(ticket=1, type=0, volume=0.1)
    dummy = DummyMT5(positions=[pos],
                     tick=types.SimpleNamespace(bid=100, ask=101),
                     send_result=None)
    ex = make_executor(monkeypatch, dummy)
    assert ex.close_position(ticket=1, symbol="XAUUSD") is None
    # ครอบ branch line 230 (_process_result with None)


def test_close_position_success_full(monkeypatch):
    pos = types.SimpleNamespace(ticket=1, type=0, volume=0.1,
                                profit=5.0, comment="series-1|note")
    good = types.SimpleNamespace(retcode=executor.TRADE_RETCODE_DONE,
                                 comment="ok")
    dummy = DummyMT5(positions=[pos],
                     tick=types.SimpleNamespace(bid=100, ask=101),
                     send_result=good)
    ex = make_executor(monkeypatch, dummy)
    result = ex.close_position(ticket=1, symbol="XAUUSD")
    assert result is good
    # ครอบ branch line 292–293 (order success path)
