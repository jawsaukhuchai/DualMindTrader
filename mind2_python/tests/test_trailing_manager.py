import pytest
import importlib
import mind2_python.trailing_manager as tm


# ------------------------------
# Helpers
# ------------------------------
class DummyTick:
    def __init__(self, bid=100.0, ask=100.5):
        self.bid = bid
        self.ask = ask


@pytest.fixture
def cfg():
    return {
        "symbols": {
            "XAUUSDc": {"pip_size": 0.1}
        },
        "global": {"exit": {}}
    }


# ------------------------------
# loop_trailing
# ------------------------------
def test_loop_trailing_no_positions(monkeypatch, cfg):
    mgr = tm.TrailingManager(cfg)

    class FakeHX:
        def recalc_for_open_positions(self, **kwargs):
            return {}
        def emergency_close_check(self, sym, pos):
            return False

    monkeypatch.setattr(tm, "HybridExit", lambda *a, **k: FakeHX())
    monkeypatch.setattr(tm.PositionManager, "get_open_positions", staticmethod(lambda s: []))

    mgr.loop_trailing()  # should not crash


def test_loop_trailing_emergency_close(monkeypatch, cfg):
    mgr = tm.TrailingManager(cfg)

    pos = {"ticket": 1, "entry_index": 1}
    class FakeHX:
        def recalc_for_open_positions(self, **kwargs):
            return {}
        def emergency_close_check(self, sym, p):
            return True

    monkeypatch.setattr(tm, "HybridExit", lambda *a, **k: FakeHX())
    monkeypatch.setattr(tm.PositionManager, "get_open_positions", staticmethod(lambda s: [pos]))

    mgr.loop_trailing()  # should trigger emergency close


def test_loop_trailing_exception(monkeypatch, cfg):
    mgr = tm.TrailingManager(cfg)
    monkeypatch.setattr(tm, "HybridExit", lambda *a, **k: (_ for _ in ()).throw(Exception("boom")))
    mgr.loop_trailing()  # should catch and log error


def test_loop_trailing_with_exits(monkeypatch, cfg):
    mgr = tm.TrailingManager(cfg)

    class FakeHX:
        def recalc_for_open_positions(self, **kwargs):
            return {123: {"trailing": {"step": 1}}}  # non-empty exits
        def emergency_close_check(self, sym, pos):
            return False

    monkeypatch.setattr(tm, "HybridExit", lambda *a, **k: FakeHX())
    monkeypatch.setattr(tm.PositionManager, "get_open_positions", staticmethod(lambda s: []))

    mgr.loop_trailing()  # should enter "if exits:" block


# ------------------------------
# update_trailing
# ------------------------------
def test_update_trailing_no_positions(monkeypatch, cfg):
    mgr = tm.TrailingManager(cfg)
    monkeypatch.setattr(tm.PositionManager, "get_open_positions", staticmethod(lambda s: []))
    mgr.update_trailing("XAUUSDc", hybrid_exit=None, exits_map={})


def test_update_trailing_no_tick(monkeypatch, cfg):
    mgr = tm.TrailingManager(cfg)
    pos = {"side": "BUY", "entry": 100, "ticket": 1, "sl": None}
    monkeypatch.setattr(tm.PositionManager, "get_open_positions", staticmethod(lambda s: [pos]))
    exits_map = {1: {"trailing": {"step": 1}}}

    class FakeHX:
        def adjust_trailing(self, **kwargs): return None

    monkeypatch.setattr(tm.mt5, "symbol_info_tick", lambda sym: None)

    mgr.update_trailing("XAUUSDc", hybrid_exit=FakeHX(), exits_map=exits_map)


def test_update_trailing_adjust_and_update(monkeypatch, cfg):
    mgr = tm.TrailingManager(cfg)

    pos = {"side": "BUY", "entry": 100, "ticket": 1, "sl": 95.0, "lot": 0.1}
    monkeypatch.setattr(tm.PositionManager, "get_open_positions", staticmethod(lambda s: [pos]))
    exits_map = {1: {"trailing": {"step": 1}, "tp": [{"price": 110}]}}

    class FakeHX:
        def adjust_trailing(self, **kwargs): return 97.0

    monkeypatch.setattr(tm.mt5, "symbol_info_tick", lambda sym: DummyTick(bid=105, ask=105.5))

    called = {}
    def fake_update_position(self, **kwargs):
        called.update(kwargs)
    monkeypatch.setattr(tm.PositionManager, "update_position", fake_update_position)

    mgr.update_trailing("XAUUSDc", hybrid_exit=FakeHX(), exits_map=exits_map)

    assert called["sl"] == 97.0
    assert called["symbol"] == "XAUUSDc"


def test_update_trailing_trailing_cfg_missing(monkeypatch, cfg):
    mgr = tm.TrailingManager(cfg)
    pos = {"side": "BUY", "entry": 100, "ticket": 1, "sl": None}
    monkeypatch.setattr(tm.PositionManager, "get_open_positions", staticmethod(lambda s: [pos]))
    exits_map = {1: {}}  # no trailing cfg

    mgr.update_trailing("XAUUSDc", hybrid_exit=None, exits_map=exits_map)


# ------------------------------
# extra coverage
# ------------------------------
def test_trailing_manager_init(cfg):
    mgr = tm.TrailingManager(cfg)
    assert isinstance(mgr, tm.TrailingManager)


def test_import_trailing_manager_module():
    # Force reload to hit top-level lines
    importlib.reload(tm)
    assert hasattr(tm, "TrailingManager")


def test_trailing_manager_update_global_atr_truthy(cfg):
    """Simulate atr_map truthy branch via update_global_atr"""
    mgr = tm.TrailingManager(cfg)
    atr_map = {"XAUUSD": 5.0}
    mgr.update_global_atr(atr_map)
    assert mgr.global_atr == {"XAUUSD": 5.0}
