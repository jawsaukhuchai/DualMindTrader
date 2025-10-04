from dataclasses import dataclass, field
from typing import List, Dict, Any, Union, Optional
from datetime import datetime
import logging
from dateutil import parser as dtparser  # รองรับ timestamp ISO ทุกแบบ

logger = logging.getLogger("Schema")

# ============================================================
# Indicators schema
# ============================================================
@dataclass
class Indicators:
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    rsi: float = 50.0
    macd_main: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    atr: float = 0.0
    stoch_k: float = 0.0
    stoch_d: float = 0.0
    vwap: float = 0.0
    bos: str = ""
    bos_val: float = 0.0
    bos_label: str = ""
    adx: float = 0.0
    bb_mid: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    trend_score: float = 0.0  # ✅ normalize composite (-100..100)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Indicators":
        return cls(
            ema_fast=d.get("ema_fast", 0.0),
            ema_slow=d.get("ema_slow", 0.0),
            rsi=d.get("rsi", 50.0),
            macd_main=d.get("macd_main", 0.0),
            macd_signal=d.get("macd_signal", 0.0),
            macd_hist=d.get("macd_hist", 0.0),
            atr=d.get("atr", 0.0),
            stoch_k=d.get("stoch_k", 0.0),
            stoch_d=d.get("stoch_d", 0.0),
            vwap=d.get("vwap", 0.0),
            bos=d.get("bos_str", d.get("bos", "")),
            bos_val=d.get("bos_val", 0.0),
            bos_label=d.get("bos_label", ""),
            adx=d.get("adx", 0.0),
            bb_mid=d.get("bb_mid", 0.0),
            bb_upper=d.get("bb_upper", 0.0),
            bb_lower=d.get("bb_lower", 0.0),
        )

# ============================================================
# Decision-ready schema
# ============================================================
@dataclass
class DecisionReady:
    timeframe: str = "H1"
    bias: str = "HOLD"            # BUY / SELL / HOLD
    confidence: float = 0.0       # 0–100
    risk_blockers: List[str] = field(default_factory=list)
    volatility_regime: str = "NORMAL"

# ============================================================
# TradeEntry schema (per symbol)
# ============================================================
@dataclass
class TradeEntry:
    symbol: str
    bid: float
    ask: float
    spread: float
    filters: Dict[str, Any]
    timeframes: Dict[str, Any]
    timestamp: str
    indicators: Indicators = field(default_factory=Indicators)
    decision_ready: DecisionReady = field(default_factory=DecisionReady)
    volatility: Dict[str, float] = field(default_factory=dict)  # ✅ atr_m5, atr_h1, atr_h4

    # --- Shortcuts ---
    @property
    def atr(self) -> float:
        return self.indicators.atr

    @property
    def adx(self) -> float:
        return self.indicators.adx

    @property
    def dt(self) -> datetime:
        try:
            return dtparser.parse(self.timestamp)
        except Exception:
            return datetime.min

    # --- Timeframe accessors ---
    def tf(self, key: str) -> Indicators:
        return Indicators.from_dict(self.timeframes.get(key, {}))

    @property
    def m1(self) -> Indicators: return self.tf("M1")
    @property
    def m5(self) -> Indicators: return self.tf("M5")
    @property
    def m30(self) -> Indicators: return self.tf("M30")
    @property
    def h1(self) -> Indicators: return self.tf("H1")
    @property
    def h4(self) -> Indicators: return self.tf("H4")
    @property
    def d1(self) -> Indicators: return self.tf("D1")

# ============================================================
# Feed parser
# ============================================================
def parse_feed(feed: Union[List[Dict[str, Any]], Dict[str, Any]]) -> List[TradeEntry]:
    if isinstance(feed, dict) and "symbols" in feed:
        feed = feed["symbols"]

    entries: List[TradeEntry] = []
    for item in feed:
        if not isinstance(item, dict) or "symbol" not in item:
            logger.warning(f"Skip invalid item: {item}")
            continue

        try:
            tf = item.get("timeframes", {})

            # fallback: H1 → M5 → default
            if "H1" in tf:
                ind = Indicators.from_dict(tf["H1"])
            elif "M5" in tf:
                ind = Indicators.from_dict(tf["M5"])
            else:
                ind = Indicators()

            volatility = {
                "atr_m5": tf.get("M5", {}).get("atr", 0.0),
                "atr_h1": tf.get("H1", {}).get("atr", 0.0),
                "atr_h4": tf.get("H4", {}).get("atr", 0.0),
            }

            entry = TradeEntry(
                symbol=item["symbol"],
                bid=item["bid"],
                ask=item["ask"],
                spread=item["spread"],
                filters=item.get("filters", {}),
                timeframes=tf,
                timestamp=item.get("timestamp", ""),
                indicators=ind,
                volatility=volatility,
                decision_ready=DecisionReady(),  # default → Mind2 จะเติม bias/confidence
            )
            entries.append(entry)

        except Exception as e:
            logger.error(f"Failed to parse item: {e} | item={item}")
    return entries

# ✅ alias for backward compatibility
load_feed_batch = parse_feed
