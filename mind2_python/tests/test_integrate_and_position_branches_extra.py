import pytest
import mind2_python.integrate_decisions as idec
from mind2_python.integrate_decisions import integrate  # alias at line 226
from mind2_python.position_manager import PositionManager
import mind2_python.position_manager as pm


# =======================================================
# integrate_decisions.py extra branches
# =======================================================

def test_integrate_fallback_single_unknown(caplog):
    """decision = '??' แค่ตัวเดียว → trigger fallback line 71"""
    caplog.set_level("DEBUG")
    scalp = {"decision": "??", "confidence": 0.5}
    day = {"decision": "BUY", "confidence": 0.5}
    swing = {"decision": "SELL", "confidence": 0.5}
    out = idec.integrate_decisions(scalp, day, swing)
    assert out["decision"] == "HOLD"
    assert out["confidence"] == 0.0
    assert "[Hybrid] unknown decision value" in caplog.text


def test_integrate_logger_debug_trend_regime(caplog):
    """regime='trend' → logger.debug lines 184–191"""
    caplog.set_level("DEBUG")
    scalp = {"decision": "BUY", "confidence": 0.9}
    day = {"decision": "SELL", "confidence": 0.9}
    swing = {"decision": "HOLD", "confidence": 0.9}
    idec.integrate_decisions(scalp, day, swing, mode="hybrid", regime="trend")
    assert any("regime=trend" in r.message for r in caplog.records)


def test_integrate_alias_direct_import():
    """cover alias integrate at line 226"""
    scalp = {"decision": "BUY", "confidence": 1.0}
    day = {"decision": "SELL", "confidence": 1.0}
    swing = {"decision": "HOLD", "confidence": 1.0}
    out = integrate(scalp, day, swing)
    assert isinstance(out, dict)
    assert "decision" in out


# =======================================================
# position_manager.py extra branches
# =======================================================

@pytest.fixture
def manager_sim():
    inst = PositionManager._instance()
    inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
    return inst


def test_update_position_symbol_missing(manager_sim):
    """lines 61–70 → state ไม่มี symbol"""
    manager_sim.state["positions"]["EURUSD"] = []  # ไม่มี BTCUSDc
    manager_sim.update_position("BTCUSDc", ticket=1, sl=99.0, tp=[{"price": 110}])


def test_update_position_ticket_mismatch(manager_sim):
    """lines 62->61, 63->65, 65->67 → loop แต่ไม่ match ticket"""
    manager_sim.state["positions"]["XAUUSDc"] = [{"ticket": 111, "sl": None, "tp": None}]
    # ticket ไม่ตรง → จะวน loop แต่ไม่เข้า if
    manager_sim.update_position("XAUUSDc", ticket=999, sl=88.0, tp=[{"price": 120}])
    # ค่าไม่ถูก update
    assert manager_sim.state["positions"]["XAUUSDc"][0]["sl"] is None


def test_get_positions_exception(monkeypatch):
    """lines 178–189 → mt5.positions_get raise Exception"""
    monkeypatch.setattr(pm.mt5, "positions_get", lambda **kwargs: (_ for _ in ()).throw(Exception("fail")))
    got = PositionManager.get_positions("BTCUSDc")
    assert got == []


@pytest.mark.parametrize("ticket", [None, 123])
def test_close_position_empty_list(manager_sim, ticket):
    """lines 187–188 → close_position safe fallback"""
    manager_sim.state["positions"]["BTCUSDc"] = []
    manager_sim.close_position("BTCUSDc", ticket=ticket)


def test_summary_no_positions(monkeypatch):
    """lines 223–225 → summary returns {}"""
    monkeypatch.setattr(PositionManager, "get_positions", staticmethod(lambda symbol=None: []))
    out = PositionManager.summary()
    assert out == {"total": 0, "symbols": {}}


@pytest.mark.parametrize("path", ["inst", "cls", "empty"])
def test_get_open_positions_fallbacks(path):
    """lines 268, 282–298, 324 → fallbacks inst/cls/empty"""
    # reset state
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

def test_integrate_logger_debug_trend_regime(caplog):
    caplog.set_level("DEBUG")
    import logging
    logging.getLogger("mind2_python.integrate_decisions").setLevel(logging.DEBUG)

    scalp = {"decision": "BUY", "confidence": 0.8}
    day = {"decision": "SELL", "confidence": 0.8}
    swing = {"decision": "HOLD", "confidence": 0.8}
    idec.integrate_decisions(scalp, day, swing, mode="hybrid", regime="trend")

    assert caplog.messages, "expected debug logs but got none"
    assert any("regime" in msg or "final" in msg for msg in caplog.messages)
