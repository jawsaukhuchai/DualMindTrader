# tests/test_position_manager.py
import types
import pytest
import MetaTrader5 as mt5
from mind2_python.position_manager import PositionManager


@pytest.fixture
def pm():
    """สร้าง instance ใหม่ของ PositionManager (simulation mode)"""
    inst = PositionManager._instance()
    inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
    return inst


# ========================
# Simulation mode tests
# ========================

def test_open_position_and_close_by_ticket(pm):
    pos = pm.open_position("XAUUSD", 1.0, "BUY", 2000, atr=10)
    ticket = pos["ticket"]
    pm.close_position("XAUUSD", ticket=ticket)
    assert not pm.state["positions"]["XAUUSD"]


def test_close_position_without_ticket(pm):
    pm.open_position("XAUUSD", 1.0, "BUY", 2000)
    pm.open_position("XAUUSD", 1.0, "SELL", 2010)
    pm.close_position("XAUUSD")
    assert len(pm.state["positions"]["XAUUSD"]) == 1


def test_close_position_symbol_not_in_state(pm):
    pm.close_position("EURUSD")  # ไม่มี key symbol → return ทันที


def test_update_position_sl_only(pm):
    pos = pm.open_position("XAUUSD", 1.0, "BUY", 2000)
    pm.update_position("XAUUSD", pos["ticket"], sl=1990)
    assert pm.state["positions"]["XAUUSD"][0]["sl"] == 1990


def test_update_position_tp_only(pm):
    pos = pm.open_position("XAUUSD", 1.0, "BUY", 2000)
    pm.update_position("XAUUSD", pos["ticket"], tp=[{"price": 2050}])
    assert pm.state["positions"]["XAUUSD"][0]["tp"][0]["price"] == 2050


def test_update_position_exit_levels_only(pm):
    pos = pm.open_position("XAUUSD", 1.0, "BUY", 2000)
    pm.update_position("XAUUSD", pos["ticket"], exit_levels={"tp": [2050]})
    assert pm.state["positions"]["XAUUSD"][0]["exit_levels"]["tp"] == [2050]


# ========================
# _parse_comment variations
# ========================

@pytest.mark.parametrize("comment,expected", [
    ("series-2|0.8|0.6", (0.8, 0.6, 2)),
    ("series-5|0.8", (0.8, 0.0, 5)),
    ("0.5|0.7", (0.5, 0.7, 1)),
    ("", (0.0, 0.0, 1)),
    ("invalid", (0.0, 0.0, 1)),
])
def test_parse_comment_variations(comment, expected):
    assert PositionManager._parse_comment(comment) == expected


def test_parse_comment_series_index_only():
    conf, winprob, idx = PositionManager._parse_comment("series-5")
    assert (conf, winprob, idx) == (0.0, 0.0, 5)


def test_parse_comment_series_index_and_conf():
    conf, winprob, idx = PositionManager._parse_comment("series-5|0.9")
    assert (conf, winprob, idx) == (0.9, 0.0, 5)


def test_parse_comment_series_only_index_branch():
    # parts len=1 → cover branch 178 True, 180 False
    conf, winprob, idx = PositionManager._parse_comment("series-7")
    assert (conf, winprob, idx) == (0.0, 0.0, 7)


def test_parse_comment_branch_len1():
    conf, winprob, idx = PositionManager._parse_comment("series-8")
    assert (conf, winprob, idx) == (0.0, 0.0, 8)


# ========================
# get_open_positions & summary
# ========================

class DummyPos:
    def __init__(self):
        self.ticket = 111
        self.symbol = "XAUUSD"
        self.volume = 0.2
        self.type = 0
        self.price_open = 2005
        self.profit = 10.5
        self.comment = "series-4|0.7|0.55"
        self.sl = 1990
        self.tp = 2025


def test_get_open_positions_with_list(monkeypatch):
    monkeypatch.setattr("mind2_python.position_manager.mt5.positions_get", lambda symbol=None: [DummyPos()])
    result = PositionManager.get_open_positions("XAUUSD")
    assert result and result[0]["conf"] == 0.7 and result[0]["winprob"] == 0.55


def test_get_open_positions_from_state(pm, monkeypatch):
    pm.open_position("XAUUSD", 1.0, "BUY", 2000)
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: None)
    result = PositionManager.get_open_positions("XAUUSD")
    assert result and result[0]["symbol"] == "XAUUSD"


def test_get_open_positions_summary_empty(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: None)
    assert PositionManager.get_open_positions_summary() == {}


class DummyForSummary:
    def __init__(self):
        self.symbol = "XAUUSD"
        self.volume = 0.3


def test_get_open_positions_summary_with_data(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: [DummyForSummary()])
    res = PositionManager.get_open_positions_summary()
    assert res == {"XAUUSD": [0.3]}


class DummyForSummary2:
    def __init__(self):
        self.symbol = "BTCUSD"
        self.volume = 0.5


def test_get_open_positions_summary_with_return(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: [DummyForSummary2()])
    res = PositionManager.get_open_positions_summary()
    assert res == {"BTCUSD": [0.5]}


class DummySummaryFinal:
    def __init__(self):
        self.symbol = "ETHUSD"
        self.volume = 1.2


def test_get_open_positions_summary_final(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: [DummySummaryFinal()])
    res = PositionManager.get_open_positions_summary()
    assert res == {"ETHUSD": [1.2]}


def test_get_open_positions_summary_exception(monkeypatch):
    def raise_err(symbol=None):
        raise RuntimeError("boom")
    monkeypatch.setattr(PositionManager, "get_positions", raise_err)
    res = PositionManager.get_open_positions_summary()
    assert res == {}


# ========================
# Production mode mocks
# ========================

class DummyInfo:
    stops_level = 10
    point = 1

class DummyTick:
    bid = 2000
    ask = 2001


def test_update_position_warning_no_symbol(monkeypatch, pm):
    monkeypatch.setattr("mind2_python.position_manager.mt5.symbol_info", lambda s: None)
    pm.update_position("XAUUSD", 123)


def test_update_position_warning_too_close(monkeypatch, pm):
    monkeypatch.setattr("mind2_python.position_manager.mt5.symbol_info", lambda s: DummyInfo())
    monkeypatch.setattr("mind2_python.position_manager.mt5.symbol_info_tick", lambda s: DummyTick())
    monkeypatch.setattr("mind2_python.position_manager.mt5.order_send", lambda req: types.SimpleNamespace(retcode=1))
    pm.update_position("XAUUSD", 123, sl=2000, tp=[{"price": 2001}])


def test_update_position_info_success(monkeypatch, pm):
    monkeypatch.setattr("mind2_python.position_manager.mt5.symbol_info", lambda s: DummyInfo())
    monkeypatch.setattr("mind2_python.position_manager.mt5.symbol_info_tick", lambda s: None)
    monkeypatch.setattr("mind2_python.position_manager.mt5.order_send",
                        lambda req: types.SimpleNamespace(retcode=mt5.TRADE_RETCODE_DONE))
    pm.update_position("XAUUSD", 123, sl=1990, tp=[{"price": 2020}])


def test_update_position_error_exception(monkeypatch, pm):
    monkeypatch.setattr("mind2_python.position_manager.mt5.symbol_info", lambda s: (_ for _ in ()).throw(RuntimeError("fail")))
    pm.update_position("XAUUSD", 123)


def test_get_positions_error(monkeypatch):
    monkeypatch.setattr("mind2_python.position_manager.mt5.positions_get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fail")))
    assert PositionManager.get_positions("XAUUSD") == []


def test_count_open_positions_error(monkeypatch):
    monkeypatch.setattr("mind2_python.position_manager.mt5.positions_get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fail")))
    assert PositionManager.count_open_positions("XAUUSD") == 0


def test_get_open_positions_summary_error(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fail")))
    assert PositionManager.get_open_positions_summary() == {}


# ========================
# Utility
# ========================

def test_compute_sl_tp_buy_and_sell():
    sl, tp = PositionManager.compute_sl_tp(2000, "BUY", 10, 2, 3)
    assert (sl, tp) == (1980, 2030)
    sl, tp = PositionManager.compute_sl_tp(2000, "SELL", 10, 2, 3)
    assert (sl, tp) == (2020, 1970)


def test_update_health_and_get_health():
    PositionManager.update_health({"balance": 1000, "equity": 1200, "margin_level": 250})
    health = PositionManager.get_health()
    assert health["balance"] == 1000 and "timestamp" in health


# ========================
# Force tests (ensure branch coverage)
# ========================

def test_parse_comment_force_branch():
    # parts = ["series-10"] → 178 True, 180 False
    result = PositionManager._parse_comment("series-10")
    assert result == (0.0, 0.0, 10)


class DummyForceSummary:
    def __init__(self):
        self.symbol = "AUDUSD"
        self.volume = 0.7

def test_get_open_positions_summary_force(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: [DummyForceSummary()])
    summary = PositionManager.get_open_positions_summary()
    assert summary == {"AUDUSD": [0.7]}
