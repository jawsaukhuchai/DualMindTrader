# mind2_python/correlation_risk.py

import logging
from typing import Dict, Tuple

logger = logging.getLogger("CorrelationRisk")
logger.setLevel(logging.INFO)
logger.propagate = True


class CorrelationRisk:
    """
    Correlation risk manager (mock).
    ใช้เฉพาะกรณีเทรด BTCUSDc และ XAUUSDc:
    - ถ้ามีทั้งสองสัญลักษณ์พร้อมกัน -> block
    - ถ้ามีแค่ตัวใดตัวหนึ่ง -> ok
    """

    def __init__(self, cfg: dict = None):
        self.cfg = cfg or {}
        self.symbol_entries: Dict[str, float] = {}

    def update(self, symbol: str, entry: float):
        """บันทึก entry ล่าสุดของ symbol"""
        self.symbol_entries[symbol] = entry
        logger.debug(f"[CorrelationRisk] update {symbol}={entry}")

    def check(self) -> Tuple[bool, str]:
        """
        ตรวจสอบ correlation risk:
        - ถ้ามี BTCUSDc และ XAUUSDc พร้อมกัน → block
        - นอกนั้น allow
        """
        if not self.symbol_entries:
            return True, "corr_ok"

        symbols = set(self.symbol_entries.keys())
        if "BTCUSDc" in symbols and "XAUUSDc" in symbols:
            reason = "corr_blocked(BTCUSDc<->XAUUSDc)"
            logger.warning(f"[CorrelationRisk] ⛔ {reason}")
            return False, reason

        return True, "corr_ok"
