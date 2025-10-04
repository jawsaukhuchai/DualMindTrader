import logging, time
from typing import Dict, Any, Tuple, List
from .position_manager import PositionManager
from mind2_python.safe_print import safe_print
from mind2_python.correlation_risk import CorrelationRisk

logger = logging.getLogger("PortfolioManager")
logger.setLevel(logging.INFO)
logger.propagate = True


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
    elif "low" in r or "rotation" in r or "override" in r or "replace" in r:
        return f"{Ansi.YELLOW}{reason}{Ansi.RESET}"
    return f"{Ansi.GRAY}{reason}{Ansi.RESET}"


class PortfolioManager:
    def __init__(self, config: dict):
        self.config = config or {}
        self.max_symbols_global = self.config.get("portfolio", {}).get("max_symbols", 3)

        # ✅ เก็บเวลา entry ล่าสุด (per symbol + global)
        self.last_entry_time: Dict[str, float] = {}

        # ✅ correlation risk manager
        self.corr_risk = CorrelationRisk(self.config.get("global", {}).get("correlation_risk", {}))

    # ---------------------------------------------------------
    def register_entry(self, symbol: str):
        """บันทึกเวลาที่มีการเปิด order ใหม่ (ใช้สำหรับ cooldown)"""
        now = time.time()
        self.last_entry_time[symbol] = now
        self.last_entry_time["GLOBAL"] = now
        msg = f"[PortfolioManager] ⏱️ register_entry {symbol} @ {now}"
        logger.debug(msg)
        safe_print(msg, log_level="debug")

    # ---------------------------------------------------------
    def _get_account_info(self) -> Dict[str, Any]:
        """
        ดึง health account ล่าสุดจาก PositionManager
        """
        try:
            health = PositionManager.get_health()
            if not health:
                raise RuntimeError("empty health feed")
            return {
                "balance": health.get("balance", 1e6),
                "equity": health.get("equity", health.get("balance", 1e6)),
                "margin": health.get("margin", 0.0),
                "margin_level": health.get("margin_level", 9999),
            }
        except Exception as e:
            logger.error(f"[PortfolioManager] ❌ Failed to get account info: {e}")
            return {"balance": 1e6, "equity": 1e6, "margin": 0.0, "margin_level": 9999}

    # ---------------------------------------------------------
    def check(
        self,
        symbol: str,
        lot: float,
        balance: float = None,
        decision: str = None,
        entry: float = 0.0,
        exit_levels: dict = None,
        open_positions: Dict[str, List[float]] = None,
        signal: Dict[str, Any] = None,
        global_reversal: bool = False,
    ) -> Tuple[float, List[str]]:
        reasons: List[str] = []
        sym_cfg = self.config.get("symbols", {}).get(symbol, {})
        pm_cfg = sym_cfg.get("portfolio", {})

        acc_info = self._get_account_info()
        effective_balance = balance if balance is not None else acc_info.get("balance", 0.0)
        if effective_balance <= 0:
            effective_balance = 1e6

        # --- Max risk pct ---
        raw_limit = pm_cfg.get("max_risk_pct", 0.3)
        max_risk_pct = raw_limit * 100 if raw_limit <= 1 else raw_limit
        current_risk_pct = (lot or 0.0) / effective_balance * 100
        if current_risk_pct > max_risk_pct:
            if global_reversal:
                reasons.append(f"risk_override({current_risk_pct:.4f}%/{max_risk_pct}%)")
            else:
                reasons.append(f"risk_blocked({current_risk_pct:.4f}%/{max_risk_pct}%)")
                return 0.0, reasons
        else:
            reasons.append("risk_ok")

        # --- Max orders per symbol ---
        max_orders = pm_cfg.get("max_orders", 1)
        open_count = PositionManager.count_open_positions(symbol)
        if open_count >= max_orders:
            if global_reversal:
                reasons.append(f"orders_override({open_count}/{max_orders})")
            else:
                reasons.append(f"orders_blocked({open_count}/{max_orders})")
                return 0.0, reasons
        else:
            reasons.append("orders_ok")

        # --- 🌍 Global max_orders_total ---
        max_orders_total = self.config.get("global", {}).get("max_orders_total")
        if max_orders_total:
            total_open = sum(PositionManager.count_open_positions(s) for s in (open_positions or {}))
            if total_open >= max_orders_total:
                if global_reversal:
                    reasons.append(f"global_orders_override({total_open}/{max_orders_total})")
                else:
                    reasons.append(f"global_orders_blocked({total_open}/{max_orders_total})")
                    return 0.0, reasons
            else:
                reasons.append(f"global_orders_ok({total_open}/{max_orders_total})")

        # --- 🌍 Cooldown check ---
        cooldown_sec = self.config.get("global", {}).get("cooldown_seconds")
        if cooldown_sec:
            last_ts = self.last_entry_time.get("GLOBAL")
            if last_ts and time.time() - last_ts < cooldown_sec:
                if global_reversal:
                    reasons.append(f"cooldown_override({time.time()-last_ts:.1f}s/{cooldown_sec}s)")
                else:
                    reasons.append(f"cooldown_blocked({time.time()-last_ts:.1f}s/{cooldown_sec}s)")
                    return 0.0, reasons
            else:
                reasons.append("cooldown_ok")

        # --- 🌍 Correlation Risk ---
        self.corr_risk.update(symbol, entry)
        ok, reason = self.corr_risk.check()
        if not ok:
            reasons.append(reason)
            return 0.0, reasons
        else:
            reasons.append(reason)

        reasons.append("allowed")
        return lot, reasons

    # ---------------------------------------------------------
    def allow(self, entry, final: dict, balance: float = None) -> Tuple[bool, List[str]]:
        lot = final.get("lot", 0.0)
        ok_lot, reasons = self.check(
            symbol=entry.symbol,
            lot=lot,
            balance=balance,
            decision=final.get("decision"),
            entry=final.get("entry"),
            exit_levels=final.get("exit_levels"),
            open_positions=final.get("open_positions"),
            signal=final.get("signal"),
            global_reversal=final.get("global_reversal", False),
        )
        if ok_lot <= 0:
            if final.get("global_reversal", False):
                msg = (f"[PortfolioManager] {entry.symbol} 🌍 override: "
                       + "|".join(colorize_reason(r) for r in reasons))
                logger.warning(msg)
                safe_print(msg, log_level="debug")
            else:
                msg = (f"[PortfolioManager] {entry.symbol} ⛔ blocked: "
                       + "|".join(colorize_reason(r) for r in reasons))
                logger.warning(msg)
                safe_print(msg, log_level="debug")
            return False, reasons
        return True, reasons
