import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "stock_info_cache.json")
CACHE_HOURS = 24

os.makedirs(CACHE_DIR, exist_ok=True)

def get_ticker_info(symbol: str):
    """Fetches info with a custom JSON file cache to prevent rate limiting."""
    symbol = symbol.upper()
    
    # 1. Load Cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
        except Exception:
            pass # corrupted cache, ignore

    # 2. Check if valid
    if symbol in cache:
        cached_data = cache[symbol]
        fetch_time = datetime.fromisoformat(cached_data.get("_timestamp", "2000-01-01T00:00:00"))
        if datetime.now() - fetch_time < timedelta(hours=CACHE_HOURS):
            return cached_data["info"]

    # 3. Fetch Fresh Data (Naked yfinance to avoid curl_cffi issues)
    t = yf.Ticker(symbol)
    info = t.info
    if not info:
        return None

    # 4. Save to Cache
    cache[symbol] = {
        "_timestamp": datetime.now().isoformat(),
        "info": info
    }
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass # silently fail if can't write to cache directory

    return info

def get_ticker(symbol: str):
    """Returns a yfinance Ticker object, letting yfinance handle sessions and curl_cffi internally."""
    return yf.Ticker(symbol)

def download_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Downloads historical data, letting yfinance handle sessions internally."""
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df
