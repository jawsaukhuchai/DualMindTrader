import MetaTrader5 as mt5
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple
from mind2_python.safe_print import safe_print

logger = logging.getLogger("PositionManager")
logger.setLevel(logging.INFO)
logger.propagate = True


class PositionManager:
    # ✅ state สำหรับ health monitor
    health_state: Dict[str, Any] = {
        "balance": 0.0,
        "equity": 0.0,
        "margin_level": 0.0,
        "timestamp": None,
    }

    @classmethod
    def update_health(cls, account: Dict[str, Any]):
        """
        Sync account health เข้ามาเก็บใน PositionManager.health_state
        """
        cls.health_state.update(
            {
                "balance": account.get("balance", 0.0),
                "equity": account.get("equity", 0.0),
                "margin_level": account.get("margin_level", 0.0),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        msg = (f"[PositionManager] ♻️ Health updated → "
               f"Balance={cls.health_state['balance']:.2f}, "
               f"Equity={cls.health_state['equity']:.2f}, "
               f"MarginLevel={cls.health_state['margin_level']:.1f}%, "
               f"Timestamp={cls.health_state['timestamp']}")
        logger.debug(msg)
        safe_print(msg, log_level="debug")

    @classmethod
    def get_health(cls) -> Dict[str, Any]:
        """Return last cached account health dict (safe copy)"""
        return dict(cls.health_state)

    # ==========================
    # Update SL/TP
    # ==========================
    def update_position(self, symbol: str, ticket: int,
                        sl: float = None, tp: list = None, exit_levels: dict = None):
        """
        Update SL/TP/exit_levels for an open position.
        - Simulation: update state dict
        - Production: send modify request to MT5
        """
        # ✅ Simulation mode
        if hasattr(self, "state") and "positions" in getattr(self, "state", {}):
            if symbol not in self.state["positions"]:
                return
            for p in self.state["positions"][symbol]:
                if p.get("ticket") == ticket:
                    if sl is not None:
                        p["sl"] = sl
                    if tp is not None:
                        p["tp"] = tp
                    if exit_levels is not None:
                        p["exit_levels"] = exit_levels
                    break
            return

        # ✅ Production mode (MT5)
        try:
            info = mt5.symbol_info(symbol)
            if not info:
                msg = f"[PositionManager] ⚠️ No symbol_info for {symbol}"
                logger.warning(msg)
                safe_print(msg, log_level="warning")
                return

            stops_level = info.stops_level * info.point if info.stops_level else 0.0

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "sl": sl if sl is not None else 0.0,
                "tp": tp[0]["price"] if (tp and isinstance(tp, list)) else (tp or 0.0),
            }

            # 🚨 Validate stops level
            tick = mt5.symbol_info_tick(symbol)
            if tick and stops_level > 0:
                if request["sl"] > 0.0 and abs(request["sl"] - tick.bid) < stops_level:
                    msg = f"[PositionManager] ⚠️ SL={request['sl']} too close (< stops_level {stops_level})"
                    logger.warning(msg)
                    safe_print(msg, log_level="warning")
                if request["tp"] > 0.0 and abs(request["tp"] - tick.ask) < stops_level:
                    msg = f"[PositionManager] ⚠️ TP={request['tp']} too close (< stops_level {stops_level})"
                    logger.warning(msg)
                    safe_print(msg, log_level="warning")

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                msg = (f"[PositionManager] ✅ Updated SL/TP for {symbol} ticket={ticket} "
                       f"→ SL={sl} TP={tp}")
                logger.info(msg)
                safe_print(msg, log_level="info")
            else:
                code = result.retcode if result else "NO_RESULT"
                msg = f"[PositionManager] ⚠️ Update SL/TP failed {symbol} ticket={ticket}, code={code}"
                logger.warning(msg)
                safe_print(msg, log_level="warning")
        except Exception as e:
            msg = f"[PositionManager] ❌ update_position failed: {e}"
            logger.error(msg)
            safe_print(msg, log_level="error")

    # ==========================
    # Production
    # ==========================
    @staticmethod
    def get_positions(symbol: str = None):
        try:
            if symbol:
                return mt5.positions_get(symbol=symbol) or []
            return mt5.positions_get() or []
        except Exception as e:
            msg = f"[PositionManager] ❌ positions_get failed: {e}"
            logger.error(msg)
            safe_print(msg, log_level="error")
            return []

    @staticmethod
    def has_open_position(symbol: str) -> bool:
        return PositionManager.count_open_positions(symbol) > 0

    @staticmethod
    def count_open_positions(symbol: str) -> int:
        try:
            positions = mt5.positions_get(symbol=symbol)
            return len(positions) if positions else 0
        except Exception as e:
            msg = f"[PositionManager] ❌ count_open_positions failed: {e}"
            logger.error(msg)
            safe_print(msg, log_level="error")
            return 0

    # ==========================
    # Global SL/TP helper
    # ==========================
    @staticmethod
    def compute_sl_tp(entry: float, side: str, atr: float,
                      sl_mult: float = 1.5, tp_mult: float = 3.0) -> Tuple[float, float]:
        if side == "BUY":
            sl = entry - atr * sl_mult
            tp = entry + atr * tp_mult
        else:  # SELL
            sl = entry + atr * sl_mult
            tp = entry - atr * tp_mult
        return sl, tp

    # ==========================
    # Comment parse helper
    # ==========================
    @staticmethod
    def _parse_comment(comment: str) -> (float, float, int):
        """
        Extract conf, winprob, entry_index จาก comment string
        format: "series-<index>|<conf>|<winprob>"
        หรือ fallback: "<conf>|<winprob>"
        """
        conf, winprob, entry_index = 0.0, 0.0, 1
        try:
            if comment:
                if "series-" in comment:
                    parts = comment.split("|")
                    entry_index = int(parts[0].replace("series-", "").strip())
                    if len(parts) > 1:
                        conf = float(parts[1])
                    if len(parts) > 2:
                        winprob = float(parts[2])
                elif "|" in comment:
                    c, w = comment.split("|")[:2]
                    conf, winprob = float(c), float(w)
        except Exception:
            pass
        return conf, winprob, entry_index

    @staticmethod
    def summary() -> Dict[str, Any]:
        positions = PositionManager.get_positions()
        out = {"total": 0, "symbols": {}}
        if not positions:
            return out
        out["total"] = len(positions)
        for p in positions:
            conf, winprob, entry_index = PositionManager._parse_comment(getattr(p, "comment", ""))
            out["symbols"].setdefault(p.symbol, []).append({
                "ticket": p.ticket,
                "lot": p.volume,
                "side": "BUY" if p.type == 0 else "SELL",
                "entry": p.price_open,
                "profit": p.profit,
                "conf": conf,
                "winprob": winprob,
                "entry_index": entry_index,
                "sl": getattr(p, "sl", None),
                "tp": getattr(p, "tp", None),
            })
        return out

    @staticmethod
    def get_open_positions_summary() -> Dict[str, List[float]]:
        summary: Dict[str, List[float]] = {}
        try:
            positions = PositionManager.get_positions()
            if not positions:
                return summary
            for p in positions:
                summary.setdefault(p.symbol, []).append(p.volume)
        except Exception as e:
            msg = f"[PositionManager] ❌ get_open_positions_summary failed: {e}"
            logger.error(msg)
            safe_print(msg, log_level="error")
        return summary

    # ==========================
    # Simulation / Test
    # ==========================
    def open_position(self, symbol: str, lot: float, side: str,
                      entry: float, conf: float = 0.0, winprob: float = 0.0,
                      atr: float = None, sl_mult: float = 1.5, tp_mult: float = 3.0,
                      extra: Dict[str, Any] = None):
        if not hasattr(self, "state"):
            self.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}

        self.state["orders_count"][symbol] = self.state["orders_count"].get(symbol, 0) + 1
        self.state["last_order_time"][symbol] = datetime.utcnow()
        if symbol not in self.state["positions"]:
            self.state["positions"][symbol] = []

        sl, tp = (None, None)
        if atr is not None:
            sl, tp = self.compute_sl_tp(entry, side, atr, sl_mult, tp_mult)

        pos = {
            "ticket": int(datetime.utcnow().timestamp() * 1000),
            "symbol": symbol,
            "lot": lot,
            "side": side,
            "entry": entry,
            "open_time": datetime.utcnow().isoformat(),
            "profit": 0.0,
            "conf": conf,
            "winprob": winprob,
            "sl": sl,
            "tp": tp,
        }
        if extra:
            pos.update(extra)
        self.state["positions"][symbol].append(pos)
        return pos

    def close_position(self, symbol: str, ticket: int = None):
        if not hasattr(self, "state") or symbol not in self.state["positions"]:
            return
        if ticket:
            self.state["positions"][symbol] = [p for p in self.state["positions"][symbol] if p["ticket"] != ticket]
        else:
            if self.state["positions"][symbol]:
                self.state["positions"][symbol].pop(0)
        self.state["orders_count"][symbol] = max(0, self.state["orders_count"].get(symbol, 0) - 1)

    @classmethod
    def get_open_positions(cls, symbol: str) -> List[Dict[str, Any]]:
        try:
            mt5_positions = cls.get_positions(symbol)
            # ✅ robust check: ต้องเป็น list และไม่ว่าง
            if isinstance(mt5_positions, list) and len(mt5_positions) > 0:
                results = []
                for p in mt5_positions:
                    conf, winprob, entry_index = cls._parse_comment(getattr(p, "comment", ""))
                    results.append({
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "lot": p.volume,
                        "side": "BUY" if p.type == 0 else "SELL",
                        "entry": p.price_open,
                        "profit": p.profit,
                        "conf": conf,
                        "winprob": winprob,
                        "entry_index": entry_index,
                        "sl": getattr(p, "sl", None),
                        "tp": getattr(p, "tp", None),
                    })
                return results
        except Exception as e:
            msg = f"[PositionManager] ❌ get_open_positions failed: {e}"
            logger.error(msg)
            safe_print(msg, log_level="error")

        # ✅ safe fallback เสมอ
        # ลองใช้ singleton _inst ก่อน
        inst = getattr(cls, "_inst", None)
        if inst and hasattr(inst, "state"):
            return inst.state.get("positions", {}).get(symbol, [])

        # ถ้าไม่มี _inst → ใช้ state จาก cls ถ้ามี
        if hasattr(cls, "state"):
            return cls.state.get("positions", {}).get(symbol, [])

        return []

    @classmethod
    def _instance(cls):
        if not hasattr(cls, "_inst"):
            cls._inst = PositionManager()
            cls._inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
        elif not hasattr(cls._inst, "state"):
            cls._inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
        return cls._inst
