import logging
import pytest

from mind2_python.pretty_logger import _emit

@pytest.mark.parametrize("level", ["info", "debug", "warning", "error"])
def test_emit_stdout_and_logger(capsys, caplog, level):
    msg = f"hello_{level}"

    # เปิด caplog สำหรับ logger "PrettyLog"
    caplog.set_level(logging.DEBUG, logger="PrettyLog")

    _emit(msg, level=level)

    # ตรวจ stdout
    captured = capsys.readouterr()
    assert msg in captured.out
    assert captured.err == ""

    # ตรวจ logger record
    found = [r for r in caplog.records if r.name == "PrettyLog" and r.message == msg]
    assert found, f"Expected log record for level={level}"
    rec = found[0]

    # ตรวจว่า level ถูกต้อง
    expected_level = {
        "info": logging.INFO,
        "debug": logging.DEBUG,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }[level]
    assert rec.levelno == expected_level
