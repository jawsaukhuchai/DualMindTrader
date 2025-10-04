import logging
import pytest

from mind2_python.pretty_logger import (
    pretty_log_tradesignal,
    pretty_log_auto_update,
    pretty_log_dashboard,
)

def test_tradesignal_winprob_raw_only(capsys):
    # ✅ กรณี winprob_raw only → เข้า elif branch line 73
    pretty_log_tradesignal(
        symbol="BTCUSDc",
        decision="BUY",
        lot=0.1,
        entry=1.1111,
        winprob_raw=0.42,  # ไม่มี score_raw/conf_raw
    )
    out = capsys.readouterr().out
    assert "WinProb raw=0.42" in out
    assert "norm≈" not in out


@pytest.mark.parametrize("symbol, entry, sl, tp", [
    ("BTCUSDc", 30000.0, 29000.0, 31000.0),
    ("XAUUSDc", 1900.0, 1850.0, 1950.0),
])
def test_tradesignal_rule_res_none_branch(capsys, symbol, entry, sl, tp):
    """ครอบ branch line 138->140: rule_res=None สำหรับ BTCUSDc และ XAUUSDc"""
    pretty_log_tradesignal(
        symbol=symbol,
        decision="BUY",
        lot=0.1,
        entry=entry,
        exit_levels={"sl": sl, "tp": [{"price": tp}]},
        reason="rule_res_none",
        rule_res=None,   # 👈 ทำให้ if rule_res: False
    )
    out = capsys.readouterr().out
    assert "Entry" in out
    assert "Integration" not in out


def test_tradesignal_no_ai_no_rule_no_fusion(capsys):
    """ครอบเคส ai_res, rule_res, fusion = None ทั้งหมด → skip block 138"""
    pretty_log_tradesignal(
        symbol="BTCUSDc",
        decision="BUY",
        lot=0.1,
        entry=30500.0,
        reason="no_ai_no_rule_no_fusion",
        ai_res=None,
        rule_res=None,
        fusion=None,
    )
    out = capsys.readouterr().out
    assert "Entry" in out
    assert "AI=" not in out
    assert "Rule=" not in out
    assert "Fusion=" not in out


def test_tradesignal_ai_only_rule_res_none(capsys):
    """เข้า block ใหญ่ด้วย ai_res แต่ rule_res=None → ครอบ branch False ของ line 138"""
    pretty_log_tradesignal(
        symbol="BTCUSDc",
        decision="BUY",
        lot=0.1,
        entry=31000.0,
        reason="ai_only_rule_res_none",
        ai_res={"decision": "BUY", "confidence": 0.9},  # truthy → เข้า block ใหญ่
        rule_res=None,  # falsy → if rule_res: False
        fusion=None,
    )
    out = capsys.readouterr().out
    assert "AI=" in out
    assert "Rule=" not in out
    assert "Fusion=" not in out


def test_auto_update_debug_logged(capsys, caplog):
    caplog.set_level(logging.DEBUG, logger="PrettyLog")
    pretty_log_auto_update("BTCUSDc", ticket=123, sl=1.0, tp=2.0)

    out = capsys.readouterr().out
    assert "AUTO-UPDATE" in out

    # ✅ ต้องมี log record ที่เป็น DEBUG
    recs = [r for r in caplog.records if r.name == "PrettyLog"]
    assert any("AUTO-UPDATE" in r.message and r.levelno == logging.DEBUG for r in recs)


def test_dashboard_non_compact_with_results(capsys):
    # ✅ ส่ง results พร้อม compact=False → ครอบ line 250
    results = {
        "XAUUSDc": {
            "decision": "HOLD",
            "signal": {"winprob": 0.0},
            "confidence": 0.0,
            "regime": "Flat",
            "votes": {"rule": {"threshold": None, "num_entries": None}},
        }
    }

    pretty_log_dashboard(
        balance=1000.0,
        equity=1000.0,
        pnl=0.0,
        margin_level=100.0,
        lots=0.0,
        results=results,
        symbols_cfg={},
        compact=False,
    )

    out = capsys.readouterr().out
    assert "Dashboard" in out
    assert "Balance=1000.00" in out
    assert "Equity=1000.00" in out
