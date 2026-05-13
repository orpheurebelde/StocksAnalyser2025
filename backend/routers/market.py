from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.yfinance_client import get_ticker, download_data
from core.technical import compute_rsi, compute_macd, compute_fibonacci_level
import numpy as np
import pandas as pd
from datetime import datetime

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.get("/analysis")
@limiter.limit("5/minute")
def get_market_analysis(request: Request):
    try:
        tickers = {"S&P 500": "^GSPC", "Nasdaq 100": "^NDX"}
        results = {}
        for name, t in tickers.items():
            data = download_data(t, period="10y", interval="1d")
            if data.empty:
                continue
                
            close = data['Close']
            price = float(close.iloc[-1])
            high_52w = float(close[-252:].max())
            low_52w = float(close[-252:].min())
            
            rsi = float(compute_rsi(close))
            macd, signal = compute_macd(close)
            macd_signal = "Bullish" if float(macd.iloc[-1]) > float(signal.iloc[-1]) else "Bearish"
            
            # Percentages
            def pct_change(days):
                return float(close.pct_change(days).iloc[-1] * 100) if len(close) > days else None
                
            p1d = pct_change(1)
            p5d = pct_change(5)
            p1m = pct_change(21)
            p6m = pct_change(126)
            p1y = pct_change(252)
            p5y = pct_change(1260)
            
            # YTD Calculation
            try:
                current_year_start = pd.Timestamp(datetime.now().year, 1, 1, tz='UTC')
                close_index_utc = close.index.tz_convert('UTC') if close.index.tzinfo else close.index.tz_localize('UTC')
                start_price_series = close.loc[close_index_utc >= current_year_start]
                start_price = float(start_price_series.iloc[0]) if not start_price_series.empty else float(close.iloc[0])
                ytd = ((price / start_price) - 1) * 100
            except:
                ytd = 0.0

            # Fibonacci
            fib_3y = float(compute_fibonacci_level(close[-252*3:])) if len(close) > 252*3 else None
            fib_5y = float(compute_fibonacci_level(close[-252*5:])) if len(close) > 252*5 else None
            fib_10y = float(compute_fibonacci_level(close))
            
            # Trend SMAs
            sma_50 = float(close[-50:].mean()) if len(close) > 50 else None
            sma_200 = float(close[-200:].mean()) if len(close) > 200 else None

            results[name] = {
                "price": price,
                "high_52w": high_52w,
                "low_52w": low_52w,
                "rsi": rsi,
                "macd_signal": macd_signal,
                "ytd": ytd,
                "p1d": p1d,
                "p5d": p5d,
                "p1m": p1m,
                "p6m": p6m,
                "p1y": p1y,
                "p5y": p5y,
                "fib_3y": fib_3y,
                "fib_5y": fib_5y,
                "fib_10y": fib_10y,
                "sma_50": sma_50,
                "sma_200": sma_200
            }
            
        vix = get_ticker("^VIX").history(period="1d", interval="1m")
        vix_val = float(vix["Close"].iloc[-1]) if not vix.empty else None
            
        return {"indices": results, "vix": vix_val}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
