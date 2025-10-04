import pytest
import mind2_python.integrate_decisions as idec
import mind2_python.position_manager as pm
from mind2_python.position_manager import PositionManager


# -------------------------------
# integrate_decisions parametrize
# -------------------------------
@pytest.mark.parametrize(
    "symbol,mode,scalp,day,swing,expected_entries",
    [
        ("BTCUSDc", "strict",
         {"decision":"BUY","confidence":1.0},
         {"decision":"BUY","confidence":1.0},
         {"decision":"BUY","confidence":1.0}, 1),

        ("XAUUSDc", "majority",
         {"decision":"BUY","confidence":1.0},
         {"decision":"BUY","confidence":1.0},
         {"decision":"SELL","confidence":1.0}, 2),

        ("BTCUSDc", "priority",
         {"decision":"SELL","confidence":0.8},
         {"decision":"SELL","confidence":0.8},
         {"decision":"SELL","confidence":0.8}, 3),

        ("XAUUSDc", "hybrid",
         {"decision":"HOLD","confidence":0.6},
         {"decision":"HOLD","confidence":0.6},
         {"decision":"HOLD","confidence":0.6}, 2),

        ("BTCUSDc", "unknown",
         {"decision":"BUY","confidence":0.5},
         {"decision":"SELL","confidence":0.5},
         {"decision":"HOLD","confidence":0.5}, 0),  # fallback
    ]
)
def test_integrate_decisions_modes(symbol, mode, scalp, day, swing, expected_entries, caplog):
    result = idec.integrate_decisions(scalp, day, swing, mode=mode, sym_cfg={"symbol": symbol})
    assert isinstance(result, dict)
    assert "decision" in result
    if mode == "unknown":
        assert result["decision"] == "HOLD"
        assert result["num_entries"] == 0
        assert "[Hybrid] unknown mode" in caplog.text
    else:
        assert result["num_entries"] <= expected_entries


# -------------------------------
# position_manager parametrize
# -------------------------------
@pytest.fixture
def manager_sim():
    inst = PositionManager._instance()
    inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
    return inst


@pytest.mark.parametrize(
    "symbol,update_symbol,should_update",
    [
        ("BTCUSDc", "BTCUSDc", True),
        ("BTCUSDc", "XAUUSDc", False),
        ("XAUUSDc", "XAUUSDc", True),
        ("XAUUSDc", "BTCUSDc", False),
    ]
)
def test_update_position_simulation_symbols(manager_sim, symbol, update_symbol, should_update):
    manager_sim.state["positions"][symbol] = [{"ticket":111,"sl":None,"tp":None}]
    manager_sim.update_position(update_symbol, ticket=111, sl=1.11, tp=[{"price":1.22}])
    if should_update:
        assert manager_sim.state["positions"][symbol][0]["sl"] == 1.11
    else:
        assert manager_sim.state["positions"][symbol][0]["sl"] is None


@pytest.mark.parametrize("fallback_path", ["inst","cls","empty"])
@pytest.mark.parametrize("symbol", ["BTCUSDc","XAUUSDc"])
def test_get_open_positions_fallbacks(symbol, fallback_path):
    if hasattr(PositionManager, "_inst"):
        delattr(PositionManager, "_inst")
    if hasattr(PositionManager, "state"):
        delattr(PositionManager, "state")

    if fallback_path == "inst":
        inst = PositionManager._instance()
        inst.state["positions"][symbol] = [{"ticket":1,"symbol":symbol,"lot":0.1}]
        result = PositionManager.get_open_positions(symbol)
        assert result and result[0]["symbol"] == symbol

    elif fallback_path == "cls":
        PositionManager.state = {"positions":{symbol:[{"ticket":2,"symbol":symbol,"lot":0.2}]}}
        result = PositionManager.get_open_positions(symbol)
        assert result and result[0]["symbol"] == symbol

    else:  # empty
        result = PositionManager.get_open_positions(symbol)
        assert result == []
