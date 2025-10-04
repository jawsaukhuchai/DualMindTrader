import logging
import MetaTrader5 as mt5
from typing import Dict, Any, Optional
from mind2_python.safe_print import safe_print

from .pretty_logger import pretty_log_auto_update, pretty_log_close_position

logger = logging.getLogger("HybridExit")


class HybridExit:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg or {}

    # ======================================================
    # Calc SL/TP for new entry
    # ======================================================
    def calc(
        self,
        decision: Dict[str, Any],
        entry: float,
        symbol: str,
        atr: Optional[float],
        atr_multi: Dict[str, float],
        global_exit_cfg: Dict[str, Any],
    ) -> Dict[str, Any]:
        sym_cfg = self.cfg.get(symbol, {})
        exit_cfg = sym_cfg.get("exit", {})
        pip_size = sym_cfg.get("pip_size", 0.0001)

        atr_val = atr or sym_cfg.get("last_atr", 0.0)
        if atr_val <= 0:
            msg = f"[HybridExit] {symbol} invalid ATR, fallback=1.0"
            logger.warning(msg)
            safe_print(msg, log_level="warning")
            atr_val = 1.0

        side = decision.get("decision", "HOLD")
        if side not in ("BUY", "SELL"):
            return {"sl": None, "tp": []}

        # --- Base config ---
        sl_atr = exit_cfg.get("sl_atr", 1.5)
        tp_steps = exit_cfg.get("tp_steps", [1.0, 2.0, 3.0])
        tp_perc = exit_cfg.get("tp_perc", [40, 30, 30])
        tp_perc = tp_perc[: len(tp_steps)]

        # --- Series scaling logic ---
        num_entries = decision.get("num_entries", 1)
        series_mode = sym_cfg.get("portfolio", {}).get("series_mode", "strict")

        if series_mode == "scaling" and num_entries > 1:
            factors = [max(0.3, 1.0 - (i - 1) * 0.33) for i in range(1, num_entries + 1)]
            sl_mults = [sl_atr * (1.0 + 0.5 * (i - 1)) for i in range(1, num_entries + 1)]
        else:
            factors = [1.0] * num_entries
            sl_mults = [sl_atr] * num_entries

        base_lot = decision.get("lot", 0.0)
        regime = decision.get("regime", "normal")

        exits = {"entries": {}}
        for i, (f, sl_m) in enumerate(zip(factors, sl_mults), start=1):
            lot = round(base_lot * f, 2)

            if side == "BUY":
                sl_price = entry - atr_val * sl_m
                tp_prices = [entry + atr_val * s for s in tp_steps]
            else:
                sl_price = entry + atr_val * sl_m
                tp_prices = [entry - atr_val * s for s in tp_steps]

            entry_exit = {
                "entry_index": i,
                "lot": lot,
                "sl": round(sl_price, sym_cfg.get("digits", 5)),
                "tp": [round(tp, sym_cfg.get("digits", 5)) for tp in tp_prices],
                "tp_perc": tp_perc,
            }
            exits["entries"][i] = entry_exit

            msg = (f"[HybridExit] {symbol} {side} entry#{i} | lot={lot:.2f} | "
                   f"SL={entry_exit['sl']} | TP={entry_exit['tp']} "
                   f"(regime={regime}, num_entries={num_entries})")
            logger.info(msg)
            safe_print(msg, log_level="debug")

        # baseline
        first = exits["entries"][1]
        exits["sl"] = first["sl"]
        exits["tp"] = [{"price": p, "perc": tp_perc[j]} for j, p in enumerate(first["tp"])]

        return exits

    # ======================================================
    # Recalc exits for open positions
    # ======================================================
    def recalc_for_open_positions(
        self,
        symbol: str,
        atr: Optional[float],
        atr_multi: Dict[str, float],
        global_exit_cfg: Dict[str, Any],
    ) -> Dict[int, Dict[str, Any]]:
        open_positions = mt5.positions_get(symbol=symbol)
        if not open_positions:
            return {}

        sym_cfg = self.cfg.get(symbol, {})
        exit_cfg = sym_cfg.get("exit", {})
        pip_size = sym_cfg.get("pip_size", 0.0001)

        atr_val = atr or sym_cfg.get("last_atr", sym_cfg.get("atr", 0.0))
        if atr_val <= 0:
            msg = f"[HybridExit] {symbol} using fallback ATR=1.0"
            logger.warning(msg)
            safe_print(msg, log_level="warning")
            atr_val = 1.0

        results: Dict[int, Dict[str, Any]] = {}

        for pos in open_positions:
            ticket = pos.ticket
            side = "BUY" if pos.type == 0 else "SELL"
            entry = pos.price_open

            # parse entry_index
            entry_index = 1
            if hasattr(pos, "comment") and pos.comment and "series-" in pos.comment:
                try:
                    entry_index = int(pos.comment.split("series-")[1].split("|")[0])
                except Exception:
                    entry_index = 1

            sl_atr = exit_cfg.get("sl_atr", 1.5)
            tp_steps = exit_cfg.get("tp_steps", [1.0, 2.0, 3.0])
            tp_perc = exit_cfg.get("tp_perc", [40, 30, 30])
            tp_perc = tp_perc[: len(tp_steps)]

            if side == "BUY":
                sl_price = entry - atr_val * sl_atr
                tp_prices = [entry + atr_val * s for s in tp_steps]
            else:
                sl_price = entry + atr_val * sl_atr
                tp_prices = [entry - atr_val * s for s in tp_steps]

            symbol_info = mt5.symbol_info(symbol)
            stops_level = getattr(symbol_info, "stops_level", 0) * pip_size if symbol_info else 0

            if stops_level > 0:
                if side == "BUY":
                    min_sl = pos.price_open - stops_level
                    if sl_price > min_sl:
                        sl_price = min_sl
                else:
                    min_sl = pos.price_open + stops_level
                    if sl_price < min_sl:
                        sl_price = min_sl

            result = {
                "entry_index": entry_index,
                "sl": round(sl_price, sym_cfg.get("digits", 5)),
                "tp": [round(tp, sym_cfg.get("digits", 5)) for tp in tp_prices],
                "tp_perc": tp_perc,
                "trailing": exit_cfg.get("trailing", {}),
            }
            results[ticket] = result

            msg = (f"[HybridExit] ♻️ Recalc exits {symbol} ticket={ticket} entry#{entry_index} → "
                   f"SL={result['sl']} | TP={result['tp']}")
            logger.info(msg)
            safe_print(msg, log_level="debug")

            pretty_log_auto_update(symbol, ticket, result["sl"], result["tp"], entry_index=entry_index)

        return results

    # ======================================================
    # Trailing adjust
    # ======================================================
    def adjust_trailing(
        self,
        current_price: float,
        side: str,
        entry: float,
        sl: Optional[float],
        trailing_cfg: Dict[str, Any],
        pip_size: float,
    ) -> Optional[float]:
        if not trailing_cfg or not current_price:
            return None

        atr_mult = trailing_cfg.get("atr_mult", 1.5)
        breakeven = trailing_cfg.get("breakeven", 0)

        if side == "BUY":
            profit = current_price - entry
            if profit <= 0:
                return sl
            new_sl = max(sl or entry, entry + breakeven * pip_size, current_price - atr_mult * pip_size)
            return round(new_sl, 5)

        elif side == "SELL":
            profit = entry - current_price
            if profit <= 0:
                return sl
            new_sl = min(sl or entry, entry - breakeven * pip_size, current_price + atr_mult * pip_size)
            return round(new_sl, 5)

        return sl

    # ======================================================
    # Emergency close
    # ======================================================
    def emergency_close_check(self, symbol: str, pos, severe_loss_pct: float = -0.15) -> bool:
        if not pos:
            return False
        if pos.sl is not None:
            return False

        entry_index = 1
        if hasattr(pos, "comment") and pos.comment and "series-" in pos.comment:
            try:
                entry_index = int(pos.comment.split("series-")[1].split("|")[0])
            except Exception:
                entry_index = 1

        if pos.profit / (pos.volume * pos.price_open) < severe_loss_pct:
            msg = (f"[HybridExit] 🔒 Emergency close SEVERE {symbol} ticket={pos.ticket} "
                   f"entry#{entry_index} PnL={pos.profit}")
            logger.error(msg)
            safe_print(msg, log_level="error")
            pretty_log_close_position(symbol, pos.ticket, pos.volume, pos.price_open,
                                      profit=pos.profit, reason="SEVERE", entry_index=entry_index)
            return True
        elif pos.profit < 0:
            msg = (f"[HybridExit] 🔒 Closing unprotected order {pos.ticket} {symbol} "
                   f"entry#{entry_index} retrace condition met (PnL={pos.profit})")
            logger.info(msg)
            safe_print(msg, log_level="warning")
            pretty_log_close_position(symbol, pos.ticket, pos.volume, pos.price_open,
                                      profit=pos.profit, reason="RETRACE", entry_index=entry_index)
            return True
        return False
