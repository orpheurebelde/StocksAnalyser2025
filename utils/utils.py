import os
import json
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import requests
from hashlib import md5
import math
import plotly.graph_objects as go

CACHE_DIR = "cache"
CSV_PATH = os.path.join(CACHE_DIR, "all_stock_info.csv")
CACHE_DURATION_HOURS = 24  # Cache data for 24 hours

os.makedirs(CACHE_DIR, exist_ok=True)

def is_cache_valid(ticker):
    """Check if the ticker's data in CSV is still valid (within 24 hours)."""
    if not os.path.exists(CSV_PATH):
        return False
    file_time = datetime.fromtimestamp(os.path.getmtime(CSV_PATH))
    return datetime.now() - file_time < timedelta(hours=CACHE_DURATION_HOURS)

def fetch_and_cache_stock_info(ticker):
    """Fetch stock info using yfinance and cache all fields in a shared CSV file."""
    ticker = ticker.upper()
    stock = yf.Ticker(ticker)

    try:
        info = stock.info
        if not info or "symbol" not in info:
            raise ValueError("Invalid ticker or empty data.")

        df_new = pd.DataFrame([info])

        if os.path.exists(CSV_PATH):
            df_existing = pd.read_csv(CSV_PATH)
            df_existing.set_index("Ticker", inplace=True)
        else:
            df_existing = pd.DataFrame().set_index("Ticker")

        new_hash = md5(json.dumps(info, sort_keys=True).encode()).hexdigest()
        existing_hash = None
        if ticker in df_existing.index:
            existing_data = df_existing.loc[ticker].dropna().to_dict()
            existing_hash = md5(json.dumps(existing_data, sort_keys=True).encode()).hexdigest()

        if new_hash != existing_hash:
            df_new.set_index("Ticker", inplace=True)
            df_combined = pd.concat([df_existing.drop(index=ticker, errors='ignore'), df_new])
            df_combined.to_csv(CSV_PATH)
            print(f"✅ Cached info for {ticker} updated.")
        else:
            print(f"ℹ️ No changes for {ticker}. Cache untouched.")

        return info

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"Error 401: Authentication failed for {ticker}. Check API keys or permissions.")
        else:
            print(f"HTTP Error {e.response.status_code}: {e.response.reason} while fetching {ticker}")
        return {"error": f"Could not retrieve data for {ticker}. Authentication failed. Please check API keys or permissions."}

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {ticker}: {e}")
        return {"error": f"Could not retrieve data for {ticker}. Please try again later."}

    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": f"An unexpected error occurred: {e}"}

def get_stock_info(ticker):
    """Get stock info, either from CSV cache or by fetching and caching."""
    ticker = ticker.upper()
    if is_cache_valid(ticker) and os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH, index_col="Ticker")
            if ticker in df.index:
                return df.loc[ticker].to_dict()
        except Exception as e:
            print(f"Error reading cached CSV: {e}")

    return fetch_and_cache_stock_info(ticker)

# Check if key exists and value is valid before using it
def safe_metric(value, divisor=1, suffix="", percentage=False):
        """Safely formats a metric value for Streamlit display."""
        try:
            if value is None:
                return "N/A"
            if isinstance(value, (int, float)):
                if math.isnan(value):  # Handle NaN values
                    return "N/A"
                if percentage:
                    return f"{value:.2%}"
                return f"${value / divisor:.2f}{suffix}" if divisor > 1 else f"${value:.2f}"
            return "N/A"
        except Exception as e:
            return f"Error: {e}"  # Return error message instead of crashing

#Get VIX data        
def get_vix_data():
    """Fetch the latest VIX value from Yahoo Finance."""
    vix = yf.Ticker("^VIX")
    data = vix.history(period="1d", interval="1m")
    if not data.empty:
        return data["Close"].iloc[-1]
    return None

def create_vix_gauge(vix_value):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=vix_value,
        number={
            "font": {"size": 36},  # Control number size
        },
        gauge={
            "axis": {"range": [0, 50], "tickwidth": 1, "tickcolor": "darkgray"},
            "bar": {"color": "darkblue", "thickness": 0.25},
            "steps": [
                {"range": [0, 12], "color": "#00cc44"},    # Extreme Greed
                {"range": [12, 20], "color": "#ffcc00"},   # Greed
                {"range": [20, 28], "color": "#cccccc"},   # Neutral
                {"range": [28, 35], "color": "#ff9933"},   # Fear
                {"range": [35, 50], "color": "#ff3333"},   # Extreme Fear
            ],
            "threshold": {
                "line": {"color": "black", "width": 4},
                "thickness": 0.75,
                "value": vix_value,
            }
        },
        domain={'x': [0, 1], 'y': [0, 1]}  # Ensure full center
    ))

    fig.update_layout(
        margin=dict(t=40, b=40, l=40, r=40),
        height=400,  # Optional: adjust size
    )

    return fig