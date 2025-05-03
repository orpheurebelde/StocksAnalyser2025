import os
import pandas as pd
import requests
from datetime import datetime, timedelta

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Finnhub URL builder
def fetch_stock_data_finnhub(ticker, apikey):
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={apikey}"
    r = requests.get(url)
    data = r.json()

    if 'error' in data:
        return None

    # Get the stock data (no volume in this endpoint)
    df = pd.DataFrame({
        'timestamp': [datetime.now()],
        'close': [data['c']],  # 'c' is the current close price
        'high': [data['h']],   # 'h' is the high price
        'low': [data['l']],    # 'l' is the low price
        'open': [data['o']],   # 'o' is the open price
        'previous_close': [data['pc']],  # 'pc' is the previous close price
    })
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def load_cached_data(ticker):
    path = os.path.join(DATA_DIR, f"{ticker.upper()}.csv")
    if os.path.exists(path):
        return pd.read_csv(path, parse_dates=["timestamp"])
    return None

def save_data(ticker, df):
    df = df.reset_index().rename(columns={"index": "timestamp"})
    df.to_csv(os.path.join(DATA_DIR, f"{ticker.upper()}.csv"), index=False)

def is_data_stale(ticker):
    path = os.path.join(DATA_DIR, f"{ticker.upper()}.csv")
    if not os.path.exists(path):
        return True
    mod_time = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - mod_time > timedelta(days=1)