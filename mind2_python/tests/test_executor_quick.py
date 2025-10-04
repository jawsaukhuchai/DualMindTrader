import types
import pytest
import mind2_python.executor as executor_mod


class DummyExecutor(executor_mod.Executor):
    """Subclass Executor เพื่อไม่ให้มันพยายาม connect จริงตอน init"""
    def __init__(self):
        # skip _connect
        self.magic = 123
        self.max_slippage = 0.0005
        self.path = None
        self.login = "1"
        self.password = "x"
        self.server = "demo"


# ------------------------------------------------------------
# Account Info
# ------------------------------------------------------------
def test_get_account_info_failure(monkeypatch, capsys):
    e = DummyExecutor()
    fake_mt5 = types.SimpleNamespace(
        account_info=lambda: None,
        last_error=lambda: ("1", "fail"),
    )
    monkeypatch.setattr(executor_mod, "mt5", fake_mt5)
    monkeypatch.setattr(
        executor_mod,
        "logger",
        types.SimpleNamespace(error=lambda *a, **k: None)
    )

    result = e.get_account_info()
    assert result == {}
    out, _ = capsys.readouterr()
    assert "Failed to get account_info" in out


# ------------------------------------------------------------
# Close Position
# ------------------------------------------------------------
def test_close_position_found_with_series_comment(monkeypatch):
    """Cover branch: p.ticket == ticket and comment has 'series-'"""
    e = DummyExecutor()

    FakePos = types.SimpleNamespace(
        ticket=123,
        symbol="TEST",
        volume=1.0,
        type=0,
        comment="series-2|extra",
        profit=5.0,
    )

    fake_mt5 = types.SimpleNamespace(
        positions_get=lambda **k: [FakePos],
        symbol_info_tick=lambda s: types.SimpleNamespace(bid=1.234, ask=1.235),
        order_send=lambda req: types.SimpleNamespace(
            retcode=executor_mod.TRADE_RETCODE_DONE
        ),
    )
    monkeypatch.setattr(executor_mod, "mt5", fake_mt5)

    called = {}
    monkeypatch.setattr(
        executor_mod,
        "pretty_log_close_position",
        lambda *a, **k: called.setdefault("ok", True),
    )
    monkeypatch.setattr(
        executor_mod,
        "logger",
        types.SimpleNamespace(
            info=lambda *a, **k: None,
            error=lambda *a, **k: None,
            warning=lambda *a, **k: None,
        ),
    )

    result = e.close_position(123, "TEST")
    assert result is not None
    assert "ok" in called


def test_close_position_comment_parse_error(monkeypatch):
    """Cover except Exception: pass when parsing comment"""
    e = DummyExecutor()

    # comment ที่ทำให้ int(...) fail → trigger except
    FakePos = types.SimpleNamespace(
        ticket=123,
        symbol="TEST",
        volume=1.0,
        type=0,
        comment="series-abc|bad",
        profit=5.0,
    )

    fake_mt5 = types.SimpleNamespace(
        positions_get=lambda **k: [FakePos],
        symbol_info_tick=lambda s: types.SimpleNamespace(bid=1.234, ask=1.235),
        order_send=lambda req: types.SimpleNamespace(
            retcode=executor_mod.TRADE_RETCODE_DONE
        ),
    )
    monkeypatch.setattr(executor_mod, "mt5", fake_mt5)

    called = {}
    monkeypatch.setattr(
        executor_mod,
        "pretty_log_close_position",
        lambda *a, **k: called.setdefault("ok", True),
    )
    monkeypatch.setattr(
        executor_mod,
        "logger",
        types.SimpleNamespace(
            info=lambda *a, **k: None,
            error=lambda *a, **k: None,
            warning=lambda *a, **k: None,
        ),
    )

    result = e.close_position(123, "TEST")
    assert result is not None
    assert "ok" in called


def test_close_position_not_found(monkeypatch, capsys):
    """Cover branch: no position found"""
    e = DummyExecutor()
    fake_mt5 = types.SimpleNamespace(
        positions_get=lambda **k: [],
    )
    monkeypatch.setattr(executor_mod, "mt5", fake_mt5)
    monkeypatch.setattr(
        executor_mod,
        "logger",
        types.SimpleNamespace(warning=lambda *a, **k: None),
    )

    result = e.close_position(999, "TEST")
    assert result is None
    out, _ = capsys.readouterr()
    assert "not found" in out


# ------------------------------------------------------------
# Normalize Lot
# ------------------------------------------------------------
def test_normalize_lot_no_symbol_info(monkeypatch):
    """Cover branch: if not info in _normalize_lot"""
    e = DummyExecutor()
    fake_mt5 = types.SimpleNamespace(symbol_info=lambda s: None)
    monkeypatch.setattr(executor_mod, "mt5", fake_mt5)

    result = e._normalize_lot("TEST", 1.234)
    assert result == round(1.234, 2)
