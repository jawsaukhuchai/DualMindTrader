import pytest
from types import SimpleNamespace
from mind2_python.decision_engine import select_mode, fusion_decision, DecisionEngine

# ======================================================
# Dummy helper classes
# ======================================================
class DummyExit:
    def __init__(self, sl=None, tp=None):
        self.sl = sl
        self.tp = tp or []

    def calc(self, final, entry, symbol, atr, atr_multi, global_exit_cfg):
        exits = {"entries": {}}
        if self.sl is not None:
            exits["sl"] = self.sl
        if self.tp:
            exits["tp"] = [{"price": p} for p in self.tp]
        return exits


class DummyIndicators(SimpleNamespace):
    def __init__(self):
        super().__init__(rsi=50, ema_fast=1.0, ema_slow=1.0, macd=0, signal=0)


class DummyTradeEntry(SimpleNamespace):
    symbol = "XAUUSD"
    bid = 2000.0
    ask = 2000.5
    atr = 2.0
    adx = 25.0
    balance = 10000
    equity = 10000
    margin = 0
    margin_level = 1000
    tf = "H1"
    m5 = DummyIndicators()
    h1 = DummyIndicators()
    h4 = DummyIndicators()


# ======================================================
# Fixtures
# ======================================================
@pytest.fixture
def base_engine(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("symbols: {XAUUSD: {pip_size: 0.1, atr_threshold: 1.0, adx_threshold: 20.0}}\n")
    return DecisionEngine(str(cfg))


# ======================================================
# Tests
# ======================================================
def test_process_with_sl_tp(base_engine):
    """Trigger SL/TP logging branches"""
    entry = DummyTradeEntry()
    base_engine.exit = DummyExit(sl=1995.0, tp=[2010.0, 2020.0])
    result = base_engine.process(entry)
    assert result["sl"] == 1995.0
    assert result["tp"] == [2010.0, 2020.0]


def test_process_without_sl_tp(base_engine, caplog):
    """Trigger fallback logging (no SL/TP)"""
    entry = DummyTradeEntry()
    base_engine.exit = DummyExit(sl=None, tp=[])
    with caplog.at_level("DEBUG"):
        result = base_engine.process(entry)
    assert result["sl"] is None
    assert result["tp"] == []
    assert any("No SL set" in m for m in caplog.messages)
    assert any("No TP set" in m for m in caplog.messages)


def test_select_mode_strict():
    """Cover strict branch in select_mode"""
    sym_cfg = {"atr_threshold": 1.0, "adx_threshold": 20.0}
    entry = SimpleNamespace(atr=0.5, adx=10)
    assert select_mode(sym_cfg, entry) == "strict"


def test_fusion_decision_tie():
    """Cover tie fallback branch in fusion_decision"""
    ai_res = {"decision": "HOLD", "confidence": 0.0}
    rule_res = {"decision": "HOLD", "confidence": 0.0}
    fused = fusion_decision(ai_res, rule_res, "normal")
    assert fused["decision"] in {"HOLD", "BUY", "SELL"}
    assert fused["score"] == 0
