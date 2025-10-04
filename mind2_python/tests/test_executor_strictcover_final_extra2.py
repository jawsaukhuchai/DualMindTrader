# mind2_python/tests/test_executor_strictcover_final_extra2.py
import types
import pytest
import mind2_python.executor as ex


class DummyResult:
    def __init__(self, retcode=ex.TRADE_RETCODE_DONE, comment="ok"):
        self.retcode = retcode
        self.comment = comment


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


def make_executor(monkeypatch, **kwargs):
    """Helper: create Executor with patched mt5"""
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "path")
    mt5 = types.SimpleNamespace(
        initialize=lambda **k: True,
        shutdown=lambda: True,
        account_info=lambda: types.SimpleNamespace(margin_free=999),
        symbol_info=lambda s: types.SimpleNamespace(
            volume_min=0.1, volume_max=5.0, volume_step=0.1, digits=5
        ),
        symbol_info_tick=lambda s: DummyTick(),
        order_calc_margin=lambda *a, **k: 1.0,
        positions_get=lambda **k: [],
        order_send=lambda req: DummyResult(),
        last_error=lambda: "err",
    )
    for k, v in kwargs.items():
        setattr(mt5, k, v)
    monkeypatch.setattr(ex, "mt5", mt5)
    return ex.Executor()


def test_connect_fail_twice(monkeypatch):
    """_connect fail 2 รอบ -> raise RuntimeError (cover 89–92)"""
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "p")
    monkeypatch.setenv("MT5_SERVER", "s")
    monkeypatch.setenv("MT5_PATH", "path")

    monkeypatch.setattr(ex.mt5, "initialize", lambda **k: False)
    with pytest.raises(RuntimeError):
        ex.Executor()


def test_shutdown_covers_log(monkeypatch, capsys):
    """shutdown() -> cover line 110"""
    e = make_executor(monkeypatch)
    e.shutdown()
    out = capsys.readouterr().out
    assert "Disconnected from MT5" in out


def test_execute_multi_entry_continue(monkeypatch):
    """multi-entry margin fail -> trigger continue (cover 230)"""
    e = make_executor(monkeypatch)
    # force margin check fail
    monkeypatch.setattr(e, "_check_margin", lambda *a, **k: False)
    dec = {
        "symbol": "X",
        "decision": "BUY",
        "exit_levels": {"entries": {"1": {"lot": 0.2, "sl": 9.0}}},
    }
    out = e.execute(dec)
    # ไม่มี result -> None (เพราะ continue ทั้งหมด)
    assert out is None


def test_close_position_retcode_fail(monkeypatch):
    """close_position order_send retcode != DONE (cover 292–293)"""
    def bad_order_send(req): return DummyResult(retcode=999, comment="bad")
    e = make_executor(
        monkeypatch,
        order_send=bad_order_send,
        positions_get=lambda **k: [DummyPos()],
    )
    out = e.close_position(1, "X")
    assert out is None
