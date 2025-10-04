# mind2_python/tests/test_snapshot_utils.py
import json
import os
import pytest

import mind2_python.snapshot_utils as su


def test_save_and_load_snapshot_roundtrip(tmp_path, monkeypatch):
    """ทดสอบ save + load snapshot ครบ flow"""
    monkeypatch.setattr(su, "SNAPSHOT_DIR", tmp_path)  # redirect ไป tmp

    data = {"a": 1, "b": [2, 3]}
    su.save_snapshot("case1", data)

    loaded = su.load_snapshot("case1")
    assert loaded == data

    # ตรวจไฟล์ว่ามีจริง
    path = tmp_path / "case1.json"
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    assert raw == data


def test_load_snapshot_file_not_found(tmp_path, monkeypatch):
    """ไฟล์ไม่มี → return {}"""
    monkeypatch.setattr(su, "SNAPSHOT_DIR", tmp_path)
    result = su.load_snapshot("nope")
    assert result == {}


def test_assert_match_snapshot_new_and_update(tmp_path, monkeypatch):
    """assert_match_snapshot: สร้างใหม่ + update overwrite"""
    monkeypatch.setattr(su, "SNAPSHOT_DIR", tmp_path)

    val1 = {"x": 1}
    val2 = {"x": 2}

    # key ยังไม่มี → เขียนใหม่
    su.assert_match_snapshot("snap", "k1", val1)
    assert su.load_snapshot("snap")["k1"] == val1

    # update=True → overwrite ค่า
    su.assert_match_snapshot("snap", "k1", val2, update=True)
    assert su.load_snapshot("snap")["k1"] == val2


def test_assert_match_snapshot_mismatch(tmp_path, monkeypatch):
    """assert_match_snapshot: ถ้ามีแล้วและค่าไม่ตรง → assert fail"""
    monkeypatch.setattr(su, "SNAPSHOT_DIR", tmp_path)
    su.save_snapshot("snap", {"k1": {"x": 1}})

    with pytest.raises(AssertionError) as e:
        su.assert_match_snapshot("snap", "k1", {"x": 999})
    assert "Snapshot mismatch" in str(e.value)
