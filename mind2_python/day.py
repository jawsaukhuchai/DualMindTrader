from typing import Dict, Any
from mind2_python.schema import TradeEntry

class DayStrategy:
    def __init__(self, symbols_cfg: Dict[str, Any]):
        self.cfg = symbols_cfg

    def evaluate(self, entry: TradeEntry) -> Dict[str, Any]:
        symbol = entry.symbol
        cfg = self.cfg.get(symbol, {})
        ind = entry.h1

        result = {"decision": "HOLD", "confidence": 0.0, "reason": []}
        if not ind:
            result["reason"].append("no_indicators")
            return result

        rsi = getattr(ind, "rsi", None)
        atr = getattr(ind, "atr", None)
        adx = getattr(ind, "adx", None)
        ema_fast = getattr(ind, "ema_fast", None)
        ema_slow = getattr(ind, "ema_slow", None)
        macd_hist = getattr(ind, "macd_hist", None)
        vwap = getattr(ind, "vwap", None)
        stoch_k = getattr(ind, "stoch_k", None)
        stoch_d = getattr(ind, "stoch_d", None)

        min_atr = cfg.get("indicators", {}).get("atr", {}).get("min_threshold", 0.0)
        min_adx = cfg.get("indicators", {}).get("adx", {}).get("min_threshold", 0.0)
        bull_level = cfg.get("indicators", {}).get("rsi", {}).get("bull_level", 60)
        bear_level = cfg.get("indicators", {}).get("rsi", {}).get("bear_level", 40)

        if not atr or atr < min_atr:
            result["reason"].append("low_volatility")
            return result
        if not adx or adx < min_adx:
            result["reason"].append("weak_trend")
            return result

        checks = []

        # RSI decision
        if rsi:
            if rsi >= bull_level:
                result["decision"] = "BUY"
                checks.append("rsi_bull")
            elif rsi <= bear_level:
                result["decision"] = "SELL"
                checks.append("rsi_bear")

        # EMA trend confirm
        if ema_fast and ema_slow:
            if ema_fast > ema_slow and result["decision"] == "BUY":
                checks.append("ema_uptrend")
            if ema_fast < ema_slow and result["decision"] == "SELL":
                checks.append("ema_downtrend")

        # MACD momentum confirm
        if macd_hist:
            if macd_hist > 0 and result["decision"] == "BUY":
                checks.append("macd_bull")
            if macd_hist < 0 and result["decision"] == "SELL":
                checks.append("macd_bear")

        # Stochastic confirm
        if stoch_k and stoch_d:
            if result["decision"] == "BUY" and stoch_k < 20 and stoch_k > stoch_d:
                checks.append("stoch_buy")
            if result["decision"] == "SELL" and stoch_k > 80 and stoch_k < stoch_d:
                checks.append("stoch_sell")

        # VWAP filter
        if vwap:
            if result["decision"] == "BUY" and entry.bid < vwap:
                checks.append("below_vwap")
            if result["decision"] == "SELL" and entry.bid > vwap:
                checks.append("above_vwap")

        # Confidence calc
        if result["decision"] in ["BUY", "SELL"]:
            base_conf = 0.5
            bonus = 0.1 * len(checks)
            result["confidence"] = min(1.0, base_conf + bonus)

        result["reason"] = checks or ["flat_zone"]
        return result
