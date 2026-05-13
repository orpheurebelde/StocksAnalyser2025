import pandas as pd
import numpy as np

def compute_rsi(series, period=14):
    if len(series) < period:
        return np.nan
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def compute_macd(series, fast=12, slow=26, signal=9):
    if len(series) < slow:
        return pd.Series([np.nan]), pd.Series([np.nan])
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def compute_fibonacci_level(series):
    if len(series) == 0:
        return np.nan
    min_price = series.min()
    max_price = series.max()
    current_price = series.iloc[-1]
    if max_price == min_price:
        return 100.0
    return ((current_price - min_price) / (max_price - min_price)) * 100
