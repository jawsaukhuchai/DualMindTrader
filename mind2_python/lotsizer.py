import logging
from typing import Dict, Any
from .position_manager import PositionManager   # ✅ ใช้เช็คจำนวน order
from mind2_python.safe_print import safe_print

logger = logging.getLogger("LotSizer")


# ------------------------------------------------------------------
# LotSizer (base)
# ------------------------------------------------------------------
class LotSizer:
    def __init__(self, balance: float = 10000.0):
        """
        LotSizer คำนวณขนาด lot ตาม balance + risk config
        """
        self.balance = balance

    def compute(self, entry: Any, sym_cfg: Dict[str, Any]) -> float:
        """
        คำนวณ lot ตาม risk percent และ clamp ด้วย min/max lot
        รองรับ 🌍 Global Reversal → Dynamic Lot Scaling
        """
        try:
            risk_cfg = sym_cfg.get("risk", {})
            risk_percent = risk_cfg.get("risk_percent", 1.0)
            min_lot = risk_cfg.get("min_lot", 0.01)
            max_lot = risk_cfg.get("max_lot", 0.5)

            # --- Base lot ---
            raw_lot = (self.balance * risk_percent) / 100000.0

            # --- Clamp ---
            lot = max(min_lot, raw_lot)
            lot = min(max_lot, lot)

            # --- 🌍 Global Reversal Scaling ---
            global_reversal = getattr(entry, "global_reversal", False) or sym_cfg.get("global_reversal", False)
            if global_reversal:
                open_count = PositionManager.count_open_positions(entry.symbol)
                # decay factor: ยิ่งมี order มาก lot ยิ่งลด
                decay_factor = max(0.3, 1.0 - (open_count * 0.2))
                scaled_lot = lot * decay_factor
                msg = (f"[LotSizer] {entry.symbol} 🌍 GlobalReversal scaling "
                       f"orders={open_count}, base_lot={lot:.2f} → scaled={scaled_lot:.2f}")
                logger.warning(msg)
                safe_print(msg, log_level="debug")
                lot = scaled_lot

            return round(lot, 2)  # ✅ ปัดสองตำแหน่งทศนิยม

        except Exception as e:
            logger.exception(f"LotSizer.compute error: {e}")
            return 0.0


# ------------------------------------------------------------------
# AdaptiveLotSizer (extends LotSizer)
# ------------------------------------------------------------------
class AdaptiveLotSizer(LotSizer):
    def compute(self, entry: Any, sym_cfg: Dict[str, Any], regime: str = "normal") -> float:
        """
        Adaptive lot sizing: ใช้ base จาก LotSizer แล้วปรับตาม volatility regime
        """
        base_lot = super().compute(entry, sym_cfg)
        try:
            factor = 1.0
            if regime == "high_vol":
                factor = 0.7    # ลด lot ถ้า volatility สูง
            elif regime == "low_vol":
                factor = 1.3    # เพิ่ม lot ถ้า volatility ต่ำ
            elif regime == "trend":
                factor = 1.1    # boost เล็กน้อยใน trend
            # "range" หรือ "normal" → factor=1.0

            lot = base_lot * factor

            min_lot = sym_cfg.get("risk", {}).get("min_lot", 0.01)
            max_lot = sym_cfg.get("risk", {}).get("max_lot", 0.5)

            # ✅ กรณี high_vol: อนุญาตให้ต่ำกว่า min_lot ได้ (ครึ่งหนึ่งของ min_lot)
            if regime == "high_vol":
                lot = max(min_lot * 0.5, lot)
            else:
                lot = max(min_lot, lot)

            # clamp max
            lot = min(max_lot, lot)

            msg = f"[AdaptiveLotSizer] {entry.symbol} regime={regime} base={base_lot:.2f} → lot={lot:.2f}"
            logger.debug(msg)
            safe_print(msg, log_level="debug")

            return round(lot, 2)

        except Exception as e:
            logger.exception(f"AdaptiveLotSizer.compute error: {e}")
            return base_lot
