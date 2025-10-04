# tests/test_position_manager_fallback.py
import pytest
from mind2_python.position_manager import PositionManager


@pytest.fixture
def pm():
    # ใช้ singleton _inst เพื่อให้ fallback ใช้ state ตัวเดียวกัน
    inst = PositionManager._instance()
    inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
    return inst


def test_get_open_positions_fallback_empty_list(pm, monkeypatch):
    pm.open_position("XAUUSD", 1.0, "BUY", 2000)
    pm.open_position("XAUUSD", 2.0, "SELL", 2010)

    # mock get_positions → คืนค่า list ว่าง
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: [])

    results = PositionManager.get_open_positions("XAUUSD")
    assert len(results) == 2
    assert {p["lot"] for p in results} == {1.0, 2.0}


def test_get_open_positions_fallback_none(pm, monkeypatch):
    pm.open_position("BTCUSD", 0.5, "BUY", 30000)

    # mock get_positions → คืนค่า None
    monkeypatch.setattr(PositionManager, "get_positions", lambda symbol=None: None)

    results = PositionManager.get_open_positions("BTCUSD")
    assert len(results) == 1
    assert results[0]["symbol"] == "BTCUSD"
    assert results[0]["lot"] == 0.5
