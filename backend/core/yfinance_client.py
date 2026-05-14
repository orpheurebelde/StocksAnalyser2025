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
        
        # If the cached data is a fallback (missing grossMargins), only keep it for 5 minutes
        is_fallback = "grossMargins" not in cached_data["info"]
        cache_duration = timedelta(minutes=5) if is_fallback else timedelta(hours=CACHE_HOURS)
        
        if datetime.now() - fetch_time < cache_duration:
            return cached_data["info"]

    # 3. Fetch Fresh Data (Naked yfinance to avoid curl_cffi issues)
    try:
        t = yf.Ticker(symbol)
        info = t.info
        
        # Fallback to fast_info if info is empty or broken
        if not info or 'regularMarketPrice' not in info and 'currentPrice' not in info:
            fast = t.fast_info
            if fast and len(fast) > 0:
                info = {
                    "currentPrice": fast.last_price,
                    "marketCap": fast.market_cap,
                    "fiftyTwoWeekLow": fast.year_low,
                    "fiftyTwoWeekHigh": fast.year_high,
                    "shortName": symbol,
                    "symbol": symbol
                }
    except Exception as e:
        print(f"Error fetching info for {symbol}: {e}")
        return None

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
    """Downloads historical data with local CSV caching."""
    symbol = symbol.upper()
    cache_path = os.path.join(CACHE_DIR, f"{symbol}_{period}_{interval}.csv")
    
    # 1. Check if valid cache exists
    if os.path.exists(cache_path):
        try:
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
            if datetime.now() - file_time < timedelta(hours=CACHE_HOURS):
                df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                if not df.empty:
                    return df
        except Exception:
            pass # corrupted cache, ignore

    # 2. Fetch Fresh Data
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 3. Save to Cache
        if not df.empty:
            df.to_csv(cache_path)
            
        return df
    except Exception as e:
        print(f"Error downloading data for {symbol}: {e}")
        return pd.DataFrame()
