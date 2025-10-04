import pytest
import types
from mind2_python.lotsizer import LotSizer, AdaptiveLotSizer

# --- Mock entry + PositionManager ---
class DummyEntry:
    def __init__(self, symbol="XAUUSD", global_reversal=False):
        self.symbol = symbol
        self.global_reversal = global_reversal


@pytest.fixture(autouse=True)
def patch_position_manager(monkeypatch):
    def fake_count(symbol):
        return patch_position_manager.open_count
    patch_position_manager.open_count = 0
    monkeypatch.setattr("mind2_python.lotsizer.PositionManager.count_open_positions", fake_count)
    yield patch_position_manager


def test_basic_compute_min_lot():
    entry = DummyEntry()
    sym_cfg = {"risk": {"risk_percent": 0.1, "min_lot": 0.05, "max_lot": 1.0}}
    lot = LotSizer(balance=1000).compute(entry, sym_cfg)
    assert lot == 0.05  # below min_lot → clamped


def test_basic_compute_max_lot():
    entry = DummyEntry()
    sym_cfg = {"risk": {"risk_percent": 50, "min_lot": 0.01, "max_lot": 0.5}}
    lot = LotSizer(balance=10000).compute(entry, sym_cfg)
    assert lot == 0.5  # above max_lot → clamped


def test_global_reversal_scaling(patch_position_manager):
    entry = DummyEntry(global_reversal=True)
    sym_cfg = {"risk": {"risk_percent": 5, "min_lot": 0.01, "max_lot": 1.0}}
    patch_position_manager.open_count = 3  # should reduce by decay factor
    lot = LotSizer(balance=10000).compute(entry, sym_cfg)
    assert lot < 0.5  # scaled down


def test_error_handling(monkeypatch):
    entry = DummyEntry(global_reversal=True)
    sym_cfg = {"risk": {"risk_percent": 1.0}}

    # บังคับให้ PositionManager.count_open_positions โยน exception
    monkeypatch.setattr(
        "mind2_python.lotsizer.PositionManager.count_open_positions",
        lambda symbol: 1 / 0
    )

    lot = LotSizer().compute(entry, sym_cfg)
    assert lot == 0.0  # ต้อง fallback มาที่ error handler


# --- AdaptiveLotSizer ---
@pytest.mark.parametrize("regime,factor", [
    ("normal", 1.0),
    ("trend", 1.1),
    ("low_vol", 1.3),
])
def test_adaptive_basic(regime, factor):
    entry = DummyEntry()
    sym_cfg = {"risk": {"risk_percent": 1.0, "min_lot": 0.01, "max_lot": 1.0}}
    base = LotSizer().compute(entry, sym_cfg)
    lot = AdaptiveLotSizer().compute(entry, sym_cfg, regime=regime)
    assert round(lot, 2) == round(base * factor, 2)


def test_adaptive_high_vol():
    entry = DummyEntry()
    sym_cfg = {"risk": {"risk_percent": 0.1, "min_lot": 0.1, "max_lot": 1.0}}
    lot = AdaptiveLotSizer(balance=1000).compute(entry, sym_cfg, regime="high_vol")
    # should allow lower than min_lot (half of min_lot)
    assert 0.05 <= lot <= sym_cfg["risk"]["min_lot"]


def test_adaptive_unknown_regime():
    entry = DummyEntry()
    sym_cfg = {"risk": {"risk_percent": 1.0, "min_lot": 0.01, "max_lot": 1.0}}
    base = LotSizer().compute(entry, sym_cfg)
    lot = AdaptiveLotSizer().compute(entry, sym_cfg, regime="weird")
    assert lot == base
