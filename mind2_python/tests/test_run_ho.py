import json
import yaml
import types
import pytest
import tempfile
from pathlib import Path

import mind2_python.run_ho as runho


# --------------------------
# Helper config/feed
# --------------------------
@pytest.fixture
def tmp_cfg_and_feed(tmp_path):
    cfg = {
        "symbols": {"XAUUSDc": {"pip_size": 0.1}},
        "exit": {}
    }
    feed = [{"symbol": "XAUUSDc", "decision": "BUY", "entry": 100,
             "signal": {"winprob": 0.7}, "score": 0.8, "confidence": 0.9, "votes": {}}]

    cfg_path = tmp_path / "config.yaml"
    feed_path = tmp_path / "feed.json"

    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    return cfg_path, feed_path


# --------------------------
# single_cycle
# --------------------------
def test_single_cycle_basic(monkeypatch, tmp_cfg_and_feed):
    cfg_path, feed_path = tmp_cfg_and_feed

    class DummyEngine:
        def __init__(self): self.global_atr = {}
        def run(self, entries): return [entries[0]]
        def get_global_atr(self): return {"XAUUSDc": 2.0}

    class DummyExecutor:
        def __init__(self): self.called = []
        def execute(self, decision): self.called.append(decision)

    class DummyHybridExit:
        def calc(self, res, **kwargs): return {"sl": 95, "tp": [{"price": 110}]}

    monkeypatch.setattr(runho, "parse_feed", lambda f: f)  # passthrough
    engine = DummyEngine()
    executor = DummyExecutor()
    hybrid_exit = DummyHybridExit()

    results = runho.single_cycle(engine, str(feed_path), executor, hybrid_exit,
                                 cfg={"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "exit": {}})
    assert results[0]["sl"] == 95
    assert results[0]["tp"] == [110]
    assert executor.called  # executor executed


def test_single_cycle_multi_entries(monkeypatch, tmp_cfg_and_feed):
    cfg_path, feed_path = tmp_cfg_and_feed

    class DummyEngine:
        def __init__(self): self.global_atr = {}
        def run(self, entries): return [entries[0]]
        def get_global_atr(self): return {"XAUUSDc": 2.0}

    class DummyExecutor:
        def __init__(self): self.called = []
        def execute(self, decision): self.called.append(decision)

    class DummyHybridExit:
        def calc(self, res, **kwargs):
            return {
                "sl": 95, "tp": [{"price": 110}],
                "entries": {
                    1: {"lot": 0.1, "sl": 95, "tp": [110]},
                    2: {"lot": 0.2, "sl": 94, "tp": [109]}
                }
            }

    monkeypatch.setattr(runho, "parse_feed", lambda f: f)
    monkeypatch.setattr(runho, "pretty_log_tradesignal", lambda **kwargs: None)

    engine = DummyEngine()
    executor = DummyExecutor()
    hybrid_exit = DummyHybridExit()

    results = runho.single_cycle(engine, str(feed_path), executor, hybrid_exit,
                                 cfg={"symbols": {"XAUUSDc": {"pip_size": 0.1}}, "exit": {}})
    assert len(executor.called) == 2  # 2 entries executed
    assert results[0]["sl"] == 95


# --------------------------
# main
# --------------------------
def test_main_exits(monkeypatch, tmp_cfg_and_feed):
    cfg_path, feed_path = tmp_cfg_and_feed

    # fake argparse
    class DummyArgs:
        balance = 1000
        interval = 1
        config = str(cfg_path)
        feed = str(feed_path)
        debug_trailing = False

    monkeypatch.setattr(runho, "argparse", types.SimpleNamespace(ArgumentParser=lambda: types.SimpleNamespace(
        add_argument=lambda *a, **k: None,
        parse_args=lambda: DummyArgs
    )))

    # fake engine/executor etc.
    monkeypatch.setattr(runho, "DecisionEngine", lambda **k: types.SimpleNamespace(
        global_atr={}, run=lambda e: [], get_global_atr=lambda: {}
    ))
    monkeypatch.setattr(runho, "Executor", lambda : types.SimpleNamespace(
        get_account_info=lambda : {"balance": 1000, "equity": 1000},
        execute=lambda d: None,
        shutdown=lambda : None
    ))
    monkeypatch.setattr(runho, "HybridExit", lambda cfg: types.SimpleNamespace(calc=lambda *a, **k: {}))
    monkeypatch.setattr(runho, "TrailingManager", lambda cfg: types.SimpleNamespace(
        update_global_atr=lambda atr: None, loop_trailing=lambda : None
    ))
    monkeypatch.setattr(runho, "RiskGuard", lambda cfg: types.SimpleNamespace(state={}))
    monkeypatch.setattr(runho, "GlobalExitManager", lambda cfg: types.SimpleNamespace(
        check_exit=lambda acc_info, daily_loss: (True, "TEST_EXIT", None)
    ))
    monkeypatch.setattr(runho, "pretty_log_dashboard", lambda **k: None)

    # prevent sleep & infinite loop
    monkeypatch.setattr(runho.time, "sleep", lambda s: (_ for _ in ()).throw(KeyboardInterrupt()))

    # Run main should exit cleanly
    runho.main()
