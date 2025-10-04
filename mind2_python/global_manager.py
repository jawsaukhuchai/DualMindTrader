import time, logging
from typing import Dict, Any, Tuple, List
from mind2_python.safe_print import safe_print

logger = logging.getLogger("GlobalManager")

# ------------------------------------------------------------------
# Allowed symbols filter
# ------------------------------------------------------------------
ALLOWED_SYMBOLS = {"BTCUSDc", "XAUUSDc"}


# ------------------------------------------------------------------
# Global Entry Manager
# ------------------------------------------------------------------
class GlobalEntryManager:
    last_entry_time = None

    def __init__(self, config: dict = None):
        self.config = config or {}

    def check(self, acc_info: dict, open_positions: dict) -> Tuple[bool, List[str]]:
        gcfg = self.config.get("global", {})
        balance = acc_info.get("balance", 0.0) or 0.0
        equity = acc_info.get("equity", 0.0) or 0.0

        if balance <= 0:
            return False, ["balance_invalid"]

        reasons = []

        # Allowed symbols guard
        if isinstance(open_positions, dict):
            symbol = open_positions.get("symbol")
            if symbol and symbol not in ALLOWED_SYMBOLS:
                return False, [f"symbol_blocked({symbol})"]

        # Equity % guard
        eq_pct = (equity / balance) * 100 if balance > 0 else 100
        min_eq = gcfg.get("min_equity_pct", 50)
        if eq_pct < min_eq:
            return False, [f"entry_blocked_equity_low({eq_pct:.1f}%<{min_eq}%)"]
        reasons.append("equity_ok")

        # Max lots exposure
        max_lots_pct = gcfg.get("max_lots_pct", 5)
        total_lots = 0.0

        if isinstance(open_positions, dict):
            total_lots += open_positions.get("lots_local", 0.0) or 0.0
            pf = open_positions.get("positions_feed")
            if isinstance(pf, (int, float)):
                total_lots += pf

        if balance > 0 and (total_lots / balance * 100) > max_lots_pct:
            return False, [f"entry_blocked_lots_exceed({total_lots:.2f}/{max_lots_pct}%)"]
        reasons.append("lots_ok")

        return True, reasons

    def register_entry(self):
        GlobalEntryManager.last_entry_time = time.time()
        msg = f"[GlobalEntry] register_entry at {GlobalEntryManager.last_entry_time}"
        logger.debug(msg)
        safe_print(msg, log_level="debug")

    @classmethod
    def get_last_entry_time(cls):
        return cls.last_entry_time


# ------------------------------------------------------------------
# Global PnL Guard
# ------------------------------------------------------------------
class GlobalPnLGuard:
    def __init__(self, config: dict = None):
        self.config = config or {}

    def check(self, balance: float, daily_loss: float) -> Tuple[bool, str]:
        gcfg = self.config.get("global", {})
        if balance <= 0:
            return True, "balance_invalid"

        # Daily loss % guard
        max_loss_pct = gcfg.get("max_daily_loss_pct")
        if max_loss_pct and balance > 0:
            daily_loss_pct = abs(daily_loss) / balance * 100
            if daily_loss_pct >= max_loss_pct:
                return True, f"daily_loss_pct_exceed({daily_loss_pct:.2f}%/{max_loss_pct}%)"

        # Daily loss absolute guard
        max_loss_abs = gcfg.get("max_daily_loss_abs")
        if max_loss_abs and abs(daily_loss) >= max_loss_abs:
            return True, f"daily_loss_abs_exceed({daily_loss:.2f}/{max_loss_abs})"

        return False, "pnl_guard_ok"


# ------------------------------------------------------------------
# Global Exit Manager
# ------------------------------------------------------------------
class GlobalExitManager:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.pnl_guard = GlobalPnLGuard(config)

    def check_exit(self, acc_info: dict, daily_loss: float = 0.0) -> Tuple[bool, str, List[str]]:
        gcfg = self.config.get("global", {})
        balance = acc_info.get("balance", 0.0) or 0.0
        equity = acc_info.get("equity", 0.0) or 0.0

        if balance <= 0:
            return False, "equity_normal", ["balance_invalid"]

        reasons = []

        # Equity %
        eq_pct = (equity / balance) * 100 if balance > 0 else 100
        min_eq = gcfg.get("min_equity_pct", 50)
        if eq_pct < min_eq:
            return True, f"equity_low({eq_pct:.1f}%<{min_eq}%)", ["equity_low"]
        reasons.append("equity_ok")

        # Drawdown %
        dd = 100 - eq_pct
        max_dd = gcfg.get("max_drawdown_pct", 20)
        if dd >= max_dd:
            return True, f"drawdown_exceed({dd:.1f}%/{max_dd}%)", ["dd_exceed"]
        reasons.append("dd_ok")

        # Daily profit target
        gain_pct = (equity - balance) / balance * 100 if balance > 0 else 0.0
        target = gcfg.get("daily_target_pct", 999)
        if gain_pct >= target:
            return True, f"daily_target_hit({gain_pct:.1f}%/{target}%)", ["daily_target_hit"]
        reasons.append("daily_target_ok")

        # Daily PnL Guard
        blocked, reason = self.pnl_guard.check(balance, daily_loss)
        if blocked:
            return True, reason, ["pnl_guard_blocked"]
        reasons.append(reason)

        return False, "equity_normal", reasons

    def force_exit_all(self, executor):
        """Force close all open positions immediately (🌍 Global Kill Switch)"""
        try:
            from mind2_python.position_manager import PositionManager
            positions = PositionManager.get_open_positions_summary()
            if not positions:
                msg = "[GlobalExit] 🌍 No positions to close"
                logger.info(msg)
                safe_print(msg, log_level="debug")
                return

            logger.warning("[GlobalExit] 🌍 Forced EXIT ALL triggered")
            executor.close_all()

            # ใช้ public API ถ้ามี
            if hasattr(PositionManager, "clear_all_positions"):
                PositionManager.clear_all_positions()
            elif hasattr(PositionManager, "_instance"):
                inst = getattr(PositionManager, "_instance")
                # กรณีเป็น callable (singleton getter)
                if callable(inst):
                    inst = inst()
                if inst and hasattr(inst, "state"):
                    pos = inst.state.get("positions")
                    if isinstance(pos, dict):
                        pos.clear()
        except Exception as e:
            logger.error(f"[GlobalExit] ❌ force_exit_all failed: {e}")


# ------------------------------------------------------------------
# Kill Switch Manager (base)
# ------------------------------------------------------------------
class _BaseKillSwitchManager:
    def __init__(self, config: dict = None):
        self.config = config or {}
        gcfg = self.config.get("global", {})
        self.enabled = gcfg.get("killswitch_enabled", True)
        self.dd_limit_pct = gcfg.get("killswitch_dd_limit_pct", 10)
        self.window_hours = gcfg.get("killswitch_window_hours", 6)
        self.history = []
        self.triggered = False

    def check(self, equity: float, now: float = None, skip_append: bool = False):
        if not self.enabled:
            return False, "disabled"

        if now is None:
            now = time.time()

        # ✅ เพิ่ม flag skip_append สำหรับ test coverage
        if not skip_append:
            self.history.append((now, equity))

        cutoff = now - self.window_hours * 3600
        self.history = [(t, e) for t, e in self.history if t >= cutoff]

        if not self.history:
            return False, "no_data"

        max_eq = max(e for _, e in self.history)
        dd = (max_eq - equity) / max_eq * 100 if max_eq > 0 else 0.0

        if dd >= self.dd_limit_pct:
            self.triggered = True
            _BaseKillSwitchManager._triggered = True
            msg = f"[KillSwitch] triggered dd={dd:.1f}%/{self.dd_limit_pct}%"
            logger.warning(msg)
            safe_print(msg, log_level="debug")
            return True, f"killswitch_triggered(dd={dd:.1f}%/{self.dd_limit_pct}%)"

        return False, f"ok(dd={dd:.1f}%/{self.dd_limit_pct}%)"


# ------------------------------------------------------------------
# Global Dashboard
# ------------------------------------------------------------------
def log_global_dashboard(*args, **kwargs):
    """
    Log global dashboard summary.
    รองรับรูปแบบเต็ม (balance, equity, pnl, margin_level, lots, open_positions, results)
    และแบบย่อ (acc_info, open_positions, results=...).
    รองรับ kwargs เพิ่มเติม: regime, ai_res, rule_res, fusion
    """
    if len(args) >= 7:
        balance, equity, pnl, margin_level, lots, open_positions, results = args[:7]
    else:
        acc_info = args[0] if args else {}
        open_positions = args[1] if len(args) > 1 else {}
        balance = acc_info.get("balance", 0.0)
        equity = acc_info.get("equity", 0.0)
        pnl = acc_info.get("open_pnl", 0.0)
        margin_level = acc_info.get("margin_level", 0.0)
        lots = 0.0
        results = kwargs.get("results", {})

        if isinstance(open_positions, dict):
            symbol = open_positions.get("symbol")
            if symbol in ALLOWED_SYMBOLS:
                lots_local = open_positions.get("lots_local", 0.0) or 0.0
                pf = open_positions.get("positions_feed", 0.0) or 0.0
                lots = lots_local + pf

    base_line = (f"[Dashboard] 💹 Balance={balance:.2f} | Equity={equity:.2f} | "
                 f"OpenPnL={pnl:.2f} | MarginLevel={margin_level:.1f}% | Lots={lots:.2f}")
    logger.info(base_line)
    safe_print(base_line, log_level="debug")

    ai_res = kwargs.get("ai_res", {})
    rule_res = kwargs.get("rule_res", {})
    fusion = kwargs.get("fusion", {})
    regime_val = kwargs.get("regime")

    allowed_syms = [sym for sym in results.keys() if sym in ALLOWED_SYMBOLS]
    overlay_count = f"[Dashboard] allowed={len(allowed_syms)}/{len(results)}"
    logger.info(overlay_count)
    safe_print(overlay_count, log_level="debug")

    if not allowed_syms and any(k in kwargs for k in ["regime", "ai_res", "rule_res", "fusion"]):
        parts = []
        if regime_val:
            parts.append(f"Regime={regime_val}")
        if ai_res:
            parts.append(f"AI={ai_res.get('decision','?')}({ai_res.get('confidence',0):.2f})")
        if rule_res:
            parts.append(f"Rule={rule_res.get('decision','?')}({rule_res.get('confidence',0):.2f})")
        if fusion:
            parts.append(f"Fusion={fusion.get('decision','?')}({fusion.get('score',0):.2f})")
        overlay = " | ".join(parts)
        logger.info(overlay)
        safe_print(overlay, log_level="debug")

    for sym in allowed_syms:
        res = results[sym]
        dec = res.get("decision", "HOLD")
        conf = res.get("confidence", 0.0)
        mode = res.get("mode", "?")

        parts = [f"{sym} → {dec} (conf={conf:.2f}, mode={mode})"]

        regime_val_sym = res.get("regime") or regime_val
        ai_res_sym = res.get("ai") or ai_res
        rule_res_sym = res.get("rule") or rule_res
        fusion_sym = res.get("fusion") or fusion

        if regime_val_sym:
            parts.append(f"Regime={regime_val_sym}")
        if ai_res_sym:
            parts.append(f"AI={ai_res_sym.get('decision','?')}({ai_res_sym.get('confidence',0):.2f})")
        if rule_res_sym:
            parts.append(f"Rule={rule_res_sym.get('decision','?')}({rule_res_sym.get('confidence',0):.2f})")
        if fusion_sym:
            parts.append(f"Fusion={fusion_sym.get('decision','?')}({fusion_sym.get('score',0):.2f})")

        overlay = " | ".join(parts)
        logger.info(overlay)
        safe_print(overlay, log_level="debug")


# ------------------------------------------------------------------
# Compat layer for unit tests
# ------------------------------------------------------------------
_BaseGlobalExitManager = GlobalExitManager

class GlobalEntryManager(GlobalEntryManager):
    _entries: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def update(cls, symbol: str, allowed: bool, reason: str):
        cls._entries[symbol] = {"allowed": allowed, "reason": reason}

    @classmethod
    def get(cls, symbol: str):
        return cls._entries.get(symbol)

    @classmethod
    def reset(cls):
        cls._entries.clear()


class GlobalExitManager(_BaseGlobalExitManager):
    _reason: str = None

    @classmethod
    def set(cls, reason: str):
        cls._reason = reason

    @classmethod
    def get(cls):
        return cls._reason

    @classmethod
    def reset(cls):
        cls._reason = None


class KillSwitchManager(_BaseKillSwitchManager):
    _reason: str = None
    _triggered: bool = False

    def check(self, equity: float, now: float = None, skip_append: bool = False):
        stop, reason = super().check(equity, now, skip_append=skip_append)
        if stop:
            KillSwitchManager._triggered = True
        return stop, reason

    # instance reset
    def reset(self):
        """Reset instance + class state"""
        self.triggered = False
        self.history = []
        KillSwitchManager._triggered = False
        KillSwitchManager._reason = None

    # class reset
    @classmethod
    def reset_class(cls):
        """Reset only class state"""
        cls._triggered = False
        cls._reason = None

    @classmethod
    def trigger(cls, reason: str):
        cls._triggered = True
        cls._reason = reason

    @classmethod
    def is_triggered(cls) -> bool:
        return cls._triggered
