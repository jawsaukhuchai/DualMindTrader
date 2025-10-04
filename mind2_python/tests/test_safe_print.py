import sys
import io
import pytest
from mind2_python.safe_print import safe_print


def test_safe_print_info(capsys):
    safe_print("hello", "world")
    captured = capsys.readouterr()
    assert "hello world" in captured.out


def test_safe_print_levels(capsys):
    safe_print("debug", log_level="debug")
    safe_print("warn", log_level="warning")
    safe_print("err", log_level="error")
    safe_print("info", log_level="info")
    captured = capsys.readouterr()
    assert "debug" in captured.out
    assert "warn" in captured.out
    assert "err" in captured.out
    assert "info" in captured.out


def test_safe_print_custom_sep_end(capsys):
    safe_print("A", "B", sep="-", end="!", log_level="info")
    captured = capsys.readouterr()
    assert "A-B!" in captured.out


def test_safe_print_fallback_stderr(monkeypatch):
    # ทำให้ stdout.write พังเพื่อ trigger fallback
    class BrokenStream:
        def write(self, *_):
            raise IOError("stdout broken")
        def flush(self): pass

    monkeypatch.setattr(sys, "stdout", BrokenStream())
    fake_err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_err)

    safe_print("x", "y", log_level="info")
    out = fake_err.getvalue()
    assert "[safe_print error]" in out
