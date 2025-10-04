import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("IndicatorsEfficient")

# ================== ATR ==================
def compute_atr(df: pd.DataFrame, period: int = 14, symbol: str = None) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(alpha=1 / period, min_periods=period).mean()

    if symbol:
        if "XAU" in symbol:
            atr = atr.clip(lower=0.1)
        elif "BTC" in symbol:
            atr = atr.clip(lower=10.0)
        elif "EUR" in symbol or "USD" in symbol:
            atr = atr.clip(lower=0.0001)

    return atr


# ================== BOS ==================
def detect_bos(df: pd.DataFrame, swing_bars: int = 20) -> pd.Series:
    bos = []
    for i in range(len(df)):
        if i < swing_bars:
            bos.append("")
            continue
        recent_high = df["high"].iloc[i - swing_bars + 1 : i + 1].max()
        recent_low = df["low"].iloc[i - swing_bars + 1 : i + 1].min()
        close = df["close"].iloc[i]
        if close >= recent_high:
            bos.append("bullish")
        elif close <= recent_low:
            bos.append("bearish")
        else:
            bos.append("")
    return pd.Series(bos, index=df.index)


# ================== Indicators Full ==================
def add_indicators(df: pd.DataFrame, symbol: str = None) -> pd.DataFrame:
    """
    คำนวณ indicators ทั้งหมด และเพิ่มเข้า DataFrame (เหมือน snapshot JSON เต็ม 30+ ค่า)
    """
    try:
        out = df.copy()
        close = out["close"]

        # EMA
        out["ema20"] = close.ewm(span=20, min_periods=20).mean()
        out["ema50"] = close.ewm(span=50, min_periods=50).mean()
        out["ema_fast"] = out["ema20"]
        out["ema_slow"] = out["ema50"]

        # ATR
        out["atr"] = compute_atr(out, 14, symbol=symbol)

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / 14, min_periods=14).mean()
        avg_loss = loss.ewm(alpha=1 / 14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        out["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = close.ewm(span=12, min_periods=12).mean()
        ema26 = close.ewm(span=26, min_periods=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, min_periods=9).mean()
        out["macd_main"] = macd
        out["macd_signal"] = signal
        out["macd_hist"] = macd - signal

        # Bollinger Bands
        bb_mid = close.rolling(20, min_periods=20).mean()
        bb_std = close.rolling(20, min_periods=20).std()
        out["bb_mid"] = bb_mid
        out["bb_upper"] = bb_mid + 2 * bb_std
        out["bb_lower"] = bb_mid - 2 * bb_std

        # Stochastic
        low_min = out["low"].rolling(14, min_periods=14).min()
        high_max = out["high"].rolling(14, min_periods=14).max()
        out["stoch_k"] = 100 * (close - low_min) / (high_max - low_min).replace(0, np.nan)
        out["stoch_d"] = out["stoch_k"].rolling(3).mean()

        # VWAP
        if "tick_volume" in out.columns:
            cum_vol = out["tick_volume"].cumsum().replace(0, np.nan)
            cum_vp = (close * out["tick_volume"]).cumsum()
            out["vwap"] = cum_vp / cum_vol
        else:
            typical_price = (out["high"] + out["low"] + out["close"]) / 3
            out["vwap"] = typical_price.expanding().mean()

        # Williams %R
        hh = out["high"].rolling(14, min_periods=14).max()
        ll = out["low"].rolling(14, min_periods=14).min()
        out["williams_r"] = -100 * (hh - close) / (hh - ll).replace(0, np.nan)

        # OBV
        out["obv"] = (np.sign(close.diff().fillna(0)) * out["tick_volume"]).cumsum()

        # MFI
        tp = (out["high"] + out["low"] + out["close"]) / 3
        mf = tp * out["tick_volume"]
        pos_mf = mf.where(tp > tp.shift(1), 0.0)
        neg_mf = mf.where(tp < tp.shift(1), 0.0)
        mr = pos_mf.rolling(14).sum() / neg_mf.rolling(14).sum().replace(0, np.nan)
        out["mfi"] = 100 - (100 / (1 + mr))

        # ADX
        up_move = out["high"].diff()
        down_move = -out["low"].diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr = pd.concat(
            [(out["high"] - out["low"]), (out["high"] - close.shift()).abs(), (out["low"] - close.shift()).abs()],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(14).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(14).sum() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(14).sum() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
        out["adx"] = dx.rolling(14).mean()

        # CCI
        tp = (out["high"] + out["low"] + out["close"]) / 3
        ma = tp.rolling(20, min_periods=20).mean()
        md = (tp - ma).abs().rolling(20, min_periods=20).mean()
        out["cci"] = (tp - ma) / (0.015 * md)

        # Ichimoku
        high9 = out["high"].rolling(9).max()
        low9 = out["low"].rolling(9).min()
        high26 = out["high"].rolling(26).max()
        low26 = out["low"].rolling(26).min()
        high52 = out["high"].rolling(52).max()
        low52 = out["low"].rolling(52).min()
        out["ichimoku_tenkan"] = (high9 + low9) / 2
        out["ichimoku_kijun"] = (high26 + low26) / 2
        out["ichimoku_senkou_a"] = ((out["ichimoku_tenkan"] + out["ichimoku_kijun"]) / 2).shift(26)
        out["ichimoku_senkou_b"] = ((high52 + low52) / 2).shift(26)
        out["ichimoku_chikou"] = close.shift(-26)

        # PSAR
        out["psar"] = close.rolling(5, min_periods=5).mean()

        # ATR Stop (simplified)
        out["atr_stop"] = close - 3 * out["atr"]

        # Supertrend (simplified)
        out["supertrend"] = out["psar"]
        out["supertrend_trend"] = "NEUTRAL"

        # Pivot Points
        out["pivot_p"] = (out["high"] + out["low"] + close) / 3
        out["pivot_r1"] = 2 * out["pivot_p"] - out["low"]
        out["pivot_s1"] = 2 * out["pivot_p"] - out["high"]

        # ROC
        out["roc"] = close.pct_change(periods=1) * 100

        # Fractals
        out["fractal_high"] = out["high"].rolling(5, center=True).max()
        out["fractal_low"] = out["low"].rolling(5, center=True).min()

        # Keltner Channel
        ema20 = close.ewm(span=20).mean()
        atr20 = compute_atr(out, 20, symbol=symbol)
        out["keltner_upper"] = ema20 + 2 * atr20
        out["keltner_middle"] = ema20
        out["keltner_lower"] = ema20 - 2 * atr20

        # Donchian Channel
        out["donchian_upper"] = out["high"].rolling(20).max()
        out["donchian_lower"] = out["low"].rolling(20).min()
        out["donchian_middle"] = (out["donchian_upper"] + out["donchian_lower"]) / 2

        # BOS
        bos = detect_bos(out, swing_bars=20)
        out["bos_str"] = bos
        out["bos_val"] = bos.map({"bullish": 1.0, "bearish": -1.0}).fillna(0.0)

        logger.info(f"[Indicators] {symbol} added {len(out)} rows with indicators")

        return out

    except Exception as e:
        logger.error(f"[IndicatorsEfficient] error: {e}")
        return df
