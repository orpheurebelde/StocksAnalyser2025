import yfinance as yf
import pandas as pd

def get_ticker(symbol: str):
    """Returns a yfinance Ticker object, letting yfinance handle sessions and curl_cffi internally."""
    return yf.Ticker(symbol)

def download_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Downloads historical data, letting yfinance handle sessions internally."""
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df
