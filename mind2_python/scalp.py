from typing import Dict, Any
from mind2_python.schema import TradeEntry

class ScalpStrategy:
    def __init__(self, symbols_cfg: Dict[str, Any]):
        self.cfg = symbols_cfg

    def evaluate(self, entry: TradeEntry) -> Dict[str, Any]:
        symbol = entry.symbol
        cfg = self.cfg.get(symbol, {})
        ind = entry.m5

        result = {"decision": "HOLD", "confidence": 0.0, "reason": []}

        if not ind:
            result["reason"].append("no_indicators")
            return result

        # Base thresholds
        rsi = getattr(ind, "rsi", None)
        atr = getattr(ind, "atr", None)
        adx = getattr(ind, "adx", None)
        stoch_k = getattr(ind, "stoch_k", None)
        stoch_d = getattr(ind, "stoch_d", None)
        vwap = getattr(ind, "vwap", None)

        min_atr = cfg.get("indicators", {}).get("atr", {}).get("min_threshold", 0.0)
        min_adx = cfg.get("indicators", {}).get("adx", {}).get("min_threshold", 0.0)
        bull_level = cfg.get("indicators", {}).get("rsi", {}).get("bull_level", 55)
        bear_level = cfg.get("indicators", {}).get("rsi", {}).get("bear_level", 45)

        # Filters
        if not atr or atr < min_atr:
            result["reason"].append("low_volatility")
            return result
        if not adx or adx < min_adx:
            result["reason"].append("weak_trend")
            return result

        checks = []

        # RSI signal
        if rsi is not None:
            if rsi >= bull_level:
                result["decision"] = "BUY"
                checks.append("rsi_bull")
            elif rsi <= bear_level:
                result["decision"] = "SELL"
                checks.append("rsi_bear")

        # Stochastic confirm
        if stoch_k and stoch_d:
            if result["decision"] == "BUY" and stoch_k < 20 and stoch_k > stoch_d:
                checks.append("stoch_confirm_buy")
            if result["decision"] == "SELL" and stoch_k > 80 and stoch_k < stoch_d:
                checks.append("stoch_confirm_sell")

        # VWAP filter
        if vwap:
            if result["decision"] == "BUY" and entry.bid < vwap:
                checks.append("below_vwap_buy")
            if result["decision"] == "SELL" and entry.bid > vwap:
                checks.append("above_vwap_sell")

        # Confidence
        if result["decision"] in ["BUY", "SELL"]:
            base_conf = 0.6
            bonus = 0.1 * len(checks)  # more confirmations = higher confidence
            result["confidence"] = min(1.0, base_conf + bonus)
        else:
            result["confidence"] = 0.0

        result["reason"] = checks or ["flat_zone"]
        return result
