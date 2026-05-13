import yfinance as yf
import requests_cache
import pandas as pd

# Set up cached session to avoid rate limits
session = requests_cache.CachedSession('yfinance_cache', expire_after=3600)
session.headers['User-agent'] = 'StocksAnalyser/1.0'

def get_ticker(symbol: str):
    """Returns a yfinance Ticker object utilizing the cached session."""
    return yf.Ticker(symbol, session=session)

def download_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Downloads historical data utilizing the cached session."""
    df = yf.download(symbol, period=period, interval=interval, session=session, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df
