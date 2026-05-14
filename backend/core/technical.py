import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import IchimokuIndicator, MACD
from ta.volatility import BollingerBands

def analyze_price_action(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    required_cols = ['Close', 'High', 'Low', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']

    df['RSI'] = RSIIndicator(close=close).rsi()

    ichimoku = IchimokuIndicator(high=high, low=low, window1=9, window2=26, window3=52)
    df['Tenkan_sen'] = ichimoku.ichimoku_conversion_line()
    df['Kijun_sen'] = ichimoku.ichimoku_base_line()
    df['Senkou_span_a'] = ichimoku.ichimoku_a()
    df['Senkou_span_b'] = ichimoku.ichimoku_b()

    bb_indicator = BollingerBands(close=close, window=20, window_dev=2)
    df['bb_high'] = bb_indicator.bollinger_hband()
    df['bb_low'] = bb_indicator.bollinger_lband()

    macd_indicator = MACD(close=close)
    df['macd'] = macd_indicator.macd()
    df['macd_signal'] = macd_indicator.macd_signal()

    df = df.dropna()
    if df.empty:
        raise ValueError("Not enough data to compute indicators.")

    recent = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(recent['Close'])
    rsi = float(recent['RSI'])
    tenkan = float(recent['Tenkan_sen'])
    kijun = float(recent['Kijun_sen'])
    span_a = float(recent['Senkou_span_a'])
    span_b = float(recent['Senkou_span_b'])
    recent_volume = float(recent['Volume'])
    bb_high = float(recent['bb_high'])
    bb_low = float(recent['bb_low'])
    recent_macd = float(recent['macd'])
    recent_signal = float(recent['macd_signal'])
    prev_macd = float(prev['macd'])
    prev_signal = float(prev['macd_signal'])

    score = 0
    explanations = []

    if 50 < rsi < 70:
        score += 2
        explanations.append("✅ RSI is strong and bullish.")
    elif rsi >= 70:
        explanations.append("⚠️ RSI indicates overbought conditions.")
    else:
        explanations.append("📉 RSI is bearish or neutral.")

    if price > span_a and price > span_b:
        score += 2
        explanations.append("✅ Price is above the cloud (bullish).")
    elif price < span_a and price < span_b:
        explanations.append("📉 Price is below the cloud (bearish).")
    else:
        explanations.append("⚠️ Price is within the cloud (neutral).")

    if tenkan > kijun:
        score += 1
        explanations.append("✅ Bullish crossover of Tenkan-sen over Kijun-sen.")
    else:
        explanations.append("📉 No bullish crossover on Ichimoku.")

    avg_volume = volume.rolling(window=20).mean().iloc[-1]
    if recent_volume > avg_volume:
        score += 1
        explanations.append("✅ Volume is higher than average (strong interest).")
    else:
        explanations.append("📉 Volume is below average.")

    if price > bb_high:
        score -= 1
        explanations.append("⚠️ Price is above upper Bollinger Band (potentially overbought).")
    elif price < bb_low:
        score += 1
        explanations.append("✅ Price is below lower Bollinger Band (potentially oversold).")
    else:
        explanations.append("ℹ️ Price is within Bollinger Bands (neutral).")

    if (prev_macd < prev_signal) and (recent_macd > recent_signal):
        score += 2
        explanations.append("✅ MACD bullish crossover.")
    elif (prev_macd > prev_signal) and (recent_macd < recent_signal):
        score -= 2
        explanations.append("⚠️ MACD bearish crossover.")
    else:
        explanations.append("⚠️ MACD is neutral.")

    return score, explanations

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

def estimate_past_shares_outstanding(current_info, hist_data):
    current_market_cap = current_info.get("marketCap")
    current_shares = current_info.get("sharesOutstanding")

    if not current_market_cap or not current_shares or hist_data.empty:
        return None, None, None

    past_price = hist_data['Close'].iloc[0]
    
    past_market_cap = current_market_cap * 0.85
    estimated_past_shares = past_market_cap / past_price if past_price else None

    if estimated_past_shares:
        return current_shares, estimated_past_shares, (current_shares - estimated_past_shares)
    return current_shares, None, None

def interpret_dilution_extended(dilution_pct, revenue_growth=None, eps_current=None,
                                 eps_forward=None, sbc_expense=None, total_revenue=None,
                                 cash_from_financing=None):    
    comments = []

    if dilution_pct > 10:
        comments.append("🔴 **High dilution** – potentially negative.")
    elif 3 < dilution_pct <= 10:
        comments.append("🟠 **Moderate dilution** – acceptable if supporting growth.")
    elif 0 < dilution_pct <= 3:
        comments.append("🟢 **Low dilution** – likely manageable.")
    elif dilution_pct == 0:
        comments.append("✅ **No dilution** – good for shareholders.")
    elif dilution_pct < 0:
        comments.append("🟢 **Share reduction** – likely due to buybacks.")

    if revenue_growth is not None:
        if revenue_growth > 0.1:
            comments.append("📈 Revenue is growing strongly (>10%), indicating dilution may be growth-driven.")
        elif revenue_growth > 0:
            comments.append("📈 Revenue is growing slightly, a mild positive.")
        else:
            comments.append("⚠️ Revenue is not growing – dilution could be risky.")

    if eps_current and eps_forward:
        if eps_forward > eps_current:
            comments.append("📊 EPS is expected to **increase**, which may offset dilution.")
        else:
            comments.append("📉 EPS is not improving – dilution may harm shareholders.")

    if sbc_expense and total_revenue:
        sbc_ratio = sbc_expense / total_revenue
        if sbc_ratio > 0.1:
            comments.append(f"💸 **High SBC**: {sbc_ratio*100:.1f}% of revenue – potential red flag.")
        elif sbc_ratio > 0.03:
            comments.append(f"💸 **Moderate SBC**: {sbc_ratio*100:.1f}% of revenue.")
        else:
            comments.append(f"💸 **Low SBC**: {sbc_ratio*100:.1f}% of revenue – good control of compensation.")

    if cash_from_financing:
        if cash_from_financing > 0:
            comments.append("🏦 Company raised capital via financing – dilution may be for funding.")
        else:
            comments.append("💰 No major financing activity noted.")

    return comments

def score_metric(value, mid, high, max_val, reverse=False):
    if value is None:
        return 0
    if reverse:
        if value < mid: return 2
        elif value <= high: return 1
        else: return 0
    else:
        if value > high: return 2
        elif value >= mid: return 1
        else: return 0

def calculate_fundamentals_score(info: dict):
    score = 0
    try:
        score += score_metric(info.get("returnOnEquity"), 0.15, 0.25, 0.4)
        ebitda_margin = (info.get("ebitda") / info.get("totalRevenue")) if info.get("ebitda") and info.get("totalRevenue") else None
        score += score_metric(ebitda_margin, 0.15, 0.3, 0.5)
        score += score_metric(info.get("trailingPegRatio"), 1, 2, 3, reverse=True)
        score += score_metric(info.get("forwardPE"), 15, 30, 50, reverse=True)
        score += score_metric(info.get("epsCurrentYear"), 1, 5, 10)
    except Exception:
        pass
    
    score_pct = (score / 10) * 100
    if score_pct >= 65:
        label, color = "Strong", "var(--status-green)"
    elif score_pct >= 40:
        label, color = "Average", "var(--accent-orange)"
    else:
        label, color = "Weak", "var(--status-red)"
        
    return {"score": score, "max_score": 10, "label": label, "color": color}
