import logging
from typing import Dict, Any, Optional
from mind2_python.safe_print import safe_print   # ✅ add safe_print

# -----------------------------
# ANSI Colors
# -----------------------------
class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

# -----------------------------
# ANSI Icons
# -----------------------------
ICONS = {
    "SL": "🛑",
    "TP": "🎯",
    "TRAIL": "🔄",
    "LOT": "💹",
    "ENTRY": "📊",
    "BUY": "📈",
    "SELL": "📉",
    "HOLD": "⏳",
    "AI": "🤖",
    "RULE": "📐",
    "FUSION": "⚡",
    "THRESH": "🎚️",
}

# -----------------------------
# Internal unified emitter
# -----------------------------
def _emit(msg: str, level: str = "info") -> None:
    log = logging.getLogger("PrettyLog")
    if level == "debug":
        log.debug(msg)
    elif level == "warning":
        log.warning(msg)
    elif level == "error":
        log.error(msg)
    else:
        log.info(msg)
    safe_print(msg, log_level=level)

# -----------------------------
# Hybrid WinProb Normalization
# -----------------------------
def normalize_winprob(score: float, conf: float) -> float:
    """Hybrid normalize: combine score & conf into [30,95]%"""
    score = max(-1.0, min(1.0, score))
    conf = max(0.0, min(1.0, conf))
    score_norm = (score + 1.0) / 2.0
    base = 0.5 * score_norm + 0.5 * conf
    return 30.0 + base * 65.0

# -----------------------------
# Color helper
# -----------------------------
def colorize_decision(decision: str, text: str) -> str:
    if decision == "BUY":
        return f"{Ansi.GREEN}{text}{Ansi.RESET}"
    elif decision == "SELL":
        return f"{Ansi.RED}{text}{Ansi.RESET}"
    elif decision == "HOLD":
        return f"{Ansi.YELLOW}{text}{Ansi.RESET}"
    return text

def colorize_reason(reason: str) -> str:
    """Map reasons to colors with ⚠ prefix"""
    reason_low = reason.lower()
    if "blocked" in reason_low:
        return f"⚠ {Ansi.RED}{reason}{Ansi.RESET}"
    elif "low_conf" in reason_low or "low_quality" in reason_low:
        return f"⚠ {Ansi.YELLOW}{reason}{Ansi.RESET}"
    elif "risk_ok" in reason_low or "allowed" in reason_low:
        return f"⚠ {Ansi.GREEN}{reason}{Ansi.RESET}"
    elif "invalid atr" in reason_low:
        return f"⚠ {Ansi.CYAN}{reason}{Ansi.RESET}"
    else:
        return f"⚠ {Ansi.GRAY}{reason}{Ansi.RESET}"

# -----------------------------
# Trade Signal style logger
# -----------------------------
def pretty_log_tradesignal(
    symbol: str,
    decision: str,
    lot: float,
    entry: float,
    exit_levels: Optional[Dict[str, Any]] = None,
    winprob_raw: Optional[float] = None,
    score_raw: Optional[float] = None,
    conf_raw: Optional[float] = None,
    timeframe: str = "H1",
    reason: str = "OK",
    pip_size: float = 0.0001,
    entry_index: int = 1,
    regime: Optional[str] = None,
    ai_res: Optional[Dict[str, Any]] = None,
    rule_res: Optional[Dict[str, Any]] = None,
    fusion: Optional[Dict[str, Any]] = None,
) -> None:
    arrow = ICONS.get(decision, ICONS["HOLD"])

    winprob_norm = None
    if score_raw is not None and winprob_raw is not None and conf_raw is not None:
        winprob_norm = normalize_winprob(score_raw, conf_raw)

    header = (
        f"[TRADE SIGNAL] {symbol:<8} entry#{entry_index} {arrow} "
        f"{colorize_decision(decision, decision):<6} "
        f"| Lot={lot:<6.4f} | TF={timeframe:<3} "
    )
    if regime:
        header += f"| Regime={Ansi.CYAN}{regime}{Ansi.RESET} "

    if winprob_raw is not None and winprob_norm is not None:
        header += f"| WinProb raw={winprob_raw:.2f} norm≈{winprob_norm:>5.1f}%"
    elif winprob_raw is not None:
        header += f"| WinProb raw={winprob_raw:.2f}"

    if conf_raw is not None:
        header += f" | Conf raw={conf_raw:.2f} norm≈{conf_raw*100:>5.1f}%"

    _emit(header)

    if ai_res or rule_res or fusion:
        parts = []
        if ai_res:
            parts.append(f"{ICONS['AI']} AI={ai_res.get('decision','?')}({ai_res.get('confidence',0):.2f})")
        if rule_res:
            parts.append(f"{ICONS['RULE']} Rule={rule_res.get('decision','?')}({rule_res.get('confidence',0):.2f})")
        if fusion:
            parts.append(f"{ICONS['FUSION']} Fusion={fusion.get('decision','?')}({fusion.get('score',0):.2f})")
        _emit(" | ".join(parts))

    if rule_res:
        th = rule_res.get("threshold")
        num_entries = rule_res.get("num_entries")
        if th is not None or num_entries is not None:
            num_str = f"📊x{num_entries}" if num_entries is not None else "📊x?"
            th_str = f"{ICONS['THRESH']}{th:.3f}" if th is not None else f"{ICONS['THRESH']}N/A"
            _emit(f"⚖️ Integration → {th_str} | {num_str}")

    if decision == "HOLD":
        _emit(f"{ICONS['HOLD']} {Ansi.YELLOW}No Trade{Ansi.RESET} (Reason={reason})")
        return

    _emit(f"{ICONS['ENTRY']} Entry @ {entry:.4f}")

    if exit_levels:
        sl = exit_levels.get("sl")
        if sl is not None:
            _emit(f"{Ansi.RED}{ICONS['SL']} SL={sl:.2f}{Ansi.RESET}")

        tps = exit_levels.get("tp", []) or exit_levels.get("tps", [])
        for i, tp in enumerate(tps, 1):
            price = tp.get("price") if isinstance(tp, dict) else tp
            perc = tp.get("perc") if isinstance(tp, dict) else None
            raw_pips = tp.get("raw_pips") if isinstance(tp, dict) else None
            if price is not None:
                if raw_pips is not None:
                    _emit(f"{Ansi.GREEN}{ICONS['TP']} TP{i}={price:.2f} ({raw_pips:+.2f} pips, {perc}%) {Ansi.RESET}")
                else:
                    _emit(f"{Ansi.GREEN}{ICONS['TP']} TP{i}={price:.2f}{Ansi.RESET}")

        trailing = exit_levels.get("trailing", {})
        atr_used = exit_levels.get("atr_used")
        atr_mode = exit_levels.get("atr_mode")
        if trailing:
            mult = trailing.get("mult")
            dist = trailing.get("distance")
            if mult:
                if dist and pip_size > 0:
                    dist_pips = dist / pip_size
                    mode_str = f"mode={atr_mode}" if atr_mode else ""
                    _emit(f"{Ansi.CYAN}{ICONS['TRAIL']} ATR×{mult:.1f} → {dist:.8f} ({dist_pips:.2f} pips) {mode_str}{Ansi.RESET}")
                else:
                    _emit(f"{Ansi.CYAN}{ICONS['TRAIL']} ATR×{mult:.1f}{Ansi.RESET}")

    _emit(f"[Reason] {Ansi.GRAY}{reason}{Ansi.RESET}")

# -----------------------------
# Close Position log
# -----------------------------
def pretty_log_close_position(
    symbol: str,
    ticket: int,
    lot: float,
    price: float,
    conf: float = 0.0,
    winprob: float = 0.0,
    profit: float = 0.0,
    reason: str = "NORMAL",
    entry_index: int = 1,
) -> None:
    if reason == "SEVERE":
        reason_str = f"{Ansi.RED}🚨 EMERGENCY CLOSE (SEVERE LOSS){Ansi.RESET}"
        level = "warning"
    elif reason == "RETRACE":
        reason_str = f"{Ansi.YELLOW}🔒 EMERGENCY CLOSE (RETRACE){Ansi.RESET}"
        level = "warning"
    else:
        reason_str = f"{Ansi.GREEN}Normal Close{Ansi.RESET}"
        level = "info"

    msg = (f"[CLOSE] 🔻 {symbol} ticket={ticket} entry#{entry_index} Lot={lot:.4f} @ {price:.2f} "
           f"| conf={conf:.2f}, wp={winprob:.2f}, P/L={profit:.2f} → {reason_str}")
    _emit(msg, level)

# -----------------------------
# Auto Update log
# -----------------------------
def pretty_log_auto_update(symbol: str, ticket: int, sl: float, tp: Any, entry_index: int = 1) -> None:
    _emit(f"[AUTO-UPDATE] {symbol} ticket={ticket} entry#{entry_index} SL={sl} TP={tp}", "debug")

# -----------------------------
# Trailing log
# -----------------------------
def pretty_log_trailing(symbol: str, ticket: int, old_sl: float, new_sl: float, entry_index: int = 1) -> None:
    _emit(f"[TRAILING] {symbol} ticket={ticket} entry#{entry_index} SL moved {old_sl} → {new_sl}")

# -----------------------------
# Positions summary
# -----------------------------
def pretty_log_positions_summary(summary: Dict[str, Any]) -> None:
    if not summary or not isinstance(summary, dict):
        return

    total = summary.get("total", 0)
    symbols = summary.get("symbols", {})
    if not symbols:
        _emit("📊 Positions: none (total=0)")
        return

    parts = []
    for sym, orders in symbols.items():
        count = len(orders)
        net_profit = sum(o.get("profit", 0.0) for o in orders)
        entry_idxs = [o.get("entry_index", 1) for o in orders]
        parts.append(f"{sym}:{count} orders idx={entry_idxs}, PnL={net_profit:.2f}")
    _emit(f"📊 Positions: total={total} → " + " | ".join(parts))

# -----------------------------
# Global Entry / Exit
# -----------------------------
def pretty_log_global_entry(symbol: str, reasons: str, allowed: bool = True) -> None:
    if allowed:
        _emit(f"[GlobalEntry] 🌍 {symbol} {Ansi.GREEN}✅ Allowed{Ansi.RESET} → {reasons}")
    else:
        _emit(f"[GlobalEntry] 🌍 {symbol} {Ansi.RED}⛔ Blocked{Ansi.RESET} → {reasons}", "warning")

def pretty_log_global_exit(reason: str, triggered: bool = False) -> None:
    if triggered:
        if "stoploss" in reason.lower() or "dd" in reason.lower():
            icon = "🚨"
        elif "takeprofit" in reason.lower():
            icon = "🎯"
        else:
            icon = "🌍"
        _emit(f"[GlobalExit] {icon} {Ansi.RED}{reason}{Ansi.RESET}", "warning")
    else:
        _emit(f"[GlobalExit] 🌍 {Ansi.GREEN}{reason}{Ansi.RESET}")

# -----------------------------
# Execution log
# -----------------------------
def pretty_log_execution(symbol: str, decision: str, allowed: bool, blocker: str = None, reasons: str = "") -> None:
    if allowed:
        _emit(f"[Execution] {symbol} {Ansi.GREEN}✅ ALLOWED{Ansi.RESET} → {colorize_decision(decision, decision)}")
    else:
        _emit(f"[Execution] {symbol} {Ansi.RED}🚫 BLOCKED{Ansi.RESET} → {colorize_decision(decision, decision)} (by {blocker} → {reasons})", "warning")

# -----------------------------
# Dashboard log
# -----------------------------
def pretty_log_dashboard(
    balance: float,
    equity: float,
    pnl: float,
    margin_level: float,
    lots: float,
    results: Dict[str, Any],
    symbols_cfg: Dict[str, Any],
    compact: bool = False,
) -> None:
    _emit(f"[Dashboard] 💹 Balance={balance:.2f} | Equity={equity:.2f} "
          f"| OpenPnL={pnl:.2f} | MarginLevel={margin_level:.1f}% | Lots={lots:.2f}")

    if compact:
        for sym, res in results.items():
            dec = res.get("decision", "HOLD")
            wp = res.get("signal", {}).get("winprob", 0.0)
            conf = res.get("confidence", 0.0)
            regime = res.get("regime", "N/A")
            rule_res = res.get("votes", {}).get("rule", {})
            th = rule_res.get("threshold")
            num_entries = rule_res.get("num_entries")
            th_str = f"{ICONS['THRESH']}{th:.3f}" if th is not None else f"{ICONS['THRESH']}N/A"
            num_str = f"📊x{num_entries}" if num_entries is not None else "📊x?"
            _emit(f"{sym} {colorize_decision(dec, dec)} "
                  f"(wp={wp:.2f}, conf={conf:.2f}, regime={regime}, {th_str}, {num_str})")
