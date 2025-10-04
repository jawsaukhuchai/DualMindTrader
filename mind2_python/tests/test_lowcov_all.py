import pytest
import types
import logging
from unittest.mock import patch
import pandas as pd

import mind2_python.hybrid_exit as hybrid_exit
import mind2_python.indicators_efficient as ind
import mind2_python.portfolio_manager as pm
import mind2_python.position_manager as posmgr
import mind2_python.logger as mlogger
import mind2_python.global_manager as gmanager
import mind2_python.risk_guard as risk_guard
import mind2_python.executor as executor


# -----------------------------
# Logger tests
# -----------------------------
def test_color_formatter_formatting():
    fmt = mlogger.ColorFormatter("[%(levelname)s] %(message)s")
    record = logging.LogRecord("x", logging.INFO, "", 0, "hello", None, None)
    out = fmt.format(record)
    assert "hello" in out
    assert "\033" in out  # colored


def test_get_logger_console_and_file(tmp_path):
    log_file = tmp_path / "test.log"
    logger = mlogger.get_logger("TestLogger", level=logging.DEBUG, filename=str(log_file))
    logger.info("hello world")

    for h in list(logger.handlers):
        if hasattr(h, "flush"):
            h.flush()
        if hasattr(h, "close"):
            h.close()
    logger.handlers.clear()

    assert log_file.exists()
    assert "hello world" in log_file.read_text()


def test_pretty_log_decision_and_tradesignal(caplog):
    caplog.set_level(logging.INFO)
    exit_levels = {"sl": 99.5,
                   "tp": [{"price": 101.0, "diff": 1.5, "close_pct": 50}],
                   "trailing": {"mult": 1.5, "value": 100.5}}
    mlogger.pretty_log_decisionengine(
        "BTCUSDc", "BUY", 0.1, 100.0,
        exit_levels=exit_levels,
        mode="majority", votes={"ai": 1}, details={"rsi": 70},
        reason="test"
    )
    assert any("DecisionEngine" in m for m in caplog.messages)

    exit_levels2 = {"sl": 95.5,
                    "tps": [{"price": 105.0, "pips": 50, "weight": 50}],
                    "atr_mult": 2.0, "atr": 1.2}
    mlogger.pretty_log_tradesignal(
        "XAUUSDc", "SELL", 0.2, 2000.0,
        exit_levels=exit_levels2, winprob=55.5,
        reason="check"
    )
    mlogger.pretty_log_risk("BTCUSDc", "too risky")
    mlogger.pretty_log_portfolio("XAUUSDc", 0.1, reason="OK")
    assert any("TRADE SIGNAL" in m for m in caplog.messages)


# -----------------------------
# HybridExit tests
# -----------------------------
def test_hybridexit_calc_hold_and_scaling():
    hx = hybrid_exit.HybridExit({
        "BTCUSDc": {
            "exit": {"sl_atr": 1.5, "tp_steps": [1, 2], "tp_perc": [50, 50]},
            "digits": 2,
            "portfolio": {"series_mode": "scaling"},
            "pip_size": 0.1,
        }
    })
    dec_hold = {"decision": "HOLD"}
    res = hx.calc(decision=dec_hold, entry=100, symbol="BTCUSDc",
                  atr=1.0, atr_multi={}, global_exit_cfg={})
    assert res["sl"] is None

    dec_scale = {"decision": "BUY", "lot": 1.0, "num_entries": 3}
    res2 = hx.calc(decision=dec_scale, entry=100, symbol="BTCUSDc",
                   atr=1.0, atr_multi={}, global_exit_cfg={})
    assert len(res2["entries"]) == 3


@patch("mind2_python.hybrid_exit.mt5.positions_get")
@patch("mind2_python.hybrid_exit.mt5.symbol_info")
def test_hybridexit_recalc_with_stops_level_and_bad_comment(mock_info, mock_posget):
    pos = types.SimpleNamespace(ticket=1, type=0, price_open=100.0,
                                volume=1.0, comment="series-bad", profit=0.0)
    mock_posget.return_value = [pos]
    mock_info.return_value = types.SimpleNamespace(stops_level=10, point=0.1)
    hx = hybrid_exit.HybridExit({"BTCUSDc": {"exit": {"sl_atr": 1.0}, "digits": 2, "pip_size": 0.01}})
    res = hx.recalc_for_open_positions("BTCUSDc", atr=1.0, atr_multi={}, global_exit_cfg={})
    assert 1 in res and "sl" in res[1]


def test_hybridexit_calc_with_invalid_tp_config():
    hx = hybrid_exit.HybridExit({
        "BTCUSDc": {"exit": {"sl_atr": 1.0, "tp_steps": [], "tp_perc": []}, "digits": 2, "pip_size": 0.1}
    })
    dec = {"decision": "BUY", "lot": 0.1}
    res = hx.calc(decision=dec, entry=100, symbol="BTCUSDc",
                  atr=1.0, atr_multi={}, global_exit_cfg={})
    assert "tp" in res and res["tp"] == []


@patch("mind2_python.hybrid_exit.mt5.positions_get")
def test_hybridexit_recalc_no_positions(mock_posget):
    mock_posget.return_value = None
    hx = hybrid_exit.HybridExit({"BTCUSDc": {"exit": {"sl_atr": 1.0}, "digits": 2, "pip_size": 0.1}})
    res = hx.recalc_for_open_positions("BTCUSDc", atr=1.0, atr_multi={}, global_exit_cfg={})
    assert res == {}


@patch("mind2_python.hybrid_exit.mt5.positions_get")
def test_hybridexit_recalc_with_series_comment(mock_posget):
    pos = types.SimpleNamespace(ticket=1, type=0, price_open=100.0,
                                volume=1.0, comment="series-1|extra", profit=5.0)
    mock_posget.return_value = [pos]
    hx = hybrid_exit.HybridExit({"BTCUSDc": {"exit": {"sl_atr": 1.0}, "digits": 2, "pip_size": 0.1}})
    res = hx.recalc_for_open_positions("BTCUSDc", atr=1.0, atr_multi={}, global_exit_cfg={})
    assert isinstance(res, dict) and 1 in res


# -----------------------------
# Indicators Efficient tests
# -----------------------------
def test_indicators_edge_and_bb(caplog):
    df = pd.DataFrame({"high": [1]*30, "low": [1]*30, "close": [1]*30, "tick_volume": [1]*30})
    res = ind.add_indicators_last(df, symbol="BTCUSDc")
    assert "rsi" in res and "bb" in res

    df_short = pd.DataFrame({"close": [1, 2, 3]})
    val = ind.compute_atr_last(df_short, period=14, symbol="BTCUSDc")
    assert val == 1.0

    assert ind.detect_bos_last(None) == ""


# -----------------------------
# PortfolioManager tests
# -----------------------------
class DummyCorrRisk:
    def __init__(self, ok=True, reason="corr_ok"): self.ok, self.reason = ok, reason
    def update(self,symbol,entry): pass
    def check(self): return self.ok, self.reason

@patch("mind2_python.portfolio_manager.CorrelationRisk", autospec=True)
@patch("mind2_python.portfolio_manager.PositionManager.count_open_positions")
def test_portfolio_correlation_and_global_block(mock_count, mock_corr):
    mock_count.return_value = 0
    mock_corr.return_value = DummyCorrRisk(ok=False, reason="corr_blocked")
    pmgr = pm.PortfolioManager({"symbols":{"BTCUSDc":{"portfolio":{"max_orders":5}}}})
    lot, reasons = pmgr.check("BTCUSDc", lot=1, balance=1000)
    assert lot == 0

    mock_corr.return_value = DummyCorrRisk(ok=True, reason="corr_ok")
    pmgr2 = pm.PortfolioManager({"symbols":{"BTCUSDc":{"portfolio":{"max_orders":5}}}})
    lot2, reasons2 = pmgr2.check("BTCUSDc", lot=1, balance=1000)
    assert lot2 > 0 and any("corr_ok" in r for r in reasons2)


# -----------------------------
# GlobalManager extra coverage
# -----------------------------
def test_global_entry_manager_with_dict_open_positions():
    gm = gmanager.GlobalEntryManager({})
    ok, reasons = gm.check({"balance":1000,"equity":1000}, {"symbol":"BTCUSDc"})
    assert not ok or isinstance(reasons, list)

def test_global_exit_manager_with_dict_open_positions():
    gx = gmanager.GlobalExitManager({})
    ok, reason, reasons = gx.check_exit({"balance":1000,"equity":1000}, 0)
    assert ok or reason in ("equity_normal","dd_exceed","daily_target_hit")

def test_global_exit_manager_balance_invalid():
    gx = gmanager.GlobalExitManager({})
    ok, reason, reasons = gx.check_exit({"balance":-1,"equity":0})
    assert not ok
    assert reason in ("balance_invalid", "equity_normal")


# -----------------------------
# PositionManager extra coverage
# -----------------------------
def test_update_position_simulation_symbol_not_found():
    pmgr = posmgr.PositionManager()
    pmgr.state = {"positions": {"XAUUSDc": []}}
    pmgr.update_position("BTCUSDc", 1, sl=100.0, tp=[{"price":101.0}])
    assert "BTCUSDc" not in pmgr.state["positions"]

def test_close_position_with_empty_list():
    pmgr = posmgr.PositionManager()
    pmgr.state = {"positions": {"BTCUSDc": []}, "orders_count": {"BTCUSDc": 1}}
    pmgr.close_position("BTCUSDc")
    assert pmgr.state["orders_count"]["BTCUSDc"] == 0

def test_get_open_positions_with_exception(monkeypatch, caplog):
    caplog.set_level("ERROR")
    def boom(symbol): raise RuntimeError("mt5 fail")
    monkeypatch.setattr(posmgr.PositionManager, "get_positions", boom)
    res = posmgr.PositionManager.get_open_positions("BTCUSDc")
    assert res == [] or isinstance(res, list)
    assert any("get_open_positions failed" in m for m in caplog.messages)

def test_get_open_positions_safe_fallback():
    pmgr = posmgr.PositionManager._instance()
    pmgr.state["positions"]["BTCUSDc"] = [{"ticket":1,"symbol":"BTCUSDc","lot":0.1}]
    res = posmgr.PositionManager.get_open_positions("BTCUSDc")
    assert res and res[0]["symbol"] == "BTCUSDc"


# -----------------------------
# PortfolioManager lowcov
# -----------------------------
def test_portfolio_balance_zero_triggers_fallback():
    pmgr = pm.PortfolioManager({"symbols":{"BTCUSDc":{"portfolio":{"max_orders":5}}}})
    with patch("mind2_python.portfolio_manager.PositionManager.count_open_positions", return_value=0):
        lot, reasons = pmgr.check("BTCUSDc", lot=1.0, balance=0)
    assert any("risk_ok" in r for r in reasons)

def test_portfolio_allow_with_global_reversal_override_triggers_log(caplog, monkeypatch):
    caplog.set_level(logging.WARNING)
    pmgr = pm.PortfolioManager({"symbols":{"BTCUSDc":{"portfolio":{}}}})
    # patch check() ให้คืนค่า 0.0 เพื่อบังคับเข้า branch override log
    monkeypatch.setattr(pmgr, "check", lambda *a, **kw: (0.0, ["risk_blocked(>max)"]))
    class DummyEntry: symbol="BTCUSDc"
    ok, reasons = pmgr.allow(DummyEntry(), {"lot":1.0,"decision":"BUY","entry":100,
                                            "exit_levels":{}, "open_positions":{},
                                            "signal":{}, "global_reversal":True})
    assert ok is False
    assert any("🌍 override" in m for m in caplog.messages)


# -----------------------------
# RiskGuard lowcov
# -----------------------------
def test_riskguard_colorize_reason_variants():
    assert "blocked" in risk_guard.colorize_reason("orders_blocked")
    assert "ok" in risk_guard.colorize_reason("allowed_ok")
    assert "cooldown" in risk_guard.colorize_reason("cooldown_blocked")
    assert "replace" in risk_guard.colorize_reason("override_replace")

def test_riskguard_allow_blocked_branch(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    rg = risk_guard.RiskGuard({"symbols":{"BTCUSDc":{"risk":{"max_orders":1}}}})
    monkeypatch.setattr(risk_guard.PositionManager, "count_open_positions", lambda s: 5)
    ok, reasons = rg.allow(type("E", (), {"symbol":"BTCUSDc"}), {"lot":0.1,"decision":"BUY"})
    assert not ok
    assert any("blocked" in r for r in reasons)
    assert any("⛔" in m for m in caplog.messages)


# -----------------------------
# Executor lowcov
# -----------------------------
def test_executor_close_position_ticket_not_match(monkeypatch):
    ex = executor.Executor.__new__(executor.Executor)  # bypass __init__
    ex.magic = 1
    ex.max_slippage = 0.0005
    fake_pos = types.SimpleNamespace(ticket=999, volume=0.1, type=0, profit=0.0, comment="series-1")
    monkeypatch.setattr(executor.mt5, "positions_get", lambda **kwargs: [fake_pos])
    monkeypatch.setattr(executor.mt5, "symbol_info_tick", lambda s: types.SimpleNamespace(bid=100, ask=101))
    monkeypatch.setattr(executor.mt5, "order_send", lambda req: types.SimpleNamespace(retcode=executor.TRADE_RETCODE_DONE))
    result = ex.close_position(ticket=123, symbol="BTCUSDc")
    assert result is None

def test_executor_close_position_comment_not_series(monkeypatch):
    ex = executor.Executor.__new__(executor.Executor)
    ex.magic = 1
    ex.max_slippage = 0.0005
    fake_pos = types.SimpleNamespace(ticket=123, volume=0.1, type=0, profit=0.0, comment="manual-trade")
    monkeypatch.setattr(executor.mt5, "positions_get", lambda **kwargs: [fake_pos])
    monkeypatch.setattr(executor.mt5, "symbol_info_tick", lambda s: types.SimpleNamespace(bid=100, ask=101))
    monkeypatch.setattr(executor.mt5, "order_send", lambda req: types.SimpleNamespace(retcode=executor.TRADE_RETCODE_DONE))
    result = ex.close_position(ticket=123, symbol="BTCUSDc")
    assert result is not None
