# tests/test_edge_negative.py
import pytest
import logging
import types
from mind2_python import lotsizer, logger as lg, pretty_logger as pl
from mind2_python import position_manager as pm
from mind2_python import schema, swing, trailing_manager

# -------------------------------
# Lotsizer exception path
# -------------------------------
def test_lotsizer_compute_exception():
    ls = lotsizer.LotSizer()
    class BadEntry:
        def __getattr__(self, name):
            raise Exception("boom")
    bad_entry = BadEntry()
    result = ls.compute(bad_entry, {"risk": {"risk_percent": 1.0}})
    assert result == 0.0


# -------------------------------
# Logger edge paths
# -------------------------------
def test_logger_pretty_log_decision_invalid_exit(caplog):
    with caplog.at_level(logging.INFO):
        lg.pretty_log_decisionengine(
            "BTC", "HOLD", 0.1, 100,
            exit_levels={"tp": [{"bad": "data"}]},  # missing price/diff
            reason="LOW_CONF"
        )
    assert any("DecisionEngine" in m for m in caplog.messages)

def test_logger_pretty_log_tradesignal_invalid_exit(caplog):
    with caplog.at_level(logging.INFO):
        lg.pretty_log_tradesignal(
            "XAU", "SELL", 0.2, 200,
            exit_levels={"tps": [{"bad": "data"}], "atr_mult": 1.5, "atr": 2.0},
            winprob=50
        )
    assert any("TRADE SIGNAL" in m for m in caplog.messages)


# -------------------------------
# PrettyLogger negative branches
# -------------------------------
def test_pretty_logger_trailing_and_dashboard():
    pl.pretty_log_trailing("BTC", 1, 100, 105, entry_index=2)
    pl.pretty_log_dashboard(1000, 900, -100, 120, 0.1, {}, {}, compact=False)
    pl.pretty_log_global_exit("Safe mode", triggered=False)
    pl.pretty_log_execution("XAU", "BUY", allowed=True)


# -------------------------------
# PositionManager error paths
# -------------------------------
def test_positionmanager_update_position_fail(monkeypatch):
    mgr = pm.PositionManager()
    monkeypatch.setattr(pm, "mt5", types.SimpleNamespace(
        symbol_info=lambda sym: None,
        symbol_info_tick=lambda sym: None,
        order_send=lambda req: None,
        TRADE_ACTION_SLTP=1,
        TRADE_RETCODE_DONE=10009,
    ))
    mgr.update_position("BTCUSDc", ticket=1, sl=100, tp=[{"price": 200}])

def test_positionmanager_count_open_positions_fail(monkeypatch):
    monkeypatch.setattr(pm, "mt5", types.SimpleNamespace(
        positions_get=lambda **kw: (_ for _ in ()).throw(Exception("fail"))
    ))
    out = pm.PositionManager.count_open_positions("BTC")
    assert out == 0


# -------------------------------
# Schema negative branches
# -------------------------------
def test_schema_parse_feed_bad_item():
    feed = ["not_a_dict"]
    out = schema.parse_feed(feed)
    assert out == []


# -------------------------------
# Swing branches
# -------------------------------
def test_swing_flat_zone():
    entry = schema.TradeEntry("BTC", 1, 2, 0.1, {}, {}, "2020-01-01")
    entry.timeframes["H4"] = {"rsi": 50, "atr": 10, "adx": 30}
    strat = swing.SwingStrategy({"BTC": {"indicators": {"atr": {"min_threshold": 1}, "adx": {"min_threshold": 1}}}})
    res = strat.evaluate(entry)
    assert res["reason"] == ["flat_zone"]

def test_swing_hold_no_buy_sell():
    entry = schema.TradeEntry("BTC", 1, 2, 0.1, {}, {}, "2020-01-01")
    # indicators valid atr/adx, but RSI neutral zone
    entry.timeframes["H4"] = {"rsi": 50, "atr": 10, "adx": 30}
    strat = swing.SwingStrategy({"BTC": {"indicators": {
        "atr": {"min_threshold": 1},
        "adx": {"min_threshold": 1},
        "rsi": {"bull_level": 70, "bear_level": 30}
    }}})
    res = strat.evaluate(entry)
    assert res["decision"] == "HOLD"


# -------------------------------
# TrailingManager negative paths
# -------------------------------
def test_trailingmanager_no_tick(monkeypatch):
    tm = trailing_manager.TrailingManager({"symbols": {"BTCUSDc": {"pip_size": 1.0}}})
    hx = types.SimpleNamespace(adjust_trailing=lambda **kw: None)
    pos = {"side": "BUY", "entry": 100, "ticket": 1, "sl": 100, "lot": 0.1}
    monkeypatch.setattr(trailing_manager.PositionManager, "get_open_positions", lambda sym: [pos])
    monkeypatch.setattr(trailing_manager, "mt5", types.SimpleNamespace(symbol_info_tick=lambda sym: None))
    tm.update_trailing("BTCUSDc", hx, {1: {"trailing": {"atr_mult": 1}, "tp": []}}, pip_size=1)

def test_trailingmanager_no_update_sl(monkeypatch):
    tm = trailing_manager.TrailingManager({"symbols": {"BTCUSDc": {"pip_size": 1.0}}})
    pos = {"side": "BUY", "entry": 100, "ticket": 1, "sl": 105, "lot": 0.1}
    hx = types.SimpleNamespace(adjust_trailing=lambda **kw: 105)  # new_sl == sl
    monkeypatch.setattr(trailing_manager.PositionManager, "get_open_positions", lambda sym: [pos])
    monkeypatch.setattr(trailing_manager, "mt5", types.SimpleNamespace(
        symbol_info_tick=lambda sym: types.SimpleNamespace(bid=110, ask=90)))
    tm.update_trailing("BTCUSDc", hx, {1: {"trailing": {"atr_mult": 1}, "tp": []}}, pip_size=1)

def test_trailingmanager_loop_error(monkeypatch):
    tm = trailing_manager.TrailingManager({"symbols": {"BTCUSDc": {"pip_size": 1.0}}})
    monkeypatch.setattr(trailing_manager, "HybridExit", lambda *a, **k: types.SimpleNamespace(
        recalc_for_open_positions=lambda **kw: (_ for _ in ()).throw(Exception("boom")),
        adjust_trailing=lambda **kw: None
    ))
    monkeypatch.setattr(trailing_manager.PositionManager, "get_open_positions", lambda sym: [])
    monkeypatch.setattr(trailing_manager, "mt5", types.SimpleNamespace(symbol_info_tick=lambda sym: None))
    tm.loop_trailing()
