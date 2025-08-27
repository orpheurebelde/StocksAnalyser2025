import os
import json
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import requests
import traceback
from hashlib import md5
import math
import plotly.graph_objects as go
import streamlit as st
import numpy as np
from io import BytesIO
from ta.trend import IchimokuIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
import time

# Constants
CACHE_DIR = "cache"
CSV_PATH = os.path.join(CACHE_DIR, "all_stock_info.csv")
CACHE_DURATION_HOURS = 24
SENTIMENT_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
SENTIMENT_PATH = "data/sentiment.xls"

# Ensure cache folder exists
os.makedirs(CACHE_DIR, exist_ok=True)

def is_cache_valid():
    """Check if cache file exists and is fresh."""
    return os.path.exists(CSV_PATH) and (
        datetime.now() - datetime.fromtimestamp(os.path.getmtime(CSV_PATH))
        < timedelta(hours=CACHE_DURATION_HOURS)
    )

def fetch_and_cache_stock_info(ticker: str) -> dict:
    """
    Fetch full yfinance info for a ticker and cache entire dict.
    Returns the full info dict with guaranteed 'Ticker' key.
    """
    ticker = ticker.upper()
    try:
        stock = yf.Ticker(ticker)
        info_full = {}

        # Try fast_info first
        try:
            fast_data = stock.fast_info or {}
        except Exception:
            fast_data = {}

        # Full info fallback
        try:
            info_full = stock.info or {}
        except Exception:
            info_full = {}

        # Merge fast_info into info_full (fast_info overrides)
        for k, v in fast_data.items():
            if v is not None:
                info_full[k] = v

        # Always include Ticker key
        info_full["Ticker"] = ticker

        # Only cache if we got any data
        if info_full:
            df_new = pd.DataFrame([info_full]).set_index("Ticker")

            # Load existing cache
            if os.path.exists(CSV_PATH):
                try:
                    df_existing = pd.read_csv(CSV_PATH).set_index("Ticker")
                except Exception:
                    os.remove(CSV_PATH)
                    df_existing = pd.DataFrame().set_index("Ticker")
            else:
                df_existing = pd.DataFrame().set_index("Ticker")

            # Check if hash changed
            new_hash = md5(json.dumps(info_full, sort_keys=True).encode()).hexdigest()
            existing_hash = None
            if ticker in df_existing.index:
                existing_info = df_existing.loc[ticker].dropna().to_dict()
                existing_hash = md5(json.dumps(existing_info, sort_keys=True).encode()).hexdigest()

            if new_hash != existing_hash:
                df_combined = pd.concat([df_existing.drop(index=ticker, errors="ignore"), df_new])
                df_combined.to_csv(CSV_PATH)

        return info_full

    except Exception as e:
        print(f"❌ Error fetching {ticker}: {e}")
        return {"Ticker": ticker}

# Load stock list
@st.cache_data
def load_stock_list():
    df = pd.read_csv("stocks_list.csv", sep=";")
    df["Display"] = df["Ticker"] + " - " + df["Name"]
    return df

@st.cache_data
def get_stock_info(ticker: str) -> dict:
    """
    Return full stock info from cache or fetch fresh.
    Guarantees at least the 'Ticker' key exists.
    """
    ticker = ticker.upper()

    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH).set_index("Ticker")
            if ticker in df.index:
                data = df.loc[ticker].to_dict()
                data["Ticker"] = ticker
                return data
        except Exception:
            os.remove(CSV_PATH)

    return fetch_and_cache_stock_info(ticker)

@st.cache_data(ttl=CACHE_DURATION_HOURS * 3600, show_spinner=False)
def get_stock_price_yf(ticker):
    try:
        return yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1]
    except Exception:
        return None

# Utility: Safe metric formatting
def safe_metric(value, divisor=1, suffix="", percentage=False):
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "N/A"
        if percentage:
            return f"{value:.2%}"
        return f"${value / divisor:.2f}{suffix}" if divisor > 1 else f"${value:.2f}"
    except Exception as e:
        return f"Err: {e}"

# Get VIX value
def get_vix_data():
    vix = yf.Ticker("^VIX")
    data = vix.history(period="1d", interval="1m")
    if not data.empty:
        return data["Close"].iloc[-1]
    return None

# Create VIX gauge
def create_vix_gauge(vix_value):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=vix_value,
        number={"font": {"size": 36}},
        gauge={
            "axis": {"range": [0, 50], "tickwidth": 1, "tickcolor": "darkgray"},
            "bar": {"color": "darkblue", "thickness": 0.25},
            "steps": [
                {"range": [0, 12], "color": "#00cc44"},
                {"range": [12, 20], "color": "#ffcc00"},
                {"range": [20, 28], "color": "#cccccc"},
                {"range": [28, 35], "color": "#ff9933"},
                {"range": [35, 50], "color": "#ff3333"},
            ],
            "threshold": {"line": {"color": "black", "width": 4}, "thickness": 0.75, "value": vix_value}
        },
        domain={'x': [0, 1], 'y': [0, 1]}
    ))

    fig.update_layout(margin=dict(t=40, b=40, l=40, r=40), height=400)
    return fig

def get_ai_analysis(prompt, api_key):
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "mistral-small-latest",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1500
        }

        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()

    except Exception:
        return f"ERROR: {traceback.format_exc()}"

def format_number(num):
    if isinstance(num, (int, float)):
        if num > 1e12:
            return f"{num / 1e12:.2f} trillion"
        elif num > 1e9:
            return f"{num / 1e9:.2f} billion"
        elif num > 1e6:
            return f"{num / 1e6:.2f} million"
        else:
            return f"{num}"
    return num


def login(USERNAME, PASSWORD):
    st.subheader("🔐 Login")

    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", key="login_button"):
        if username == USERNAME and password == PASSWORD:
            st.session_state["authenticated"] = True
            st.session_state["last_activity"] = time.time()
            st.success("Login successful.")
            try:
                st.rerun()  # or st.experimental_rerun()
            except Exception as e:
                st.error(f"Failed to rerun app: {e}")
        else:
            st.error("Invalid credentials. Please try again.")

def monte_carlo_simulation(data, n_simulations=1000, n_days=252, log_normal=False, volatility=None):
    daily_returns = data['Close'].pct_change().dropna()
    mean_return = daily_returns.mean()
    vol = volatility if volatility else daily_returns.std()

    simulations = np.zeros((n_simulations, n_days))
    last_price = data['Close'].iloc[-1]

    for i in range(n_simulations):
        prices = [last_price]
        for j in range(n_days):
            shock = np.random.normal(0, vol)
            drift = mean_return
            if log_normal:
                prices.append(prices[-1] * np.exp(drift + shock))
            else:
                prices.append(prices[-1] * (1 + drift + shock))
        simulations[i] = prices[1:]

    return simulations

@st.cache_data
def fetch_data(ticker):
    try:
        # Fetch data from Yahoo Finance
        stock = yf.Ticker(ticker)
        data = stock.history(period="10y")  # Fetch 10 years of historical data
        info = stock.info  # Fetch stock information

        # Ensure data and info are not empty
        if data.empty:
            st.error(f"No historical data found for ticker: {ticker}")
            return None, None
        if not info:
            st.error(f"No stock information found for ticker: {ticker}")
            return data, None

        return data, info

    except Exception as e:
        st.error(f"Error fetching data for ticker {ticker}: {e}")
        return None, None
    
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def compute_fibonacci_level(series):
    min_price = series.min()
    max_price = series.max()
    current_price = series.iloc[-1]
    return ((current_price - min_price) / (max_price - min_price)) * 100

def score_metric(value, low, mid, high, reverse=False):
    if value is None:
        return 0
    if reverse:  # lower is better
        if value < low:
            return 2
        elif value <= mid:
            return 1
        else:
            return 0
    else:  # higher is better
        if value > high:
            return 2
        elif value >= mid:
            return 1
        else:
            return 0

def display_fundamentals_score(info: dict):
    score = 0
    max_score = 5 * 2  # 5 metrics, 2 points each

    try:
        # Return on Equity: high ROE is good
        score += score_metric(info.get("returnOnEquity"), 0.15, 0.25, 0.4)

        # EBITDA Margin: ebitda / revenue
        ebitda_margin = (
            info.get("ebitda") / info.get("totalRevenue")
            if info.get("ebitda") and info.get("totalRevenue")
            else None
        )
        score += score_metric(ebitda_margin, 0.15, 0.3, 0.5)

        # PEG Ratio: < 1 is great, 1–2 is okay
        score += score_metric(info.get("trailingPegRatio"), 1, 2, 3, reverse=True)

        # Forward P/E: adjusted for tech
        score += score_metric(info.get("forwardPE"), 15, 30, 50, reverse=True)

        # EPS growth (estimate): optional bonus
        score += score_metric(info.get("epsCurrentYear"), 1, 5, 10)
        
    except Exception as e:
        st.error(f"Error scoring fundamentals: {e}")
        return

    score_pct = (score / max_score) * 100

    if score_pct >= 65:
        label = "Strong"
        color = "green"
    elif score_pct >= 40:
        label = "Average"
        color = "orange"
    else:
        label = "Weak"
        color = "red"

    st.markdown(f"""
        <div style='padding: 1rem; border: 2px solid {color}; border-radius: 1rem; background-color: #1e1e1e; margin-bottom: 1rem;'>
            <h4 style='margin: 0 0 0.5rem 0; color: #FFFFFF;'>🔎 Valuation Quality Score</h4>
            <span style='font-size: 48px; font-weight: bold; color: {color};'>{label}</span>
            <div style='font-size: 18px; color: #AAAAAA;'>({score}/10 points)</div>
        </div>
    """, unsafe_allow_html=True)

def clean_aaii_sentiment(df):
    percent_columns = ['Bullish', 'Neutral', 'Bearish']
    
    for col in percent_columns:
        # Convert '37,5%' ➜ 37.5 ➜ 37.5 (float)
        df[col] = (
            df[col]
            .astype(str)                  # ensure all are strings
            .str.replace('%', '', regex=False)  # remove %
            .str.replace(',', '.', regex=False)  # convert comma to dot
            .astype(float)
        )
    
    # Convert Date if not already
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])
    
    return df

def load_aaii_sentiment():
    df = pd.read_excel("data/aaii_sentiment.xls", skiprows=3)  # Skip metadata
    df.columns = df.columns.str.strip()  # Remove extra whitespace
    df = df.dropna(subset=["Date"])     # Remove empty rows

    # Convert date and percentages
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ["Bullish", "Neutral", "Bearish"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace('%', '', regex=False)
                .str.replace(',', '.', regex=False)
                .astype(float)
            )

    return df


def should_download_sentiment():
    """Only download if file is missing or last modified before last Thursday."""
    if not os.path.exists(SENTIMENT_PATH):
        return True

    file_time = datetime.fromtimestamp(os.path.getmtime(SENTIMENT_PATH))
    today = datetime.today()
    last_thursday = today - timedelta(days=(today.weekday() - 3) % 7 + 7)

    return file_time.date() < last_thursday.date()

def download_aaii_sentiment():
    """Downloads the AAII sentiment Excel file if needed."""
    if should_download_sentiment():
        try:
            response = requests.get(SENTIMENT_URL)
            response.raise_for_status()

            os.makedirs("data", exist_ok=True)
            with open(SENTIMENT_PATH, "wb") as f:
                f.write(response.content)

            print("Sentiment data downloaded.")
        except Exception as e:
            print(f"Failed to download sentiment data: {e}")
    else:
        print("Sentiment file is up-to-date.")

def fetch_price_data(ticker: str) -> pd.DataFrame:
    if not ticker or not isinstance(ticker, str):
        raise ValueError("Invalid ticker")

    df = yf.download(ticker, period="6mo", interval="1d", progress=False)
    if df.empty:
        raise ValueError(f"No data found for ticker '{ticker}'")
    return df

def analyze_price_action(df):
    # Required columns
    required_cols = ['Close', 'High', 'Low', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Extract series
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']

    # Handle multi-columns if needed
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    if isinstance(high, pd.DataFrame):
        high = high.iloc[:, 0]
    if isinstance(low, pd.DataFrame):
        low = low.iloc[:, 0]
    if isinstance(volume, pd.DataFrame):
        volume = volume.iloc[:, 0]

    # Calculate indicators
    df['RSI'] = RSIIndicator(close=close).rsi()

    ichimoku = IchimokuIndicator(high=high, low=low, window1=9, window2=26, window3=52)
    df['Tenkan_sen'] = ichimoku.ichimoku_conversion_line()
    df['Kijun_sen'] = ichimoku.ichimoku_base_line()
    df['Senkou_span_a'] = ichimoku.ichimoku_a()
    df['Senkou_span_b'] = ichimoku.ichimoku_b()

    bb_indicator = BollingerBands(close=close, window=20, window_dev=2)
    df['bb_high'] = bb_indicator.bollinger_hband()
    df['bb_low'] = bb_indicator.bollinger_lband()

    # MACD calculation
    macd_indicator = MACD(close=close)
    df['macd'] = macd_indicator.macd()
    df['macd_signal'] = macd_indicator.macd_signal()

    # Drop rows with NaNs after all indicators are added
    df = df.dropna()
    if df.empty:
        raise ValueError("Not enough data to compute indicators (after dropping NaNs).")

    recent = df.iloc[-1]
    prev = df.iloc[-2]

    # Extract values from recent row
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

    # RSI analysis
    if 50 < rsi < 70:
        score += 2
        explanations.append("✅ RSI is strong and bullish.")
    elif rsi >= 70:
        explanations.append("⚠️ RSI indicates overbought conditions.")
    else:
        explanations.append("📉 RSI is bearish or neutral.")

    # Ichimoku price position
    if price > span_a and price > span_b:
        score += 2
        explanations.append("✅ Price is above the cloud (bullish).")
    elif price < span_a and price < span_b:
        explanations.append("📉 Price is below the cloud (bearish).")
    else:
        explanations.append("⚠️ Price is within the cloud (neutral).")

    # Tenkan-sen vs Kijun-sen
    if tenkan > kijun:
        score += 1
        explanations.append("✅ Bullish crossover of Tenkan-sen over Kijun-sen.")
    else:
        explanations.append("📉 No bullish crossover on Ichimoku.")

    # Volume check
    avg_volume = volume.rolling(window=20).mean().iloc[-1]
    if recent_volume > avg_volume:
        score += 1
        explanations.append("✅ Volume is higher than average (strong interest).")
    else:
        explanations.append("📉 Volume is below average.")

    # Bollinger Bands check
    if price > bb_high:
        score -= 1
        explanations.append("⚠️ Price is above upper Bollinger Band (potentially overbought).")
    elif price < bb_low:
        score += 1
        explanations.append("✅ Price is below lower Bollinger Band (potentially oversold).")
    else:
        explanations.append("ℹ️ Price is within Bollinger Bands (neutral).")

    # MACD scoring
    if (prev_macd < prev_signal) and (recent_macd > recent_signal):
        score += 2
        explanations.append("✅ MACD bullish crossover.")
    elif (prev_macd > prev_signal) and (recent_macd < recent_signal):
        score -= 2
        explanations.append("⚠️ MACD bearish crossover.")
    else:
        explanations.append("⚠️ MACD is neutral.")

    return score, explanations

def calculate_dcf_valor(ticker, revenue_growth_base=0.10, revenue_growth_bull=0.18, revenue_growth_bear=0.05,
                        discount_rate=0.10, years=5, terminal_growth_rate=0.025):
    import yfinance as yf

    try:
        ticker = ticker.strip().upper()
        stock = yf.Ticker(ticker)
        info = stock.info

        revenue = info.get("totalRevenue")
        free_cf = info.get("freeCashflow")
        shares_outstanding = info.get("sharesOutstanding")
        current_price = info.get("currentPrice", 0)

        if not revenue or not free_cf or not shares_outstanding:
            raise ValueError("Missing required financial data.")

        # Use a more conservative FCF margin if none is available
        fcf_margin = free_cf / revenue if revenue else 0.15

        # Net debt: total debt - cash
        total_debt = info.get("totalDebt", 0)
        cash = info.get("cash", 0)
        net_debt = total_debt - cash

        def project_fcf(growth_rate):
            fcf_list = []
            rev = revenue
            for _ in range(years):
                rev *= (1 + growth_rate)
                fcf_list.append(rev * fcf_margin)
            return fcf_list

        def discount_cash_flows(fcf_list):
            if terminal_growth_rate >= discount_rate:
                raise ValueError("Terminal growth rate must be less than discount rate.")
            discounted = [fcf / (1 + discount_rate) ** (i + 1) for i, fcf in enumerate(fcf_list)]
            terminal_value = fcf_list[-1] * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
            terminal_discounted = terminal_value / ((1 + discount_rate) ** years)
            return sum(discounted) + terminal_discounted

        base_valuation = discount_cash_flows(project_fcf(revenue_growth_base)) - net_debt
        bull_valuation = discount_cash_flows(project_fcf(revenue_growth_bull)) - net_debt
        bear_valuation = discount_cash_flows(project_fcf(revenue_growth_bear)) - net_debt

        return {
            "Base": round(base_valuation / shares_outstanding, 2),
            "Bull": round(bull_valuation / shares_outstanding, 2),
            "Bear": round(bear_valuation / shares_outstanding, 2),
            "Current Price": current_price
        }

    except Exception as e:
        return {"Error": str(e)}
    
def calculate_peg_ratio(pe_ratio, eps_growth_percent):
    if pe_ratio is not None and eps_growth_percent is not None and eps_growth_percent != 0:
        return round(pe_ratio / eps_growth_percent, 2)
    return None

def estimate_past_shares_outstanding(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)

    current_info = ticker.info
    current_price = current_info.get("currentPrice")
    current_market_cap = current_info.get("marketCap")
    current_shares = current_info.get("sharesOutstanding")

    # Get historical price and market cap for 1 year ago
    hist = ticker.history(period="1y", interval="1mo")
    if len(hist) < 2:
        return None, None, None

    past_price = hist['Close'].iloc[0]
    # Estimate past shares using approximate market cap / price
    past_market_cap = current_market_cap * 0.85  # crude approx: assume 15% growth
    estimated_past_shares = past_market_cap / past_price if past_price else None

    return current_shares, estimated_past_shares, (current_shares - estimated_past_shares)

def interpret_dilution_extended(dilution_pct, revenue_growth=None, eps_current=None,
                                 eps_forward=None, sbc_expense=None, total_revenue=None,
                                 cash_from_financing=None):    
    comments = []

    # Base on dilution %
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

    # Revenue growth
    if revenue_growth is not None:
        if revenue_growth > 0.1:
            comments.append("📈 Revenue is growing strongly (>10%), indicating dilution may be growth-driven.")
        elif revenue_growth > 0:
            comments.append("📈 Revenue is growing slightly, a mild positive.")
        else:
            comments.append("⚠️ Revenue is not growing – dilution could be risky.")

    # EPS trend
    if eps_current and eps_forward:
        if eps_forward > eps_current:
            comments.append("📊 EPS is expected to **increase**, which may offset dilution.")
        else:
            comments.append("📉 EPS is not improving – dilution may harm shareholders.")

    # SBC ratio
    if sbc_expense and total_revenue:
        sbc_ratio = sbc_expense / total_revenue
        if sbc_ratio > 0.1:
            comments.append(f"💸 **High SBC**: {sbc_ratio:.1%} of revenue – potential red flag.")
        elif sbc_ratio > 0.03:
            comments.append(f"💸 **Moderate SBC**: {sbc_ratio:.1%} of revenue.")
        else:
            comments.append(f"💸 **Low SBC**: {sbc_ratio:.1%} of revenue – good control of compensation.")

    # Cash from financing
    if cash_from_financing:
        if cash_from_financing > 0:
            comments.append("🏦 Company raised capital via financing – dilution may be for funding.")
        else:
            comments.append("💰 No major financing activity noted.")

    return "\n\n".join(comments)


