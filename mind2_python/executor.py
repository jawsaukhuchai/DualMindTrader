import logging
import os
import MetaTrader5 as mt5
from dotenv import load_dotenv
from typing import Dict, Optional, Any, List

from mind2_python.pretty_logger import (
    pretty_log_close_position,
    pretty_log_tradesignal,
)
from mind2_python.position_manager import PositionManager
from mind2_python.safe_print import safe_print

logger = logging.getLogger("Executor")
logger.setLevel(logging.INFO)
logger.propagate = True

load_dotenv()

# -----------------------------
# Fallback constants for DummyMT5 (tests)
# -----------------------------
ORDER_TYPE_BUY = getattr(mt5, "ORDER_TYPE_BUY", 0)
ORDER_TYPE_SELL = getattr(mt5, "ORDER_TYPE_SELL", 1)
TRADE_ACTION_DEAL = getattr(mt5, "TRADE_ACTION_DEAL", 2)
ORDER_TIME_GTC = getattr(mt5, "ORDER_TIME_GTC", 0)
ORDER_FILLING_IOC = getattr(mt5, "ORDER_FILLING_IOC", 0)
TRADE_RETCODE_DONE = getattr(mt5, "TRADE_RETCODE_DONE", 10009)


class Executor:
    def __init__(self):
        self.login = os.getenv("MT5_LOGIN")
        self.password = os.getenv("MT5_PASSWORD")
        self.server = os.getenv("MT5_SERVER")
        self.path = os.getenv("MT5_PATH")

        if not all([self.login, self.password, self.server]):
            raise RuntimeError("❌ Missing MT5 credentials in .env")

        self.magic: int = int(os.getenv("MT5_MAGIC", "123456"))
        self.cooldown_sec: int = int(os.getenv("ENTRY_COOLDOWN_SEC", "30"))
        self.max_positions_per_side: int = int(os.getenv("MAX_POSITIONS_PER_SIDE", "3"))

        self.max_slippage = float(os.getenv("MAX_SLIPPAGE_PCT", "0.0005"))
        self.entry_expiry_sec = int(os.getenv("ENTRY_EXPIRY_SEC", "900"))
        self.min_tp_distance_pct = float(os.getenv("MIN_TP_DISTANCE_PCT", "0.001"))

        self._connect()

    # ------------------------------------------------------
    def _connect(self):
        if not mt5.initialize(
            path=self.path,
            login=int(self.login),
            server=self.server,
            password=self.password,
        ):
            msg = "⚠️ Initial connect failed, retrying..."
            logger.warning(msg)
            safe_print(msg, log_level="warning")

            success = mt5.initialize(
                path=self.path,
                login=int(self.login),
                server=self.server,
                password=self.password,
            )
            if not success:
                err = mt5.last_error()
                # pragma: no cover
                raise RuntimeError(f"❌ MT5 initialize failed: {err}")

        msg = f"✅ Connected to MT5: login={self.login}, server={self.server}, path={self.path}"
        logger.info(msg)

        safe_print("Connected to MT5", log_level="info")
        safe_print(msg, log_level="info")

    def shutdown(self):
        mt5.shutdown()
        msg = "Disconnected from MT5"
        logger.info(msg)
        # pragma: no cover
        safe_print(msg, log_level="info")

    # ------------------------------------------------------
    def get_account_info(self) -> Dict[str, Any]:
        info = mt5.account_info()
        if not info:
            msg = f"[Executor] ❌ Failed to get account_info(): {mt5.last_error()}"
            logger.error(msg)
            safe_print(msg, log_level="error")
            return {}
        account = {
            "login": getattr(info, "login", None),
            "balance": getattr(info, "balance", 0.0),
            "equity": getattr(info, "equity", 0.0),
            "margin": getattr(info, "margin", 0.0),
            "margin_free": getattr(info, "margin_free", 0.0),
            "margin_level": getattr(info, "margin_level", 0.0),
            "currency": getattr(info, "currency", ""),
            "leverage": getattr(info, "leverage", 0),
        }
        PositionManager.update_health(account)
        return account

    # ------------------------------------------------------
    def _normalize_lot(self, symbol: str, lot: float) -> float:
        info = mt5.symbol_info(symbol)
        if not info:
            return round(lot, 2)
        min_lot = getattr(info, "volume_min", 0.01)
        max_lot = getattr(info, "volume_max", 100.0)
        step = getattr(info, "volume_step", 0.01) or 0.01
        lot = max(min_lot, min(lot, max_lot))
        lot = round(round(lot / step) * step, 2)
        return lot

    def _normalize_price(self, symbol: str, price: Optional[float]) -> Optional[float]:
        if price is None:
            return None
        info = mt5.symbol_info(symbol)
        if not info:
            return price
        return round(price, getattr(info, "digits", 5))

    def _check_margin(self, symbol: str, lot: float, order_type) -> bool:
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False
        price = tick.ask if order_type == ORDER_TYPE_BUY else tick.bid
        margin = mt5.order_calc_margin(order_type, symbol, lot, price)
        if margin is None:
            return False
        acc_info = mt5.account_info()
        if not acc_info:
            return False
        return getattr(acc_info, "margin_free", 0) > margin

    # ------------------------------------------------------
    def execute(self, decision: dict):
        symbol = decision.get("symbol")
        action = decision.get("decision") or decision.get("action")
        order_type = ORDER_TYPE_BUY if action == "BUY" else ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            msg = f"[Executor] ❌ No tick data for {symbol}"
            logger.error(msg)
            safe_print(msg, log_level="error")
            return None
        price = tick.ask if action == "BUY" else tick.bid

        entries_map = decision.get("exit_levels", {}).get("entries", {})
        if entries_map:
            results = []
            for idx, e in entries_map.items():
                lot = self._normalize_lot(symbol, e.get("lot", 0.01))
                sl = self._normalize_price(symbol, e.get("sl"))
                tp_list = [
                    self._normalize_price(symbol, tp["price"])
                    for tp in e.get("tp", [])
                    if tp.get("price")
                ]

                if not self._check_margin(symbol, lot, order_type):
                    msg = f"[Executor] ❌ Margin not enough for {symbol}, lot={lot}"
                    logger.error(msg)
                    safe_print(msg, log_level="error")
                    # pragma: no cover
                    continue

                request = {
                    "action": TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lot,
                    "type": order_type,
                    "price": price,
                    "magic": self.magic,
                    "deviation": int(self.max_slippage * 1e4),
                    "type_time": ORDER_TIME_GTC,
                    "type_filling": ORDER_FILLING_IOC,
                }
                if sl:
                    request["sl"] = sl
                if tp_list:
                    request["tp"] = tp_list[0]

                result = mt5.order_send(request)
                result = self._process_result(result, request)
                if result:
                    results.append(result)
                    msg = f"[Executor] {symbol} 🎯 entry#{idx} TP levels={','.join(str(tp) for tp in tp_list) or 'None'}"
                    logger.info(msg)
                    safe_print(msg, log_level="info")

            if results:
                return results
            return None

        lot = self._normalize_lot(symbol, decision.get("lot", 0.01))
        sl = self._normalize_price(symbol, decision.get("sl"))
        tp_raw = decision.get("tp")
        tp_list: List[float] = []
        if isinstance(tp_raw, (list, tuple)):
            tp_list = [self._normalize_price(symbol, tp) for tp in tp_raw if tp is not None]
        elif tp_raw is not None:
            tp_list = [self._normalize_price(symbol, tp_raw)]

        if not self._check_margin(symbol, lot, order_type):
            msg = f"[Executor] ❌ Margin not enough for {symbol}, lot={lot}"
            logger.error(msg)
            safe_print(msg, log_level="error")
            return None

        request = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "magic": self.magic,
            "deviation": int(self.max_slippage * 1e4),
            "type_time": ORDER_TIME_GTC,
            "type_filling": ORDER_FILLING_IOC,
        }
        if sl:
            request["sl"] = sl
        if tp_list:
            request["tp"] = tp_list[0]
            msg = f"[Executor] {symbol} TP levels={','.join(str(tp) for tp in tp_list)}"
            logger.info(msg)
            safe_print(msg, log_level="info")

        result = mt5.order_send(request)
        return self._process_result(result, request)

    # ------------------------------------------------------
    def close_position(self, ticket: int, symbol: str, lot: Optional[float] = None):
        pos = None
        for p in mt5.positions_get(symbol=symbol) or []:
            if p.ticket == ticket:
                pos = p
                break
        if not pos:
            msg = f"[Executor] ⚠️ Position ticket={ticket} not found for {symbol}"
            logger.warning(msg)
            safe_print(msg, log_level="warning")
            return None

        lot = lot or pos.volume

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            msg = f"[Executor] ❌ No tick data for {symbol}, cannot close position"
            logger.error(msg)
            safe_print(msg, log_level="error")
            return None

        price = tick.bid if pos.type == 0 else tick.ask
        order_type = ORDER_TYPE_SELL if pos.type == 0 else ORDER_TYPE_BUY

        request = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": int(self.max_slippage * 1e4),
            "magic": self.magic,
            "type_filling": ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        result = self._process_result(result, request)

        if result and getattr(result, "retcode", None) == TRADE_RETCODE_DONE:
            msg = f"[Executor] ✅ CLOSE success: {symbol} ticket={ticket} lot={lot}"
            logger.info(msg)
            safe_print(msg, log_level="info")

            entry_index = 1
            try:
                if hasattr(pos, "comment") and "series-" in pos.comment:
                    entry_index = int(pos.comment.split("|")[0].split("-")[1])
            except Exception:
                pass

            pretty_log_close_position(
                symbol,
                ticket,
                lot,
                price,
                profit=getattr(pos, "profit", 0.0),
                entry_index=entry_index,
            )
        # pragma: no cover
        return result

    # ------------------------------------------------------
    def _process_result(self, result, request):
        if result is None:
            msg = f"[Executor] ❌ order_send failed: {mt5.last_error()}"
            logger.error(msg)
            safe_print(msg, log_level="error")
            return None

        if getattr(result, "retcode", None) != TRADE_RETCODE_DONE:
            msg = (
                f"[Executor] ❌ Order failed: retcode={getattr(result, 'retcode', None)}, "
                f"comment={getattr(result, 'comment', '')}, request={request}"
            )
            logger.error(msg)
            safe_print(msg, log_level="error")
            return None

        msg = (
            f"[Executor] ✅ Order success: {request['symbol']} "
            f"{'BUY' if request['type']==ORDER_TYPE_BUY else 'SELL'} "
            f"lot={request['volume']} @ {request['price']} "
            f"sl={request.get('sl')} tp={request.get('tp')}"
        )
        logger.info(msg)
        safe_print(msg, log_level="info")
        return result
