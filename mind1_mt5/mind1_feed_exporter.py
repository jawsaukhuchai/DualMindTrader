import sys
import os
import MetaTrader5 as mt5
import json
import time
import pandas as pd
from datetime import datetime

# ================================
# Fix import path so we can run directly from mind1_mt5/
# ================================
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# ✅ ใช้ add_indicators จาก mind1_mt5/indicators_efficient.py
from mind1_mt5.indicators_efficient import add_indicators, compute_atr

# -------------------------------
# Settings
# -------------------------------
EXPORT_INTERVAL = 60  # seconds → real-time กว่าเดิม
SYMBOLS = ["BTCUSDc", "XAUUSDc"]
TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}
ATR_PERIOD = 14

# -------------------------------
# Dynamic Filter Thresholds
# -------------------------------
FILTER_RULES = {
    "BTCUSDc": {"spread_limit": 1000},   # BTC: ≤ 1000 point
    "XAUUSDc": {"spread_limit": 300},    # Gold: ≤ 300 point
}

# -------------------------------
# Utility: convert MT5 rates → DataFrame
# -------------------------------
def rates_to_df(rates):
    df = pd.DataFrame(rates, columns=[
        "time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"
    ])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df

# -------------------------------
# ATR calculation unified
# -------------------------------
def calc_atr(df: pd.DataFrame, period: int = ATR_PERIOD, symbol: str = None) -> float:
    if df is None or df.empty:
        return 0.0
    atr_series = compute_atr(df, period=period, symbol=symbol)
    return float(atr_series.iloc[-1]) if not atr_series.empty else 0.0

# -------------------------------
# Connect MT5
# -------------------------------
if not mt5.initialize():
    print("❌ MT5 initialize() failed")
    # export disconnect state
    with open("mind1_feed.json", "w", encoding="utf-8") as f:
        json.dump({"state": "DISCONNECTED", "timestamp": datetime.utcnow().isoformat()}, f, indent=2)
    quit()
print("✅ MT5 initialized")

# -------------------------------
# Loop forever
# -------------------------------
while True:
    feeds = []
    now = datetime.utcnow().isoformat()

    account_info = mt5.account_info()
    health = {}
    if account_info:
        health = {
            "balance": account_info.balance,
            "equity": account_info.equity,
            "margin": account_info.margin,
            "margin_level": account_info.margin_level,
            "positions": mt5.positions_total(),
        }
    else:
        health = {"state": "DISCONNECTED"}

    for sym in SYMBOLS:
        info = mt5.symbol_info(sym)
        tick = mt5.symbol_info_tick(sym)
        if info is None or tick is None:
            print(f"⚠️ Warning: {sym} not available")
            continue

        bid = tick.bid
        ask = tick.ask
        spread = (ask - bid) / info.point

        # ✅ dynamic filter per symbol
        spread_limit = FILTER_RULES.get(sym, {}).get("spread_limit", 99999)
        filters = {
            "spread": {"value": spread, "limit": spread_limit, "pass": spread <= spread_limit},
            "news": {"impact": "NONE", "pass": True},  # TODO: integrate news API
            "sideway": {"state": False, "pass": True}, # TODO: ATR-based sideways detection
        }

        tf_data = {}
        for name, tf in TIMEFRAMES.items():
            raw_rates = mt5.copy_rates_from_pos(sym, tf, 0, 200)
            if raw_rates is None or len(raw_rates) == 0:
                continue

            df = rates_to_df(raw_rates)
            df = add_indicators(df, symbol=sym)  # ✅ enrich ด้วย indicators ครบชุด

            # ✅ unified ATR
            atr_val = calc_atr(df, ATR_PERIOD, symbol=sym)
            df.loc[df.index[-1], "atr"] = atr_val

            last = df.iloc[-1].to_dict()
            tf_data[name] = {
                k: (None if pd.isna(v) else v)
                for k, v in last.items()
                if k not in ["time"]
            }

        feed = {
            "symbol": sym,
            "bid": round(bid, info.digits),
            "ask": round(ask, info.digits),
            "spread": round(spread, 1),
            "filters": filters,
            "timeframes": tf_data,
            "timestamp": now,
        }
        feeds.append(feed)

    # ✅ save JSON with global health state
    export_data = {
        "state": "CONNECTED",
        "timestamp": now,
        "health": health,
        "feeds": feeds,
    }
    with open("mind1_feed.json", "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)

    print(f"✅ Exported mind1_feed.json with {len(feeds)} symbols at {now}")
    time.sleep(EXPORT_INTERVAL)
