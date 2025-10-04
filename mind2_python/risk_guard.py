import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("RiskGuard")
logger.setLevel(logging.INFO)
logger.propagate = True

from .position_manager import PositionManager   # ✅ ใช้สำหรับ replace order

# ------------------------------------------------------------------
# ANSI helper
# ------------------------------------------------------------------
class Ansi:
    RESET = "\033[0m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

def colorize_reason(reason: str) -> str:
    r = reason.lower()
    if "blocked" in r:
        return f"{Ansi.RED}{reason}{Ansi.RESET}"
    elif "ok" in r or "allowed" in r:
        return f"{Ansi.GREEN}{reason}{Ansi.RESET}"
    elif "low" in r or "cooldown" in r or "override" in r or "replace" in r:
        return f"{Ansi.YELLOW}{reason}{Ansi.RESET}"
    return f"{Ansi.GRAY}{reason}{Ansi.RESET}"


class RiskGuard:
    def __init__(self, config: dict = None, cfg: dict = None):
        if config is None and cfg is not None:
            config = cfg
        self.config = config or {}
        self.state = {
            "daily_loss": 0.0,
            "orders_count": {},
            "last_sl_hit": {},
        }

    def _find_worst_order(self, symbol: str) -> Optional[Dict]:
        """
        หา order ที่ 'แย่ที่สุด' (เช่น กำไรติดลบมากสุด) เพื่อนำมา replace
        """
        positions = PositionManager.get_open_positions(symbol)
        if not positions:
            return None
        worst = min(positions, key=lambda p: p.get("profit", 0.0))
        return worst

    def check(
        self,
        symbol: str,
        balance: float,
        decision: Optional[str] = None,
        lot: Optional[float] = None,
        entry: Optional[float] = None,
        open_positions: Optional[Dict[str, List[float]]] = None,
        daily_loss: Optional[float] = None,
        global_reversal: bool = False,   # ✅ เพิ่ม param
    ) -> Tuple[bool, List[str]]:
        """
        Global risk guard checks:
        - max_orders (real MT5 check)
        - daily loss % (loss_limit_percent / max_daily_loss_pct)
        - cooldown after SL
        - override for global_reversal
        Returns (ok, reasons: list of tags)
        """
        reasons: List[str] = []
        risk_cfg = self.config.get("symbols", {}).get(symbol, {}).get("risk", {})
        max_orders = risk_cfg.get("max_orders", 5)

        # unified loss percent key
        max_daily_loss_pct = (
            risk_cfg.get("max_daily_loss_pct")
            or risk_cfg.get("loss_limit_percent")
            or 5.0
        )

        cooldown_minutes = risk_cfg.get("cooldown_minutes", 15)

        # --- Max orders (real MT5 check) ---
        open_count = PositionManager.count_open_positions(symbol)
        if open_count >= max_orders:
            if global_reversal:
                # 🌍 override: ปิด order ที่แย่ที่สุด แล้ว allow order ใหม่
                worst_order = self._find_worst_order(symbol)
                if worst_order:
                    PositionManager().close_position(symbol, ticket=worst_order["ticket"])
                    reasons.append(f"override_replace(ticket={worst_order['ticket']})")
                    return True, reasons
                else:
                    reasons.append("override_allowed(no_replace)")
                    return True, reasons
            else:
                reasons.append(f"orders_blocked({open_count}/{max_orders})")
                return False, reasons
        else:
            reasons.append("orders_ok")

        # --- Balance check ---
        if balance <= 0:
            reasons.append("balance_blocked")
            return False, reasons
        else:
            reasons.append("balance_ok")

        # ✅ override สำหรับ test
        effective_daily_loss = daily_loss if daily_loss is not None else self.state["daily_loss"]

        # --- Daily loss ---
        daily_loss_pct = abs(effective_daily_loss) / balance * 100
        if daily_loss_pct >= max_daily_loss_pct:
            reasons.append(f"loss_blocked({daily_loss_pct:.2f}%/{max_daily_loss_pct}%)")
            return False, reasons
        else:
            reasons.append("loss_ok")

        # --- Cooldown ---
        last_sl = self.state["last_sl_hit"].get(symbol)
        if last_sl and datetime.utcnow() - last_sl < timedelta(minutes=cooldown_minutes):
            if global_reversal:
                reasons.append("cooldown_override")
                return True, reasons
            reasons.append("cooldown_blocked")
            return False, reasons
        else:
            reasons.append("cooldown_ok")

        return True, reasons

    def allow(self, entry, final: dict, balance: float = 10000) -> Tuple[bool, List[str]]:
        """
        Wrapper ให้ DecisionEngine ใช้งานง่าย
        """
        ok, reasons = self.check(
            symbol=entry.symbol,
            balance=balance,
            decision=final.get("decision"),
            lot=final.get("lot"),
            entry=final.get("entry"),
            global_reversal=final.get("global_reversal", False),  # ✅ ใช้ flag
        )
        if not ok:
            logger.warning(
                f"[RiskGuard] {entry.symbol} ⛔ {Ansi.RED}blocked{Ansi.RESET}: "
                + "|".join(colorize_reason(r) for r in reasons)
            )
        else:
            if final.get("global_reversal", False):
                logger.warning(
                    f"[RiskGuard] {entry.symbol} 🌍 {Ansi.YELLOW}override{Ansi.RESET}: "
                    + "|".join(colorize_reason(r) for r in reasons)
                )
            else:
                logger.info(
                    f"[RiskGuard] {entry.symbol} ✅ {Ansi.GREEN}allowed{Ansi.RESET} "
                    f"({ '|'.join(colorize_reason(r) for r in reasons) })"
                )
        return ok, reasons

    def register_order(self, symbol: str):
        self.state["orders_count"][symbol] = self.state["orders_count"].get(symbol, 0) + 1

    def register_loss(self, symbol: str, loss: float):
        self.state["daily_loss"] += loss
        self.state["last_sl_hit"][symbol] = datetime.utcnow()

    def record_trade(self, symbol: str, pnl: float):
        """
        Record a trade result (used in tests).
        Negative pnl updates daily_loss and cooldown.
        """
        self.state["orders_count"][symbol] = self.state["orders_count"].get(symbol, 0) + 1
        if pnl < 0:
            self.register_loss(symbol, pnl)
