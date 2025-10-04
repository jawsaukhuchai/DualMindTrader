import logging
from typing import Dict, Any, List

from mind2_python.schema import TradeEntry
from mind2_python.scalp import ScalpStrategy
from mind2_python.day import DayStrategy
from mind2_python.swing import SwingStrategy
from mind2_python.hybrid_exit import HybridExit
from mind2_python.risk_guard import RiskGuard
from mind2_python.portfolio_manager import PortfolioManager, CorrelationRisk
from mind2_python.config_loader import load_config
from mind2_python.pretty_logger import (
    pretty_log_tradesignal,
    pretty_log_positions_summary,
    pretty_log_global_entry,
    pretty_log_global_exit,
    pretty_log_dashboard,
    pretty_log_execution,
)
from mind2_python.position_manager import PositionManager
from mind2_python.global_manager import GlobalEntryManager, GlobalExitManager, KillSwitchManager
from mind2_python.lotsizer import AdaptiveLotSizer
from mind2_python.integrate_decisions import integrate
from mind2_python.safe_print import safe_print

logger = logging.getLogger("DecisionEngine")


# ------------------------------------------------------------------
def score_to_winprob(score: float) -> float:
    score = max(-1.0, min(1.0, score))
    return round(abs(score) * 100.0, 1)


def join_reasons(reasons) -> str:
    if isinstance(reasons, (list, tuple)):
        return "|".join([str(r) for r in reasons])
    return str(reasons)


# ------------------------------------------------------------------
def select_mode(sym_cfg: Dict[str, Any], entry: TradeEntry) -> str:
    atr_val = getattr(entry, "atr", sym_cfg.get("last_atr", 0))
    adx_val = getattr(entry, "adx", 0)
    atr_thr = sym_cfg.get("atr_threshold", 1.0)
    adx_thr = sym_cfg.get("adx_threshold", 20.0)

    if atr_val >= atr_thr and adx_val >= adx_thr:
        return "scaler"
    else:
        return "strict"


# ------------------------------------------------------------------
# Regime Detector
# ------------------------------------------------------------------
class RegimeDetector:
    def __init__(self, cfg: Dict[str, Any]):
        self.atr_thr = cfg.get("atr_threshold", 1.0)
        self.adx_thr = cfg.get("adx_threshold", 20.0)

    def detect(self, entry_or_atr, adx: float = None) -> str:
        if hasattr(entry_or_atr, "atr"):
            atr_val = getattr(entry_or_atr, "atr", 0.0)
            adx_val = getattr(entry_or_atr, "adx", 0.0)
        else:
            atr_val = float(entry_or_atr)
            adx_val = float(adx) if adx is not None else 0.0

        if atr_val == 0 and adx_val == 0:
            return "normal"

        if atr_val >= self.atr_thr and adx_val >= self.adx_thr:
            return "trend"
        elif atr_val < self.atr_thr and adx_val < self.adx_thr:
            return "range"
        elif atr_val >= self.atr_thr and adx_val < self.adx_thr:
            return "high_vol"
        elif atr_val < self.atr_thr and adx_val >= self.adx_thr:
            return "low_vol"
        else:
            return "normal"


# ------------------------------------------------------------------
# AI Manager (stub)
# ------------------------------------------------------------------
class AIManager:
    def __init__(self):
        pass

    def evaluate(self, entry: TradeEntry) -> Dict[str, Any]:
        return {"decision": "HOLD", "confidence": 0.5}


# ------------------------------------------------------------------
# Fusion Decision (AI + Rule blending)
# ------------------------------------------------------------------
FUSION_WEIGHTS = {
    "trend": {"ai": 0.7, "rule": 0.3},
    "range": {"ai": 0.3, "rule": 0.7},
    "high_vol": {"ai": 0.5, "rule": 0.5},
    "low_vol": {"ai": 0.4, "rule": 0.6},
    "event": {"ai": 0.6, "rule": 0.4},
    "normal": {"ai": 0.5, "rule": 0.5},
}


def fusion_decision(ai_res: Dict[str, Any], rule_res: Dict[str, Any], regime: str) -> Dict[str, Any]:
    weights = FUSION_WEIGHTS.get(regime, FUSION_WEIGHTS["normal"])
    ai_weight = weights["ai"]
    rule_weight = weights["rule"]

    def score(dec: str) -> int:
        return 1 if dec == "BUY" else -1 if dec == "SELL" else 0

    ai_score = score(ai_res.get("decision")) * ai_res.get("confidence", 0.0) * ai_weight
    rule_score = score(rule_res.get("decision")) * rule_res.get("confidence", 0.0) * rule_weight

    total_score = ai_score + rule_score

    if total_score > 0:
        final_decision = "BUY"
    elif total_score < 0:
        final_decision = "SELL"
    else:
        final_decision = ai_res.get("decision") or "HOLD"

    return {
        "decision": final_decision,
        "score": total_score,
        "weights": weights,
        "ai": ai_res,
        "rule": rule_res,
        "regime": regime,
    }


# ------------------------------------------------------------------
class DecisionEngine:
    def __init__(self, config_path: str, balance: float = 10000, overrides: dict = None):
        self.config: Dict[str, Any] = load_config(config_path, overrides=overrides)
        self.symbols_cfg: Dict[str, Any] = self.config.get("symbols", {})

        self.scalp = ScalpStrategy(self.symbols_cfg)
        self.day = DayStrategy(self.symbols_cfg)
        self.swing = SwingStrategy(self.symbols_cfg)

        self.risk = RiskGuard(self.symbols_cfg)
        self.portfolio = PortfolioManager(self.config)

        self.lotsizer = AdaptiveLotSizer(balance=balance)
        self.exit = HybridExit(self.symbols_cfg)

        self.global_entry = GlobalEntryManager(self.config)
        self.global_exit = GlobalExitManager(self.config)
        self.killswitch = KillSwitchManager(self.config)
        self.corr_risk = CorrelationRisk(self.config.get("global", {}).get("correlation_risk", {}))

        self.global_atr: Dict[str, float] = {}
        self.regime_detector = RegimeDetector(self.config.get("global", {}))
        self.ai_manager = AIManager()

    # ------------------------------------------------------------------
    def apply_override(self, overrides: dict):
        from mind2_python.config_loader import _deep_update
        self.config = _deep_update(self.config, overrides)
        self.symbols_cfg = self.config.get("symbols", {})

        # update submodules
        self.scalp.symbols_cfg = self.symbols_cfg
        self.day.symbols_cfg = self.symbols_cfg
        self.swing.symbols_cfg = self.symbols_cfg
        self.risk.symbols_cfg = self.symbols_cfg
        self.exit.cfg = self.symbols_cfg
        self.portfolio.config = self.config
        self.global_entry.config = self.config
        self.global_exit.config = self.config
        self.killswitch.config = self.config

        msg = f"[DecisionEngine] ⚙️ Overrides applied → {overrides}"
        logger.info(msg)
        safe_print(msg, log_level="debug")

    # ------------------------------------------------------------------
    def process(self, entry: TradeEntry) -> Dict[str, Any]:
        symbol = entry.symbol
        sym_cfg = self.symbols_cfg.get(symbol, {})
        global_cfg = self.config.get("global", {})
        pip_size = sym_cfg.get("pip_size", 0.0001)

        entry_price = (entry.bid + entry.ask) / 2.0

        acc_info = {
            "balance": getattr(entry, "balance", 10000),
            "equity": getattr(entry, "equity", 10000),
            "margin": getattr(entry, "margin", 0.0),
            "margin_level": getattr(entry, "margin_level", 9999.0),
        }

        # 🌍 Global Exit
        stop, reason, _ = self.global_exit.check_exit(acc_info)
        if stop:
            pretty_log_global_exit(reason, triggered=True)
            return {"symbol": symbol, "decision": "CLOSE_ALL", "reason": reason,
                    "lot": 0.0, "exit_levels": {}, "sl": None, "tp": []}
        else:
            pretty_log_global_exit(reason, triggered=False)

        # 🎯 Rule-based strategies
        scalp_res = self.scalp.evaluate(entry)
        day_res = self.day.evaluate(entry)
        swing_res = self.swing.evaluate(entry)
        mode = select_mode(sym_cfg, entry)

        # ⚡ Regime + integration
        regime = self.regime_detector.detect(entry)
        rule_res = integrate(scalp_res, day_res, swing_res, sym_cfg, global_cfg, regime=regime)

        # 🤖 AI Manager
        ai_res = self.ai_manager.evaluate(entry)

        # Fusion
        fused = fusion_decision(ai_res, rule_res, regime)

        final: Dict[str, Any] = {
            "symbol": symbol,
            "decision": fused["decision"],
            "votes": {"scalp": scalp_res, "day": day_res, "swing": swing_res, "fusion": fused},
            "reason": "OK",
            "confidence": fused["ai"].get("confidence", 0.0),
            "score": fused.get("score", 0.0),
            "entry": entry_price,
            "sl": None,
            "tp": [],
            "mode": mode,
            "regime": regime,
            "num_entries": rule_res.get("num_entries", 1),
        }
        final["signal"] = {
            "conf": final["confidence"],
            "winprob": score_to_winprob(final["score"]) / 100.0,
        }

        msg = (f"[DecisionEngine] {symbol} 🎯 "
               f"{final['decision']} (mode={final['mode']}, regime={regime}, score={final['score']:.2f}, "
               f"conf={final['confidence']:.2f}, num_entries={final['num_entries']})")
        logger.info(msg)
        safe_print(msg, log_level="debug")

        # 🌍 KillSwitch
        stop, reason = self.killswitch.check(acc_info["equity"])
        if stop:
            final.update({"decision": "HOLD", "reason": reason, "lot": 0.0})
            return final

        # 🌍 Global Entry
        open_positions = PositionManager.get_open_positions_summary()
        ok, reasons = self.global_entry.check(acc_info, open_positions)
        if not ok:
            pretty_log_global_entry(symbol, "|".join(reasons), allowed=False)
            final.update({"decision": "HOLD", "reason": "|".join(reasons),
                          "lot": 0.0, "exit_levels": {}, "sl": None, "tp": []})
            return final
        else:
            pretty_log_global_entry(symbol, "|".join(reasons), allowed=True)

        # 🌍 Correlation Risk
        self.corr_risk.update(symbol, entry_price)
        ok, reason = self.corr_risk.check()
        if not ok:
            final.update({"decision": "HOLD", "reason": reason, "lot": 0.0})
            return final

        # RiskGuard
        ok, reasons = self.risk.allow(entry, final, balance=acc_info["balance"])
        if not ok:
            pretty_log_execution(symbol, final["decision"], allowed=False,
                                 blocker="RiskGuard", reasons=join_reasons(reasons))
            final.update({"decision": "HOLD", "reason": join_reasons(reasons),
                          "lot": 0.0, "exit_levels": {}, "sl": None, "tp": []})
            return final

        # Lot sizing (adaptive)
        lot = self.lotsizer.compute(entry, sym_cfg, regime=regime)
        final["lot"] = lot

        # PortfolioManager
        final["open_positions"] = open_positions
        allowed, reasons = self.portfolio.allow(entry, final, balance=acc_info["balance"])
        if not allowed:
            pretty_log_execution(symbol, final["decision"], allowed=False,
                                 blocker="PortfolioManager", reasons=join_reasons(reasons))
            final.update({"decision": "HOLD", "reason": join_reasons(reasons),
                          "lot": 0.0, "exit_levels": {}, "sl": None, "tp": []})
            return final
        else:
            final["reason"] = join_reasons(reasons)
            pretty_log_execution(symbol, final["decision"], allowed=True)

        # Save exit levels
        atr_val = sym_cfg.get("last_atr", None)
        exit_cfg_global = global_cfg.get("exit", {})
        exits = self.exit.calc(final, entry=entry_price, symbol=symbol,
                               atr=atr_val, atr_multi={}, global_exit_cfg=exit_cfg_global)

        final["exit_levels"] = exits
        final["sl"] = exits.get("sl")
        final["tp"] = [tp["price"] for tp in exits.get("tp", [])]

        # 🔧 Add logging branches for SL/TP
        if final["sl"]:
            msg = (f"[DecisionEngine] {symbol} 🛑 SL={final['sl']:.5f} "
                   f"| entry={entry_price:.5f} | dist={abs(entry_price-final['sl']):.5f}")
            logger.info(msg)
            safe_print(msg, log_level="debug")
        else:
            logger.debug(f"[DecisionEngine] {symbol} 🛑 No SL set (default HOLD).")

        if final["tp"]:
            tp_str = ", ".join([f"{p:.5f}" for p in final["tp"]])
            msg = f"[DecisionEngine] {symbol} 🎯 TP={tp_str} | entry={entry_price:.5f}"
            logger.info(msg)
            safe_print(msg, log_level="debug")
        else:
            logger.debug(f"[DecisionEngine] {symbol} 🎯 No TP set (default HOLD).")

        return final

    # ------------------------------------------------------------------
    def run(self, entries: List[TradeEntry]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for entry in entries:
            try:
                results.append(self.process(entry))
            except Exception as e:
                logger.exception(f"Error processing {getattr(entry, 'symbol', 'UNKNOWN')}: {e}")
                results.append({"symbol": getattr(entry, "symbol", "UNKNOWN"),
                                "decision": "HOLD", "reason": f"error_eval: {e}",
                                "lot": 0.0, "exit_levels": {}, "sl": None, "tp": []})

        try:
            pretty_log_positions_summary(PositionManager.summary())
        except Exception as e:
            logger.error(f"Error logging positions summary: {e}")

        try:
            if results:
                entry0 = entries[0]
                pretty_log_dashboard(getattr(entry0, "balance", 0.0),
                                     getattr(entry0, "equity", 0.0),
                                     getattr(entry0, "pnl", 0.0),
                                     getattr(entry0, "margin_level", 0.0),
                                     sum(r.get("lot", 0.0) for r in results),
                                     {r["symbol"]: r for r in results},
                                     self.symbols_cfg, compact=False)
        except Exception as e:
            logger.error(f"Error logging dashboard: {e}")
        return results

    def get_global_atr(self) -> Dict[str, float]:
        return self.global_atr


# -------------------------------------------------------
# Compatibility exports
# -------------------------------------------------------
from mind2_python.pretty_logger import colorize_decision, colorize_reason
