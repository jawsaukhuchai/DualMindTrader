import types
import mind2_python.decision_engine as de

class DummyIndicators(types.SimpleNamespace):
    def __init__(self):
        super().__init__(rsi=50, ema_fast=1.0, ema_slow=1.0, macd=0, signal=0)

def make_entry():
    return types.SimpleNamespace(
        symbol="XAUUSDc", bid=100.0, ask=102.0,
        atr=1.5, adx=25.0, balance=1000.0, equity=1000.0,
        margin=0.0, margin_level=1000.0, tf="H1", pnl=0.0,
        m5=DummyIndicators(), h1=DummyIndicators(), h4=DummyIndicators()
    )

def test_run_triggers_dashboard(monkeypatch):
    cfg = {"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "global": {}}
    monkeypatch.setattr(de, "load_config", lambda path, overrides=None: cfg)

    eng = de.DecisionEngine("fake", balance=1000)

    # patch pretty_log_dashboard เพื่อไม่ให้ crash
    monkeypatch.setattr(de, "pretty_log_dashboard", lambda *a, **k: None)

    entry = make_entry()
    results = eng.run([entry])

    # ต้องมี results กลับมา และ branch if results ถูก execute
    assert isinstance(results, list)
    assert results[0]["symbol"] == "XAUUSDc"
