import pytest
from datetime import datetime
from dataclasses import MISSING
from mind2_python.swing import SwingStrategy
from mind2_python.schema import TradeEntry


# ===== Helper Classes =====
class DummyInd:
    """Mock indicator object with attributes that SwingStrategy expects"""
    def __init__(self, rsi=None, atr=None, adx=None, macd_hist=None, bos=None, bb=None):
        self.rsi = rsi
        self.atr = atr
        self.adx = adx
        self.macd_hist = macd_hist
        self.bos = bos
        self.bb = bb


def make_entry(**overrides):
    fields = TradeEntry.__dataclass_fields__
    defaults = {}
    for name, field in fields.items():
        if name in overrides:
            defaults[name] = overrides[name]
            continue

        if field.default is not MISSING:
            defaults[name] = field.default
        elif field.default_factory is not MISSING:  # type: ignore
            defaults[name] = field.default_factory()
        else:
            if name == "symbol":
                defaults[name] = "XAUUSDc"
            elif name == "bid":
                defaults[name] = 2000.0
            elif name == "ask":
                defaults[name] = 2001.0
            elif name == "spread":
                defaults[name] = 1.0
            elif name == "filters":
                defaults[name] = {}
            elif name == "timeframes":
                defaults[name] = {}
            elif name == "timestamp":
                defaults[name] = datetime.utcnow().isoformat()
            else:
                defaults[name] = None

    entry = TradeEntry(**defaults)

    if "h4" in overrides:
        entry.__dict__["h4"] = overrides["h4"]
    if "d1" in overrides:
        entry.__dict__["d1"] = overrides["d1"]

    return entry


# ===== Fixtures =====
@pytest.fixture
def base_cfg():
    return {
        "XAUUSDc": {
            "indicators": {
                "atr": {"min_threshold": 0.1},
                "adx": {"min_threshold": 20.0},
                "rsi": {"bull_level": 65, "bear_level": 35},
            }
        }
    }


# ===== Tests =====
def test_no_indicators(base_cfg):
    strat = SwingStrategy(base_cfg)
    entry = make_entry(h4=None, d1=None)
    result = strat.evaluate(entry)
    assert result["decision"] == "HOLD"
    assert any(reason in result["reason"] for reason in ["no_indicators", "low_volatility"])


def test_no_indicators_with_empty_object(base_cfg):
    strat = SwingStrategy(base_cfg)
    ind = DummyInd(rsi=None, atr=None, adx=None)
    entry = make_entry(h4=ind)
