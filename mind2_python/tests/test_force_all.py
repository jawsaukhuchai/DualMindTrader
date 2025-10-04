import pytest
import types
import logging

import mind2_python.decision_engine as de
import mind2_python.global_manager as gm
import mind2_python.portfolio_manager as pm
import mind2_python.position_manager as pos
import mind2_python.pretty_logger as pl

from mind2_python.schema import TradeEntry, Indicators


# ------------------------------------------------------
# Helpers
# ------------------------------------------------------
class DummyExecutor:
    def __init__(self):
        self.closed = False
    def close_all(self):
        self.closed = True


def make_entry(symbol="BTCUSDc", atr=2.0, adx=25.0):
    """Minimal TradeEntry mock"""
    return TradeEntry(
        symbol=symbol,
        bid=100.0,
        ask=101.0,
        spread=0.1,
        filters={},
        timeframes={"H1": {"atr": atr, "adx": adx, "rsi": 70}},
        timestamp="2025-01-01T00:00:00",
        indicators=Indicators(atr=atr, adx=adx, rsi=70),
    )


# ------------------------------------------------------
# DecisionEngine force coverage
# ------------------------------------------------------
def test_decision_engine_killswitch_trigger(monkeypatch):
    engine = de.DecisionEngine(config_path="tests/config_dummy.yaml")

    # Force killswitch to trigger
    engine.killswitch.enabled = True
    engine.killswitch.dd_limit_pct = 0
    entry = make_entry()
    res = engine.process(entry)
    assert res["decision"] in ("HOLD", "CLOSE_ALL")


def test_decision_engine_run_error(monkeypatch):
    engine = de.DecisionEngine(config_path="tests/config_dummy.yaml")

    class BadEntry:  # missing symbol
        pass

    results = engine.run([BadEntry()])
    assert results[0]["decision"] == "HOLD"
    assert "error_eval" in results[0]["reason"]


# ------------------------------------------------------
# GlobalManager force coverage
# ------------------------------------------------------
def test_global_exit_force_exit_all(monkeypatch):
    mgr = gm.GlobalExitManager({})
    dummy = DummyExecutor()

    # Patch PositionManager inside its real module
    import mind2_python.position_manager as pm_mod
    monkeypatch.setattr(pm_mod, "PositionManager", types.SimpleNamespace(
        get_open_positions_summary=lambda: {"BTCUSDc": [0.1]},
        clear_all_positions=lambda : None
    ))

    mgr.force_exit_all(dummy)
    assert dummy.closed is True


def test_killswitch_manager_reset_and_trigger():
    ks = gm.KillSwitchManager({"global": {}})
    ks.history = [(1, 100)]
    ks.trigger("manual")
    assert gm.KillSwitchManager.is_triggered() is True
    ks.reset()
    assert gm.KillSwitchManager.is_triggered() is False


# ------------------------------------------------------
# PortfolioManager force coverage
# ------------------------------------------------------
def test_portfolio_manager_overrides(monkeypatch):
    config = {"symbols": {"BTCUSDc": {"portfolio": {"max_orders": 1}}}}
    pf = pm.PortfolioManager(config)

    # Patch PositionManager to fake open positions
    monkeypatch.setattr(pm.PositionManager, "count_open_positions", lambda sym: 1)

    lot, reasons = pf.check("BTCUSDc", lot=1000000, balance=1000, global_reversal=True)
    assert any("override" in r for r in reasons)


def test_portfolio_manager_cooldown(monkeypatch):
    config = {"global": {"cooldown_seconds": 10}, "symbols": {"BTCUSDc": {}}}
    pf = pm.PortfolioManager(config)
    pf.last_entry_time["GLOBAL"] = __import__("time").time()

    lot, reasons = pf.check("BTCUSDc", lot=1, balance=1000)
    assert any("cooldown" in r for r in reasons)


# ------------------------------------------------------
# PositionManager force coverage
# ------------------------------------------------------
def test_parse_comment_variants():
    assert pos.PositionManager._parse_comment("series-2|0.7|0.8") == (0.7, 0.8, 2)
    assert pos.PositionManager._parse_comment("0.5|0.9")[:2] == (0.5, 0.9)
    assert pos.PositionManager._parse_comment("bad") == (0.0, 0.0, 1)


def test_get_open_positions_fallback(monkeypatch):
    # Remove mt5 to force fallback
    monkeypatch.setattr(pos, "mt5", types.SimpleNamespace(positions_get=lambda *a, **k: None))
    res = pos.PositionManager.get_open_positions("BTCUSDc")
    assert isinstance(res, list)


# ------------------------------------------------------
# PrettyLogger force coverage
# ------------------------------------------------------
def test_pretty_logger_close_variants(capsys):
    pl.pretty_log_close_position("BTCUSDc", 1, 0.1, 100, reason="SEVERE")
    pl.pretty_log_close_position("BTCUSDc", 1, 0.1, 100, reason="RETRACE")
    pl.pretty_log_close_position("BTCUSDc", 1, 0.1, 100, reason="NORMAL")
    out = capsys.readouterr().out
    assert "CLOSE" in out


def test_pretty_logger_trailing_and_compact(capsys):
    pl.pretty_log_trailing("BTCUSDc", 1, 99.0, 100.0)
    pl.pretty_log_dashboard(
        balance=1000, equity=1200, pnl=200, margin_level=999,
        lots=0.1, results={"BTCUSDc": {"decision": "BUY", "signal": {"winprob":0.5},
                                       "confidence":0.8, "regime":"trend",
                                       "votes":{"rule":{"threshold":0.1,"num_entries":2}}}},
        symbols_cfg={"BTCUSDc": {}}, compact=True
    )
    out = capsys.readouterr().out
    assert "Dashboard" in out
