import mind2_python.decision_engine as de

def test_fusion_decision_total_score_negative():
    """ครอบ branch total_score < 0 → ต้องได้ SELL"""
    ai_res = {"decision": "SELL", "confidence": 1.0}
    rule_res = {"decision": "HOLD", "confidence": 0.0}
    out = de.fusion_decision(ai_res, rule_res, "normal")

    # ตรวจว่า decision เป็น SELL และ score เป็นค่าลบ
    assert out["decision"] == "SELL"
    assert out["score"] < 0
