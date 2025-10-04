import logging
from typing import Dict, Any, Optional

# -----------------------------
# ANSI Colors / Icons
# -----------------------------
COLORS = {
    "BUY": "\033[92m",
    "SELL": "\033[91m",
    "HOLD": "\033[93m",
    "INFO": "\033[96m",
    "RESET": "\033[0m",
}

ICONS = {
    "SL": "🛑",
    "TP": "🎯",
    "TRAIL": "🔄",
    "LOT": "💹",
    "ENTRY": "📊",
    "BUY": "📈",
    "SELL": "📉",
    "HOLD": "⏳",
    "RISK": "🛡️",
    "PORTFOLIO": "💼",
    "INTEGRATION": "🔀",
}

# -----------------------------
# Logger setup
# -----------------------------
class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[37m",
        "INFO": "\033[36m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


def get_logger(
    name: str = "Mind2",
    level: int = logging.INFO,
    filename: str = None,
) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

    if filename:
        file_handler = logging.FileHandler(filename)
        file_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        )
        logger.addHandler(file_handler)

    logger.setLevel(level)
    return logger


# -----------------------------
# Pretty unified logger
# -----------------------------
def pretty_log_decisionengine(
    symbol: str,
    decision: str,
    lot: float,
    entry: float,
    exit_levels: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None,
    votes: Optional[Dict[str, int]] = None,
    details: Optional[Dict[str, Any]] = None,
    reason: str = "OK",
):
    """
    Unified pretty logger for DecisionEngine results
    """
    log = logging.getLogger("PrettyLog")
    icon = ICONS.get(decision, ICONS["HOLD"])

    # Header
    log.info(f"[DecisionEngine] {symbol} {icon} {decision} | Lot={lot:.4f}")

    # Entry
    log.info(f"{ICONS['ENTRY']} Entry @ {entry:.4f}")

    # Integration
    if mode or votes or details:
        log.info(f"{ICONS['INTEGRATION']} Mode={mode}, Votes={votes}, Details={details}")

    # Portfolio allowance
    log.info(f"{ICONS['PORTFOLIO']} Allowed Lot={lot:.4f}")

    # Exit plan (SL/TP/Trailing)
    if exit_levels:
        sl = exit_levels.get("sl")
        if sl:
            log.info(f"{ICONS['SL']} SL={sl:.2f}")

        tps = exit_levels.get("tp", [])
        for i, tp in enumerate(tps, 1):
            price = tp.get("price")
            diff = tp.get("diff")
            pct = tp.get("close_pct")
            if price:
                log.info(f"{ICONS['TP']} TP{i}={price:.2f} (+{diff:.2f}, {pct}%)")

        trailing = exit_levels.get("trailing")
        if trailing:
            log.info(
                f"{ICONS['TRAIL']} Trailing=ATR×{trailing['mult']} → {trailing['value']:.2f}"
            )
    else:
        log.info("SL=— TP=—")

    # Reason
    log.info(f"{ICONS['HOLD']} Reason: {reason}")


# -----------------------------
# Trade Signal style logger
# -----------------------------
def pretty_log_tradesignal(
    symbol: str,
    decision: str,
    lot: float,
    entry: float,
    exit_levels: Optional[Dict[str, Any]] = None,
    winprob: Optional[float] = None,
    timeframe: str = "H1",
    reason: str = "OK",
):
    """
    Trade Signal style logger
    """
    log = logging.getLogger("PrettyLog")
    arrow = ICONS.get(decision, ICONS["HOLD"])

    header = f"[TRADE SIGNAL] {symbol} {arrow} {decision} | Lot={lot:.4f} | TF={timeframe}"
    if winprob is not None:
        header += f" | WinProb≈{winprob:.1f}%"
    log.info(header)

    log.info(f"{ICONS['ENTRY']} Entry @ {entry:.4f}")

    if exit_levels:
        sl = exit_levels.get("sl")
        if sl:
            log.info(f"{ICONS['SL']} SL={sl:.2f}")

        tps = exit_levels.get("tps", [])
        for i, tp in enumerate(tps, 1):
            price = tp.get("price")
            pips = tp.get("pips")
            weight = tp.get("weight")
            if price:
                sign = "+" if pips >= 0 else ""
                log.info(f"{ICONS['TP']} TP{i}={price:.2f} ({sign}{pips:.2f}, {weight}%)")

        atr_mult = exit_levels.get("atr_mult")
        atr = exit_levels.get("atr")
        if atr_mult and atr:
            log.info(f"{ICONS['TRAIL']} ATR×{atr_mult} → {atr:.2f}")

    log.info(f"⏳ Reason: {reason}")


# -----------------------------
# Compat aliases
# -----------------------------
pretty_log_decision = pretty_log_decisionengine
pretty_log_integration = pretty_log_decisionengine


def pretty_log_risk(symbol: str, reason: str):
    """RiskGuard log"""
    logging.getLogger("PrettyLog").info(f"[RiskGuard] {symbol} ⛔ Blocked → {reason}")


def pretty_log_portfolio(symbol: str, lot: float, reason: str = "OK"):
    """PortfolioManager log"""
    if reason == "OK":
        logging.getLogger("PrettyLog").info(
            f"[PortfolioManager] 💼 {symbol} ✅ Allowed Lot={lot:.4f}"
        )
    else:
        logging.getLogger("PrettyLog").info(
            f"[PortfolioManager] 💼 {symbol} ⛔ Blocked → {reason}"
        )
