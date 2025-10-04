import os
import yaml
import pytest

from mind2_python.config_loader import load_config, _deep_update


def test_load_config_with_existing_file(tmp_path):
    # สร้างไฟล์ YAML ชั่วคราว
    cfg_path = tmp_path / "test_config.yaml"
    data = {"symbols": {"BTCUSDc": {"risk": {"min_lot": 0.1}}}}
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)

    cfg = load_config(str(cfg_path))
    assert "symbols" in cfg
    assert cfg["symbols"]["BTCUSDc"]["risk"]["min_lot"] == 0.1


def test_load_config_with_missing_file(tmp_path):
    # path ที่ไม่มีจริง → ต้องได้ dict ว่าง
    fake_path = tmp_path / "no_config.yaml"
    cfg = load_config(str(fake_path))
    assert cfg == {}


def test_load_config_with_overrides(tmp_path):
    # สร้าง config เดิม
    cfg_path = tmp_path / "base.yaml"
    base = {"symbols": {"XAUUSDc": {"risk": {"min_lot": 0.1, "max_lot": 1.0}}}}
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(base, f)

    overrides = {"symbols": {"XAUUSDc": {"risk": {"max_lot": 2.0}}}}
    cfg = load_config(str(cfg_path), overrides=overrides)

    # min_lot ควรยังอยู่, max_lot ควรถูก override
    risk_cfg = cfg["symbols"]["XAUUSDc"]["risk"]
    assert risk_cfg["min_lot"] == 0.1
    assert risk_cfg["max_lot"] == 2.0


def test_deep_update_nested():
    orig = {"a": {"b": 1, "c": 2}, "d": 3}
    upd = {"a": {"b": 99}, "e": 100}
    merged = _deep_update(orig.copy(), upd)

    assert merged["a"]["b"] == 99   # ถูก override
    assert merged["a"]["c"] == 2    # ค่าดั้งเดิมยังอยู่
    assert merged["d"] == 3         # ไม่ถูกแก้
    assert merged["e"] == 100       # เพิ่มใหม่


def test_load_config_default_path(monkeypatch):
    # simulate ไม่มีไฟล์ default (path=None)
    monkeypatch.setattr("os.path.exists", lambda _: False)
    cfg = load_config(None)
    assert cfg == {}  # เพราะหาไฟล์ไม่เจอ


def test_load_config_open_fail(tmp_path, monkeypatch):
    # สร้างไฟล์ แต่ mock open ให้ fail
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text("not valid: : : yaml")

    def bad_open(*a, **k):
        raise IOError("mock open fail")

    monkeypatch.setattr("builtins.open", bad_open)

    cfg = load_config(str(cfg_path))
    assert cfg == {}
