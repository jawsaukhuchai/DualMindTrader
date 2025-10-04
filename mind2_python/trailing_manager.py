import logging
import MetaTrader5 as mt5
from mind2_python.safe_print import safe_print

from .hybrid_exit import HybridExit
from .position_manager import PositionManager
from .pretty_logger import pretty_log_tradesignal, pretty_log_trailing

logger = logging.getLogger("TrailingManager")


class TrailingManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self.global_atr = {}

    def update_global_atr(self, atr_map):
        """อัปเดตค่า ATR global map จาก DecisionEngine"""
        self.global_atr = atr_map or {}

    def loop_trailing(self):
        """
        Loop ทุก symbol ที่ config ไว้ แล้วจัดการ trailing stop + emergency close check
        """
        for sym, sym_cfg in self.cfg.get("symbols", {}).items():
            pip_size = sym_cfg.get("pip_size", 0.0001)
            try:
                hx = HybridExit(self.cfg.get("symbols", {}))

                # ✅ recalc exits baseline (update SL/TP สำหรับ open positions)
                atr_val = self.global_atr.get(sym, None)
                exits = hx.recalc_for_open_positions(
                    symbol=sym,
                    atr=atr_val,
                    atr_multi={},
                    global_exit_cfg=self.cfg.get("global", {}).get("exit", {}),
                )

                if exits:
                    msg = f"[Trailing] 🔄 {sym} ATR updated → recalc exits {list(exits.keys())}"
                    logger.debug(msg)
                    safe_print(msg, log_level="debug")

                # ✅ update trailing สำหรับแต่ละ position
                self.update_trailing(sym, hx, exits, pip_size=pip_size)

                # ✅ emergency close check (per position)
                open_positions = PositionManager.get_open_positions(sym)
                for pos in open_positions:
                    if hx.emergency_close_check(sym, pos):
                        msg = (f"[Trailing] 🚨 Emergency close triggered for {sym} "
                               f"ticket={pos.get('ticket')} entry#{pos.get('entry_index',1)}")
                        logger.warning(msg)
                        safe_print(msg, log_level="warning")

            except Exception as e:
                msg = f"[Trailing] ❌ Error managing {sym}: {e}"
                logger.exception(msg)
                safe_print(msg, log_level="error")

    def update_trailing(self, symbol: str, hybrid_exit: HybridExit, exits_map, pip_size: float = 0.0001):
        """
        Adjust trailing stop-loss สำหรับทุก open positions ของ symbol
        """
        open_positions = PositionManager.get_open_positions(symbol)
        if not open_positions:
            msg = f"[Trailing] ⏸️ No positions for {symbol}"
            logger.debug(msg)
            safe_print(msg, log_level="debug")
            return

        for pos in open_positions:
            side = pos.get("side")
            entry = pos.get("entry")
            ticket = pos.get("ticket")
            sl = pos.get("sl")
            lot = pos.get("lot", 0.0)
            entry_index = pos.get("entry_index", 1)
            regime = pos.get("regime", "normal")
            num_entries = pos.get("num_entries", 1)

            e = exits_map.get(ticket, {})
            trailing_cfg = e.get("trailing", {})

            if not trailing_cfg:
                continue

            # ✅ ใช้ live tick price
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                msg = f"[Trailing] ⚠️ No live tick for {symbol}, skip trailing"
                logger.warning(msg)
                safe_print(msg, log_level="warning")
                continue
            price = tick.bid if side == "BUY" else tick.ask

            new_sl = hybrid_exit.adjust_trailing(
                current_price=price,
                side=side,
                entry=entry,
                sl=sl,
                trailing_cfg=trailing_cfg,
                pip_size=pip_size,
            )

            if new_sl and (sl is None or abs(new_sl - sl) > 1e-9):
                # ✅ update position memory & MT5
                PositionManager().update_position(
                    symbol=symbol,
                    ticket=ticket,
                    sl=new_sl,
                    tp=e.get("tp"),
                    exit_levels=e,
                )

                # ✅ log SL moved per entry (include regime + num_entries)
                pretty_log_trailing(symbol, ticket, sl, new_sl, entry_index=entry_index)
                msg = (f"[Trailing] {symbol} entry#{entry_index}/{num_entries} "
                       f"regime={regime} SL moved {sl} → {new_sl}")
                logger.info(msg)
                safe_print(msg, log_level="info")

                # ✅ pretty log trade signal (show SL/TP/trailing)
                pretty_log_tradesignal(
                    symbol=symbol,
                    decision=side,
                    lot=lot,
                    entry=entry,
                    exit_levels=e,
                    winprob_raw=pos.get("winprob"),
                    score_raw=0.0,
                    conf_raw=pos.get("conf"),
                    timeframe="H1",
                    reason=f"Trailing update (entry#{entry_index}/{num_entries}, regime={regime})",
                    pip_size=pip_size,
                    entry_index=entry_index,
                    regime=regime,
                )
