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