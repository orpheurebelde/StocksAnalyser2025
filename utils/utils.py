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

# Constants
CACHE_DIR = "cache"
CSV_PATH = os.path.join(CACHE_DIR, "all_stock_info.csv")
CACHE_DURATION_HOURS = 24

# Ensure cache folder exists
os.makedirs(CACHE_DIR, exist_ok=True)

def is_cache_valid():
    """Check if cache file exists and is fresh."""
    return os.path.exists(CSV_PATH) and (
        datetime.now() - datetime.fromtimestamp(os.path.getmtime(CSV_PATH))
        < timedelta(hours=CACHE_DURATION_HOURS)
    )

def fetch_and_cache_stock_info(ticker):
    """Fetch info and save to CSV cache."""
    ticker = ticker.upper()
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info:
            raise ValueError("Empty info returned.")

        info["Ticker"] = ticker  # ✅ Ensure Ticker is always added
        df_new = pd.DataFrame([info])
        df_new.set_index("Ticker", inplace=True)

        # Load or create cache
        if os.path.exists(CSV_PATH):
            try:
                df_existing = pd.read_csv(CSV_PATH)
                if "Ticker" not in df_existing.columns:
                    raise ValueError("Missing 'Ticker' column")
                df_existing.set_index("Ticker", inplace=True)
            except Exception as e:
                print(f"⚠️ Corrupted cache. Removing: {e}")
                os.remove(CSV_PATH)
                df_existing = pd.DataFrame()
        else:
            df_existing = pd.DataFrame()

        # Check if info changed
        new_hash = md5(json.dumps(info, sort_keys=True).encode()).hexdigest()
        existing_hash = None
        if ticker in df_existing.index:
            existing_info = df_existing.loc[ticker].dropna().to_dict()
            existing_hash = md5(json.dumps(existing_info, sort_keys=True).encode()).hexdigest()

        if new_hash != existing_hash:
            df_combined = pd.concat([df_existing.drop(index=ticker, errors="ignore"), df_new])
            df_combined.to_csv(CSV_PATH)
            print(f"✅ Cache updated for {ticker}")
        else:
            print(f"ℹ️ No change for {ticker}")

        return info

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {"error": f"An unexpected error occurred: {e}"}

def get_stock_info(ticker):
    """Get stock info from cache or fetch if needed."""
    ticker = ticker.upper()
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
            if "Ticker" not in df.columns:
                print("⚠️ CSV missing Ticker column. Deleting.")
                os.remove(CSV_PATH)
                return fetch_and_cache_stock_info(ticker)
            df.set_index("Ticker", inplace=True)
            if ticker in df.index:
                return df.loc[ticker].to_dict()
        except Exception as e:
            print(f"⚠️ Read error: {e}")
            try:
                os.remove(CSV_PATH)
            except:
                pass
            return fetch_and_cache_stock_info(ticker)

    return fetch_and_cache_stock_info(ticker)

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
            "max_tokens": 700
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

import streamlit as st
import time

def login(USERNAME, PASSWORD):
    st.subheader("🔐 Login")

    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", key="login_button"):
        if username == USERNAME and password == PASSWORD:
            st.session_state["authenticated"] = True
            st.session_state["last_activity"] = time.time()
            st.success("Login successful.")
            st.stop()  # <- This safely ends this run and allows rerun
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