import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("IndicatorsEfficient")


# ================== ATR ==================
def compute_atr_last(df: pd.DataFrame, period: int = 14, symbol: str = None) -> float:
    try:
        if len(df) < period + 1:
            return 1.0

        atr_series = pd.concat(
            [
                (df["high"] - df["low"]),
                (df["high"] - df["close"].shift()).abs(),
                (df["low"] - df["close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = atr_series.ewm(alpha=1 / period, min_periods=period).mean().iloc[-1]

        # ✅ support only BTCUSDc and XAUUSDc
        if symbol:
            if "XAU" in symbol:
                atr = max(atr, 0.1)
            elif "BTC" in symbol:
                atr = max(atr, 10.0)

        logger.debug(f"[ATR] {symbol} period={period} → {atr:.4f}")
        return float(atr)
    except Exception as e:
        logger.error(f"[ATR Efficient] calc error: {e}")
        return 1.0


# ================== BOS realtime ==================
def detect_bos_last(df: pd.DataFrame, swing_bars: int = 20) -> str:
    """Break of Structure ล่าสุด"""
    if df is None or len(df) < swing_bars:
        return ""
    try:
        recent_high = df["high"].iloc[-swing_bars:].max()
        recent_low = df["low"].iloc[-swing_bars:].min()
        close = df["close"].iloc[-1]

        if close >= recent_high:
            return "bullish"
        elif close <= recent_low:
            return "bearish"
        return ""
    except Exception as e:
        logger.error(f"[BOS Efficient] error: {e}")
        return ""


# ================== BOS labeling (past+future) ==================
def detect_bos_label(df: pd.DataFrame, past: int = 200, future: int = 200) -> pd.DataFrame:
    """
    Label BOS โดยดู high/low ย้อนหลัง N และอนาคต M
    ใช้สำหรับ backtest/ML ไม่ใช่ realtime
    """
    try:
        df = df.copy()
        past_high = df["high"].rolling(past).max()
        past_low = df["low"].rolling(past).min()
        future_high = df["high"].shift(-future).rolling(future).max()
        future_low = df["low"].shift(-future).rolling(future).min()

        bos_labels = []
        for i in range(len(df)):
            if i >= past and i < len(df) - future:
                if df["close"].iloc[i] >= future_high.iloc[i]:
                    bos_labels.append("bullish")
                elif df["close"].iloc[i] <= future_low.iloc[i]:
                    bos_labels.append("bearish")
                else:
                    bos_labels.append("")
            else:
                bos_labels.append("")
        df["bos_label"] = bos_labels
        return df
    except Exception as e:
        logger.error(f"[BOS Label] error: {e}")
        df["bos_label"] = ""
        return df


# ================== Indicators Efficient ==================
def add_indicators_last(df: pd.DataFrame, symbol: str = None) -> dict:
    """
    คำนวณ indicators เฉพาะแท่งล่าสุด → return dict
    """
    try:
        row = df.iloc[-1]

        # EMA
        ema_fast = df["close"].ewm(span=20, min_periods=20).mean().iloc[-1]
        ema_slow = df["close"].ewm(span=50, min_periods=50).mean().iloc[-1]
        logger.debug(f"[EMA] {symbol} fast={ema_fast:.4f}, slow={ema_slow:.4f}")

        # ATR
        atr = compute_atr_last(df, 14, symbol=symbol)

        # RSI
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / 14, min_periods=14).mean()
        avg_loss = loss.ewm(alpha=1 / 14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        rsi = float(np.clip(rsi, 0, 100))
        logger.debug(f"[RSI] {symbol} → {rsi:.2f}")

        # MACD
        ema12 = df["close"].ewm(span=12, min_periods=12).mean()
        ema26 = df["close"].ewm(span=26, min_periods=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, min_periods=9).mean()
        macd_main = macd.iloc[-1]
        macd_signal = signal.iloc[-1]
        macd_hist = macd_main - macd_signal
        logger.debug(f"[MACD] {symbol} main={macd_main:.4f}, signal={macd_signal:.4f}, hist={macd_hist:.4f}")

        # Bollinger Bands
        bb_mid = df["close"].rolling(20, min_periods=20).mean().iloc[-1]
        bb_std = df["close"].rolling(20, min_periods=20).std().iloc[-1]
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        bb = (row["close"] - bb_mid) / (bb_std if bb_std != 0 else 1)
        logger.debug(f"[BB] {symbol} z-score={bb:.2f}")

        # Stochastic
        low_min = df["low"].rolling(14, min_periods=14).min().iloc[-1]
        high_max = df["high"].rolling(14, min_periods=14).max().iloc[-1]
        stoch_k = 100 * (row["close"] - low_min) / (high_max - low_min) if high_max != low_min else 50
        stoch_d = pd.Series([stoch_k]).rolling(3).mean().iloc[-1]
        logger.debug(f"[Stoch] {symbol} k={stoch_k:.2f}, d={stoch_d:.2f}")

        # VWAP
        if "tick_volume" in df.columns:
            cum_vol = df["tick_volume"].cumsum().replace(0, np.nan)
            cum_vp = (df["close"] * df["tick_volume"]).cumsum()
            vwap = (cum_vp / cum_vol).iloc[-1]
        else:
            typical_price = (df["high"] + df["low"] + df["close"]) / 3
            vwap = typical_price.expanding().mean().iloc[-1]
        logger.debug(f"[VWAP] {symbol} → {vwap:.4f}")

        # BOS realtime
        bos = detect_bos_last(df, swing_bars=20)
        bos_val = 1.0 if bos == "bullish" else -1.0 if bos == "bearish" else 0.0

        indicators = {
            "ema_fast": float(ema_fast),
            "ema_slow": float(ema_slow),
            "rsi": rsi,
            "macd_main": float(macd_main),
            "macd_signal": float(macd_signal),
            "macd_hist": float(macd_hist),
            "atr": atr,
            "bb": float(bb),
            "stoch_k": float(stoch_k),
            "stoch_d": float(stoch_d),
            "vwap": float(vwap),
            "bos": bos,
            "bos_val": bos_val,
            "bb_mid": float(bb_mid),
            "bb_upper": float(bb_upper),
            "bb_lower": float(bb_lower),
            "bos_label": row.get("bos_label", ""),
        }

        logger.info(f"[Indicators] {symbol} latest → {indicators}")
        return indicators

    except Exception as e:
        logger.error(f"[IndicatorsEfficient] error: {e}")
        return {}
