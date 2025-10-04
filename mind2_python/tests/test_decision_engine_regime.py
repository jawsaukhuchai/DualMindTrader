import pytest
import mind2_python.decision_engine as de


def test_regime_detector_with_plain_values():
    """ครอบ branch else: detect() ถูกเรียกด้วย float (ไม่ใช่ object)"""
    det = de.RegimeDetector({"atr_threshold": 1.0, "adx_threshold": 20.0})

    # กรณี atr >= threshold และ adx >= threshold → trend
    assert det.detect(2.0, adx=25.0) == "trend"

    # กรณี atr < threshold และ adx < threshold → range
    assert det.detect(0.5, adx=10.0) == "range"

    # กรณี atr >= threshold และ adx < threshold → high_vol
    assert det.detect(2.0, adx=10.0) == "high_vol"

    # กรณี atr < threshold และ adx >= threshold → low_vol
    assert det.detect(0.5, adx=25.0) == "low_vol"

    # กรณี atr=0, adx=0 → normal
    assert det.detect(0.0, adx=0.0) == "normal"

    # กรณีไม่ส่งค่า adx → fallback เป็น 0.0
    assert det.detect(5.0) in {"trend", "high_vol"}  # ขึ้นกับ threshold


def test_regime_detector_with_mixed_inputs():
    """เพิ่มกรณีค่าขอบ (boundary)"""
    det = de.RegimeDetector({"atr_threshold": 2.0, "adx_threshold": 30.0})

    # เท่ากับ threshold พอดี → ถือว่า >=
    assert det.detect(2.0, adx=30.0) == "trend"

    # atr ต่ำกว่า threshold, adx เท่ากับ threshold → low_vol
    assert det.detect(1.5, adx=30.0) == "low_vol"

    # atr เท่ากับ threshold, adx ต่ำกว่า threshold → high_vol
    assert det.detect(2.0, adx=20.0) == "high_vol"
