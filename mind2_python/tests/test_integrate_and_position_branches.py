import pytest
import mind2_python.integrate_decisions as idec
from mind2_python.position_manager import PositionManager


# -------------------------------
# integrate_decisions missing branches
# -------------------------------

def test_integrate_unknown_decision_value_triggers_fallback(caplog):
    caplog.set_level("DEBUG")
    # scalp decision ไม่รู้จัก → ควร fallback
    scalp = {"decision": "??", "confidence": 0.8}
    day = {"decision": "BUY", "confidence": 0.8}
    swing = {"decision": "SELL", "confidence": 0.8}
    out = idec.integrate_decisions(scalp, day, swing)
    assert out["decision"] == "HOLD"
    assert out["confidence"] == 0.0
    assert "[Hybrid] unknown decision value" in caplog.text


def test_integrate_alias_function_covers_line_226():
    scalp = {"decision": "BUY", "confidence": 1.0}
    day = {"decision": "SELL", "confidence": 1.0}
    swing = {"decision": "HOLD", "confidence": 1.0}
    out = idec.integrate(scalp, day, swing)
    assert isinstance(out, dict)
    assert "decision" in out


def test_integrate_logger_debug_line(caplog):
    caplog.set_level("DEBUG")
    scalp = {"decision": "BUY", "confidence": 0.5}
    day = {"decision": "SELL", "confidence": 0.5}
    swing = {"decision": "HOLD", "confidence": 0.5}
    idec.integrate_decisions(scalp, day, swing, mode="hybrid", regime="normal")
    # ควรมี log debug ครอบ line 184-191
    assert any("final=" in r.message for r in caplog.records)


# -------------------------------
# position_manager missing branches
# -------------------------------

@pytest.fixture
def manager_sim():
    inst = PositionManager._instance()
    inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
    return inst


def test_update_position_symbol_not_in_state(manager_sim):
    # ไม่มี symbol ใน state → ไม่ควร crash
    manager_sim.update_position("BTCUSDc", ticket=999, sl=100.0, tp=[{"price": 110}])


@pytest.mark.parametrize("ticket", [123, None])
def test_close_position_empty_and_missing_ticket(manager_sim, ticket):
    manager_sim.state["positions"]["XAUUSDc"] = []
    manager_sim.close_position("XAUUSDc", ticket=ticket)
    # ไม่ควร raise error


@pytest.mark.parametrize("fallback", ["inst", "cls", "empty"])
def test_get_open_positions_all_fallbacks(fallback):
    # reset
    if hasattr(PositionManager, "_inst"):
        delattr(PositionManager, "_inst")
    if hasattr(PositionManager, "state"):
        delattr(PositionManager, "state")

    if fallback == "inst":
        inst = PositionManager._instance()
        inst.state["positions"]["BTCUSDc"] = [{"ticket": 1, "symbol": "BTCUSDc"}]
        got = PositionManager.get_open_positions("BTCUSDc")
        assert got and got[0]["symbol"] == "BTCUSDc"

    elif fallback == "cls":
        PositionManager.state = {"positions": {"XAUUSDc": [{"ticket": 2, "symbol": "XAUUSDc"}]}}
        got = PositionManager.get_open_positions("XAUUSDc")
        assert got and got[0]["symbol"] == "XAUUSDc"

    else:  # empty
        got = PositionManager.get_open_positions("SOMETHING")
        assert got == []


def test_integrate_logger_debug_line(caplog):
    caplog.set_level("DEBUG")
    import logging
    logging.getLogger("mind2_python.integrate_decisions").setLevel(logging.DEBUG)

    scalp = {"decision": "BUY", "confidence": 0.7}
    day = {"decision": "SELL", "confidence": 0.8}
    swing = {"decision": "HOLD", "confidence": 0.6}
    idec.integrate_decisions(scalp, day, swing, mode="hybrid", regime="trend")

    assert caplog.messages, "expected debug logs but got none"
    assert any("regime" in msg or "final" in msg for msg in caplog.messages)
