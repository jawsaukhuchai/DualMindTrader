import pytest
from mind2_python.position_manager import PositionManager

def test_close_position_without_ticket_btc():
    pm = PositionManager._instance()
    pos1 = pm.open_position("BTCUSDc", 0.1, "BUY", 50000)
    pos2 = pm.open_position("BTCUSDc", 0.1, "BUY", 50100)
    before = len(pm.state["positions"]["BTCUSDc"])
    pm.close_position("BTCUSDc")  # no ticket → remove first
    after = len(pm.state["positions"]["BTCUSDc"])
    assert after == before - 1

def test_update_position_symbol_not_in_state_xau():
    pm = PositionManager._instance()
    # ไม่มี XAUUSDc ใน state → ควร return เงียบ ๆ
    pm.update_position("XAUUSDc", ticket=999, sl=1800, tp=[{"price":1850}])

def test_get_open_positions_fallback_btc(monkeypatch):
    pm = PositionManager._instance()
    pm.open_position("BTCUSDc", 0.2, "SELL", 48000)
    # บังคับให้ get_positions throw → ใช้ fallback state
    monkeypatch.setattr(PositionManager, "get_positions", staticmethod(lambda symbol=None: (_ for _ in ()).throw(Exception("fail"))))
    res = PositionManager.get_open_positions("BTCUSDc")
    assert res and res[0]["symbol"] == "BTCUSDc"

def test__instance_reinitialize_state_xau():
    PositionManager._inst = PositionManager()
    if hasattr(PositionManager._inst, "state"):
        delattr(PositionManager._inst, "state")
    inst = PositionManager._instance()
    assert "positions" in inst.state
    assert isinstance(inst.state["positions"], dict)
