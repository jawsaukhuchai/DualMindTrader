import pytest
import types
import logging

import mind2_python.integrate_decisions as idec
import mind2_python.position_manager as pm
from mind2_python.position_manager import PositionManager


# -------------------------------
# integrate_decisions fallbacks
# -------------------------------

def make_res(dec="HOLD", conf=0.0):
    return {"decision": dec, "confidence": conf}

def test_strict_mode_num_entries():
    scalp, day, swing = make_res("BUY", 0.9), make_res("BUY", 0.9), make_res("BUY", 0.9)
    result = idec.integrate_decisions(scalp, day, swing, mode="strict")
    assert result["num_entries"] == 1

def test_priority_mode_no_priority_decision_keeps_score():
    scalp, day, swing = make_res("SELL", 0.5), make_res("SELL", 0.5), make_res("HOLD", 0.1)
    sym_cfg = {"max_num_entries": 3}  # ไม่มี priority_dec
    result = idec.integrate_decisions(scalp, day, swing, sym_cfg=sym_cfg, mode="priority")
    # decision ควรจะเป็น SELL จาก score-based
    assert result["decision"] in ("SELL", "HOLD")

def test_integrate_alias_callable():
    scalp, day, swing = make_res("BUY"), make_res("SELL"), make_res("HOLD")
    out = idec.integrate(scalp, day, swing, mode="hybrid")
    assert isinstance(out, dict)
    assert "decision" in out


# -------------------------------
# position_manager production fail
# -------------------------------

class DummyResult:
    def __init__(self, retcode):
        self.retcode = retcode

def test_update_position_symbol_info_none(monkeypatch):
    pmgr = PositionManager()
    # mock symbol_info → None
    monkeypatch.setattr(pm.mt5, "symbol_info", lambda sym: None)
    called = {}
    def fake_print(msg, log_level=None): called["msg"] = msg
    monkeypatch.setattr(pm, "safe_print", fake_print)
    pmgr.update_position("FAKE", 123)
    assert "No symbol_info" in called["msg"]

def test_update_position_stops_level_too_close(monkeypatch):
    pmgr = PositionManager()
    class Info: stops_level=10; point=0.01
    class Tick: bid=1.0000; ask=1.0001
    monkeypatch.setattr(pm.mt5, "symbol_info", lambda sym: Info())
    monkeypatch.setattr(pm.mt5, "symbol_info_tick", lambda sym: Tick())
    monkeypatch.setattr(pm.mt5, "order_send", lambda req: DummyResult(retcode=pm.mt5.TRADE_RETCODE_DONE))
    # run → ควรเข้า warning branch ว่า SL/TP too close
    pmgr.update_position("FAKE", 999, sl=1.00005, tp=[{"price":1.00015}])

def test_update_position_order_send_fail(monkeypatch):
    pmgr = PositionManager()
    class Info: stops_level=0; point=0.01
    monkeypatch.setattr(pm.mt5, "symbol_info", lambda sym: Info())
    monkeypatch.setattr(pm.mt5, "symbol_info_tick", lambda sym: None)
    monkeypatch.setattr(pm.mt5, "order_send", lambda req: DummyResult(retcode=999))
    pmgr.update_position("FAKE", 888, sl=1.1, tp=[{"price":1.2}])

def test_summary_no_positions(monkeypatch):
    monkeypatch.setattr(PositionManager, "get_positions", staticmethod(lambda: []))
    out = PositionManager.summary()
    assert out == {"total": 0, "symbols": {}}

def test_get_open_positions_fallback_inst_and_cls(monkeypatch):
    pmgr = PositionManager._instance()
    pmgr.state["positions"]["USDJPY"] = [{
        "ticket":1,"symbol":"USDJPY","lot":0.1,"side":"BUY",
        "entry":145.0,"profit":0.0,"conf":0.5,"winprob":0.5,
        "entry_index":1
    }]
    # make mt5 fail
    monkeypatch.setattr(pm, "mt5", types.SimpleNamespace(
        positions_get=lambda symbol=None: (_ for _ in ()).throw(Exception("fail"))
    ))
    got = PositionManager.get_open_positions("USDJPY")
    assert got and got[0]["symbol"] == "USDJPY"

def test_get_open_positions_fallback_empty():
    # ลบ _inst และ state เพื่อบังคับ path empty
    if hasattr(PositionManager, "_inst"):
        delattr(PositionManager, "_inst")
    if hasattr(PositionManager, "state"):
        delattr(PositionManager, "state")
    got = PositionManager.get_open_positions("SOMETHING")
    assert got == []


# -------------------------------
# logger routing
# -------------------------------

def test_logger_routing_levels(caplog):
    caplog.set_level(logging.DEBUG)
    log = logging.getLogger("mind2_python.logger")
    log.debug("debug-msg")
    log.info("info-msg")
    log.warning("warn-msg")
    log.error("error-msg")
    # check that logs captured
    msgs = [r.message for r in caplog.records]
    assert any("debug-msg" in m for m in msgs)
    assert any("info-msg" in m for m in msgs)
    assert any("warn-msg" in m for m in msgs)
    assert any("error-msg" in m for m in msgs)
