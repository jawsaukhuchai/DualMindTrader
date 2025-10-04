import pytest
from types import SimpleNamespace
from mind2_python.hybrid_exit import HybridExit


@pytest.fixture
def cfg():
    return {
        "XAUUSD": {
            "pip_size": 0.1,
            "digits": 2,
            "exit": {"sl_atr": 2.0, "tp_steps": [1, 2], "tp_perc": [50, 50]},
            "portfolio": {"series_mode": "scaling"},
        }
    }


def test_calc_invalid_side_and_atr(cfg, capsys):
    he = HybridExit(cfg)
    decision = {"decision": "HOLD"}
    result = he.calc(decision, entry=100, symbol="XAUUSD",
                     atr=0, atr_multi={}, global_exit_cfg={})
    assert result == {"sl": None, "tp": []}
    captured = capsys.readouterr()
    assert "invalid ATR" in captured.out or captured.err


def test_calc_scaling_mode(cfg):
    he = HybridExit(cfg)
    decision = {"decision": "BUY", "num_entries": 3, "lot": 0.3}
    result = he.calc(decision, entry=100, symbol="XAUUSD",
                     atr=2.0, atr_multi={}, global_exit_cfg={})
    assert len(result["entries"]) == 3
    assert all("sl" in e for e in result["entries"].values())


def test_recalc_no_positions(monkeypatch, cfg):
    he = HybridExit(cfg)
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda **_: [])
    result = he.recalc_for_open_positions("XAUUSD", atr=2.0,
                                          atr_multi={}, global_exit_cfg={})
    assert result == {}


def test_recalc_with_positions(monkeypatch, cfg, capsys):
    he = HybridExit(cfg)

    class DummyPos:
        def __init__(self):
            self.ticket = 1
            self.type = 0
            self.price_open = 100
            self.comment = "series-2|extra"
            self.sl = None
            self.volume = 1
            self.profit = 0

    dummy_pos = DummyPos()
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda **_: [dummy_pos])
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.symbol_info",
                        lambda sym: SimpleNamespace(stops_level=5))

    result = he.recalc_for_open_positions("XAUUSD", atr=0,
                                          atr_multi={}, global_exit_cfg={})
    assert 1 in result
    captured = capsys.readouterr()
    assert "fallback ATR" in captured.out or captured.err


def test_adjust_trailing_cases(cfg):
    he = HybridExit(cfg)
    # BUY profit <= 0
    sl = he.adjust_trailing(current_price=100, side="BUY", entry=101,
                            sl=99, trailing_cfg={"atr_mult": 2, "breakeven": 1}, pip_size=0.1)
    assert sl == 99
    # SELL profit <= 0
    sl = he.adjust_trailing(current_price=101, side="SELL", entry=100,
                            sl=102, trailing_cfg={"atr_mult": 2, "breakeven": 1}, pip_size=0.1)
    assert sl == 102
    # invalid side
    sl = he.adjust_trailing(current_price=101, side="HOLD", entry=100,
                            sl=100, trailing_cfg={"atr_mult": 2}, pip_size=0.1)
    assert sl == 100


def test_emergency_close_check_cases(cfg, monkeypatch):
    he = HybridExit(cfg)

    class DummyPos:
        def __init__(self, sl=None, profit=-50, volume=1, price_open=100, ticket=99):
            self.sl = sl
            self.profit = profit
            self.volume = volume
            self.price_open = price_open
            self.ticket = ticket
            self.comment = "series-1"

    # None pos
    assert he.emergency_close_check("XAUUSD", None) is False
    # pos with sl set
    assert he.emergency_close_check("XAUUSD", DummyPos(sl=1)) is False
    # severe loss
    severe_pos = DummyPos(sl=None, profit=-200, volume=1, price_open=100)
    assert he.emergency_close_check("XAUUSD", severe_pos, severe_loss_pct=-0.5) is True
    # retrace
    retrace_pos = DummyPos(sl=None, profit=-10, volume=1, price_open=100)
    assert he.emergency_close_check("XAUUSD", retrace_pos) is True
