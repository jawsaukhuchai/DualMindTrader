import sys
import types
import json
import pytest
import runpy
import pathlib
import os

# ------------------------------
# Autouse fixture: Patch MetaTrader5 before run_ho import
# ------------------------------
@pytest.fixture(autouse=True, scope="module")
def patch_mt5_module():
    class DummyMT5Module:
        def __init__(self):
            self.calls = {"initialize": 0, "shutdown": 0}
        def initialize(self, *a, **k):
            self.calls["initialize"] += 1
            return True
        def shutdown(self):
            self.calls["shutdown"] += 1
            return True
        def last_error(self): return (0, "ok")
        def account_info(self):
            return types.SimpleNamespace(balance=1000, equity=1000,
                                         margin_free=500, margin_level=200)
        def symbol_info(self, s):
            return types.SimpleNamespace(volume_min=0.01, volume_max=2.0,
                                         volume_step=0.01, digits=5)
        def symbol_info_tick(self, s): return types.SimpleNamespace(bid=100.0, ask=101.0)
        def order_calc_margin(self, *a, **k): return 1.0
        def order_send(self, *a, **k): return types.SimpleNamespace(retcode=10009)
        def positions_get(self, *a, **k): return []
    sys.modules["MetaTrader5"] = DummyMT5Module()
    yield


# ------------------------------
# Import run_ho after patch
# ------------------------------
import mind2_python.run_ho as run_ho


# ------------------------------
# Dummy helpers
# ------------------------------
class DummyEngine:
    def __init__(self): self.global_atr = {}
    def run(self, entries): return [{"symbol": "XAUUSD", "decision": "HOLD"}]
    def get_global_atr(self): return {"XAUUSD": 1.0}

class DummyExecutor:
    def __init__(self): self.closed = False
    def get_account_info(self): return {"balance": 1000, "equity": 1000}
    def execute(self, d): return {"ok": True}
    def shutdown(self): self.closed = True

class DummyHybridExit:
    def calc(self, *a, **k): return {"sl": 1.0, "tp": [{"price": 2.0}]}

class DummyTrailing:
    def __init__(self, cfg): self.updated = False; self.looped = False
    def update_global_atr(self, atr): self.updated = True
    def loop_trailing(self): self.looped = True

class DummyGlobalExitMgr:
    def __init__(self, cfg): self.calls = 0
    def check_exit(self, acc_info, daily_loss=0.0):
        self.calls += 1
        if self.calls == 1:
            return (False, "", {})
        return (True, "stop", {})

class DummyRiskGuard:
    def __init__(self, cfg): self.state = {}


# ------------------------------
# Tests
# ------------------------------
def test_single_cycle_basic(tmp_path):
    feed_path = tmp_path / "feed.json"
    feed_path.write_text(json.dumps([{"symbol": "XAUUSD", "entry": {}, "atr": 1.0}]))

    out = run_ho.single_cycle(
        engine=DummyEngine(),
        feed_path=str(feed_path),
        executor=DummyExecutor(),
        hybrid_exit=DummyHybridExit(),
        cfg={"exit": {}, "symbols": {"XAUUSD": {"pip_size": 0.01}}}
    )
    assert isinstance(out, list)
    assert out[0]["decision"] == "HOLD"


def test_main_with_loop_and_shutdown(monkeypatch, tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    feed_path = tmp_path / "feed.json"
    cfg_path.write_text("symbols: {XAUUSD: {pip_size: 0.01}}")
    feed_path.write_text("[]")

    monkeypatch.setattr("sys.argv",
        ["run_ho", "--balance", "1000", "--config", str(cfg_path),
         "--feed", str(feed_path), "--interval", "1"])

    dummy_exec = DummyExecutor()
    monkeypatch.setattr(run_ho, "DecisionEngine", lambda **k: DummyEngine())
    monkeypatch.setattr(run_ho, "Executor", lambda : dummy_exec)
    monkeypatch.setattr(run_ho, "TrailingManager", lambda cfg: DummyTrailing(cfg))
    monkeypatch.setattr(run_ho, "RiskGuard", lambda cfg: DummyRiskGuard(cfg))
    monkeypatch.setattr(run_ho, "GlobalExitManager", lambda cfg: DummyGlobalExitMgr(cfg))
    monkeypatch.setattr(run_ho, "HybridExit", lambda cfg: DummyHybridExit())
    monkeypatch.setattr(run_ho.time, "sleep", lambda x: None)

    run_ho.main()
    assert dummy_exec.closed is True


def test_main_debug_trailing(monkeypatch, tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    feed_path = tmp_path / "feed.json"
    cfg_path.write_text("symbols: {XAUUSD: {pip_size: 0.01}}")
    feed_path.write_text("[]")

    monkeypatch.setattr("sys.argv",
        ["run_ho", "--balance", "1000", "--config", str(cfg_path),
         "--feed", str(feed_path), "--interval", "1", "--debug-trailing"])

    dummy_exec = DummyExecutor()
    monkeypatch.setattr(run_ho, "DecisionEngine", lambda **k: DummyEngine())
    monkeypatch.setattr(run_ho, "Executor", lambda : dummy_exec)
    monkeypatch.setattr(run_ho, "TrailingManager", lambda cfg: DummyTrailing(cfg))
    monkeypatch.setattr(run_ho, "RiskGuard", lambda cfg: DummyRiskGuard(cfg))
    monkeypatch.setattr(run_ho, "GlobalExitManager", lambda cfg: DummyGlobalExitMgr(cfg))
    monkeypatch.setattr(run_ho, "HybridExit", lambda cfg: DummyHybridExit())
    monkeypatch.setattr(run_ho.time, "sleep", lambda x: (_ for _ in ()).throw(KeyboardInterrupt()))

    run_ho.main()
    assert dummy_exec.closed is True


def test_single_cycle_no_atr_field(tmp_path):
    """Cover hasattr False case"""
    feed_path = tmp_path / "feed.json"
    feed_path.write_text(json.dumps([{"symbol": "XAUUSD", "entry": {}}]))

    class Engine:
        def __init__(self): self.global_atr = {}
        def run(self, entries): return [{"symbol": "XAUUSD", "decision": "HOLD"}]
        def get_global_atr(self): return {}

    engine = Engine()
    out = run_ho.single_cycle(engine, str(feed_path), DummyExecutor(), DummyHybridExit(),
                              {"exit": {}, "symbols": {"XAUUSD": {"pip_size": 0.01}}})
    assert out[0]["decision"] == "HOLD"
    assert engine.global_atr == {}


def test_single_cycle_atr_zero_and_none(tmp_path):
    """Cover hasattr True but falsy values"""
    for atr_val in [0, None]:
        feed_path = tmp_path / f"feed_{atr_val}.json"
        feed_path.write_text(json.dumps([{"symbol": "XAUUSD", "entry": {}, "atr": atr_val}]))

        class Engine:
            def __init__(self): self.global_atr = {}
            def run(self, entries): return [{"symbol": "XAUUSD", "decision": "HOLD"}]
            def get_global_atr(self): return {}

        engine = Engine()
        out = run_ho.single_cycle(engine, str(feed_path), DummyExecutor(), DummyHybridExit(),
                                  {"exit": {}, "symbols": {"XAUUSD": {"pip_size": 0.01}}})
        assert out[0]["decision"] == "HOLD"
        assert engine.global_atr == {}


def test_single_cycle_atr_positive(monkeypatch, tmp_path):
    """Cover line 47→48: atr truthy updates engine.global_atr"""

    class FakeEntry:
        def __init__(self):
            self.symbol = "XAUUSD"
            self.atr = 5.0

    monkeypatch.setattr(run_ho, "parse_feed", lambda feed: [FakeEntry()])

    class Engine:
        def __init__(self): self.global_atr = {}
        def run(self, entries): return [{"symbol": entries[0].symbol, "decision": "HOLD"}]
        def get_global_atr(self): return self.global_atr

    engine = Engine()
    feed_path = tmp_path / "feed.json"
    feed_path.write_text("[]")

    run_ho.single_cycle(engine, str(feed_path), DummyExecutor(), DummyHybridExit(),
                        {"exit": {}, "symbols": {"XAUUSD": {"pip_size": 0.01}}})

    assert "XAUUSD" in engine.global_atr
    assert engine.global_atr["XAUUSD"] == 5.0


def test_single_cycle_exception(tmp_path):
    feed_path = tmp_path / "feed.json"
    feed_path.write_text("[]")

    class BadEngine:
        def run(self, entries): raise RuntimeError("boom")
        def get_global_atr(self): return {}

    with pytest.raises(RuntimeError):
        run_ho.single_cycle(
            engine=BadEngine(),
            feed_path=str(feed_path),
            executor=DummyExecutor(),
            hybrid_exit=DummyHybridExit(),
            cfg={"exit": {}, "symbols": {"XAUUSD": {"pip_size": 0.01}}}
        )


def test_main_cycle_exception_break(monkeypatch, tmp_path):
    """Cover line 182→183: exception + PYTEST_RUNNING triggers break"""
    cfg_path = tmp_path / "cfg.yaml"
    feed_path = tmp_path / "feed.json"
    cfg_path.write_text("symbols: {XAUUSD: {pip_size: 0.01}}")
    feed_path.write_text("[]")

    monkeypatch.setenv("PYTEST_RUNNING", "1")
    monkeypatch.setattr("sys.argv",
        ["run_ho", "--balance", "1000", "--config", str(cfg_path),
         "--feed", str(feed_path), "--interval", "1"])

    dummy_exec = DummyExecutor()
    monkeypatch.setattr(run_ho, "Executor", lambda: dummy_exec)

    monkeypatch.setattr(run_ho, "single_cycle", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("forced")))

    run_ho.main()
    assert dummy_exec.closed is True


def test_run_as_script(monkeypatch, tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    feed_path = tmp_path / "feed.json"
    cfg_path.write_text("symbols: {XAUUSD: {pip_size: 0.01}}")
    feed_path.write_text("[]")

    monkeypatch.setenv("PYTEST_RUNNING", "1")
    monkeypatch.setenv("MT5_LOGIN", "1000")
    monkeypatch.setenv("MT5_PASSWORD", "dummy")
    monkeypatch.setenv("MT5_SERVER", "demo")

    monkeypatch.setattr(sys, "argv", [
        "run_ho", "--balance", "1000",
        "--config", str(cfg_path),
        "--feed", str(feed_path),
        "--interval", "1",
    ])

    monkeypatch.setattr(run_ho.mt5, "initialize", lambda *a, **k: True)
    monkeypatch.setattr(run_ho.mt5, "shutdown", lambda *a, **k: True)
    monkeypatch.setattr(run_ho.mt5, "last_error", lambda: (0, "ok"))
    monkeypatch.setattr(run_ho.mt5, "account_info",
                        lambda: types.SimpleNamespace(balance=1000, equity=1000))

    dummy_exec = DummyExecutor()
    monkeypatch.setattr(run_ho, "Executor", lambda: dummy_exec)

    monkeypatch.setattr(run_ho, "DecisionEngine", lambda **k: DummyEngine())
    monkeypatch.setattr(run_ho, "TrailingManager", lambda cfg: DummyTrailing(cfg))
    monkeypatch.setattr(run_ho, "RiskGuard", lambda cfg: DummyRiskGuard(cfg))
    monkeypatch.setattr(run_ho, "HybridExit", lambda cfg: DummyHybridExit())
    monkeypatch.setattr(run_ho, "GlobalExitManager",
                        lambda cfg: types.SimpleNamespace(check_exit=lambda *a, **k: (True, "stop", {})))
    monkeypatch.setattr(run_ho.time, "sleep", lambda x: None)

    run_ho.main()
    assert dummy_exec.closed is True


def test_run_as_main_block(monkeypatch, tmp_path):
    """Cover __main__ block in run_ho.py"""
    cfg_path = tmp_path / "cfg.yaml"
    feed_path = tmp_path / "feed.json"
    cfg_path.write_text("symbols: {XAUUSD: {pip_size: 0.01}}")
    feed_path.write_text("[]")

    # set dummy env
    monkeypatch.setenv("MT5_LOGIN", "1000")
    monkeypatch.setenv("MT5_PASSWORD", "dummy")
    monkeypatch.setenv("MT5_SERVER", "demo")
    monkeypatch.setenv("PYTEST_RUNNING", "1")

    monkeypatch.setattr(sys, "argv", [
        "run_ho", "--balance", "1000",
        "--config", str(cfg_path),
        "--feed", str(feed_path),
    ])

    # dummy MT5
    class DummyMT5:
        def initialize(self, *a, **k): return True
        def shutdown(self): return True
        def last_error(self): return (0, "ok")
        def account_info(self): return types.SimpleNamespace(balance=1000, equity=1000)

    sys.modules["MetaTrader5"] = DummyMT5()

    # dummy Executor (avoid calling real _connect)
    class DummyExec:
        def __init__(self): self.closed = False
        def shutdown(self): self.closed = True

    sys.modules["mind2_python.executor"] = types.SimpleNamespace(Executor=DummyExec)

    # clear run_ho to reload fresh
    sys.modules.pop("mind2_python.run_ho", None)

    # run as __main__
    runpy.run_module("mind2_python.run_ho", run_name="__main__")
