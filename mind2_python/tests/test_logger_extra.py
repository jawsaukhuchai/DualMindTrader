import logging
import pytest
import mind2_python.logger as mylogger


# -------------------------------
# ColorFormatter coverage
# -------------------------------
def test_color_formatter_wraps_message():
    fmt = mylogger.ColorFormatter("[%(levelname)s] %(message)s")
    rec = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )
    out = fmt.format(rec)
    # ควรมีสี + ข้อความ
    assert "\033" in out and "hello" in out


def test_color_formatter_default_color():
    fmt = mylogger.ColorFormatter("%(message)s")
    rec = logging.LogRecord(
        name="test",
        level=60,  # custom level → ไม่มีสีใน dict
        pathname=__file__,
        lineno=20,
        msg="weird",
        args=(),
        exc_info=None,
    )
    out = fmt.format(rec)
    # ไม่มี error และต้องเป็น str
    assert isinstance(out, str)
    assert "weird" in out


# -------------------------------
# get_logger coverage
# -------------------------------
def test_get_logger_console_and_file(tmp_path):
    log_path = tmp_path / "test.log"
    logger = mylogger.get_logger("UnitTestLogger", level=logging.DEBUG, filename=str(log_path))
    logger.info("something")
    # logger เดิมถูก cache → เรียกอีกครั้งไม่ควรเพิ่ม handler ซ้ำ
    logger2 = mylogger.get_logger("UnitTestLogger", level=logging.DEBUG, filename=str(log_path))
    assert logger is logger2
    # log file ต้องถูกสร้าง
    logger.handlers[1].flush()
    content = log_path.read_text()
    assert "something" in content


# -------------------------------
# pretty_log_decisionengine coverage
# -------------------------------
def test_pretty_log_decisionengine_full(caplog):
    caplog.set_level(logging.INFO)
    exit_levels = {
        "sl": 99.9,
        "tp": [
            {"price": 110.0, "diff": 10.1, "close_pct": 50},
            {"price": 120.0, "diff": 20.1, "close_pct": 50},
        ],
        "trailing": {"mult": 2, "value": 5.5},
    }
    mylogger.pretty_log_decisionengine(
        "BTCUSDc",
        "BUY",
        lot=0.1234,
        entry=100.0,
        exit_levels=exit_levels,
        mode="majority",
        votes={"BUY": 2, "SELL": 1},
        details={"day": "BUY"},
        reason="test",
    )
    msgs = [r.message for r in caplog.records]
    assert any("DecisionEngine" in m for m in msgs)
    assert any("SL=" in m for m in msgs)
    assert any("TP1=" in m for m in msgs)
    assert any("Trailing" in m for m in msgs)


def test_pretty_log_decisionengine_no_exit(caplog):
    caplog.set_level(logging.INFO)
    mylogger.pretty_log_decisionengine(
        "XAUUSDc", "SELL", lot=0.01, entry=2000.0, exit_levels=None, reason="noexit"
    )
    msgs = [r.message for r in caplog.records]
    assert any("SL=— TP=—" in m for m in msgs)


# -------------------------------
# pretty_log_tradesignal coverage
# -------------------------------
def test_pretty_log_tradesignal_full(caplog):
    caplog.set_level(logging.INFO)
    exit_levels = {
        "sl": 90.0,
        "tps": [
            {"price": 105.0, "pips": 5.0, "weight": 50},
            {"price": 95.0, "pips": -5.0, "weight": 50},
        ],
        "atr_mult": 2,
        "atr": 1.5,
    }
    mylogger.pretty_log_tradesignal(
        "BTCUSDc",
        "BUY",
        lot=0.01,
        entry=100.0,
        exit_levels=exit_levels,
        winprob=70.5,
        timeframe="M15",
        reason="ok",
    )
    msgs = [r.message for r in caplog.records]
    assert any("TRADE SIGNAL" in m for m in msgs)
    assert any("TP1" in m for m in msgs)
    assert any("ATR" in m for m in msgs)


def test_pretty_log_tradesignal_minimal(caplog):
    caplog.set_level(logging.INFO)
    mylogger.pretty_log_tradesignal("XAUUSDc", "SELL", lot=0.02, entry=2000.0)
    msgs = [r.message for r in caplog.records]
    assert any("TRADE SIGNAL" in m for m in msgs)


# -------------------------------
# pretty_log_risk / portfolio
# -------------------------------
def test_pretty_log_risk_and_portfolio(caplog):
    caplog.set_level(logging.INFO)
    mylogger.pretty_log_risk("BTCUSDc", "too risky")
    mylogger.pretty_log_portfolio("XAUUSDc", 0.05, reason="OK")
    mylogger.pretty_log_portfolio("XAUUSDc", 0.05, reason="blocked")
    msgs = [r.message for r in caplog.records]
    assert any("RiskGuard" in m for m in msgs)
    assert any("PortfolioManager" in m for m in msgs)
