import pytest
import mind2_python.integrate_decisions as idec
from mind2_python.integrate_decisions import integrate  # alias ตรง line 226
import mind2_python.position_manager as pm
from mind2_python.position_manager import PositionManager


# =======================================================
# integrate_decisions.py missing branches
# =======================================================

def test_integrate_all_unknown_decisions_trigger_fallback(caplog):
    """ทุก decision = '??' → score() = None → trigger _fallback_dict (line 71)"""
    caplog.set_level("DEBUG")
    scalp = {"decision": "??", "confidence": 0.1}
    day = {"decision": "??", "confidence": 0.2}
    swing = {"decision": "??", "confidence": 0.3}
    out = idec.integrate_decisions(scalp, day, swing)
    assert out["decision"] == "HOLD"
    assert out["confidence"] == 0.0
    assert "[Hybrid] unknown decision value" in caplog.text


def test_integrate_logger_debug_branch(caplog):
    """logger.debug lines 184–191"""
    caplog.set_level("DEBUG")
    scalp = {"decision": "BUY", "confidence": 0.5}
    day = {"decision": "SELL", "confidence": 0.5}
    swing = {"decision": "HOLD", "confidence": 0.5}
    idec.integrate_decisions(scalp, day, swing, mode="hybrid", regime="trend")
    assert any("[Hybrid] regime=" in r.message for r in caplog.records)


def test_integrate_alias_direct_import():
    """cover alias integrate = integrate_decisions (line 226)"""
    scalp = {"decision": "BUY", "confidence": 1.0}
    day = {"decision": "SELL", "confidence": 1.0}
    swing = {"decision": "HOLD", "confidence": 0.5}
    out = integrate(scalp, day, swing)
    assert isinstance(out, dict)
    assert "decision" in out


# =======================================================
# position_manager.py missing branches
# =======================================================

@pytest.fixture
def manager_sim():
    inst = PositionManager._instance()
    inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
    return inst


def test_update_position_symbol_not_in_state(manager_sim):
    """lines 61–70 → symbol ไม่มีใน state"""
    manager_sim.update_position("BTCUSDc", ticket=999, sl=101.0, tp=[{"price": 110}])


@pytest.mark.parametrize("ticket", [123, None])
def test_close_position_empty_and_missing_ticket(manager_sim, ticket):
    """lines 187–188 → close_position safe fallback"""
    manager_sim.state["positions"]["XAUUSDc"] = []
    manager_sim.close_position("XAUUSDc", ticket=ticket)


def test_get_positions_exception(monkeypatch):
    """lines 178–180 → get_positions exception path"""
    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: (_ for _ in ()).throw(Exception("fail")))
    got = PositionManager.get_positions("BTCUSDc")
    assert got == []


def test_summary_no_positions(monkeypatch):
    """lines 223–225 → summary returns {} when no positions"""
    monkeypatch.setattr(PositionManager, "get_positions", staticmethod(lambda symbol=None: []))
    out = PositionManager.summary()
    assert out == {"total": 0, "symbols": {}}


@pytest.mark.parametrize("path", ["inst", "cls", "empty"])
def test_get_open_positions_fallbacks(path):
    """cover lines 268, 282–298, 324"""
    # reset
    if hasattr(PositionManager, "_inst"):
        delattr(PositionManager, "_inst")
    if hasattr(PositionManager, "state"):
        delattr(PositionManager, "state")

    if path == "inst":
        inst = PositionManager._instance()
        inst.state["positions"]["BTCUSDc"] = [{"ticket": 1, "symbol": "BTCUSDc"}]
        got = PositionManager.get_open_positions("BTCUSDc")
        assert got and got[0]["symbol"] == "BTCUSDc"

    elif path == "cls":
        PositionManager.state = {"positions": {"XAUUSDc": [{"ticket": 2, "symbol": "XAUUSDc"}]}}
        got = PositionManager.get_open_positions("XAUUSDc")
        assert got and got[0]["symbol"] == "XAUUSDc"

    else:  # empty
        got = PositionManager.get_open_positions("SOMETHING")
        assert got == []


def test_integrate_logger_debug_branch(caplog):
    caplog.set_level("DEBUG")
    import logging
    logging.getLogger("mind2_python.integrate_decisions").setLevel(logging.DEBUG)

    scalp = {"decision": "BUY", "confidence": 0.5}
    day = {"decision": "SELL", "confidence": 0.5}
    swing = {"decision": "HOLD", "confidence": 0.5}
    idec.integrate_decisions(scalp, day, swing, mode="hybrid", regime="trend")

    assert caplog.messages, "expected debug logs but got none"
    assert any("regime" in msg or "final" in msg for msg in caplog.messages)


def test_get_positions_with_parts(monkeypatch):
    """cover case when mt5.positions_get returns non-empty list"""
    import mind2_python.position_manager as pm

    class MockPos:
        ticket = 1
        symbol = "XAUUSDc"
        volume = 0.1
        type = 0
        price_open = 2000.0
        profit = 5.0
        comment = "series-1|0.8|0.7"
        sl = 1990.0
        tp = 2020.0

        def _asdict(self):
            return {
                "ticket": self.ticket,
                "symbol": self.symbol,
                "volume": self.volume,
                "type": self.type,
                "price_open": self.price_open,
                "profit": self.profit,
                "comment": self.comment,
                "sl": self.sl,
                "tp": self.tp,
            }

    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: [MockPos()])
    got = pm.PositionManager.get_open_positions("XAUUSDc")
    assert isinstance(got, list)
    assert got and got[0]["symbol"] == "XAUUSDc"
    assert got[0]["ticket"] == 1
    assert got[0]["lot"] == 0.1
    assert got[0]["side"] == "BUY"
    assert got[0]["conf"] == 0.8
    assert got[0]["winprob"] == 0.7


def test_get_open_positions_false_branch_empty(monkeypatch):
    """force condition False: list but empty"""
    import mind2_python.position_manager as pm
    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: [])
    result = pm.PositionManager.get_open_positions("XAUUSDc")
    assert result == []


def test_get_open_positions_false_branch_none(monkeypatch):
    """force condition False: not a list"""
    import mind2_python.position_manager as pm
    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: None)
    result = pm.PositionManager.get_open_positions("XAUUSDc")
    assert result == []
