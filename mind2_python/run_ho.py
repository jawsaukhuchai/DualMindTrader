import argparse
import json
import logging
import sys
import time
import os   # ✅ เพิ่มเพื่อตรวจ env PYTEST_RUNNING
from pathlib import Path

import yaml
import MetaTrader5 as mt5

from mind2_python.decision_engine import DecisionEngine
from mind2_python.schema import parse_feed
from mind2_python.executor import Executor
from mind2_python.trailing_manager import TrailingManager
from mind2_python.global_manager import GlobalExitManager
from mind2_python.risk_guard import RiskGuard
from mind2_python.hybrid_exit import HybridExit
from mind2_python.position_manager import PositionManager   # ✅ ใช้ health state
from mind2_python.pretty_logger import (
    pretty_log_tradesignal,
    pretty_log_dashboard,
)

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Single cycle
# ----------------------------------------------------------------------
def single_cycle(engine: DecisionEngine, feed_path: str, executor: Executor, hybrid_exit: HybridExit, cfg: dict):
    with open(feed_path, "r", encoding="utf-8") as f:
        feed = json.load(f)

    entries = parse_feed(feed)

    # ✅ inject ATR values จาก feed เข้า engine.global_atr
    for e in entries:
        if hasattr(e, "atr") and e.atr:
            engine.global_atr[e.symbol] = e.atr

    results = engine.run(entries)

    atr_map = engine.get_global_atr()

    for res in results:
        if res.get("decision") in ("BUY", "SELL"):
            exits = hybrid_exit.calc(
                res,
                entry=res.get("entry"),
                symbol=res["symbol"],
                atr=atr_map.get(res["symbol"]),
                atr_multi={},
                global_exit_cfg=cfg.get("exit", {}),
            )
            res["exit_levels"] = exits
            res["sl"] = exits.get("sl")
            res["tp"] = [tp["price"] for tp in exits.get("tp", [])]
            res["entry_time"] = time.time()

            # ✅ multi-entry orders
            if "entries" in exits:
                total_entries = len(exits["entries"])
                for idx, e in exits["entries"].items():
                    sub_decision = {
                        "symbol": res["symbol"],
                        "decision": res["decision"],
                        "lot": e["lot"],
                        "sl": e["sl"],
                        "tp": [tp for tp in e.get("tp", [])],
                        "exit_levels": e,
                        "entry": res["entry"],
                    }
                    executor.execute(sub_decision)

                    # ✅ log per-entry (with regime + num_entries)
                    pretty_log_tradesignal(
                        symbol=res["symbol"],
                        decision=res["decision"],
                        lot=e["lot"],
                        entry=res["entry"],
                        exit_levels=e,
                        winprob_raw=res["signal"]["winprob"],
                        score_raw=res["score"],
                        conf_raw=res["confidence"],
                        timeframe="H1",
                        reason="Multi-entry order",
                        pip_size=cfg["symbols"][res["symbol"]].get("pip_size", 0.0001),
                        entry_index=idx,
                        regime=res.get("regime", "normal"),
                        fusion=res.get("votes", {}).get("fusion"),
                        rule_res=res.get("votes", {}).get("rule"),
                        ai_res=res.get("votes", {}).get("ai"),
                    )
            else:
                executor.execute(res)

    return results


# ----------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--balance", type=float, required=True)
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--feed", type=str, required=True)
    parser.add_argument("--debug-trailing", action="store_true")
    args = parser.parse_args()

    balance = args.balance
    interval = args.interval
    config_path = args.config
    feed_path = args.feed

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    engine = DecisionEngine(config_path=config_path, balance=balance)
    executor = Executor()
    trailing_mgr = TrailingManager(cfg)
    risk_guard = RiskGuard(cfg)
    global_exit_mgr = GlobalExitManager(cfg)
    hybrid_exit = HybridExit(cfg)

    if args.debug_trailing:
        logging.getLogger("TrailingManager").setLevel(logging.DEBUG)
        logging.getLogger("HybridExit").setLevel(logging.DEBUG)
        logger.info("🔍 TrailingManager + HybridExit debug logging ENABLED")

    logger.info(f"Starting loop mode... Press Ctrl+C to stop. (interval={interval}s)")

    try:
        while True:
            try:
                # ✅ account info (update health state)
                acc_info = executor.get_account_info() or {"balance": balance, "equity": balance}

                should_exit, reason, _ = global_exit_mgr.check_exit(
                    acc_info,
                    daily_loss=risk_guard.state.get("daily_loss", 0.0),
                )
                if should_exit:
                    logger.warning(f"[GlobalExit] 🌍 {reason} → stopping trading loop")
                    break

                results = single_cycle(engine, feed_path=feed_path, executor=executor, hybrid_exit=hybrid_exit, cfg=cfg)

                atr_map = engine.get_global_atr()
                trailing_mgr.update_global_atr(atr_map)
                trailing_mgr.loop_trailing()

                # ✅ pretty dashboard multi-line compact
                if results:
                    pretty_log_dashboard(
                        balance=acc_info.get("balance", 0.0),
                        equity=acc_info.get("equity", 0.0),
                        pnl=sum(r.get("pnl", 0.0) for r in results),
                        margin_level=acc_info.get("margin_level", 0.0),
                        lots=sum(r.get("lot", 0.0) for r in results),
                        results={r["symbol"]: r for r in results},
                        symbols_cfg=cfg.get("symbols", {}),
                        compact=True,   # ✅ multi-line
                    )

            except Exception as e:
                logger.exception(f"Error in cycle: {e}")

            time.sleep(interval)

            # ✅ Break loop ระหว่าง pytest
            if os.getenv("PYTEST_RUNNING"):
                break

    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        executor.shutdown()


if __name__ == "__main__":
    main()
