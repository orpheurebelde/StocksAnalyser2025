import os
import pickle
from datetime import datetime, timedelta
import pandas as pd
import requests
import streamlit as st

FINNHUB_API_KEY = st.secrets["FINNHUB_API_KEY"]
BASE_URL = "https://finnhub.io/api/v1"
DATA_FOLDER = "data"

# Make sure the data folder exists
os.makedirs(DATA_FOLDER, exist_ok=True)

def get_stock_history(symbol, start_date="2018-01-01", end_date=None):
    if end_date is None:
        end_date = datetime.today().strftime('%Y-%m-%d')

    cache_filename = os.path.join(DATA_FOLDER, f"{symbol}_{start_date}_{end_date}.pkl")

    # Use cached data if it's less than 1 day old
    if os.path.exists(cache_filename):
        file_timestamp = os.path.getmtime(cache_filename)
        last_modified = datetime.fromtimestamp(file_timestamp)
        if (datetime.now() - last_modified).days < 1:
            with open(cache_filename, 'rb') as f:
                return pickle.load(f)

    # Convert dates to UNIX timestamps
    try:
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
    except Exception as e:
        st.error(f"Date parsing error: {e}")
        return None

    # Call Finnhub daily candle API
    url = f"{BASE_URL}/stock/candle"
    params = {
        "symbol": symbol,
        "resolution": "D",
        "from": start_ts,
        "to": end_ts,
        "token": FINNHUB_API_KEY
    }
    response = requests.get(url, params=params)
    data = response.json()

    # Handle API errors
    if data.get("s") != "ok":
        st.error(f"No historical data found for {symbol}. Response: {data}")
        return None

    # Convert to DataFrame
    df = pd.DataFrame({
        "time": pd.to_datetime(data["t"], unit="s"),
        "open": data["o"],
        "high": data["h"],
        "low": data["l"],
        "close": data["c"],
        "volume": data["v"]
    })

    # Cache to disk
    with open(cache_filename, 'wb') as f:
        pickle.dump(df, f)

    return df

# Function to fetch technical indicators (e.g., RSI)
def get_technical_indicators(symbol, indicator='rsi', start_date='2015-01-01', end_date='2025-01-01'):
    df = get_stock_history(symbol, start_date, end_date)
    if df is None:
        return None  # Return None if no data available
    
    if indicator == 'rsi':
        return calculate_rsi(df)
    # Add more indicators (e.g., MACD) as needed

# Example function to calculate RSI
def calculate_rsi(df, window=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df['RSI'] = rsi
    return df

# Function to get stock data and technical indicators combined
def get_stock_analysis(symbol, start_date='2015-01-01', end_date='2025-01-01'):
    # Get Stock Data
    stock_data = get_stock_data(symbol)

    if stock_data.get('error', False):
        return f"Error: Could not fetch data for {symbol}."
    
    # Get Historical Data and Indicators
    historical_data = get_stock_history(symbol, start_date, end_date)
    if historical_data is None:
        return f"Error: No historical data found for {symbol}."
    
    # Get RSI (can add other indicators as well)
    rsi_data = get_technical_indicators(symbol, indicator='rsi', start_date=start_date, end_date=end_date)
    
    return {
        'stock_data': stock_data,
        'historical_data': historical_data,
        'rsi_data': rsi_data
    }