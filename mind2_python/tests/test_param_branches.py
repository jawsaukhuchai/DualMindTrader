import pytest
import mind2_python.integrate_decisions as idec
from mind2_python.position_manager import PositionManager


# -------------------------------
# integrate_decisions branches
# -------------------------------
@pytest.mark.parametrize(
    "mode,scalp,day,swing,expected_num",
    [
        ("strict", {"decision":"BUY","confidence":1.0},
                   {"decision":"BUY","confidence":1.0},
                   {"decision":"BUY","confidence":1.0}, 1),
        ("majority", {"decision":"BUY","confidence":0.5},
                     {"decision":"BUY","confidence":0.5},
                     {"decision":"SELL","confidence":0.5}, 2),
        ("priority", {"decision":"SELL","confidence":0.9},
                     {"decision":"SELL","confidence":0.9},
                     {"decision":"SELL","confidence":0.9}, 3),
        ("hybrid", {"decision":"HOLD","confidence":0.2},
                   {"decision":"HOLD","confidence":0.2},
                   {"decision":"HOLD","confidence":0.2}, 1),
    ]
)
def test_integrate_modes_cover_branches(mode, scalp, day, swing, expected_num):
    sym_cfg = {"max_num_entries": 3}
    res = idec.integrate_decisions(scalp, day, swing, sym_cfg=sym_cfg, mode=mode)
    assert isinstance(res, dict)
    assert res["num_entries"] <= expected_num


@pytest.mark.parametrize("decision", ["BUY","SELL","HOLD",None,"??"])
def test_integrate_score_variants(decision):
    scalp, day, swing = {"decision":decision,"confidence":0.1}, {"decision":"HOLD"}, {"decision":"HOLD"}
    out = idec.integrate_decisions(scalp, day, swing)
    assert "decision" in out
    assert "num_entries" in out


# -------------------------------
# position_manager simulation + fallback
# -------------------------------
@pytest.mark.parametrize(
    "setup_symbol,update_symbol,expect_update",
    [
        ("EURUSD", "EURUSD", True),   # symbol exists
        ("EURUSD", "GBPUSD", False),  # symbol missing
    ]
)
def test_update_position_simulation_symbols(pmgr, setup_symbol, update_symbol, expect_update):
    pmgr.state["positions"][setup_symbol] = [{"ticket":111,"sl":None,"tp":None}]
    pmgr.update_position(update_symbol, ticket=111, sl=1.11, tp=[{"price":1.22}])
    if expect_update:
        assert pmgr.state["positions"][setup_symbol][0]["sl"] == 1.11
    else:
        assert pmgr.state["positions"][setup_symbol][0]["sl"] is None


@pytest.mark.parametrize("positions_get_result", [None, [], Exception("fail")])
def test_get_positions_variants(monkeypatch, positions_get_result):
    import mind2_python.position_manager as pm
    if isinstance(positions_get_result, Exception):
        monkeypatch.setattr(pm.mt5, "positions_get", lambda symbol=None: (_ for _ in ()).throw(positions_get_result))
    else:
        monkeypatch.setattr(pm.mt5, "positions_get", lambda symbol=None: positions_get_result)
    out = PositionManager.get_positions("FAKE")
    assert isinstance(out, list)


@pytest.mark.parametrize("state_setup", [None, "inst", "cls"])
def test_get_open_positions_fallback_paths(state_setup):
    import mind2_python.position_manager as pm
    # reset
    if hasattr(PositionManager, "_inst"):
        delattr(PositionManager, "_inst")
    if hasattr(PositionManager, "state"):
        delattr(PositionManager, "state")

    if state_setup == "inst":
        pmgr = PositionManager._instance()
        pmgr.state["positions"]["USDCHF"] = [{"ticket":1,"symbol":"USDCHF","lot":0.1}]
    elif state_setup == "cls":
        PositionManager.state = {"positions":{"AUDUSD":[{"ticket":2,"symbol":"AUDUSD","lot":0.2}]}}
    got = PositionManager.get_open_positions("USDCHF" if state_setup=="inst" else "AUDUSD")
    assert isinstance(got, list)
