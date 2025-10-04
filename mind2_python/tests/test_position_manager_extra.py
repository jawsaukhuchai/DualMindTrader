import pytest
import types
import mind2_python.position_manager as pm
from mind2_python.position_manager import PositionManager

def test_update_and_get_health(monkeypatch):
    acc = {"balance": 1000, "equity": 1200, "margin_level": 250}
    PositionManager.update_health(acc)
    state = PositionManager.get_health()
    assert state["balance"] == 1000
    assert "timestamp" in state

def test_open_and_close_position_simulation():
    pmgr = PositionManager._instance()
    pos = pmgr.open_position("EURUSD", lot=0.1, side="BUY", entry=1.2345, atr=0.01)
    assert pos["symbol"] == "EURUSD"
    # update_position simulation
    pmgr.update_position("EURUSD", ticket=pos["ticket"], sl=1.22, tp=[{"price":1.25}])
    updated = [p for p in pmgr.state["positions"]["EURUSD"] if p["ticket"] == pos["ticket"]][0]
    assert updated["sl"] == 1.22
    # close position
    pmgr.close_position("EURUSD", ticket=pos["ticket"])
    assert all(p["ticket"] != pos["ticket"] for p in pmgr.state["positions"]["EURUSD"])

def test_parse_comment_formats():
    c1 = PositionManager._parse_comment("series-2|0.8|0.6")
    assert c1 == (0.8, 0.6, 2)
    c2 = PositionManager._parse_comment("0.5|0.7")
    assert c2 == (0.5, 0.7, 1)
    c3 = PositionManager._parse_comment("bad-data")
    assert c3 == (0.0, 0.0, 1)

def test_get_open_positions_fallback_state(monkeypatch):
    pmgr = PositionManager._instance()
    pmgr.open_position("XAUUSD", lot=0.2, side="SELL", entry=1800.0)
    # mock ให้ mt5.positions_get raise exception
    monkeypatch.setattr(pm.mt5, "positions_get", lambda symbol=None: (_ for _ in ()).throw(Exception("fail")))
    positions = PositionManager.get_open_positions("XAUUSD")
    assert positions and positions[0]["symbol"] == "XAUUSD"

def test_get_positions_and_count(monkeypatch):
    fake_positions = [types.SimpleNamespace(ticket=1, symbol="EURUSD", volume=0.1,
                                            type=0, price_open=1.2345, profit=5.0, comment="0.8|0.6")]
    monkeypatch.setattr(pm.mt5, "positions_get", lambda symbol=None: fake_positions)
    assert PositionManager.count_open_positions("EURUSD") == 1
    got = PositionManager.get_positions("EURUSD")
    assert got[0].symbol == "EURUSD"

def test_get_positions_exception(monkeypatch):
    monkeypatch.setattr(pm.mt5, "positions_get", lambda symbol=None: (_ for _ in ()).throw(Exception("fail")))
    got = PositionManager.get_positions("EURUSD")
    assert got == []

def test_compute_sl_tp_buy_and_sell():
    sl, tp = PositionManager.compute_sl_tp(100.0, "BUY", atr=2.0)
    assert sl < 100 and tp > 100
    sl2, tp2 = PositionManager.compute_sl_tp(100.0, "SELL", atr=2.0)
    assert sl2 > 100 and tp2 < 100
