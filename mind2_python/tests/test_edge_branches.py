# tests/test_edge_branches.py
import pytest
import logging
import sys
import types
import importlib
from argparse import Namespace
from mind2_python import risk_guard, schema, trailing_manager

# -------------------------------
# RiskGuard edge cases
# -------------------------------
def test_risk_guard_block_and_exit(monkeypatch):
    rg = risk_guard.RiskGuard({"symbols": {"BTCUSDc": {"risk": {"max_orders": 1}}}})

    # mock open positions = too many
    monkeypatch.setattr(risk_guard.PositionManager, "count_open_positions", lambda sym: 1)
    monkeypatch.setattr(risk_guard.PositionManager, "get_open_positions",
                        lambda sym: [{"ticket": 123, "profit": -5}])
    ok, reasons = rg.check("BTCUSDc", balance=1000, global_reversal=True)
    assert ok and any("override" in r for r in reasons)

    # trigger daily loss block
    monkeypatch.setattr(risk_guard.PositionManager, "count_open_positions", lambda sym: 0)
    ok, reasons = rg.check("BTCUSDc", balance=1000, daily_loss=-1000)
    assert not ok and any("loss" in r for r in reasons)


# -------------------------------
# run_ho edge cases
# -------------------------------
def test_run_ho_main_once(monkeypatch, caplog, tmp_path):
    import mind2_python.run_ho as run_ho
    importlib.reload(run_ho)

    # fake args
    monkeypatch.setattr(run_ho.argparse.ArgumentParser, "parse_args",
                        lambda self=None: Namespace(
                            balance=1000, interval=0,
                            config=str(tmp_path / "dummy.yaml"),
                            feed=str(tmp_path / "dummy.json"),
                            debug_trailing=False))

    # dummy config + feed files
    (tmp_path / "dummy.yaml").write_text("symbols: {}")
    (tmp_path / "dummy.json").write_text("{}")

    # patch dependencies
    monkeypatch.setattr(run_ho, "DecisionEngine", lambda **kw: types.SimpleNamespace(
        global_atr={}, run=lambda entries: [], get_global_atr=lambda: {}))
    monkeypatch.setattr(run_ho, "Executor", lambda: types.SimpleNamespace(
        get_account_info=lambda: {"balance": 1000, "equity": 1000},
        shutdown=lambda: None, execute=lambda r: None))
    monkeypatch.setattr(run_ho, "TrailingManager", lambda cfg: types.SimpleNamespace(
        update_global_atr=lambda x: None, loop_trailing=lambda: None))
    monkeypatch.setattr(run_ho, "RiskGuard", lambda cfg: types.SimpleNamespace(state={}))
    monkeypatch.setattr(run_ho, "GlobalExitManager", lambda cfg: types.SimpleNamespace(
        check_exit=lambda *a, **k: (False, "", None)))
    monkeypatch.setattr(run_ho, "HybridExit", lambda cfg: types.SimpleNamespace(calc=lambda *a, **k: {}))
    monkeypatch.setattr(run_ho, "pretty_log_dashboard", lambda **kw: None)

    # break loop fast
    monkeypatch.setattr(run_ho, "time", types.SimpleNamespace(
        sleep=lambda x: (_ for _ in ()).throw(KeyboardInterrupt)))

    with caplog.at_level(logging.INFO):
        run_ho.main()

    # ตรวจสอบว่ามี log ที่เกี่ยวข้องออกมา
    assert any("Starting loop mode" in m for m in caplog.messages) or \
           any("Stopped by user" in m for m in caplog.messages)


# -------------------------------
# Schema parse_feed exit branches
# -------------------------------
def test_schema_parse_feed_invalid():
    bad_feed = [{"symbol": "BTCUSDc", "timeframes": {"H1": "not_a_dict"}}]
    out = schema.parse_feed(bad_feed)
    assert out == []


def test_schema_parse_feed_dict_wrapper():
    feed = {"symbols": [{"symbol": "XAUUSDc", "bid": 1, "ask": 2, "spread": 0.1,
                         "timeframes": {"H1": {"atr": 1.0}}, "timestamp": "2020-01-01"}]}
    out = schema.parse_feed(feed)
    assert len(out) == 1
    assert out[0].symbol == "XAUUSDc"


# -------------------------------
# TrailingManager edge cases
# -------------------------------
def test_trailingmanager_adjust_buy_and_sell(monkeypatch):
    tm = trailing_manager.TrailingManager({"symbols": {"BTCUSDc": {"pip_size": 1.0}}})

    hx = types.SimpleNamespace(adjust_trailing=lambda **kw: 105)
    pos = {"side": "BUY", "entry": 100, "ticket": 1, "sl": 100, "lot": 0.1}
    monkeypatch.setattr(trailing_manager.PositionManager, "get_open_positions", lambda sym: [pos])
    monkeypatch.setattr(trailing_manager, "mt5", types.SimpleNamespace(
        symbol_info_tick=lambda sym: types.SimpleNamespace(bid=110, ask=90)))
    tm.update_trailing("BTCUSDc", hx, {1: {"trailing": {"atr_mult": 1, "breakeven": 1}, "tp": []}}, pip_size=1)


def test_trailingmanager_no_config(monkeypatch):
    tm = trailing_manager.TrailingManager({"symbols": {"BTCUSDc": {"pip_size": 1.0}}})
    hx = types.SimpleNamespace(adjust_trailing=lambda **kw: None)
    monkeypatch.setattr(trailing_manager.PositionManager, "get_open_positions", lambda sym: [])
    tm.update_trailing("BTCUSDc", hx, {}, pip_size=1)
