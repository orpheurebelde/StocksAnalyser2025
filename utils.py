import os
import json
import pandas as pd
from datetime import datetime, timedelta
import requests

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Alpha Vantage URL builder
def fetch_stock_data_alpha(ticker, apikey):
    url = (
        f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED"
        f"&symbol={ticker}&outputsize=full&apikey={apikey}"
    )
    r = requests.get(url)
    data = r.json()

    if "Time Series (Daily)" not in data:
        return None

    df = pd.DataFrame.from_dict(data["Time Series (Daily)"], orient="index")
    df = df.rename(columns={"5. adjusted close": "adj_close"}).astype(float)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df[["adj_close"]]

def load_cached_data(ticker):
    path = os.path.join(DATA_DIR, f"{ticker.upper()}.csv")
    if os.path.exists(path):
        return pd.read_csv(path, parse_dates=["Date"])
    return None

def save_data(ticker, df):
    df = df.reset_index().rename(columns={"index": "Date"})
    df.to_csv(os.path.join(DATA_DIR, f"{ticker.upper()}.csv"), index=False)

def is_data_stale(ticker):
    path = os.path.join(DATA_DIR, f"{ticker.upper()}.csv")
    if not os.path.exists(path):
        return True
    mod_time = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - mod_time > timedelta(days=1)