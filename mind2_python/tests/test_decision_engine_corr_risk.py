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

def test_process_corr_risk_block(monkeypatch):
    # config fake
    cfg = {"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "global": {}}
    monkeypatch.setattr(de, "load_config", lambda path, overrides=None: cfg)

    eng = de.DecisionEngine("fake", balance=1000)

    # mock corr_risk ให้บล็อก
    eng.corr_risk = types.SimpleNamespace(
        update=lambda s, p: None,
        check=lambda: (False, "corr_blocked")
    )

    entry = make_entry()
    result = eng.process(entry)

    assert result["decision"] == "HOLD"
    assert "corr_blocked" in result["reason"]
