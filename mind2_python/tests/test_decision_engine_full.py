import pytest
from types import SimpleNamespace
from mind2_python.decision_engine import select_mode, fusion_decision, DecisionEngine


# ======================================================
# Dummy helper classes
# ======================================================
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
    cfg.write_text(
        "symbols: {XAUUSD: {pip_size: 0.1, atr_threshold: 1.0, adx_threshold: 20.0}}\n"
    )
    return DecisionEngine(str(cfg))


# ======================================================
# Tests
# ======================================================

# --- select_mode branches (scaler + strict) ---
@pytest.mark.parametrize(
    "atr,adx,expected",
    [
        (2.0, 25.0, "scaler"),  # above thresholds
        (0.5, 10.0, "strict"),  # below thresholds
    ],
)
def test_select_mode_branches(atr, adx, expected):
    sym_cfg = {"atr_threshold": 1.0, "adx_threshold": 20.0}
    entry = SimpleNamespace(atr=atr, adx=adx)
    assert select_mode(sym_cfg, entry) == expected


# --- fusion_decision tie fallback (ai_res + rule_res HOLD) ---
def test_fusion_decision_tie_fallback():
    ai_res = {"decision": "HOLD", "confidence": 0.0}
    rule_res = {"decision": "HOLD", "confidence": 0.0}
    fused = fusion_decision(ai_res, rule_res, "normal")
    assert fused["decision"] == "HOLD"
    assert fused["score"] == 0


# --- process() with SL/TP set ---
class DummyExitWithSLTP:
    def calc(self, *a, **k):
        return {
            "entries": {},
            "sl": 1995.0,
            "tp": [{"price": 2010.0}, {"price": 2020.0}],
        }


def test_process_with_sl_tp(base_engine, monkeypatch):
    entry = DummyTradeEntry()
    base_engine.exit = DummyExitWithSLTP()

    # ปิดทุกฟังก์ชันที่อาจ crash
    monkeypatch.setattr(
        "mind2_python.position_manager.PositionManager.open_position", lambda *a, **k: None
    )
    monkeypatch.setattr("mind2_python.pretty_logger.pretty_log_tradesignal", lambda *a, **k: None)
    monkeypatch.setattr("mind2_python.pretty_logger.pretty_log_positions_summary", lambda *a, **k: None)
    monkeypatch.setattr("mind2_python.pretty_logger.pretty_log_dashboard", lambda *a, **k: None)

    result = base_engine.process(entry)
    assert result["sl"] == 1995.0
    assert result["tp"] == [2010.0, 2020.0]


# --- process() fallback logging (no sl/tp keys at all) ---
class DummyExitNoKeys:
    def calc(self, *a, **k):
        return {"entries": {}, "sl": None, "tp": []}


def test_process_no_sl_tp_fallback(base_engine, caplog, monkeypatch):
    entry = DummyTradeEntry()
    base_engine.exit = DummyExitNoKeys()

    # ปิดทุกฟังก์ชันที่อาจ crash
    monkeypatch.setattr(
        "mind2_python.position_manager.PositionManager.open_position", lambda *a, **k: None
    )
    monkeypatch.setattr("mind2_python.pretty_logger.pretty_log_tradesignal", lambda *a, **k: None)
    monkeypatch.setattr("mind2_python.pretty_logger.pretty_log_positions_summary", lambda *a, **k: None)
    monkeypatch.setattr("mind2_python.pretty_logger.pretty_log_dashboard", lambda *a, **k: None)

    with caplog.at_level("DEBUG"):
        result = base_engine.process(entry)

    assert result["sl"] is None
    assert result["tp"] == []
    assert any("No SL set" in m for m in caplog.messages)
    assert any("No TP set" in m for m in caplog.messages)
