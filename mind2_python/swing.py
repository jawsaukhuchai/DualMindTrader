from typing import Dict, Any
from mind2_python.schema import TradeEntry


def safe_float(val):
    """แปลงค่าเป็น float แบบ robust"""
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


class SwingStrategy:
    def __init__(self, symbols_cfg: Dict[str, Any]):
        self.cfg = symbols_cfg

    def evaluate(self, entry: TradeEntry) -> Dict[str, Any]:
        symbol = entry.symbol
        cfg = self.cfg.get(symbol, {})
        ind = entry.h4 or entry.d1

        result = {"decision": "HOLD", "confidence": 0.0, "reason": []}
        if not ind:
            result["reason"].append("no_indicators")
            return result

        # --- ดึงค่า indicators ---
        rsi = getattr(ind, "rsi", None)
        atr = getattr(ind, "atr", None)
        adx = getattr(ind, "adx", None)
        macd_hist = getattr(ind, "macd_hist", None)
        bos = getattr(ind, "bos", None)
        bb = getattr(ind, "bb", None)

        # --- config thresholds ---
        ind_cfg = cfg.get("indicators", {})
        min_atr = ind_cfg.get("atr", {}).get("min_threshold", 0.0)
        min_adx = ind_cfg.get("adx", {}).get("min_threshold", 0.0)
        bull_level = ind_cfg.get("rsi", {}).get("bull_level", 65)
        bear_level = ind_cfg.get("rsi", {}).get("bear_level", 35)

        # --- ใช้ safe_float ---
        atr_val = safe_float(atr)
        adx_val = safe_float(adx)

        # --- Robust checks ---
        if atr_val is None or atr_val < min_atr:
            result["reason"].append("low_volatility")
            return result
        if adx_val is None or adx_val < min_adx:
            result["reason"].append("weak_trend")
            return result

        checks = []

        # RSI base
        if rsi is not None:
            if rsi >= bull_level:
                result["decision"] = "BUY"
                checks.append("rsi_bull")
            elif rsi <= bear_level:
                result["decision"] = "SELL"
                checks.append("rsi_bear")

        # MACD confirm
        if macd_hist is not None:
            if macd_hist > 0 and result["decision"] == "BUY":
                checks.append("macd_bull")
            elif macd_hist < 0 and result["decision"] == "SELL":
                checks.append("macd_bear")

        # Break of Structure confirm
        if bos and result["decision"] in ["BUY", "SELL"]:
            checks.append("bos_confirm")

        # Bollinger Bands confirm (trend continuation)
        if bb and result["decision"] in ["BUY", "SELL"]:
            upper = bb.get("upper")
            lower = bb.get("lower")
            if result["decision"] == "BUY" and upper is not None and entry.bid > upper:
                checks.append("bb_breakout_up")
            elif result["decision"] == "SELL" and lower is not None and entry.bid < lower:
                checks.append("bb_breakout_down")

        # Confidence calc
        if result["decision"] in ["BUY", "SELL"]:
            base_conf = 0.4
            bonus = 0.15 * len(checks)
            result["confidence"] = min(1.0, base_conf + bonus)

        result["reason"] = checks or ["flat_zone"]
        return result
