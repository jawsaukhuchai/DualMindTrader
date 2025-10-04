import sys, types
import pytest
import time

# --- Fix missing correlation_risk module ---
fake_corr = types.ModuleType("mind2_python.correlation_risk")
class DummyCorrelationRisk:
    def __init__(self, cfg=None): pass
    def update(self, s, p): pass
    def check(self): return True, "ok"
fake_corr.CorrelationRisk = DummyCorrelationRisk
sys.modules["mind2_python.correlation_risk"] = fake_corr

# --- Fix missing config_loader module ---
fake_cfg = types.ModuleType("mind2_python.config_loader")
def fake_load_config(path, overrides=None): 
    return {"symbols": {"TEST": {}}, "global": {}}
def fake_deep_update(cfg, overrides): 
    cfg.update(overrides); return cfg
fake_cfg.load_config = fake_load_config
fake_cfg._deep_update = fake_deep_update
sys.modules["mind2_python.config_loader"] = fake_cfg

from mind2_python.decision_engine import (
    colorize_decision,
    colorize_reason,
    score_to_winprob,
    join_reasons,
    select_mode,
    RegimeDetector,
    AIManager,
    fusion_decision,
    DecisionEngine,
    GlobalExitManager,
    KillSwitchManager,
)
from mind2_python.schema import TradeEntry, Indicators


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------
def test_colorize_decision_variants():
    assert "BUY" in colorize_decision("BUY", "BUY")
    assert "SELL" in colorize_decision("SELL", "SELL")
    assert "HOLD" in colorize_decision("HOLD", "HOLD")
    assert "TEXT" in colorize_decision("OTHER", "TEXT")

def test_colorize_reason_variants():
    assert "blocked" in colorize_reason("blocked_reason").lower()
    assert "low_conf" in colorize_reason("low_conf").lower()
    assert "risk_ok" in colorize_reason("risk_ok").lower()
    assert "invalid atr" in colorize_reason("invalid atr").lower()

    # fallback branch → should contain original reason text
    res = colorize_reason("something")
    assert "something" in res

def test_score_to_winprob_and_join_reasons():
    assert score_to_winprob(0.5) == 50.0
    assert score_to_winprob(2) == 100.0
    assert join_reasons(["a", "b"]) == "a|b"
    assert "x" in join_reasons("x")


def test_select_mode_thresholds():
    sym_cfg = {"atr_threshold": 2.0, "adx_threshold": 30.0}
    entry = TradeEntry("T", 1, 2, 0.1, {}, {}, "2025-01-01", Indicators(atr=3, adx=40))
    assert select_mode(sym_cfg, entry) == "scaler"

    entry = TradeEntry("T", 1, 2, 0.1, {}, {}, "2025-01-01", Indicators(atr=0.5, adx=10))
    assert select_mode(sym_cfg, entry) == "strict"


# ------------------------------------------------------------
# RegimeDetector
# ------------------------------------------------------------
def test_regime_detector_all_paths():
    det = RegimeDetector({"atr_threshold": 2.0, "adx_threshold": 30.0})
    e = Indicators(atr=3, adx=40)  # trend
    assert det.detect(e) == "trend"

    e = Indicators(atr=0.5, adx=10)  # range
    assert det.detect(e) == "range"

    e = Indicators(atr=3, adx=10)  # high_vol
    assert det.detect(e) == "high_vol"

    e = Indicators(atr=0.5, adx=40)  # low_vol
    assert det.detect(e) == "low_vol"

    e = Indicators(atr=0, adx=0)  # normal
    assert det.detect(e) == "normal"


# ------------------------------------------------------------
# AIManager + Fusion
# ------------------------------------------------------------
def test_ai_manager_and_fusion():
    ai = AIManager()
    dummy_entry = TradeEntry("T", 1, 2, 0.1, {}, {}, "2025-01-01")
    ai_res = ai.evaluate(dummy_entry)
    assert ai_res["decision"] == "HOLD"

    rule_res = {"decision": "BUY", "confidence": 0.8}
    fused = fusion_decision(ai_res, rule_res, regime="trend")
    assert fused["decision"] in ["BUY", "SELL", "HOLD"]
    assert "score" in fused


# ------------------------------------------------------------
# DecisionEngine (mocked heavy parts)
# ------------------------------------------------------------
@pytest.fixture
def dummy_entry():
    tf = {
        "H1": {"rsi": 60, "atr": 2.0, "adx": 25, "ema_fast": 110, "ema_slow": 100, "macd_hist": 1.0},
        "M5": {"rsi": 55, "atr": 1.5, "adx": 20},
    }
    return TradeEntry(
        symbol="TEST",
        bid=100,
        ask=102,
        spread=2,
        filters={},
        timeframes=tf,
        timestamp="2025-09-26T00:00:00",
        indicators=Indicators.from_dict(tf["H1"]),
    )


def test_apply_override(monkeypatch, tmp_path):
    engine = DecisionEngine(config_path=str(tmp_path))
    engine.apply_override({"symbols": {"TEST": {"pip_size": 0.01}}})
    assert "TEST" in engine.symbols_cfg


def test_process_minimal(monkeypatch, dummy_entry, tmp_path):
    # patch heavy dependencies
    monkeypatch.setattr("mind2_python.decision_engine.RiskGuard", lambda cfg: type("R", (), {"allow": lambda self,e,f,balance: (True,["risk_ok"])})())
    monkeypatch.setattr("mind2_python.decision_engine.PortfolioManager", lambda cfg: type("P", (), {"allow": lambda self,e,f,balance: (True,["portfolio_ok"])})())
    monkeypatch.setattr("mind2_python.decision_engine.HybridExit", lambda cfg: type("H", (), {"calc": lambda self,*a,**kw: {"sl":None,"tp":[],"entries":{}}})())
    monkeypatch.setattr("mind2_python.decision_engine.PositionManager", type("PM", (), {"get_open_positions_summary": staticmethod(lambda : {}), "summary": staticmethod(lambda : {}), "open_position": lambda *a,**kw: None}))

    engine = DecisionEngine(config_path=str(tmp_path))
    result = engine.process(dummy_entry)
    assert isinstance(result, dict)
    assert "decision" in result
    assert result["symbol"] == "TEST"


def test_run_with_error(monkeypatch, dummy_entry, tmp_path):
    monkeypatch.setattr("mind2_python.decision_engine.DecisionEngine.process", lambda self, entry: (_ for _ in ()).throw(Exception("boom")))
    engine = DecisionEngine(config_path=str(tmp_path))
    results = engine.run([dummy_entry])
    assert results[0]["decision"] == "HOLD"
    assert "error_eval" in results[0]["reason"]



def test_run_triggers_dashboard(monkeypatch, dummy_entry, tmp_path):
    # patch heavy parts
    monkeypatch.setattr("mind2_python.decision_engine.RiskGuard", lambda cfg: type("R", (), {"allow": lambda self,e,f,balance: (True,["risk_ok"])})())
    monkeypatch.setattr("mind2_python.decision_engine.PortfolioManager", lambda cfg: type("P", (), {"allow": lambda self,e,f,balance: (True,["portfolio_ok"])})())
    monkeypatch.setattr("mind2_python.decision_engine.HybridExit", lambda cfg: type("H", (), {"calc": lambda self,*a,**kw: {"sl":None,"tp":[],"entries":{}}})())
    monkeypatch.setattr("mind2_python.decision_engine.PositionManager", type("PM", (), {
        "get_open_positions_summary": staticmethod(lambda : {}),
        "summary": staticmethod(lambda : {})
    }))

    # patch pretty_log_dashboard เพื่อให้ไม่ crash แต่ยังถูกเรียก
    called = {}
    def fake_dashboard(*a, **kw):
        called["ok"] = True
    monkeypatch.setattr("mind2_python.decision_engine.pretty_log_dashboard", fake_dashboard)

    engine = DecisionEngine(config_path=str(tmp_path))
    results = engine.run([dummy_entry])

    assert isinstance(results, list)
    assert results[0]["symbol"] == "TEST"
    # confirm dashboard ถูกเรียก
    assert "ok" in called


def test_run_positions_summary_error(monkeypatch, dummy_entry, tmp_path):
    # mock load_config
    monkeypatch.setattr("mind2_python.decision_engine.load_config", lambda path, overrides=None: {"symbols": {"TEST": {}}, "global": {}})

    # mock PositionManager.summary ให้โยน exception
    monkeypatch.setattr("mind2_python.decision_engine.PositionManager", type("PM", (), {
        "summary": staticmethod(lambda : (_ for _ in ()).throw(Exception("summary_fail"))),
        "get_open_positions_summary": staticmethod(lambda : {})
    }))

    # patch pretty_log_positions_summary เพื่อไม่ให้ crash เพิ่ม
    monkeypatch.setattr("mind2_python.decision_engine.pretty_log_positions_summary", lambda *a, **k: (_ for _ in ()).throw(Exception("log_fail")))

    engine = DecisionEngine(config_path=str(tmp_path))
    # run ต้องไม่ crash แต่ log error จะถูก trigger
    results = engine.run([dummy_entry])

    assert isinstance(results, list)
    assert results[0]["symbol"] == "TEST"


def test_run_dashboard_error(monkeypatch, dummy_entry, tmp_path):
    # mock load_config
    monkeypatch.setattr("mind2_python.decision_engine.load_config", lambda path, overrides=None: {"symbols": {"TEST": {}}, "global": {}})

    # mock PositionManager
    monkeypatch.setattr("mind2_python.decision_engine.PositionManager", type("PM", (), {
        "get_open_positions_summary": staticmethod(lambda : {}),
        "summary": staticmethod(lambda : {})
    }))

    # ทำ pretty_log_dashboard ให้โยน exception
    def fake_dashboard(*a, **k):
        raise Exception("dashboard_fail")
    monkeypatch.setattr("mind2_python.decision_engine.pretty_log_dashboard", fake_dashboard)

    engine = DecisionEngine(config_path=str(tmp_path))
    results = engine.run([dummy_entry])

    assert isinstance(results, list)
    assert results[0]["symbol"] == "TEST"


def test_get_global_atr(monkeypatch, tmp_path):
    # mock load_config ให้ไม่ crash
    monkeypatch.setattr("mind2_python.decision_engine.load_config", lambda path, overrides=None: {"symbols": {}, "global": {}})

    engine = DecisionEngine(config_path=str(tmp_path))
    result = engine.get_global_atr()

    # global_atr เริ่มต้นควรเป็น dict ว่าง
    assert isinstance(result, dict)
    assert result == {}


# ------------------------------------------------------------
# Extra patches for failed cases
# ------------------------------------------------------------
def test_force_exit_all_import_error(monkeypatch, caplog):
    """Extra coverage: simulate import PositionManager failure"""
    gm = GlobalExitManager()

    # บังคับให้ import ล้ม
    sys.modules.pop("mind2_python.position_manager", None)
    import builtins
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *a, **k: (_ for _ in ()).throw(ImportError("boom"))
        if name.startswith("mind2_python.position_manager")
        else __import__(name, *a, **k),
    )

    class DummyExecutor:
        def close_all(self): return "closed"

    caplog.set_level("ERROR")
    gm.force_exit_all(DummyExecutor())
    assert any("force_exit_all failed" in rec.message for rec in caplog.records)


def test_killswitch_no_data(monkeypatch):
    """Check killswitch when history is empty"""
    ks = KillSwitchManager(config={"global": {"killswitch_dd_limit_pct": 10}})
    ks.enabled = True
    ks.history = []  # reset
    stop, reason = ks.check(1000.0, now=time.time())
    assert not stop
    assert reason.startswith("ok(")


# ------------------------------------------------------------
# Extra test to cover if results: False branch
# ------------------------------------------------------------
def test_run_no_entries(monkeypatch, tmp_path):
    # mock load_config
    monkeypatch.setattr("mind2_python.decision_engine.load_config",
                        lambda path, overrides=None: {"symbols": {}, "global": {}})

    # mock PositionManager เพื่อไม่ให้ crash
    monkeypatch.setattr("mind2_python.decision_engine.PositionManager",
                        type("PM", (), {
                            "get_open_positions_summary": staticmethod(lambda : {}),
                            "summary": staticmethod(lambda : {})
                        }))

    engine = DecisionEngine(config_path=str(tmp_path))
    # เรียก run ด้วย entries ว่าง
    results = engine.run([])
    assert isinstance(results, list)
    assert results == []
