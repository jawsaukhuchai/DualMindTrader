import types
import pytest
from types import SimpleNamespace

import mind2_python.decision_engine as de
from mind2_python.schema import Indicators


# ======================================================
# Helpers
# ======================================================
class DummyIndicators(SimpleNamespace):
    def __init__(self):
        super().__init__(rsi=50, ema_fast=1.0, ema_slow=1.0, macd=0, signal=0)


def make_entry(symbol="XAUUSDc", atr=1.5, adx=25.0):
    return types.SimpleNamespace(
        symbol=symbol, bid=100.0, ask=102.0,
        atr=atr, adx=adx, balance=1000.0, equity=1000.0,
        margin=0.0, margin_level=1000.0, tf="H1", pnl=0.0,
        m5=DummyIndicators(), h1=DummyIndicators(), h4=DummyIndicators()
    )


def make_engine(monkeypatch, **overrides):
    cfg = {"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "global": {}}
    monkeypatch.setattr(de, "load_config", lambda path, overrides=None: cfg)
    eng = de.DecisionEngine("fake", balance=1000)
    # override strategies/exits if provided
    if "scalp" in overrides: eng.scalp = overrides["scalp"]
    if "day" in overrides: eng.day = overrides["day"]
    if "swing" in overrides: eng.swing = overrides["swing"]
    if "exit" in overrides: eng.exit = overrides["exit"]
    return eng


class DummyStrategy:
    def __init__(self, res=None):
        self.res = res or {"decision": "HOLD", "confidence": 0.5}
    def evaluate(self, entry): return self.res


class DummyExit:
    def __init__(self, sl=None, tp=None):
        self.sl = sl
        self.tp = tp or []
    def calc(self, *a, **k):
        exits = {"entries": {}}
        if self.sl is not None:
            exits["sl"] = self.sl
        if self.tp:
            exits["tp"] = [{"price": p} for p in self.tp]
        return exits


# ======================================================
# Utility Functions
# ======================================================
def test_score_to_winprob_normal_and_clamp():
    assert de.score_to_winprob(0.5) == 50.0
    assert de.score_to_winprob(2.0) == 100.0
    assert de.score_to_winprob(-5.0) == 100.0

def test_join_reasons_variants():
    assert de.join_reasons(["a", "b"]) == "a|b"
    assert de.join_reasons("single") == "single"

def test_join_reasons_string_standalone():
    assert de.join_reasons("abc") == "abc"


# ======================================================
# Fusion + Colorize
# ======================================================
def test_fusion_decision_cases():
    ai = {"decision": "BUY", "confidence": 1.0}
    rule = {"decision": "SELL", "confidence": 1.0}
    out = de.fusion_decision(ai, rule, "normal")
    assert out["decision"] in ("BUY", "SELL", "HOLD")

def test_colorize_decision_variants():
    assert "BUY" in de.colorize_decision("BUY", "BUY")
    assert "SELL" in de.colorize_decision("SELL", "SELL")
    assert "HOLD" in de.colorize_decision("HOLD", "HOLD")
    assert "TEXT" in de.colorize_decision("OTHER", "TEXT")

def test_colorize_reason_variants():
    assert "blocked" in de.colorize_reason("blocked_reason").lower()
    assert "low_conf" in de.colorize_reason("low_conf").lower()
    assert "risk_ok" in de.colorize_reason("risk_ok").lower()
    assert "invalid atr" in de.colorize_reason("invalid atr").lower()
    assert "something" in de.colorize_reason("something")


# ======================================================
# RegimeDetector
# ======================================================
def test_regime_detector_all_paths():
    det = de.RegimeDetector({"atr_threshold": 1.0, "adx_threshold": 20.0})
    assert det.detect(Indicators(atr=2.0, adx=25.0)) == "trend"
    assert det.detect(Indicators(atr=0.5, adx=10.0)) == "range"
    assert det.detect(Indicators(atr=2.0, adx=10.0)) == "high_vol"
    assert det.detect(Indicators(atr=0.5, adx=25.0)) == "low_vol"
    assert det.detect(Indicators(atr=0, adx=0)) == "normal"
    e = types.SimpleNamespace(atr=float("nan"), adx=float("nan"))
    assert det.detect(e) == "normal"


# ======================================================
# select_mode
# ======================================================
@pytest.mark.parametrize(
    "atr,adx,expected",
    [
        (2.0, 25.0, "scaler"),
        (0.5, 10.0, "strict"),
    ],
)
def test_select_mode_variants(atr, adx, expected):
    sym_cfg = {"atr_threshold": 1.0, "adx_threshold": 20.0}
    entry = SimpleNamespace(atr=atr, adx=adx)
    assert de.select_mode(sym_cfg, entry) == expected


# ======================================================
# Process() Branches
# ======================================================
def test_global_exit_stop(monkeypatch):
    eng = make_engine(monkeypatch)
    entry = make_entry()
    monkeypatch.setattr(eng.global_exit, "check_exit", lambda acc: (True, "forced", []))
    res = eng.process(entry)
    assert res["decision"] == "CLOSE_ALL"

def test_global_entry_block(monkeypatch):
    eng = make_engine(monkeypatch)
    entry = make_entry()
    monkeypatch.setattr(eng.global_entry, "check", lambda acc, pos: (False, ["blocked"]))
    res = eng.process(entry)
    assert res["decision"] == "HOLD"
    assert "blocked" in res["reason"]

def test_global_entry_allowed(monkeypatch, caplog):
    eng = make_engine(monkeypatch)
    entry = make_entry()
    monkeypatch.setattr(eng.global_entry, "check", lambda acc, pos: (True, ["ok"]))
    with caplog.at_level("DEBUG"):
        res = eng.process(entry)
    assert res["decision"] in ("BUY", "SELL", "HOLD")
    assert "ok" in res["reason"]

def test_risk_guard_block(monkeypatch):
    eng = make_engine(monkeypatch)
    entry = make_entry()
    monkeypatch.setattr(eng.risk, "allow", lambda *a, **k: (False, ["risk_blocked"]))
    res = eng.process(entry)
    assert res["decision"] == "HOLD"
    assert "risk_blocked" in res["reason"]

def test_portfolio_block(monkeypatch):
    eng = make_engine(monkeypatch)
    entry = make_entry()
    monkeypatch.setattr(eng.portfolio, "allow", lambda *a, **k: (False, ["portfolio_blocked"]))
    res = eng.process(entry)
    assert res["decision"] == "HOLD"
    assert "portfolio_blocked" in res["reason"]

def test_process_with_sl_tp(monkeypatch, caplog):
    eng = make_engine(monkeypatch)
    entry = make_entry()
    monkeypatch.setattr(eng.exit, "calc", lambda *a, **k: {"entries": {}, "sl": 99.0, "tp": [{"price": 111.0}]})
    with caplog.at_level("DEBUG"):
        res = eng.process(entry)
    assert res["sl"] == 99.0
    assert res["tp"] == [111.0]
    assert any("SL=" in m for m in caplog.messages)
    assert any("TP=" in m for m in caplog.messages)

def test_process_no_sl_tp(monkeypatch, caplog):
    eng = make_engine(monkeypatch)
    entry = make_entry()
    monkeypatch.setattr(eng.exit, "calc", lambda *a, **k: {"entries": {}, "sl": None, "tp": []})
    with caplog.at_level("DEBUG"):
        res = eng.process(entry)
    assert res["sl"] is None
    assert res["tp"] == []
    assert any("No SL set" in m for m in caplog.messages)
    assert any("No TP set" in m for m in caplog.messages)


# ======================================================
# Run()
# ======================================================
def test_run_with_error(monkeypatch):
    eng = make_engine(monkeypatch)
    monkeypatch.setattr(de.DecisionEngine, "process", lambda self, entry: (_ for _ in ()).throw(Exception("boom")))
    results = eng.run([make_entry()])
    assert results[0]["decision"] == "HOLD"
    assert "error_eval" in results[0]["reason"]
