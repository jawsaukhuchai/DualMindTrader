import logging
import pytest
import mind2_python.logger as mylogger


# -------------------------------
# ColorFormatter coverage
# -------------------------------
def test_color_formatter_known_and_unknown_level():
    fmt = mylogger.ColorFormatter("[%(levelname)s] %(message)s")

    # level INFO (มีใน COLORS)
    rec_info = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=10,
        msg="hello-info", args=(), exc_info=None
    )
    out_info = fmt.format(rec_info)
    assert "\033" in out_info and "hello-info" in out_info

    # level custom (ไม่อยู่ใน COLORS)
    rec_custom = logging.LogRecord(
        name="test", level=60, pathname=__file__, lineno=20,
        msg="hello-custom", args=(), exc_info=None
    )
    out_custom = fmt.format(rec_custom)
    assert "hello-custom" in out_custom


# -------------------------------
# get_logger coverage
# -------------------------------
def test_get_logger_with_and_without_file(tmp_path):
    log_file = tmp_path / "log.txt"

    # logger ใหม่ → จะสร้าง handler ทั้ง console + file
    logger = mylogger.get_logger("LoggerFull", level=logging.DEBUG, filename=str(log_file))
    logger.info("msg-file")

    # เรียกซ้ำ → ไม่ควรเพิ่ม handler ซ้ำ
    logger2 = mylogger.get_logger("LoggerFull", level=logging.DEBUG, filename=str(log_file))
    assert logger is logger2

    # flush log file
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler):
            h.flush()
    content = log_file.read_text()
    assert "msg-file" in content


# -------------------------------
# Pretty log functions
# -------------------------------
def test_pretty_log_decision_and_integration_aliases(caplog):
    """ครอบ pretty_log_decision / pretty_log_integration (alias ไป decisionengine)"""
    caplog.set_level(logging.INFO)
    mylogger.pretty_log_decision("BTCUSDc", "BUY", lot=0.1, entry=100.0, exit_levels=None)
    mylogger.pretty_log_integration("XAUUSDc", "SELL", lot=0.2, entry=2000.0, exit_levels=None)
    msgs = [r.message for r in caplog.records]
    assert any("DecisionEngine" in m for m in msgs)


def test_pretty_log_risk_and_portfolio(caplog):
    caplog.set_level(logging.INFO)
    mylogger.pretty_log_risk("BTCUSDc", "too risky")
    mylogger.pretty_log_portfolio("BTCUSDc", 0.1, reason="OK")
    mylogger.pretty_log_portfolio("BTCUSDc", 0.1, reason="Blocked")
    msgs = [r.message for r in caplog.records]
    assert any("RiskGuard" in m for m in msgs)
    assert any("PortfolioManager" in m for m in msgs)


def test_pretty_log_tradesignal_and_reason(caplog):
    caplog.set_level(logging.INFO)
    exit_levels = {
        "sl": 95.0,
        "tps": [{"price": 105.0, "pips": 5.0, "weight": 50}],
        "atr_mult": 2,
        "atr": 1.5,
    }
    mylogger.pretty_log_tradesignal(
        "BTCUSDc", "BUY", lot=0.1, entry=100.0,
        exit_levels=exit_levels, winprob=80.0, timeframe="M15", reason="ok"
    )
    mylogger.pretty_log_tradesignal(
        "XAUUSDc", "SELL", lot=0.2, entry=2000.0, exit_levels={}, reason="noexit"
    )
    msgs = [r.message for r in caplog.records]
    assert any("TRADE SIGNAL" in m for m in msgs)


def test_pretty_log_decisionengine_full(caplog):
    caplog.set_level(logging.INFO)
    exit_levels = {"sl": 99.9, "tp": [{"price": 110, "diff": 10, "close_pct": 50}]}
    mylogger.pretty_log_decisionengine("BTCUSDc", "BUY", lot=0.1, entry=100.0, exit_levels=exit_levels)
    msgs = [r.message for r in caplog.records]
    assert any("DecisionEngine" in m for m in msgs)
