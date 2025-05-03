import os
import requests
import pandas as pd
import pickle
from datetime import datetime
import streamlit as st

# Finnhub API Key from Streamlit Secrets
FINNHUB_API_KEY = st.secrets["FINNHUB_API_KEY"]

# Finnhub Base URL
BASE_URL = "https://finnhub.io/api/v1"

# Cache folder location
DATA_FOLDER = './data'

# Ensure data folder exists
os.makedirs(DATA_FOLDER, exist_ok=True)

# Function to fetch stock data (latest price, open, high, low, etc.)
def get_stock_data(symbol):
    url = f"{BASE_URL}/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    response = requests.get(url)
    data = response.json()
    return data

# Function to fetch historical data for a stock (10 years of daily prices)
def get_stock_history(symbol, start_date, end_date):
    # Check if data exists in the cache folder
    cache_filename = os.path.join(DATA_FOLDER, f"{symbol}_{start_date}_{end_date}.pkl")
    
    # If the cached data exists and is recent, return the cached data
    if os.path.exists(cache_filename):
        file_timestamp = os.path.getmtime(cache_filename)
        last_modified = datetime.fromtimestamp(file_timestamp)
        if (datetime.now() - last_modified).days < 1:
            with open(cache_filename, 'rb') as f:
                df = pickle.load(f)
            return df
    
    # Otherwise, fetch the data from the API
    start_timestamp = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
    end_timestamp = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
    url = f"{BASE_URL}/stock/candle?symbol={symbol}&resolution=D&from={start_timestamp}&to={end_timestamp}&token={FINNHUB_API_KEY}"
    response = requests.get(url)
    data = response.json()
    
    if 'error' in data:
        return None  # Return None if there is an error in fetching data
    
    # Convert data to DataFrame
    df = pd.DataFrame(data['c'], columns=['close'])
    df['time'] = pd.to_datetime(data['t'], unit='s')
    
    # Cache the data for future use
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