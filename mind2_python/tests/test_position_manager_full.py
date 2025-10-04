import pytest
import mind2_python.position_manager as pm
from mind2_python.position_manager import PositionManager

# ---------------------------
# Fixtures
# ---------------------------
@pytest.fixture
def manager_sim():
    """Fixture สำหรับ simulation mode: reset state ทุกครั้ง"""
    inst = PositionManager._instance()
    inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
    return inst


# ---------------------------
# Health state
# ---------------------------
def test_update_and_get_health():
    acc = {"balance": 1000, "equity": 900, "margin_level": 200}
    PositionManager.update_health(acc)
    state = PositionManager.get_health()
    assert state["balance"] == 1000
    assert state["equity"] == 900
    assert state["margin_level"] == 200
    assert "timestamp" in state


# ---------------------------
# Simulation mode update_position
# ---------------------------
def test_update_position_simulation(manager_sim):
    pos = manager_sim.open_position("XAUUSDc", lot=0.1, side="BUY", entry=100)
    ticket = pos["ticket"]
    manager_sim.update_position("XAUUSDc", ticket, sl=95.0, tp=[{"price": 110}], exit_levels={"tp": 110})
    updated = manager_sim.state["positions"]["XAUUSDc"][0]
    assert updated["sl"] == 95.0
    assert updated["tp"] == [{"price": 110}]
    assert updated["exit_levels"] == {"tp": 110}


# ---------------------------
# Production mode update_position
# ---------------------------
class DummyInfo:
    def __init__(self):
        self.stops_level = 10
        self.point = 0.1

class DummyTick:
    bid = 100
    ask = 101

class DummyResult:
    def __init__(self, retcode):
        self.retcode = retcode


def test_update_position_production_success(monkeypatch):
    mgr = PositionManager()  # instance ธรรมดา → production path

    monkeypatch.setattr(pm.mt5, "symbol_info", lambda sym: DummyInfo())
    monkeypatch.setattr(pm.mt5, "symbol_info_tick", lambda sym: DummyTick())
    monkeypatch.setattr(pm.mt5, "order_send", lambda req: DummyResult(pm.mt5.TRADE_RETCODE_DONE))
    monkeypatch.setattr(pm.mt5, "TRADE_ACTION_SLTP", 42)
    monkeypatch.setattr(pm.mt5, "TRADE_RETCODE_DONE", 100)

    mgr.update_position("XAUUSDc", ticket=1, sl=99, tp=[{"price": 105}])


def test_update_position_production_no_info(monkeypatch):
    mgr = PositionManager()

    monkeypatch.setattr(pm.mt5, "symbol_info", lambda sym: None)
    mgr.update_position("XAUUSDc", ticket=1, sl=99, tp=[{"price": 105}])


def test_update_position_production_fail(monkeypatch):
    mgr = PositionManager()

    monkeypatch.setattr(pm.mt5, "symbol_info", lambda sym: DummyInfo())
    monkeypatch.setattr(pm.mt5, "symbol_info_tick", lambda sym: DummyTick())
    monkeypatch.setattr(pm.mt5, "order_send", lambda req: DummyResult(999))
    monkeypatch.setattr(pm.mt5, "TRADE_ACTION_SLTP", 42)
    monkeypatch.setattr(pm.mt5, "TRADE_RETCODE_DONE", 100)

    mgr.update_position("XAUUSDc", ticket=1, sl=99, tp=[{"price": 105}])


# ---------------------------
# get_positions / count_open_positions
# ---------------------------
def test_get_positions_and_count(monkeypatch):
    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: [1, 2, 3])
    assert len(PositionManager.get_positions()) == 3
    assert PositionManager.count_open_positions("XAUUSDc") == 3
    assert PositionManager.has_open_position("XAUUSDc") is True


def test_get_positions_exception(monkeypatch):
    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: (_ for _ in ()).throw(Exception("boom")))
    assert PositionManager.get_positions("XAUUSDc") == []
    assert PositionManager.count_open_positions("XAUUSDc") == 0


# ---------------------------
# SL/TP helper
# ---------------------------
def test_compute_sl_tp():
    sl, tp = PositionManager.compute_sl_tp(100, "BUY", atr=2)
    assert sl == 97 and tp == 106
    sl, tp = PositionManager.compute_sl_tp(100, "SELL", atr=2)
    assert sl == 103 and tp == 94


# ---------------------------
# _parse_comment
# ---------------------------
@pytest.mark.parametrize("comment,expected", [
    ("series-2|0.8|0.6", (0.8, 0.6, 2)),
    ("0.7|0.5", (0.7, 0.5, 1)),
    ("invalid", (0.0, 0.0, 1)),
    ("", (0.0, 0.0, 1)),
])
def test_parse_comment(comment, expected):
    assert PositionManager._parse_comment(comment) == expected


# ---------------------------
# summary & get_open_positions_summary
# ---------------------------
class DummyPosition:
    def __init__(self):
        self.ticket = 1
        self.symbol = "XAUUSDc"
        self.volume = 0.1
        self.type = 0
        self.price_open = 100
        self.profit = 5
        self.comment = "series-1|0.9|0.8"
        self.sl = 95
        self.tp = 110

def test_summary_and_open_positions_summary(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", staticmethod(lambda symbol=None: [DummyPosition()]))
    out = PositionManager.summary()
    assert out["total"] == 1
    assert "XAUUSDc" in out["symbols"]

    out2 = PositionManager.get_open_positions_summary()
    assert "XAUUSDc" in out2


# ---------------------------
# Simulation open/close/get_open_positions
# ---------------------------
def test_open_and_close_positions(manager_sim):
    pos = manager_sim.open_position("XAUUSDc", lot=0.1, side="BUY", entry=100, atr=2)
    assert "sl" in pos and "tp" in pos
    ticket = pos["ticket"]

    manager_sim.close_position("XAUUSDc", ticket=ticket)
    assert manager_sim.state["orders_count"]["XAUUSDc"] >= 0

    pos2 = manager_sim.open_position("XAUUSDc", lot=0.1, side="BUY", entry=100)
    manager_sim.close_position("XAUUSDc")
    assert isinstance(pos2, dict)


def test_get_open_positions_fallback(manager_sim, monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", staticmethod(lambda symbol=None: (_ for _ in ()).throw(Exception("boom"))))

    inst = PositionManager._instance()
    inst.state["positions"] = {"XAUUSDc": [{"ticket": 1, "symbol": "XAUUSDc"}]}
    out = PositionManager.get_open_positions("XAUUSDc")
    assert out and out[0]["symbol"] == "XAUUSDc"
