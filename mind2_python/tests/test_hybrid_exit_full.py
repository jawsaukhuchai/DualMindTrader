import pytest
import types
import mind2_python.hybrid_exit as hx_mod
from mind2_python.hybrid_exit import HybridExit


@pytest.fixture
def cfg():
    return {
        "XAUUSD": {
            "digits": 2,
            "pip_size": 0.1,
            "exit": {"sl_atr": 1.5, "tp_steps": [1.0, 2.0], "tp_perc": [50, 50]},
            "portfolio": {"series_mode": "strict"},
        }
    }


# -------------------------------------------------------------------
# calc tests
# -------------------------------------------------------------------

def test_calc_invalid_atr(cfg, caplog):
    hx = HybridExit(cfg)
    d = {"decision": "BUY", "lot": 1}
    out = hx.calc(d, 100, "XAUUSD", atr=0, atr_multi={}, global_exit_cfg={})
    assert out["sl"] is not None
    assert "invalid ATR" in caplog.text


def test_calc_sell_scaling(cfg):
    hx = HybridExit(cfg)
    d = {"decision": "SELL", "lot": 1, "num_entries": 2}
    cfg["XAUUSD"]["portfolio"]["series_mode"] = "scaling"
    out = hx.calc(d, 100, "XAUUSD", atr=1, atr_multi={}, global_exit_cfg={})
    assert len(out["entries"]) == 2
    assert all("sl" in e for e in out["entries"].values())


def test_calc_hold(cfg):
    hx = HybridExit(cfg)
    d = {"decision": "HOLD"}
    out = hx.calc(d, 100, "XAUUSD", atr=1, atr_multi={}, global_exit_cfg={})
    assert out["sl"] is None
    assert out["tp"] == []


# -------------------------------------------------------------------
# recalc_for_open_positions tests
# -------------------------------------------------------------------

def test_recalc_no_positions(monkeypatch, cfg):
    hx = HybridExit(cfg)
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda **_: [])
    out = hx.recalc_for_open_positions("XAUUSD", atr=1, atr_multi={}, global_exit_cfg={})
    assert out == {}


def test_recalc_with_positions(monkeypatch, cfg):
    hx = HybridExit(cfg)
    pos = types.SimpleNamespace(
        ticket=1, type=0, price_open=100, comment="series-1", sl=None, volume=1, profit=0
    )
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda **_: [pos])
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.symbol_info", lambda s: None)
    monkeypatch.setattr("mind2_python.hybrid_exit.pretty_log_auto_update", lambda *a, **k: None)
    out = hx.recalc_for_open_positions("XAUUSD", atr=1, atr_multi={}, global_exit_cfg={})
    assert 1 in out
    assert "sl" in out[1]


def test_recalc_with_stops_level_force_adjust(monkeypatch, cfg):
    """ครอบ branch 154, 158"""
    hx = HybridExit(cfg)

    # BUY case
    pos_buy = types.SimpleNamespace(
        ticket=1, type=0, price_open=100, comment="series-1",
        sl=None, volume=1, profit=0
    )
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda **_: [pos_buy])
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.symbol_info", lambda s: types.SimpleNamespace(stops_level=1))
    monkeypatch.setattr("mind2_python.hybrid_exit.pretty_log_auto_update", lambda *a, **k: None)
    out = hx.recalc_for_open_positions("XAUUSD", atr=0.01, atr_multi={}, global_exit_cfg={})
    assert out[1]["sl"] <= pos_buy.price_open

    # SELL case
    pos_sell = types.SimpleNamespace(
        ticket=2, type=1, price_open=100, comment="series-1",
        sl=None, volume=1, profit=0
    )
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda **_: [pos_sell])
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.symbol_info", lambda s: types.SimpleNamespace(stops_level=1))
    out = hx.recalc_for_open_positions("XAUUSD", atr=0.01, atr_multi={}, global_exit_cfg={})
    assert out[2]["sl"] >= pos_sell.price_open


def test_recalc_comment_without_series(monkeypatch, cfg):
    """ครอบ branch 129->135"""
    hx = HybridExit(cfg)
    pos = types.SimpleNamespace(
        ticket=10, type=0, price_open=100, comment="no-series",
        sl=None, volume=1, profit=0
    )
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda **_: [pos])
    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.symbol_info", lambda s: None)
    monkeypatch.setattr("mind2_python.hybrid_exit.pretty_log_auto_update", lambda *a, **k: None)
    out = hx.recalc_for_open_positions("XAUUSD", atr=1, atr_multi={}, global_exit_cfg={})
    assert 10 in out


def test_force_sell_sl_adjust_btc(monkeypatch):
    """บังคับ sl_price < min_sl → ปิด branch 157->160"""
    hx = HybridExit({
        "BTCUSDc": {
            "digits": 1,
            "pip_size": 1.0,  # ต้องเป็น 1.0
            "exit": {"sl_atr": 1.5, "tp_steps": [1.0, 2.0], "tp_perc": [50, 50]},
        }
    })

    pos = types.SimpleNamespace(
        ticket=700,
        type=1,  # SELL
        price_open=100,
        comment="series-1",
        sl=None,
        volume=1,
        profit=0,
    )

    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.positions_get", lambda **_: [pos])

    class FakeSymbol:
        stops_level = 10

    monkeypatch.setattr("mind2_python.hybrid_exit.mt5.symbol_info", lambda s: FakeSymbol())
    monkeypatch.setattr("mind2_python.hybrid_exit.pretty_log_auto_update", lambda *a, **k: None)

    out = hx.recalc_for_open_positions("BTCUSDc", atr=0.01, atr_multi={}, global_exit_cfg={})
    sl_val = out[700]["sl"]

    pip_size = hx.cfg["BTCUSDc"]["pip_size"]
    min_sl = pos.price_open + FakeSymbol.stops_level * pip_size
    sl_price = pos.price_open + 0.01 * hx.cfg["BTCUSDc"]["exit"]["sl_atr"]

    # Debug assert
    assert sl_val == pytest.approx(min_sl, rel=1e-6), (
        f"Expected branch trigger: sl_price={sl_price}, min_sl={min_sl}, final_sl={sl_val}, pip_size={pip_size}"
    )


# -------------------------------------------------------------------
# adjust_trailing tests
# -------------------------------------------------------------------

def test_adjust_trailing_buy_sell(cfg):
    hx = HybridExit(cfg)
    sl = hx.adjust_trailing(105, "BUY", 100, None, {"atr_mult": 2, "breakeven": 1}, 0.1)
    assert sl is not None
    sl = hx.adjust_trailing(95, "SELL", 100, None, {"atr_mult": 2, "breakeven": 1}, 0.1)
    assert sl is not None


def test_adjust_trailing_no_cfg(cfg):
    hx = HybridExit(cfg)
    out = hx.adjust_trailing(100, "BUY", 100, None, {}, 0.1)
    assert out is None


# -------------------------------------------------------------------
# emergency_close_check tests
# -------------------------------------------------------------------

def test_emergency_close_check_severe(monkeypatch, cfg):
    hx = HybridExit(cfg)
    pos = types.SimpleNamespace(
        ticket=1, type=0, price_open=100, volume=1, profit=-20, sl=None, comment="series-1"
    )
    monkeypatch.setattr("mind2_python.hybrid_exit.pretty_log_close_position", lambda *a, **k: None)
    out = hx.emergency_close_check("XAUUSD", pos, severe_loss_pct=-0.1)
    assert out is True


def test_emergency_close_check_retrace(monkeypatch, cfg):
    hx = HybridExit(cfg)
    pos = types.SimpleNamespace(
        ticket=2, type=0, price_open=100, volume=1, profit=-5, sl=None, comment=None
    )
    monkeypatch.setattr("mind2_python.hybrid_exit.pretty_log_close_position", lambda *a, **k: None)
    out = hx.emergency_close_check("XAUUSD", pos)
    assert out is True


def test_emergency_close_comment_parse_fail(monkeypatch, cfg):
    """ครอบ branch 222->228, 225-226"""
    hx = HybridExit(cfg)
    pos = types.SimpleNamespace(
        ticket=3, type=0, price_open=100, volume=1, profit=-5,
        sl=None, comment="series-abc"
    )
    monkeypatch.setattr("mind2_python.hybrid_exit.pretty_log_close_position", lambda *a, **k: None)
    out = hx.emergency_close_check("XAUUSD", pos, severe_loss_pct=-0.1)
    assert out is True


def test_emergency_close_return_false(cfg):
    """ครอบ branch 244"""
    hx = HybridExit(cfg)
    pos = types.SimpleNamespace(
        ticket=201, type=0, price_open=100, volume=1, profit=10, sl=95, comment=None
    )
    out = hx.emergency_close_check("XAUUSD", pos)
    assert out is False


def test_emergency_close_profit_zero(monkeypatch, cfg):
    """ครอบ branch 236->244 → return False"""
    hx = HybridExit(cfg)
    pos = types.SimpleNamespace(
        ticket=301, type=0, price_open=100, volume=1, profit=0,
        sl=None, comment=None
    )
    monkeypatch.setattr("mind2_python.hybrid_exit.pretty_log_close_position", lambda *a, **k: None)
    out = hx.emergency_close_check("XAUUSD", pos)
    assert out is False
